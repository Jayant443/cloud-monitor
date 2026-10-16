import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.auth import get_current_user
from app.db import get_db
from app.models import (
    ApplicationHealthMetric,
    ContainerMetric,
    Host,
    HostMetric,
)
from app.schemas import (
    ApplicationHealthMetricResponse,
    ApplicationHealthHistoryResponse,
    ApplicationHealthResponse,
    LatestContainerListResponse,
    LatestContainerResponse,
    LatestMetricsResponse,
    MachineListResponse,
    MachineResponse,
    MetricHistoryResponse,
    MetricSnapshotResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["metrics read"], dependencies=[Depends(get_current_user)])

def _database_unavailable(exc: SQLAlchemyError) -> HTTPException:
    logger.exception("Read query failed", extra={"event": "metrics_read_failed"})
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database is unavailable",
    )

def _validate_time_range(start_time: datetime | None, end_time: datetime | None) -> None:
    for label, value in (("start_time", start_time), ("end_time", end_time)):
        if value is not None and (value.tzinfo is None or value.utcoffset() != timedelta(0)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{label} must include a UTC timezone",
            )
    if start_time is not None and end_time is not None and start_time > end_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_time must be earlier than or equal to end_time",
        )

async def _require_machine(session: AsyncSession, machine_id: str) -> None:
    if await session.get(Host, machine_id) is None:
        raise HTTPException(status_code=404, detail="Machine not found")

def _snapshot_options():
    return (
        selectinload(HostMetric.disks),
        selectinload(HostMetric.containers),
        selectinload(HostMetric.application_health),
        selectinload(HostMetric.processes),
    )

@router.get("/machines", response_model=MachineListResponse)
async def list_machines(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0), db: AsyncSession = Depends(get_db)) -> MachineListResponse:
    try:
        total = await db.scalar(select(func.count()).select_from(Host)) or 0
        result = await db.scalars(select(Host).order_by(Host.last_seen_at.desc(), Host.machine_id).limit(limit).offset(offset))
        return MachineListResponse(
            items=[MachineResponse.model_validate(host) for host in result.all()],
            total=total,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise _database_unavailable(exc) from exc

@router.get("/machines/{machine_id}/metrics/latest", response_model=LatestMetricsResponse,)
async def get_latest_metrics(machine_id: str, db: AsyncSession = Depends(get_db)) -> LatestMetricsResponse:
    try:
        await _require_machine(db, machine_id)
        result = await db.scalars(
            select(HostMetric)
            .where(HostMetric.machine_id == machine_id)
            .options(*_snapshot_options())
            .order_by(HostMetric.collected_at.desc(), HostMetric.id.desc())
            .limit(1)
        )
        latest = result.first()
        return LatestMetricsResponse(
            machine_id=machine_id,
            metrics=MetricSnapshotResponse.model_validate(latest) if latest else None,
        )
    except SQLAlchemyError as exc:
        raise _database_unavailable(exc) from exc

@router.get("/machines/{machine_id}/metrics/history", response_model=MetricHistoryResponse)
async def get_metric_history(machine_id: str, start_time: datetime | None = None, end_time: datetime | None = None, limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0), db: AsyncSession = Depends(get_db)) -> MetricHistoryResponse:
    _validate_time_range(start_time, end_time)
    try:
        await _require_machine(db, machine_id)
        filters = [HostMetric.machine_id == machine_id]
        if start_time is not None:
            filters.append(HostMetric.collected_at >= start_time)
        if end_time is not None:
            filters.append(HostMetric.collected_at <= end_time)

        total = await db.scalar(
            select(func.count()).select_from(HostMetric).where(*filters)
        ) or 0
        result = await db.scalars(
            select(HostMetric)
            .where(*filters)
            .options(*_snapshot_options())
            .order_by(HostMetric.collected_at.desc(), HostMetric.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return MetricHistoryResponse(
            machine_id=machine_id,
            items=[MetricSnapshotResponse.model_validate(item) for item in result.all()],
            total=total,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise _database_unavailable(exc) from exc

@router.get("/containers/latest", response_model=LatestContainerListResponse)
async def list_latest_containers(machine_id: str | None = None, limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0), db: AsyncSession = Depends(get_db)) -> LatestContainerListResponse:
    try:
        if machine_id is not None:
            await _require_machine(db, machine_id)

        rank = func.row_number().over(
            partition_by=(HostMetric.machine_id, ContainerMetric.container_id),
            order_by=(
                ContainerMetric.sampled_at.desc().nulls_last(),
                HostMetric.collected_at.desc(),
                ContainerMetric.id.desc(),
            ),
        ).label("reading_rank")
        ranked_query = (
            select(
                ContainerMetric.id.label("container_metric_id"),
                ContainerMetric.sampled_at.label("container_sampled_at"),
                HostMetric.machine_id.label("machine_id"),
                rank,
            )
            .join(
                HostMetric,
                (ContainerMetric.host_metric_id == HostMetric.id)
                & (ContainerMetric.host_metric_collected_at == HostMetric.collected_at),
            )
            .where(ContainerMetric.container_id.is_not(None))
        )
        if machine_id is not None:
            ranked_query = ranked_query.where(HostMetric.machine_id == machine_id)
        ranked = ranked_query.subquery()

        latest_filter = ranked.c.reading_rank == 1
        total = await db.scalar(
            select(func.count()).select_from(ranked).where(latest_filter)
        ) or 0
        result = await db.execute(
            select(ContainerMetric, HostMetric.machine_id, HostMetric.collected_at)
            .join(
                ranked,
                (ranked.c.container_metric_id == ContainerMetric.id)
                & (ranked.c.container_sampled_at == ContainerMetric.sampled_at),
            )
            .join(
                HostMetric,
                (ContainerMetric.host_metric_id == HostMetric.id)
                & (ContainerMetric.host_metric_collected_at == HostMetric.collected_at),
            )
            .where(latest_filter)
            .order_by(
                ContainerMetric.sampled_at.desc().nulls_last(),
                ContainerMetric.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        items = [
            LatestContainerResponse.model_validate(
                {
                    **{column.name: getattr(container, column.name) for column in ContainerMetric.__table__.columns},
                    "machine_id": row_machine_id,
                    "sampled_at": container.sampled_at or host_collected_at,
                }
            )
            for container, row_machine_id, host_collected_at in result.all()
        ]
        return LatestContainerListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise _database_unavailable(exc) from exc

@router.get("/machines/{machine_id}/application-health/latest", response_model=ApplicationHealthResponse)
async def get_latest_application_health(machine_id: str, db: AsyncSession = Depends(get_db)) -> ApplicationHealthResponse:
    try:
        await _require_machine(db, machine_id)
        latest_result = await db.execute(
            select(
                HostMetric.id,
                HostMetric.collected_at,
                HostMetric.application_health_collection_error,
            )
            .where(HostMetric.machine_id == machine_id)
            .order_by(HostMetric.collected_at.desc(), HostMetric.id.desc())
            .limit(1)
        )
        latest = latest_result.first()
        if latest is None:
            return ApplicationHealthResponse(
                machine_id=machine_id,
                sampled_at=None,
                collection_error=None,
                items=[],
            )

        result = await db.scalars(
            select(ApplicationHealthMetric)
            .where(
                ApplicationHealthMetric.host_metric_id == latest.id,
                ApplicationHealthMetric.host_metric_collected_at == latest.collected_at,
            )
            .order_by(ApplicationHealthMetric.sampled_at.desc().nulls_last(), ApplicationHealthMetric.id)
        )
        return ApplicationHealthResponse(
            machine_id=machine_id,
            sampled_at=latest.collected_at,
            collection_error=latest.application_health_collection_error,
            items=[
                ApplicationHealthMetricResponse.model_validate(item)
                for item in result.all()
            ],
        )
    except SQLAlchemyError as exc:
        raise _database_unavailable(exc) from exc


@router.get("/machines/{machine_id}/application-health/history", response_model=ApplicationHealthHistoryResponse,)
async def get_application_health_history(
    machine_id: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ApplicationHealthHistoryResponse:
    _validate_time_range(start_time, end_time)
    try:
        await _require_machine(db, machine_id)
        filters = [HostMetric.machine_id == machine_id]
        if start_time is not None:
            filters.append(ApplicationHealthMetric.sampled_at >= start_time)
        if end_time is not None:
            filters.append(ApplicationHealthMetric.sampled_at <= end_time)
        join_condition = (
            (ApplicationHealthMetric.host_metric_id == HostMetric.id)
            & (ApplicationHealthMetric.host_metric_collected_at == HostMetric.collected_at)
        )
        total = await db.scalar(
            select(func.count())
            .select_from(ApplicationHealthMetric)
            .join(HostMetric, join_condition)
            .where(*filters)
        ) or 0
        result = await db.scalars(
            select(ApplicationHealthMetric)
            .join(HostMetric, join_condition)
            .where(*filters)
            .order_by(
                ApplicationHealthMetric.sampled_at.desc(),
                ApplicationHealthMetric.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return ApplicationHealthHistoryResponse(
            machine_id=machine_id,
            items=[
                ApplicationHealthMetricResponse.model_validate(item)
                for item in result.all()
            ],
            total=total,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise _database_unavailable(exc) from exc
