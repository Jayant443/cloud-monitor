import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.schemas import MetricsAccepted, MetricsPayload
from app.services.metrics import persist_metrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["metrics"])

@router.post("/metrics", response_model=MetricsAccepted, status_code=status.HTTP_202_ACCEPTED,)
async def receive_metrics(payload: MetricsPayload, db: AsyncSession = Depends(get_db)) -> MetricsAccepted:
    try:
        metric = await persist_metrics(db, payload)
        await db.commit()
    except SQLAlchemyError as exc:
        try:
            await db.rollback()
        except SQLAlchemyError:
            logger.exception("Could not roll back failed metrics transaction")
        logger.exception("Could not persist metrics", extra={"event": "metrics_persistence_failed"})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable; metrics were not persisted",
        ) from exc
    logger.info("metrics payload persisted", extra={
        "event": "metrics_persisted",
        "collector_count": len(payload.agent_health.collectors),
        "disk_mount_count": len(payload.disk.mounts),
        "container_count": len(payload.containers.containers),
        "application_endpoint_count": len(payload.application_health.endpoints),
        "host_metric_id": metric.id,
    })
    return MetricsAccepted()
