from functools import lru_cache
import logging
import os
from collections.abc import AsyncGenerator
from pathlib import Path
from dotenv import load_dotenv
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


def _database_url_from_env() -> str:
    raw_url = os.getenv("DATABASE_URL", "").strip()
    if not raw_url:
        return ""
    url = make_url(raw_url)
    if url.get_backend_name() in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+asyncpg")
    return url.render_as_string(hide_password=False)

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


async def _refine_existing_schema(connection) -> None:
    child_tables = (
        "disk_mount_metrics",
        "container_metrics",
        "application_health_metrics",
    )
    for table_name in child_tables:
        await connection.execute(
            text(
                f"ALTER TABLE {table_name} "
                "ADD COLUMN IF NOT EXISTS host_metric_collected_at TIMESTAMPTZ"
            )
        )
        await connection.execute(
            text(
                f"UPDATE {table_name} AS child "
                "SET host_metric_collected_at = parent.collected_at "
                "FROM (SELECT id, min(collected_at) AS collected_at "
                "FROM host_metrics GROUP BY id HAVING count(*) = 1) AS parent "
                "WHERE child.host_metric_id = parent.id "
                "AND child.host_metric_collected_at IS NULL"
            )
        )
        await connection.execute(
            text(
                f"UPDATE {table_name} AS child "
                "SET sampled_at = child.host_metric_collected_at "
                "WHERE child.sampled_at IS NULL "
                "AND child.host_metric_collected_at IS NOT NULL"
            )
        )
        missing_refs = await connection.scalar(
            text(
                f"SELECT count(*) FROM {table_name} AS child "
                "LEFT JOIN host_metrics AS parent "
                "ON parent.id = child.host_metric_id "
                "AND parent.collected_at = child.host_metric_collected_at "
                "WHERE child.host_metric_id IS NULL "
                "OR child.host_metric_collected_at IS NULL "
                "OR child.sampled_at IS NULL OR parent.id IS NULL"
            )
        )
        if missing_refs:
            raise RuntimeError(
                f"Cannot safely require host/time references in {table_name}: "
                f"{missing_refs} rows have missing or unmatched references/timestamps"
            )
        await connection.execute(
            text(
                f"ALTER TABLE {table_name} "
                "ALTER COLUMN host_metric_id SET NOT NULL, "
                "ALTER COLUMN host_metric_collected_at SET NOT NULL, "
                "ALTER COLUMN sampled_at SET NOT NULL"
            )
        )

    await connection.execute(
        text("ALTER TABLE host_metrics ALTER COLUMN collected_at SET NOT NULL")
    )

    indexes = (
        "CREATE INDEX IF NOT EXISTS ix_hosts_last_seen_at "
        "ON hosts (last_seen_at)",
        "CREATE INDEX IF NOT EXISTS ix_host_metrics_machine_time "
        "ON host_metrics (machine_id, collected_at)",
        "CREATE INDEX IF NOT EXISTS ix_disk_mount_metrics_host_metric_time "
        "ON disk_mount_metrics (host_metric_id, host_metric_collected_at, sampled_at)",
        "CREATE INDEX IF NOT EXISTS ix_container_metrics_host_metric_time "
        "ON container_metrics (host_metric_id, host_metric_collected_at)",
        "CREATE INDEX IF NOT EXISTS ix_container_metrics_container_time "
        "ON container_metrics (container_id, sampled_at)",
        "CREATE INDEX IF NOT EXISTS ix_application_health_metrics_host_metric_time "
        "ON application_health_metrics "
        "(host_metric_id, host_metric_collected_at, sampled_at)",
        "CREATE INDEX IF NOT EXISTS ix_application_health_metrics_endpoint_time "
        "ON application_health_metrics (endpoint_name, sampled_at)",
    )
    for statement in indexes:
        await connection.execute(text(statement))

    obsolete_indexes = (
        "ix_host_metrics_machine_id",
        "ix_disk_mount_metrics_host_metric_id",
        "ix_container_metrics_host_metric_id",
        "ix_container_metrics_container_id",
        "ix_application_health_metrics_host_metric_id",
        "ix_application_health_metrics_endpoint_name",
    )
    for index_name in obsolete_indexes:
        await connection.execute(text(f"DROP INDEX IF EXISTS {index_name}"))

    await connection.execute(
        text(
            "ALTER TABLE api_keys "
            "ADD COLUMN IF NOT EXISTS created_by_user_id BIGINT "
            "REFERENCES users (id) ON DELETE SET NULL"
        )
    )
    await connection.execute(
        text(
            "ALTER TABLE hosts "
            "ADD COLUMN IF NOT EXISTS owner_key_id BIGINT "
            "REFERENCES api_keys (id) ON DELETE SET NULL"
        )
    )
    await connection.execute(
        text("CREATE INDEX IF NOT EXISTS ix_hosts_owner_key_id ON hosts (owner_key_id)")
    )

    await _refine_alert_schema(connection)


async def _refine_alert_schema(connection) -> None:
    """Bring pre-existing alert tables up to date without full migrations."""
    await connection.execute(
        text(
            "ALTER TABLE alert_rules "
            "ADD COLUMN IF NOT EXISTS consecutive_breaches_required INTEGER "
            "NOT NULL DEFAULT 1"
        )
    )
    await connection.execute(
        text(
            "ALTER TABLE alert_rules "
            "ADD COLUMN IF NOT EXISTS last_evaluated_at TIMESTAMPTZ"
        )
    )
    await connection.execute(
        text(
            "ALTER TABLE alerts "
            "ADD COLUMN IF NOT EXISTS resource_type VARCHAR(32) "
            "NOT NULL DEFAULT 'host'"
        )
    )
    await connection.execute(
        text(
            "ALTER TABLE alerts "
            "ADD COLUMN IF NOT EXISTS resource_key VARCHAR(1024) "
            "NOT NULL DEFAULT ''"
        )
    )
    await connection.execute(
        text("UPDATE alerts SET resource_type = 'host' WHERE resource_type IS NULL")
    )
    await connection.execute(
        text("UPDATE alerts SET resource_key = '' WHERE resource_key IS NULL")
    )
    await connection.execute(
        text(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
            "WHERE conname = 'ck_alerts_valid_status') THEN "
            "ALTER TABLE alerts ADD CONSTRAINT ck_alerts_valid_status "
            "CHECK (status IN ('active', 'acknowledged', 'resolved')); "
            "END IF; END $$"
        )
    )
    # Deduplicate legacy rows before enforcing the partial unique index.
    await connection.execute(
        text(
            "DELETE FROM alerts a USING alerts b "
            "WHERE a.id < b.id "
            "AND a.rule_id = b.rule_id "
            "AND a.machine_id = b.machine_id "
            "AND COALESCE(a.resource_key, '') = COALESCE(b.resource_key, '') "
            "AND a.status IN ('active', 'acknowledged') "
            "AND b.status IN ('active', 'acknowledged')"
        )
    )
    await connection.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_alerts_active_rule_machine_resource "
            "ON alerts (rule_id, machine_id, resource_key) "
            "WHERE status IN ('active', 'acknowledged')"
        )
    )
    await connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_alert_eval_state_rule "
            "ON alert_evaluation_state (rule_id)"
        )
    )

    await connection.execute(
        text(
            "INSERT INTO alert_rules "
            "(name, metric, condition, threshold, evaluation_interval_seconds, "
            "severity, enabled, consecutive_breaches_required) "
            "SELECT 'Host offline', 'host_inactivity_seconds', 'gte', 30, 15, "
            "'critical', true, 2 "
            "WHERE NOT EXISTS ("
            "SELECT 1 FROM alert_rules WHERE metric = 'host_inactivity_seconds'"
            ")"
        )
    )
    await connection.execute(
        text(
            "UPDATE alert_rules SET threshold = 30, "
            "evaluation_interval_seconds = 15, updated_at = NOW() "
            "WHERE name = 'Host offline' "
            "AND metric = 'host_inactivity_seconds' "
            "AND threshold = 120 AND evaluation_interval_seconds = 60"
        )
    )
    await connection.execute(
        text(
            "INSERT INTO alert_rules "
            "(name, metric, condition, threshold, evaluation_interval_seconds, "
            "severity, enabled, consecutive_breaches_required) "
            "SELECT 'Container stopped', 'container_stopped', 'gte', 1, 60, "
            "'warning', true, 2 "
            "WHERE NOT EXISTS ("
            "SELECT 1 FROM alert_rules WHERE metric = 'container_stopped'"
            ")"
        )
    )


async def initialize_database() -> bool:
    database_url = _database_url_from_env()
    if not database_url:
        logger.error("DATABASE_URL is not configured", extra={"event": "database_unconfigured"})
        return False

    try:
        from app.models import Base

        engine = _engine_for(database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await _refine_existing_schema(connection)
        try:
            async with engine.begin() as connection:
                await connection.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
                for table_name, time_column in (
                    ("host_metrics", "collected_at"),
                    ("disk_mount_metrics", "sampled_at"),
                    ("container_metrics", "sampled_at"),
                    ("application_health_metrics", "sampled_at"),
                    ("process_metrics", "sampled_at"),
                ):
                    await connection.execute(
                        text(
                            "SELECT create_hypertable("
                            "to_regclass(:table_name), by_range(:time_column), "
                            "if_not_exists => TRUE)"
                        ),
                        {
                            "table_name": f"public.{table_name}",
                            "time_column": time_column,
                        },
                    )
        except Exception:
            logger.warning(
                "TimescaleDB is not available, running on plain tables",
                extra={"event": "timescaledb_unavailable"},
            )
        logger.info("Database tables are ready", extra={"event": "database_initialized"})
        return True
    except Exception:
        logger.exception("Could not initialize database tables", extra={"event": "database_initialization_failed"})
        return False

async def close_database() -> None:
    database_url = _database_url_from_env()
    if database_url:
        await _engine_for(database_url).dispose()
    _session_factory.cache_clear()
    _engine_for.cache_clear()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    database_url = _database_url_from_env()
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
