from collectors.cpu import cpu_usage
from collectors.disk import disk_usage
from collectors.memory import memory_usage
from collectors.network import network_usage

def main() -> None:
    for _ in range(100):
        cpu_reading = cpu_usage()
        memory_reading = memory_usage()
        disk_reading = disk_usage()
        network_reading = network_usage()
        print(
            f"CPU usage: {cpu_reading['cpu_usage']}% at "
            f"{cpu_reading['timestamp']} | "
            f"Memory usage: {memory_reading['memory_usage']}% at "
            f"{memory_reading['timestamp']} | "
            f"Disk usage: {disk_reading['disk_usage']}% "
            f"({disk_reading['used_bytes']} bytes used, "
            f"{disk_reading['free_bytes']} bytes free) at "
            f"{disk_reading['timestamp']} | "
            f"Network: {network_reading['bytes_sent']} bytes sent, "
            f"{network_reading['bytes_received']} bytes received at "
            f"{network_reading['timestamp']}"
        )

if __name__ == "__main__":
    main()
