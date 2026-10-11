import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from src.collectors import cpu, disk, memory, network


def assert_utc_timestamp(test_case: unittest.TestCase, value: str) -> None:
    timestamp = datetime.fromisoformat(value)
    test_case.assertIsNotNone(timestamp.tzinfo)
    test_case.assertEqual(timestamp.utcoffset(), timezone.utc.utcoffset(timestamp))


class CpuCollectorTests(unittest.TestCase):
    @patch("src.collectors.cpu.psutil.cpu_percent", return_value=23.5)
    def test_returns_usage_and_utc_timestamp(self, cpu_percent):
        reading = cpu.cpu_usage(interval=0.25)
        cpu_percent.assert_called_once_with(interval=0.25)
        self.assertEqual(reading["cpu_usage"], 23.5)
        self.assertIsNone(reading["collection_error"])
        assert_utc_timestamp(self, reading["timestamp"])

    @patch("src.collectors.cpu.psutil.cpu_percent", side_effect=OSError("unavailable"))
    def test_returns_error_when_collection_fails(self, _cpu_percent):
        reading = cpu.cpu_usage(interval=1)
        self.assertIsNone(reading["cpu_usage"])
        self.assertEqual(reading["collection_error"], "unavailable")
        assert_utc_timestamp(self, reading["timestamp"])


class MemoryCollectorTests(unittest.TestCase):
    @patch(
        "src.collectors.memory.psutil.virtual_memory",
        return_value=SimpleNamespace(percent=42.0, used=420, available=580, total=1000),
    )
    def test_returns_memory_reading(self, _virtual_memory):
        reading = memory.memory_usage()
        self.assertEqual(reading["memory_usage"], 42.0)
        self.assertEqual(reading["used_bytes"], 420)
        self.assertEqual(reading["available_bytes"], 580)
        self.assertEqual(reading["total_bytes"], 1000)
        self.assertIsNone(reading["collection_error"])
        assert_utc_timestamp(self, reading["timestamp"])

    @patch("src.collectors.memory.psutil.virtual_memory", side_effect=OSError("denied"))
    def test_returns_error_when_collection_fails(self, _virtual_memory):
        reading = memory.memory_usage()
        self.assertIsNone(reading["memory_usage"])
        self.assertIsNone(reading["used_bytes"])
        self.assertEqual(reading["collection_error"], "denied")


class DiskCollectorTests(unittest.TestCase):
    @patch(
        "src.collectors.disk.psutil.disk_usage",
        side_effect=[
            SimpleNamespace(percent=50.0, used=500, free=500, total=1000),
            PermissionError("inaccessible"),
        ],
    )
    def test_collects_mounts_and_handles_inaccessible_mount(self, disk_usage_mock):
        reading = disk.disk_usage(["/data", "/private"])
        self.assertEqual(disk_usage_mock.call_args_list[0].args, ("/data",))
        self.assertEqual(disk_usage_mock.call_args_list[1].args, ("/private",))
        self.assertEqual(reading["mounts"][0], {
            "mount_point": "/data",
            "usage_percent": 50.0,
            "used_bytes": 500,
            "free_bytes": 500,
            "total_bytes": 1000,
            "collection_error": None,
        })
        inaccessible = reading["mounts"][1]
        self.assertEqual(inaccessible["mount_point"], "/private")
        self.assertIsNone(inaccessible["total_bytes"])
        self.assertEqual(inaccessible["collection_error"], "inaccessible")
        assert_utc_timestamp(self, reading["timestamp"])


class NetworkCollectorTests(unittest.TestCase):
    def setUp(self):
        network._previous_sample = None

    def test_first_sample_has_no_rates(self):
        with (
            patch("src.collectors.network.psutil.net_io_counters", return_value=SimpleNamespace(bytes_sent=10, bytes_recv=20)),
            patch("src.collectors.network.time.monotonic", return_value=1.0),
        ):
            reading = network.network_usage()
        self.assertEqual(reading["bytes_sent"], 10)
        self.assertEqual(reading["bytes_received"], 20)
        self.assertIsNone(reading["bytes_sent_per_second"])
        self.assertIsNone(reading["bytes_received_per_second"])
        assert_utc_timestamp(self, reading["timestamp"])

    def test_rates_use_successive_counters_and_elapsed_time(self):
        counters = [
            SimpleNamespace(bytes_sent=10, bytes_recv=20),
            SimpleNamespace(bytes_sent=50, bytes_recv=80),
        ]
        with (
            patch("src.collectors.network.psutil.net_io_counters", side_effect=counters),
            patch("src.collectors.network.time.monotonic", side_effect=[1.0, 3.0]),
        ):
            network.network_usage()
            reading = network.network_usage()
        self.assertEqual(reading["bytes_sent_per_second"], 20.0)
        self.assertEqual(reading["bytes_received_per_second"], 30.0)

    def test_counter_reset_produces_zero_rate_for_reset_direction(self):
        counters = [
            SimpleNamespace(bytes_sent=100, bytes_recv=100),
            SimpleNamespace(bytes_sent=10, bytes_recv=140),
        ]
        with (
            patch("src.collectors.network.psutil.net_io_counters", side_effect=counters),
            patch("src.collectors.network.time.monotonic", side_effect=[1.0, 3.0]),
        ):
            network.network_usage()
            reading = network.network_usage()
        self.assertEqual(reading["bytes_sent_per_second"], 0.0)
        self.assertEqual(reading["bytes_received_per_second"], 20.0)

    def test_failed_sample_keeps_last_successful_baseline(self):
        responses = [
            SimpleNamespace(bytes_sent=10, bytes_recv=10),
            OSError("counter unavailable"),
            SimpleNamespace(bytes_sent=30, bytes_recv=50),
        ]

        def read_counters():
            result = responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with (
            patch("src.collectors.network.psutil.net_io_counters", side_effect=read_counters),
            patch("src.collectors.network.time.monotonic", side_effect=[1.0, 3.0]),
        ):
            network.network_usage()
            failed = network.network_usage()
            reading = network.network_usage()
        self.assertEqual(failed["collection_error"], "counter unavailable")
        self.assertEqual(reading["bytes_sent_per_second"], 10.0)
        self.assertEqual(reading["bytes_received_per_second"], 20.0)


if __name__ == "__main__":
    unittest.main()
