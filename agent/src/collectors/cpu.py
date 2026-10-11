import psutil


def print_cpu_usage() -> None:
    for _ in range(20):
        usage = psutil.cpu_percent(interval=1)
        print(f"CPU usage: {usage:.1f}%")
