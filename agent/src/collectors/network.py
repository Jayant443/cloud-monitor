from datetime import datetime, timezone
import psutil

def network_usage() -> dict[str, str | int]:
    counters = psutil.net_io_counters()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "bytes_sent": counters.bytes_sent,
        "bytes_received": counters.bytes_recv,
    }
