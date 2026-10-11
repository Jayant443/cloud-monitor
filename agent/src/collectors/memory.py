from datetime import datetime, timezone

import psutil


def memory_usage() -> dict[str, str | float]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "memory_usage": psutil.virtual_memory().percent,
    }
