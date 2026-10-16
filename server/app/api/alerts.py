import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.auth import get_current_user
from app.db import get_db
from app.models import Alert, AlertEvaluationState, AlertRule
from app.schemas import (
    AlertListResponse,
    AlertResponse,
    AlertRuleCreate,
    AlertRuleListResponse,
    AlertRuleResponse,
    AlertRuleUpdate,
    AlertSummaryResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["alerts"], dependencies=[Depends(get_current_user)])


def _db_unavailable(exc: Exception) -> HTTPException:
    logger.exception("Alert query failed", extra={"event": "alert_query_failed"})
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database is unavailable",
    )


def _rule_to_response(rule: AlertRule, active_count: int = 0) -> AlertRuleResponse:
    return AlertRuleResponse(
        id=rule.id,
        name=rule.name,
        metric=rule.metric,
        condition=rule.condition,
        threshold=rule.threshold,
        evaluation_interval_seconds=rule.evaluation_interval_seconds,
        severity=rule.severity,
        enabled=rule.enabled,
        consecutive_breaches_required=rule.consecutive_breaches_required,
        last_evaluated_at=rule.last_evaluated_at,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        active_alert_count=active_count,
    )


def _alert_to_response(alert: Alert) -> AlertResponse:
    rule = alert.rule if isinstance(getattr(alert, "rule", None), AlertRule) else None
    return AlertResponse(
        id=alert.id,
        rule_id=alert.rule_id,
        machine_id=alert.machine_id,
        resource_type=alert.resource_type,
        resource_key=alert.resource_key,
        observed_value=alert.observed_value,
        status=alert.status,
        triggered_at=alert.triggered_at,
        resolved_at=alert.resolved_at,
        rule_name=rule.name if rule else None,
        rule_metric=rule.metric if rule else None,
        rule_severity=rule.severity if rule else None,
    )


async def _active_counts(db: AsyncSession, rule_ids: list[int]) -> dict[int, int]:
    if not rule_ids:
        return {}
    rows = await db.execute(
        select(Alert.rule_id, func.count())
        .where(
            Alert.rule_id.in_(rule_ids),
            Alert.status.in_(("active", "acknowledged")),
        )
        .group_by(Alert.rule_id)
    )
    return {rule_id: count for rule_id, count in rows.all()}


@router.post("/alert-rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(body: AlertRuleCreate, db: AsyncSession = Depends(get_db)) -> AlertRuleResponse:
    try:
        rule = AlertRule(
            name=body.name.strip(),
            metric=body.metric,
            condition=body.condition,
            threshold=body.threshold,
            evaluation_interval_seconds=body.evaluation_interval_seconds,
            severity=body.severity,
            enabled=body.enabled,
            consecutive_breaches_required=body.consecutive_breaches_required,
        )
        db.add(rule)
        await db.commit()
        await db.refresh(rule)
        return _rule_to_response(rule)
    except SQLAlchemyError as exc:
        try:
            await db.rollback()
        except SQLAlchemyError:
            pass
        raise _db_unavailable(exc) from exc


@router.get("/alert-rules", response_model=AlertRuleListResponse)
async def list_alert_rules(
    enabled: bool | None = None,
    metric: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> AlertRuleListResponse:
    try:
        filters = []
        if enabled is not None:
            filters.append(AlertRule.enabled == enabled)
        if metric is not None:
            filters.append(AlertRule.metric == metric)
        total = await db.scalar(select(func.count()).select_from(AlertRule).where(*filters)) or 0
        result = await db.scalars(
            select(AlertRule).where(*filters).order_by(AlertRule.id).limit(limit).offset(offset)
        )
        rules = result.all()
        counts = await _active_counts(db, [r.id for r in rules])
        return AlertRuleListResponse(
            items=[_rule_to_response(r, counts.get(r.id, 0)) for r in rules],
            total=total,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise _db_unavailable(exc) from exc


@router.get("/alert-rules/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(rule_id: int, db: AsyncSession = Depends(get_db)) -> AlertRuleResponse:
    try:
        rule = await db.get(AlertRule, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        counts = await _active_counts(db, [rule.id])
        return _rule_to_response(rule, counts.get(rule.id, 0))
    except SQLAlchemyError as exc:
        raise _db_unavailable(exc) from exc


@router.patch("/alert-rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(rule_id: int, body: AlertRuleUpdate, db: AsyncSession = Depends(get_db)) -> AlertRuleResponse:
    try:
        rule = await db.get(AlertRule, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        data = body.model_dump(exclude_unset=True)
        if "name" in data and isinstance(data["name"], str):
            data["name"] = data["name"].strip()
            if not data["name"]:
                raise HTTPException(status_code=422, detail="name must not be empty")
        # Validate percent thresholds when metric changes or threshold changes.
        metric = data.get("metric", rule.metric)
        if "threshold" in data and metric in {"cpu_usage", "memory_usage", "disk_usage"}:
            if not 0 <= data["threshold"] <= 100:
                raise HTTPException(
                    status_code=422,
                    detail="threshold must be between 0 and 100 for usage metrics",
                )
        for key, value in data.items():
            setattr(rule, key, value)
        await db.commit()
        await db.refresh(rule)
        counts = await _active_counts(db, [rule.id])
        return _rule_to_response(rule, counts.get(rule.id, 0))
    except SQLAlchemyError as exc:
        try:
            await db.rollback()
        except SQLAlchemyError:
            pass
        raise _db_unavailable(exc) from exc


@router.post("/alert-rules/{rule_id}/enable", response_model=AlertRuleResponse)
async def enable_alert_rule(rule_id: int, db: AsyncSession = Depends(get_db)) -> AlertRuleResponse:
    return await update_alert_rule(rule_id, AlertRuleUpdate(enabled=True), db)


@router.post("/alert-rules/{rule_id}/disable", response_model=AlertRuleResponse)
async def disable_alert_rule(rule_id: int, db: AsyncSession = Depends(get_db)) -> AlertRuleResponse:
    try:
        rule = await db.get(AlertRule, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        rule.enabled = False
        await db.commit()
        await db.refresh(rule)
        counts = await _active_counts(db, [rule.id])
        return _rule_to_response(rule, counts.get(rule.id, 0))
    except SQLAlchemyError as exc:
        try:
            await db.rollback()
        except SQLAlchemyError:
            pass
        raise _db_unavailable(exc) from exc


@router.delete("/alert-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(rule_id: int, db: AsyncSession = Depends(get_db)) -> None:
    try:
        rule = await db.get(AlertRule, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        # Remove dependent rows first (alerts are RESTRICT in older schemas).
        await db.execute(AlertEvaluationState.__table__.delete().where(AlertEvaluationState.rule_id == rule_id))
        await db.execute(Alert.__table__.delete().where(Alert.rule_id == rule_id))
        await db.delete(rule)
        await db.commit()
    except IntegrityError as exc:
        try:
            await db.rollback()
        except SQLAlchemyError:
            pass
        raise HTTPException(status_code=409, detail="Alert rule has dependent alerts") from exc
    except SQLAlchemyError as exc:
        try:
            await db.rollback()
        except SQLAlchemyError:
            pass
        raise _db_unavailable(exc) from exc
    return None


@router.get("/alerts", response_model=AlertListResponse)
async def list_alerts(
    alert_status: str | None = Query(default=None, alias="status"),
    rule_id: int | None = None,
    machine_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> AlertListResponse:
    try:
        filters = []
        if alert_status is not None:
            if alert_status not in ("active", "acknowledged", "resolved"):
                raise HTTPException(status_code=422, detail="Invalid status filter")
            filters.append(Alert.status == alert_status)
        if rule_id is not None:
            filters.append(Alert.rule_id == rule_id)
        if machine_id is not None:
            filters.append(Alert.machine_id == machine_id)
        total = await db.scalar(select(func.count()).select_from(Alert).where(*filters)) or 0
        result = await db.scalars(
            select(Alert)
            .options(selectinload(Alert.rule))
            .where(*filters)
            .order_by(Alert.triggered_at.desc(), Alert.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return AlertListResponse(
            items=[_alert_to_response(a) for a in result.all()],
            total=total,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise _db_unavailable(exc) from exc


@router.get("/alerts/summary", response_model=AlertSummaryResponse)
async def alert_summary(db: AsyncSession = Depends(get_db)) -> AlertSummaryResponse:
    try:
        active = await db.scalar(select(func.count()).select_from(Alert).where(Alert.status == "active")) or 0
        acknowledged = await db.scalar(select(func.count()).select_from(Alert).where(Alert.status == "acknowledged")) or 0
        critical_active = await db.scalar(
            select(func.count())
            .select_from(Alert)
            .join(AlertRule, Alert.rule_id == AlertRule.id)
            .where(Alert.status == "active", AlertRule.severity == "critical")
        ) or 0
        return AlertSummaryResponse(active=active, acknowledged=acknowledged, critical_active=critical_active)
    except SQLAlchemyError as exc:
        raise _db_unavailable(exc) from exc


async def _transition_alert(db: AsyncSession, alert_id: int, to_status: str) -> AlertResponse:
    try:
        result = await db.scalars(
            select(Alert).options(selectinload(Alert.rule)).where(Alert.id == alert_id)
        )
        alert = result.first()
        if alert is None:
            raise HTTPException(status_code=404, detail="Alert not found")
        if to_status == "acknowledged":
            if alert.status != "active":
                raise HTTPException(status_code=409, detail="Only active alerts can be acknowledged")
            alert.status = "acknowledged"
        elif to_status == "resolved":
            if alert.status not in ("active", "acknowledged"):
                raise HTTPException(status_code=409, detail="Alert is already resolved")
            alert.status = "resolved"
            alert.resolved_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(alert)
        # Ensure rule relationship for response shaping.
        if alert.rule is None:
            alert.rule = await db.get(AlertRule, alert.rule_id)
        return _alert_to_response(alert)
    except SQLAlchemyError as exc:
        try:
            await db.rollback()
        except SQLAlchemyError:
            pass
        raise _db_unavailable(exc) from exc


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(alert_id: int, db: AsyncSession = Depends(get_db)) -> AlertResponse:
    return await _transition_alert(db, alert_id, "acknowledged")


@router.post("/alerts/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(alert_id: int, db: AsyncSession = Depends(get_db)) -> AlertResponse:
    return await _transition_alert(db, alert_id, "resolved")
