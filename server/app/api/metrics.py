import logging
from fastapi import APIRouter, status
from app.schemas import MetricsAccepted, MetricsPayload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["metrics"])

@router.post("/metrics", response_model=MetricsAccepted, status_code=status.HTTP_202_ACCEPTED,)
async def receive_metrics(payload: MetricsPayload) -> MetricsAccepted:
    logger.info(
        "metrics payload validated",
        extra={
            "event": "metrics_accepted",
            "collector_count": len(payload.agent_health.collectors),
        },
    )
    return MetricsAccepted()
