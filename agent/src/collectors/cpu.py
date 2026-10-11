import psutil
from datetime import datetime, timezone

def cpu_usage() -> dict[str, str | float]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cpu_usage": psutil.cpu_percent(interval=2),
    }
