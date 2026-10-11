import json
import os
from application_health import check_endpoints
from collectors.cpu import cpu_usage
from collectors.container import container_usage
from collectors.disk import disk_usage
from collectors.host import host_identity
from collectors.memory import memory_usage
from collectors.network import network_usage
from collectors.process import process_usage
from monitoring import AgentHealthMonitor

def _csv_setting(name: str) -> list[str]:
    return [value.strip() for value in os.getenv(name, "").split(",") if value.strip()]

def _float_setting(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
        return value if value > 0 else default
    except ValueError:
        return default

def _configured_endpoints() -> list[dict[str, str]]:
    try:
        endpoints = json.loads(os.getenv("APP_HEALTH_ENDPOINTS", "[]"))
        if isinstance(endpoints, list):
            return [item for item in endpoints if isinstance(item, dict) and item.get("url")]
    except (json.JSONDecodeError, TypeError):
        pass
    return [{"name": "configuration_error", "url": "invalid://configuration"}]

def _configured_processes() -> tuple[bool, list[int], list[str]]:
    enabled = os.getenv("PROCESS_MONITOR_ENABLED", "false").casefold() in {
        "1", "true", "yes", "on"
    }
    pids: list[int] = []
    for value in _csv_setting("PROCESS_MONITOR_PIDS"):
        try:
            pids.append(int(value))
        except ValueError:
            continue
    return enabled, pids, _csv_setting("PROCESS_MONITOR_NAMES")

def main() -> None:
    monitor = AgentHealthMonitor()
    endpoints = _configured_endpoints()
    process_enabled, process_pids, process_names = _configured_processes()
    cpu_interval = _float_setting("CPU_SAMPLE_INTERVAL_SECONDS", 2)
    mount_points = _csv_setting("DISK_MOUNT_POINTS") or ["/"]

    for _ in range(100):
        cpu_reading = monitor.run("cpu", cpu_usage, cpu_interval)
        memory_reading = monitor.run("memory", memory_usage)
        disk_reading = monitor.run("disk", disk_usage, mount_points)
        network_reading = monitor.run("network", network_usage)
        containers_reading = monitor.run("containers", container_usage)
        host_reading = monitor.run("host", host_identity)
        application_reading = monitor.run(
            "application_health",
            check_endpoints,
            endpoints,
            _float_setting("APP_HEALTH_TIMEOUT_SECONDS", 5),
        )
        process_reading = monitor.run(
            "processes",
            process_usage,
            process_enabled,
            process_pids,
            process_names,
        )
        print(json.dumps({
            "cpu": cpu_reading,
            "memory": memory_reading,
            "disk": disk_reading,
            "network": network_reading,
            "containers": containers_reading,
            "host": host_reading,
            "application_health": application_reading,
            "processes": process_reading,
            "agent_health": monitor.report(),
        }))

if __name__ == "__main__":
    main()
