from datetime import datetime, timezone
from typing import Any
import docker
from docker.errors import DockerException

def _timestamp() -> datetime:
    return datetime.now(timezone.utc)

def _parse_docker_time(value: str | None) -> datetime | None:
    if not value or value.startswith("0001-"):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None

def _cpu_percent(stats: dict[str, Any]) -> float | None:
    cpu = stats.get("cpu_stats") or {}
    previous = stats.get("precpu_stats") or {}
    cpu_delta = (cpu.get("cpu_usage") or {}).get("total_usage", 0) - (
        (previous.get("cpu_usage") or {}).get("total_usage", 0)
    )
    system_delta = cpu.get("system_cpu_usage", 0) - previous.get(
        "system_cpu_usage", 0
    )
    if cpu_delta < 0 or system_delta <= 0:
        return None

    online_cpus = cpu.get("online_cpus")
    if online_cpus is None:
        online_cpus = len((cpu.get("cpu_usage") or {}).get("percpu_usage") or [])
    if not online_cpus:
        return None
    return round((cpu_delta / system_delta) * online_cpus * 100, 2)

def _memory_values(stats: dict[str, Any]) -> tuple[int | None, int | None]:
    memory = stats.get("memory_stats") or {}
    usage = memory.get("usage")
    limit = memory.get("limit")
    cache_stats = memory.get("stats") or {}
    cache = cache_stats.get("inactive_file", cache_stats.get("total_inactive_file"))
    if cache is None:
        cache = cache_stats.get("cache", 0)
    if usage is not None:
        usage = max(0, usage - cache)
    return usage, limit

def _network_values(stats: dict[str, Any]) -> tuple[int, int]:
    networks = stats.get("networks") or {}
    received = sum(int(values.get("rx_bytes", 0)) for values in networks.values())
    transmitted = sum(int(values.get("tx_bytes", 0)) for values in networks.values())
    return received, transmitted

def _block_io_values(stats: dict[str, Any]) -> tuple[int, int]:
    entries = (stats.get("blkio_stats") or {}).get("io_service_bytes_recursive") or []
    read_bytes = 0
    write_bytes = 0
    for entry in entries:
        operation = str(entry.get("op", "")).lower()
        value = int(entry.get("value", 0))
        if operation == "read":
            read_bytes += value
        elif operation == "write":
            write_bytes += value
    return read_bytes, write_bytes

def _container_record(container: Any, sampled_at: datetime) -> dict[str, Any]:
    errors: list[str] = []
    try:
        container.reload()
        attrs = container.attrs or {}
        config = attrs.get("Config") or {}
        state = attrs.get("State") or {}
        status = state.get("Status", getattr(container, "status", "unknown"))
        image_data = config.get("Image")
        if not image_data:
            image_data = getattr(container, "image", None)
            image_data = getattr(image_data, "tags", None)
        if isinstance(image_data, list):
            image_data = image_data[0] if image_data else None
        if isinstance(image_data, dict):
            image_data = image_data.get("id")

        started = _parse_docker_time(state.get("StartedAt"))
        ended = _parse_docker_time(state.get("FinishedAt")) if status != "running" else None
        uptime = None
        if started:
            uptime = max(0.0, ((ended or sampled_at) - started).total_seconds())

        health = (state.get("Health") or {}).get("Status") or "not_configured"
        record: dict[str, Any] = {
            "timestamp": sampled_at.isoformat(),
            "container_id": getattr(container, "id", None),
            "name": getattr(container, "name", None),
            "image": image_data,
            "status": status,
            "cpu_usage_percent": None,
            "memory_usage_bytes": None,
            "memory_limit_bytes": None,
            "network_received_bytes": None,
            "network_transmitted_bytes": None,
            "block_read_bytes": None,
            "block_write_bytes": None,
            "restart_count": attrs.get("RestartCount", 0),
            "uptime_seconds": uptime,
            "exit_code": state.get("ExitCode") if status != "running" else None,
            "health_status": health,
            "collection_errors": errors,
        }

        if status == "running":
            try:
                stats = container.stats(stream=False)
                record["cpu_usage_percent"] = _cpu_percent(stats)
                record["memory_usage_bytes"], record["memory_limit_bytes"] = (
                    _memory_values(stats)
                )
                received, transmitted = _network_values(stats)
                record["network_received_bytes"] = received
                record["network_transmitted_bytes"] = transmitted
                record["block_read_bytes"], record["block_write_bytes"] = (
                    _block_io_values(stats)
                )
            except Exception as exc:
                errors.append(f"stats collection failed: {exc}")
        return record
    except Exception as exc:
        return {
            "timestamp": sampled_at.isoformat(),
            "container_id": getattr(container, "id", None),
            "name": getattr(container, "name", None),
            "image": None,
            "status": "unknown",
            "cpu_usage_percent": None,
            "memory_usage_bytes": None,
            "memory_limit_bytes": None,
            "network_received_bytes": None,
            "network_transmitted_bytes": None,
            "block_read_bytes": None,
            "block_write_bytes": None,
            "restart_count": None,
            "uptime_seconds": None,
            "exit_code": None,
            "health_status": "unknown",
            "collection_errors": [f"container collection failed: {exc}"],
        }

def container_usage(client: Any | None = None) -> dict[str, Any]:
    sampled_at = _timestamp()
    owns_client = client is None
    try:
        client = client or docker.from_env()
        containers = client.containers.list(all=True)
        records = [_container_record(container, sampled_at) for container in containers]
        return {
            "timestamp": sampled_at.isoformat(),
            "containers": records,
            "collection_errors": [],
        }
    except DockerException as exc:
        return {
            "timestamp": sampled_at.isoformat(),
            "containers": [],
            "collection_errors": [f"Docker collection failed: {exc}"],
        }
    except Exception as exc:
        return {
            "timestamp": sampled_at.isoformat(),
            "containers": [],
            "collection_errors": [f"Container listing failed: {exc}"],
        }
    finally:
        if owns_client and client is not None:
            try:
                client.close()
            except Exception:
                pass
