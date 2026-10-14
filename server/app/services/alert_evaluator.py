import asyncio
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.db import _database_url_from_env, _session_factory
from app.models import Alert, AlertEvaluationState, AlertRule, Host, HostMetric

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("active", "acknowledged")


def _poll_seconds() -> float:
    try:
        value = float(os.getenv("ALERT_EVALUATOR_POLL_SECONDS", "15"))
        if value >= 5:
            return value
    except ValueError:
        pass
    return 15.0


def _enabled() -> bool:
    return os.getenv("ALERT_EVALUATOR_ENABLED", "true").strip().casefold() in {
        "1", "true", "yes", "on",
    }


def condition_breached(value: float, condition: str, threshold: float) -> bool:
    if condition == "gt":
        return value > threshold
    if condition == "gte":
        return value >= threshold
    if condition == "lt":
        return value < threshold
    if condition == "lte":
        return value <= threshold
    return False


async def _latest_metric(session, machine_id: str) -> HostMetric | None:
    result = await session.scalars(
        select(HostMetric)
        .where(HostMetric.machine_id == machine_id)
        .options(
            selectinload(HostMetric.disks),
            selectinload(HostMetric.containers),
            selectinload(HostMetric.application_health),
        )
        .order_by(HostMetric.collected_at.desc(), HostMetric.id.desc())
        .limit(1)
    )
    return result.first()


async def _collect_candidates(session, rule: AlertRule) -> list[tuple[str, str, str, float]]:
    """Return (machine_id, resource_type, resource_key, observed_value) list."""
    now = datetime.now(timezone.utc)
    hosts = (await session.scalars(select(Host))).all()
    candidates: list[tuple[str, str, str, float]] = []

    for host in hosts:
        machine_id = host.machine_id
        if rule.metric == "host_inactivity_seconds":
            observed = (now - host.last_seen_at).total_seconds() if host.last_seen_at else float("inf")
            candidates.append((machine_id, "host", "", float(observed)))
            continue

        latest = await _latest_metric(session, machine_id)
        if latest is None:
            continue

        if rule.metric == "cpu_usage":
            if latest.cpu_usage is not None:
                candidates.append((machine_id, "host", "", float(latest.cpu_usage)))
        elif rule.metric == "memory_usage":
            if latest.memory_usage is not None:
                candidates.append((machine_id, "host", "", float(latest.memory_usage)))
        elif rule.metric == "disk_usage":
            for disk in latest.disks:
                if disk.usage_percent is not None:
                    candidates.append((machine_id, "disk", disk.mount_point or "", float(disk.usage_percent)))
        elif rule.metric == "container_stopped":
            for container in latest.containers:
                is_stopped = (container.status or "").strip().casefold() != "running"
                key = container.container_id or container.name or str(container.id)
                if is_stopped:
                    candidates.append((machine_id, "container", key, 1.0))
                else:
                    candidates.append((machine_id, "container", key, 0.0))
        elif rule.metric == "app_health_failed":
            for check in latest.application_health:
                key = check.endpoint_name or str(check.id)
                if check.available is False:
                    candidates.append((machine_id, "endpoint", key, 1.0))
                else:
                    candidates.append((machine_id, "endpoint", key, 0.0))
    return candidates


async def _reconcile_candidate(session, rule: AlertRule, machine_id: str, resource_type: str, resource_key: str, observed: float, breached: bool, now: datetime) -> str:
    """Update breach counter and fire alerts.

    Alerts are never auto-resolved: once open they stay active/acknowledged
    until the user resolves or acknowledges them via the API.
    Returns action taken.
    """
    existing_result = await session.scalars(
        select(Alert).where(
            Alert.rule_id == rule.id,
            Alert.machine_id == machine_id,
            Alert.resource_key == resource_key,
            Alert.status.in_(ACTIVE_STATUSES),
        )
    )
    existing = existing_result.first()

    state = await session.get(AlertEvaluationState, (rule.id, machine_id, resource_key))
    if state is None:
        if not breached and existing is None:
            return "ok"
        state = AlertEvaluationState(
            rule_id=rule.id,
            machine_id=machine_id,
            resource_key=resource_key,
            consecutive_breaches=0,
        )
        session.add(state)

    if breached:
        state.consecutive_breaches = (state.consecutive_breaches or 0) + 1
    else:
        state.consecutive_breaches = 0
    state.last_observed_value = observed
    state.last_evaluated_at = now

    required = max(1, rule.consecutive_breaches_required or 1)
    if breached and state.consecutive_breaches >= required:
        if existing is None:
            session.add(
                Alert(
                    rule_id=rule.id,
                    machine_id=machine_id,
                    resource_type=resource_type,
                    resource_key=resource_key,
                    observed_value=observed,
                    status="active",
                    triggered_at=now,
                )
            )
            return "fired"
        existing.observed_value = observed
        return "sustained"

    return "tracking" if breached else "ok"


async def evaluate_rule(rule_id: int) -> dict:
    """Evaluate a single rule under an advisory lock. Returns counts."""
    database_url = _database_url_from_env()
    if not database_url:
        return {"skipped": "no-database"}
    session = _session_factory(database_url)()
    summary = {"fired": 0, "resolved": 0, "sustained": 0, "ok": 0}
    try:
        async with session.begin():
            locked = await session.scalar(
                text("SELECT pg_try_advisory_xact_lock(hashtext(:key))"),
                {"key": f"alert_rule:{rule_id}"},
            )
            if not locked:
                return {"skipped": "locked"}

            rule = await session.get(AlertRule, rule_id)
            if rule is None or not rule.enabled:
                return {"skipped": "disabled-or-missing"}

            now = datetime.now(timezone.utc)
            candidates = await _collect_candidates(session, rule)

            for machine_id, resource_type, resource_key, observed in candidates:
                breached = condition_breached(observed, rule.condition, rule.threshold)
                action = await _reconcile_candidate(
                    session, rule, machine_id, resource_type, resource_key, observed, breached, now
                )
                if action in summary:
                    summary[action] += 1
                elif action == "tracking":
                    summary["ok"] += 1

            # Manual resolution only: alerts stay open even when the condition
            # clears or the resource stops reporting, until the user
            # acknowledges or resolves them via the API.
            rule.last_evaluated_at = now
        logger.info(
            "alert rule evaluated",
            extra={"event": "alert_rule_evaluated", "rule_id": rule_id, **summary},
        )
        return summary
    except SQLAlchemyError:
        logger.exception("alert rule evaluation failed", extra={"event": "alert_evaluation_failed", "rule_id": rule_id})
        try:
            await session.rollback()
        except SQLAlchemyError:
            pass
        return {"error": True}
    finally:
        await session.close()


async def evaluate_due_rules() -> dict[int, dict]:
    database_url = _database_url_from_env()
    if not database_url or not _enabled():
        return {}
    session = _session_factory(database_url)()
    try:
        rules = (await session.scalars(select(AlertRule).where(AlertRule.enabled == True))).all()  # noqa: E712
        now = datetime.now(timezone.utc)
        due = [
            r for r in rules
            if r.last_evaluated_at is None
            or (now - r.last_evaluated_at).total_seconds() >= r.evaluation_interval_seconds
        ]
    finally:
        await session.close()

    results: dict[int, dict] = {}
    for rule in due:
        results[rule.id] = await evaluate_rule(rule.id)
    return results


async def alert_evaluator_loop() -> None:
    logger.info("alert evaluator started", extra={"event": "alert_evaluator_started"})
    while True:
        try:
            await evaluate_due_rules()
        except Exception:
            logger.exception("alert evaluator cycle failed", extra={"event": "alert_evaluator_failed"})
        await asyncio.sleep(_poll_seconds())
