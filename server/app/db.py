from functools import lru_cache
import logging
import os
from collections.abc import AsyncGenerator
from pathlib import Path
from dotenv import load_dotenv
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

@lru_cache(maxsize=4)
def _engine_for(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

@lru_cache(maxsize=4)
def _session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    engine = _engine_for(database_url)
    return async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

async def initialize_database() -> bool:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        logger.error("DATABASE_URL is not configured", extra={"event": "database_unconfigured"})
        return False

    try:
        from app.models import Base

        engine = _engine_for(database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        logger.info("Database tables are ready", extra={"event": "database_initialized"})
        return True
    except SQLAlchemyError:
        logger.exception("Could not initialize database tables", extra={"event": "database_initialization_failed"})
        return False

async def close_database() -> None:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        await _engine_for(database_url).dispose()
    _session_factory.cache_clear()
    _engine_for.cache_clear()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        logger.error("DATABASE_URL is not configured", extra={"event": "database_unconfigured"})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )

    try:
        session = _session_factory(database_url)()
    except SQLAlchemyError as exc:
        logger.exception("Could not initialize database session")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from exc

    try:
        yield session
    finally:
        await session.close()
