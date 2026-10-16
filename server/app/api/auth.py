import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.db import get_db
from app.models import User
from app.schemas import TokenResponse, UserCreate, UserLogin, UserResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["auth"])

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid username/email or password",
)


def _to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at,
    )


@router.post("/auth/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: UserCreate, db: AsyncSession = Depends(get_db)) -> UserResponse:
    try:
        existing = await db.scalar(
            select(User).where(
                or_(User.username == body.username, User.email == body.email)
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username or email is already taken",
            )
        user = User(
            username=body.username,
            email=body.email,
            display_name=body.display_name,
            password_hash=hash_password(body.password),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    except HTTPException:
        raise
    except IntegrityError as exc:
        try:
            await db.rollback()
        except SQLAlchemyError:
            pass
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email is already taken",
        ) from exc
    logger.info("user signed up", extra={"event": "user_signed_up", "user_id": user.id})
    return _to_response(user)


@router.post("/auth/login", response_model=TokenResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        user = await db.scalar(
            select(User).where(
                or_(User.username == body.identifier, User.email == body.identifier)
            )
        )
    except SQLAlchemyError:
        logger.exception("login lookup failed", extra={"event": "login_failed"})
        raise _INVALID_CREDENTIALS from None
    if user is None or not verify_password(body.password, user.password_hash):
        raise _INVALID_CREDENTIALS
    logger.info("user logged in", extra={"event": "user_logged_in", "user_id": user.id})
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/auth/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return _to_response(user)
