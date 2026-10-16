import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_ALGORITHM = "HS256"


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


def _expected_api_key() -> str:
    return os.getenv("API_KEY", "").strip()


async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    expected = _expected_api_key()
    if not expected:
        return None
    if x_api_key and secrets.compare_digest(x_api_key, expected):
        return None
    logger.warning(
        "rejected request with missing or invalid API key",
        extra={"event": "api_key_rejected"},
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
    )
