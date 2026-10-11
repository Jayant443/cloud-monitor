from datetime import datetime, timezone
import psutil

def disk_usage(path: str = "/") -> dict[str, str | float | int]:
    usage = psutil.disk_usage(path)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disk_usage": usage.percent,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
    }
