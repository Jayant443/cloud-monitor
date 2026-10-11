from collectors.cpu import cpu_usage
from collectors.memory import memory_usage

if __name__ == "__main__":
    for _ in range(100):
        cpu_reading = cpu_usage()
        memory_reading = memory_usage()
        print(
            f"CPU usage: {cpu_reading['cpu_usage']}% at "
            f"{cpu_reading['timestamp']} | Memory usage: "
            f"{memory_reading['memory_usage']}% at "
            f"{memory_reading['timestamp']}"
        )
