"""Running statistics files (M58): CSV per device, UTC, size-capped."""

import csv
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core import statslog  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.statslog import (RotatingCsv, StatsLog, column_name, file_name,  # noqa: E402
                                    format_value, stats_dir)
from proccoli.core.sysroot import SysRoot  # noqa: E402
from proccoli.core.units import iso_utc  # noqa: E402
from proccoli.devices.base import DeviceInfo, DeviceKind, Monitor, Snapshot  # noqa: E402
from proccoli.devices.manager import DeviceManager, Discoverer  # noqa: E402
from proccoli.devices.memory import MemorySnapshot  # noqa: E402

T0 = 1795470085.154            # 2026-11-23T21:41:25.154Z


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


class FormatTest(unittest.TestCase):
    def test_iso_utc(self):
        self.assertEqual(iso_utc(T0), "2026-11-23T21:41:25.154Z")
        self.assertEqual(iso_utc(0.9996), "1970-01-01T00:00:01.000Z")   # rounds up a second

    def test_columns_spell_out_units(self):
        self.assertEqual(column_name("usage", "%"), "usage_percent")
        self.assertEqual(column_name("read", "B/s"), "read_bytes_per_second")
        self.assertEqual(column_name("temperature", "°C"), "temperature_celsius")
        self.assertEqual(column_name("vram-used", "B"), "vram_used_bytes")
        self.assertEqual(column_name("cpu3", "%"), "cpu3_percent")
        self.assertEqual(column_name("odd", "lux"), "odd_lux")

    def test_file_names_are_safe(self):
        self.assertEqual(file_name("gpu-0000:02:00.0"), "gpu-0000-02-00.0.csv")
        self.assertEqual(file_name("cpu"), "cpu.csv")
        self.assertEqual(file_name("../x"), "..-x.csv")

    def test_values(self):
        self.assertEqual(format_value(None), "")
        self.assertEqual(format_value(42.0), "42")
        self.assertEqual(format_value(3.14159), "3.142")
        self.assertEqual(format_value(1e-7), "0")
        self.assertEqual(format_value(8547991552), "8547991552")

    def test_folder(self):
        self.assertEqual(stats_dir({"XDG_STATE_HOME": "/s"}), Path("/s/proccoli/stats"))
        self.assertEqual(stats_dir({}, home=Path("/h")), Path("/h/.local/state/proccoli/stats"))


class RotatingCsvTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "cpu.csv"

    def test_header_rows_crlf_private(self):
        f = RotatingCsv(self.path, 1 << 20)
        f.write(["time_utc", "usage_percent"], ["2026-11-23T21:41:25.154Z", "12"])
        f.flush()
        raw = self.path.read_bytes()
        self.assertEqual(raw, b"time_utc,usage_percent\r\n2026-11-23T21:41:25.154Z,12\r\n")
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_rolls_over_at_the_size_keeping_one_older_file(self):
        f = RotatingCsv(self.path, 200)
        header = ["time_utc", "usage_percent"]
        for i in range(40):
            f.write(header, [f"t{i:02d}", str(i)])
        f.flush()
        self.assertLessEqual(self.path.stat().st_size, 200)
        older = self.path.with_name("cpu.csv.1")
        self.assertLessEqual(older.stat().st_size, 200)
        self.assertFalse(self.path.with_name("cpu.csv.2").exists())
        for p in (self.path, older):
            self.assertEqual(read_rows(p)[0], header)            # each file has its header
        self.assertEqual(read_rows(self.path)[-1], ["t39", "39"])  # nothing lost at the end

    def test_new_columns_start_a_new_file(self):
        f = RotatingCsv(self.path, 1 << 20)
        f.write(["time_utc", "usage_percent"], ["a", "1"])
        f.write(["time_utc", "usage_percent", "cpu0_percent"], ["b", "2", "3"])
        f.flush()
        self.assertEqual(read_rows(self.path.with_name("cpu.csv.1")),
                         [["time_utc", "usage_percent"], ["a", "1"]])
        self.assertEqual(read_rows(self.path)[0], ["time_utc", "usage_percent", "cpu0_percent"])

    def test_continues_a_file_from_an_earlier_run(self):
        header = ["time_utc", "usage_percent"]
        first = RotatingCsv(self.path, 1 << 20)
        first.write(header, ["a", "1"])
        first.flush()
        again = RotatingCsv(self.path, 1 << 20)               # next start
        again.write(header, ["b", "2"])
        again.flush()
        self.assertEqual(read_rows(self.path), [header, ["a", "1"], ["b", "2"]])
        self.assertFalse(self.path.with_name("cpu.csv.1").exists())

    def test_buffers_then_writes(self):
        f = RotatingCsv(self.path, 1 << 20)
        header = ["time_utc", "usage_percent"]
        f.write(header, ["a", "1"])
        self.assertEqual(read_rows(self.path), [header])        # header only so far
        for i in range(statslog.FLUSH_EVERY):
            f.write(header, [str(i), "1"])
        self.assertGreater(len(read_rows(self.path)), 1)


class OneDevice(Discoverer):
    kind = DeviceKind.MEMORY

    def discover(self, sysroot, settings):
        return [DeviceInfo("memory", DeviceKind.MEMORY, "Memory")]

    def create_monitor(self, info, sysroot, settings):
        class M(Monitor):
            def sample(self, now):
                return MemorySnapshot(now, usage=25.0, total=16 * 2**30, used=4 * 2**30,
                                      swap_total=0, swap_used=0)
        return M(info)


class StatsLogTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "stats"
        self.settings = Settings.for_tests()
        self.devices = DeviceManager(SysRoot("/nonexistent"), self.settings)
        self.devices.register(OneDevice())
        self.clock = [T0]
        self.log = StatsLog(self.devices, self.settings, self.dir, lambda: self.clock[0])
        self.addCleanup(self.log.shutdown)
        self.devices.start()

    def tick(self, n=1):
        for _ in range(n):
            self.devices.refresh(self.clock[0])
            self.clock[0] += 1.0

    def test_on_by_default_one_row_per_refresh(self):
        self.assertTrue(self.settings.get("stats-log"))
        self.assertEqual(self.settings.get("stats-log-max-size"), 4096)
        self.tick(3)
        self.log.flush()
        rows = read_rows(self.dir / "memory.csv")
        self.assertEqual(rows[0], ["time_utc", "usage_percent", "swap_percent", "used_bytes",
                                   "total_bytes", "swap_used_bytes", "swap_total_bytes"])
        self.assertEqual(rows[1], ["2026-11-23T21:41:25.154Z", "25", "", str(4 * 2**30),
                                   str(16 * 2**30), "0", "0"])
        self.assertEqual(len(rows), 4)
        self.assertEqual(stat.S_IMODE(self.dir.stat().st_mode), 0o700)

    def test_turning_it_off_stops_recording(self):
        self.tick()
        self.settings.set("stats-log", False)
        self.tick(5)
        self.settings.set("stats-log", True)
        self.tick()
        self.log.flush()
        self.assertEqual(len(read_rows(self.dir / "memory.csv")), 3)    # header + 2

    def test_size_setting_applies_live(self):
        self.tick()
        self.settings.set("stats-log-max-size", 64)
        self.assertEqual(self.log.files["memory"].max_bytes, 64 * 1024)

    def test_shutdown_writes_out_and_stops_following(self):
        self.tick(2)
        self.log.shutdown()
        self.assertEqual(len(read_rows(self.dir / "memory.csv")), 3)
        self.tick()                                             # no longer followed
        self.assertEqual(len(read_rows(self.dir / "memory.csv")), 3)

    def test_unwritable_folder_is_logged_not_raised(self):
        self.log.directory = Path("/proc/no-such-place")
        with self.assertLogs("proccoli.core.statslog", "WARNING"):
            self.tick()


class SnapshotStatsTest(unittest.TestCase):
    def test_default_is_the_graphed_readings(self):
        s = Snapshot(0.0, usage=5.0)
        self.assertEqual(s.stats_values(), {"usage": 5.0})
        self.assertEqual(s.stats_units(), {"usage": "%"})

    def test_gpu_adds_memory_bytes(self):
        from proccoli.gpu.backend import GpuSummary
        from proccoli.gpu.controller import GpuSnapshot
        snap = GpuSnapshot(0.0, summary=GpuSummary(usage=10.0, vram_used=1, vram_total=2))
        self.assertEqual(snap.stats_values()["vram-used"], 1)
        self.assertEqual(snap.stats_units()["vram-total"], "B")
        self.assertEqual(set(snap.stats_values()), set(snap.stats_units()))


if __name__ == "__main__":
    unittest.main()
