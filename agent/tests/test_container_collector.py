import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from src.collectors.container import (
    _block_io_values,
    _container_record,
    _cpu_percent,
    _memory_values,
    _network_values,
)


class DockerMetricTests(unittest.TestCase):
    def test_cpu_percent_uses_docker_counter_delta_formula(self):
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 150},
                "system_cpu_usage": 400,
                "online_cpus": 4,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 100},
                "system_cpu_usage": 200,
            },
        }
        self.assertEqual(_cpu_percent(stats), 100.0)

    def test_cpu_percent_is_unavailable_when_baseline_is_missing(self):
        self.assertIsNone(_cpu_percent({"cpu_stats": {}}))

    def test_memory_usage_subtracts_inactive_cache_and_preserves_limit(self):
        self.assertEqual(
            _memory_values({
                "memory_stats": {
                    "usage": 1000,
                    "limit": 5000,
                    "stats": {"inactive_file": 250},
                }
            }),
            (750, 5000),
        )

    def test_missing_memory_values_remain_null(self):
        self.assertEqual(_memory_values({}), (None, None))

    def test_network_counters_sum_all_interfaces(self):
        self.assertEqual(
            _network_values({
                "networks": {
                    "eth0": {"rx_bytes": 10, "tx_bytes": 20},
                    "eth1": {"rx_bytes": 30, "tx_bytes": 40},
                }
            }),
            (40, 60),
        )
        self.assertEqual(_network_values({}), (None, None))

    def test_block_io_counters_sum_read_and_write_operations(self):
        self.assertEqual(
            _block_io_values({
                "blkio_stats": {"io_service_bytes_recursive": [
                    {"op": "Read", "value": 10},
                    {"op": "Write", "value": 20},
                    {"op": "Read", "value": 5},
                ]}
            }),
            (15, 20),
        )
        self.assertEqual(_block_io_values({}), (None, None))


class ContainerLifecycleTests(unittest.TestCase):
    def _container(self, state):
        container = Mock()
        container.id = "container-id"
        container.name = "service"
        container.attrs = {
            "Config": {"Image": "example:latest"},
            "State": state,
            "RestartCount": 3,
        }
        return container

    def test_stopped_container_keeps_runtime_metrics_null(self):
        container = self._container({
            "Status": "exited",
            "StartedAt": "2026-04-01T00:00:00Z",
            "FinishedAt": "2026-04-01T00:02:00Z",
            "ExitCode": 137,
        })
        sampled_at = datetime(2026, 4, 1, 0, 5, tzinfo=timezone.utc)

        record = _container_record(container, sampled_at)

        container.stats.assert_not_called()
        self.assertEqual(record["restart_count"], 3)
        self.assertEqual(record["uptime_seconds"], 120)
        self.assertEqual(record["exit_code"], 137)
        self.assertEqual(record["health_status"], "not_configured")
        for metric in (
            "cpu_usage_percent",
            "memory_usage_bytes",
            "memory_limit_bytes",
            "network_received_bytes",
            "network_transmitted_bytes",
            "block_read_bytes",
            "block_write_bytes",
        ):
            self.assertIsNone(record[metric])

    def test_missing_finish_time_does_not_inflate_stopped_uptime(self):
        container = self._container({"Status": "exited", "StartedAt": "2026-04-01T00:00:00Z"})
        record = _container_record(
            container,
            datetime(2026, 4, 1, 0, 5, tzinfo=timezone.utc),
        )
        self.assertIsNone(record["uptime_seconds"])

    def test_unhealthy_is_distinct_from_missing_health_check(self):
        container = self._container({"Status": "running", "Health": {"Status": "unhealthy"}})
        container.stats.return_value = {}
        record = _container_record(container, datetime.now(timezone.utc))
        self.assertEqual(record["health_status"], "unhealthy")
        self.assertIsNone(record["cpu_usage_percent"])
        self.assertIsNone(record["memory_usage_bytes"])


if __name__ == "__main__":
    unittest.main()
