import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_ALGORITHM = "HS256"
API_KEY_PREFIX_LENGTH = 12


def _jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "").strip()


def _jwt_expire_minutes() -> float:
    try:
        value = float(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
        if value > 0:
            return value
    except ValueError:
        pass
    return 1440.0


def _require_jwt_secret() -> str:
    secret = _jwt_secret()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User authentication is not configured (JWT_SECRET is empty)",
        )
    return secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int) -> str:
    secret = _require_jwt_secret()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=_jwt_expire_minutes())).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    from app.models import User

    secret = _require_jwt_secret()
    try:
        payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])
        user_id = int(payload.get("sub", ""))
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def owned_key_ids(db: AsyncSession, user) -> list[int]:
    """IDs of agent keys the user may see hosts through: their own keys
    plus legacy keys created before ownership (shared)."""
    from app.models import ApiKey

    rows = (
        await db.scalars(
            select(ApiKey.id).where(
                or_(
                    ApiKey.created_by_user_id == user.id,
                    ApiKey.created_by_user_id.is_(None),
                )
            )
        )
    ).all()
    return list(rows)


def host_visible_clause(host_model, key_ids: list[int]):
    """Hosts with no owner (env-fallback / legacy reports) are visible to
    everyone; owned hosts only through one of the user's keys."""
    from app.models import Host as _Host

    model = host_model if host_model is not None else _Host
    return or_(
        model.owner_key_id.is_(None),
        model.owner_key_id.in_(key_ids),
    )


async def require_visible_host(db: AsyncSession, user, machine_id: str):
    """Return the host or raise 404 (foreign hosts look non-existent)."""
    from app.models import Host

    host = await db.get(Host, machine_id)
    if host is None:
        raise HTTPException(status_code=404, detail="Machine not found")
    if host.owner_key_id is not None:
        key_ids = await owned_key_ids(db, user)
        if host.owner_key_id not in key_ids:
            raise HTTPException(status_code=404, detail="Machine not found")
    return host


def _expected_api_key() -> str:
    return os.getenv("API_KEY", "").strip()


def _reject_api_key() -> HTTPException:
    logger.warning(
        "rejected request with missing or invalid API key",
        extra={"event": "api_key_rejected"},
    )
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
    )


def generate_api_key() -> tuple[str, str, str]:
    """Return (plain_key, bcrypt_hash, prefix). The plain key is only
    available here; callers must show it once and never persist it."""
    plain = secrets.token_urlsafe(32)
    hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return plain, hashed, plain[:API_KEY_PREFIX_LENGTH]


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Agent authentication for ingest.

    If any API keys exist in the database, the presented key must match an
    active stored (bcrypt-hashed) key. Otherwise fall back to the legacy
    ``API_KEY`` environment variable so existing setups keep working.
    """
    from app.models import ApiKey

    try:
        stored_count = await db.scalar(select(func.count()).select_from(ApiKey)) or 0
    except Exception:
        logger.exception("API key lookup failed", extra={"event": "api_key_lookup_failed"})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from None

    if stored_count > 0:
        if x_api_key and len(x_api_key) >= API_KEY_PREFIX_LENGTH:
            candidates = (
                await db.scalars(
                    select(ApiKey).where(
                        ApiKey.key_prefix == x_api_key[:API_KEY_PREFIX_LENGTH],
                        ApiKey.is_active == True,  # noqa: E712
                    )
                )
            ).all()
            for candidate in candidates:
                if verify_password(x_api_key, candidate.key_hash):
                    candidate.last_used_at = datetime.now(timezone.utc)
                    try:
                        await db.commit()
                    except Exception:
                        try:
                            await db.rollback()
                        except Exception:
                            pass
                    return candidate
        raise _reject_api_key()

    # Backward compatibility: no keys stored yet, honor the env var.
    expected = _expected_api_key()
    if not expected:
        return None
    if x_api_key and secrets.compare_digest(x_api_key, expected):
        return None
    raise _reject_api_key()
