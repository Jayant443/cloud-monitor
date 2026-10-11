import json
from collectors.cpu import cpu_usage
from collectors.container import container_usage
from collectors.disk import disk_usage
from collectors.memory import memory_usage
from collectors.network import network_usage

def main() -> None:
    for _ in range(100):
        cpu_reading = cpu_usage()
        memory_reading = memory_usage()
        disk_reading = disk_usage()
        network_reading = network_usage()
        containers_reading = container_usage()
        print(json.dumps({
            "cpu": cpu_reading,
            "memory": memory_reading,
            "disk": disk_reading,
            "network": network_reading,
            "containers": containers_reading,
        }))

if __name__ == "__main__":
    main()
