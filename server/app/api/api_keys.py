import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import generate_api_key, get_current_user
from app.db import get_db
from app.models import ApiKey, User
from app.schemas import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api",
    tags=["api keys"],
    dependencies=[Depends(get_current_user)],
)


def _to_response(key: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        is_active=key.is_active,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
    )


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)) -> list[ApiKeyResponse]:
    keys = (
        await db.scalars(
            select(ApiKey)
            .where(
                or_(
                    ApiKey.created_by_user_id == user.id,
                    ApiKey.created_by_user_id.is_(None),
                )
            )
            .order_by(ApiKey.created_at.desc())
        )
    ).all()
    return [_to_response(key) for key in keys]


@router.post("/api-keys", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(body: ApiKeyCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)) -> ApiKeyCreatedResponse:
    plain, hashed, prefix = generate_api_key()
    record = ApiKey(
        name=body.name,
        key_hash=hashed,
        key_prefix=prefix,
        is_active=True,
        created_by_user_id=user.id,
    )
    db.add(record)
    try:
        await db.commit()
        await db.refresh(record)
    except SQLAlchemyError as exc:
        try:
            await db.rollback()
        except SQLAlchemyError:
            pass
        logger.exception("API key creation failed", extra={"event": "api_key_create_failed"})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from exc
    logger.info("API key created", extra={"event": "api_key_created", "api_key_id": record.id})
    created = _to_response(record)
    return ApiKeyCreatedResponse(**created.model_dump(), key=plain)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(key_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    record = await db.get(ApiKey, key_id)
    if (
        record is None
        or (
            record.created_by_user_id is not None
            and record.created_by_user_id != user.id
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    await db.delete(record)
    try:
        await db.commit()
    except SQLAlchemyError as exc:
        try:
            await db.rollback()
        except SQLAlchemyError:
            pass
        logger.exception("API key revocation failed", extra={"event": "api_key_revoke_failed"})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from exc
    logger.info("API key revoked", extra={"event": "api_key_revoked", "api_key_id": key_id})
    return None
