"""The metrics history database: core.history_db,
core.history_store, core.history_export, and History.backfill."""

import csv
import json
import os
import random
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from proccoli.core.history import Averager, History  # noqa: E402
from proccoli.core.history_db import (DAY_MS, HOUR_MS, MINUTE_MS, HistoryDb, delete_files,  # noqa: E402
                                      column_name, from_fixed, scale_for, table_name,
                                      mend_drift, to_fixed, unit_of_column)
from proccoli.core.history_export import (export_session, file_stem,  # noqa: E402
                                          folder_name, format_value)
from proccoli.core import history_store  # noqa: E402
from proccoli.core.history_store import (HistoryStore, history_path, import_csv,  # noqa: E402
                                         offline_slots, old_stats_dir, open_run)
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.sysroot import SysRoot  # noqa: E402
from proccoli.core.units import iso_utc, parse_iso_utc  # noqa: E402
from proccoli.devices.base import DeviceInfo, DeviceKind, Monitor, Snapshot  # noqa: E402
from proccoli.devices.manager import DeviceManager, Discoverer  # noqa: E402
from proccoli.devices.memory import MemorySnapshot  # noqa: E402

T0 = 1795470085.154            # 2026-11-23T21:41:25.154Z
MONO = 5000.0                  # the monitors' clock at T0


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


class TempFolder(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.path = self.dir / "state" / "history.sqlite3"


class FormatTest(unittest.TestCase):
    def test_iso_utc_round_trip(self):
        self.assertEqual(iso_utc(T0), "2026-11-23T21:41:25.154Z")
        self.assertAlmostEqual(parse_iso_utc("2026-11-23T21:41:25.154Z"), T0, places=6)
        self.assertEqual(parse_iso_utc("1970-01-01T00:00:01Z"), 1.0)
        with self.assertRaises(ValueError):
            parse_iso_utc("yesterday")

    def test_columns_spell_out_units(self):
        self.assertEqual(column_name("usage", "%"), "usage_percent")
        self.assertEqual(column_name("read", "B/s"), "read_bytes_per_second")
        self.assertEqual(column_name("temperature", "°C"), "temperature_celsius")
        self.assertEqual(column_name("vram-used", "B"), "vram_used_bytes")
        self.assertEqual(column_name("odd", "lux"), "odd_lux")

    def test_units_back_from_columns(self):
        self.assertEqual(unit_of_column("read_bytes_per_second"), ("read", "B/s"))
        self.assertEqual(unit_of_column("vram_used_bytes"), ("vram_used", "B"))
        self.assertEqual(unit_of_column("cpu3_percent"), ("cpu3", "%"))
        self.assertEqual(unit_of_column("odd_lux"), ("odd_lux", ""))

    def test_tables_match_the_old_file_names(self):
        self.assertEqual(table_name("gpu-0000:02:00.0"), "d_gpu_0000_02_00_0")
        self.assertEqual(table_name("gpu-0000-02-00.0"), "d_gpu_0000_02_00_0")
        self.assertEqual(table_name("../"), "d_device")
        self.assertEqual(file_stem("gpu-0000:02:00.0"), "gpu-0000-02-00.0")

    def test_fixed_point_round_trips(self):
        cases = [(12.34, "%"), (45.67, "°C"), (12.345, "W"), (8547991552, "B"),
                 (1234.5, "B/s"), (1.5e9, "Hz"), (1.2345, "lux")]
        for value, unit in cases:
            scale = scale_for(unit)
            self.assertAlmostEqual(from_fixed(to_fixed(value, scale), scale), value,
                                   delta=0.5 / scale, msg=unit)
        self.assertIsNone(to_fixed(None, 100))
        self.assertIsNone(to_fixed(float("nan"), 100))
        self.assertIsNone(to_fixed(float("inf"), 100))
        self.assertIsInstance(to_fixed(12.34, 100), int)

    def test_export_values_and_names(self):
        self.assertEqual(format_value(None), "")
        self.assertEqual(format_value(42.0), "42")
        self.assertEqual(format_value(3.14159), "3.142")
        self.assertEqual(format_value(8547991552), "8547991552")
        self.assertEqual(folder_name(T0), "proccoli-statistics-20261123T214125Z")

    def test_paths(self):
        env = {"XDG_STATE_HOME": "/s"}
        self.assertEqual(history_path(env), Path("/s/proccoli/history.sqlite3"))
        self.assertEqual(old_stats_dir(env), Path("/s/proccoli/stats"))
        self.assertEqual(history_path({}, home=Path("/h")),
                         Path("/h/.local/state/proccoli/history.sqlite3"))


class HistoryBackfillTest(unittest.TestCase):
    def setUp(self):
        self.h = History(6)
        self.h.add(10.0, {"usage": 50.0}, {"usage": "%"})
        self.h.add(11.0, {"usage": 60.0})

    def test_older_samples_go_in_front(self):
        added = self.h.backfill([7.0, 8.0, 9.0], {"usage": [1.0, None, 3.0],
                                                  "unknown": [9.0, 9.0, 9.0]})
        self.assertEqual(added, 3)
        self.assertEqual(list(self.h.times), [7.0, 8.0, 9.0, 10.0, 11.0])
        self.assertEqual(list(self.h.series("usage").values), [1.0, None, 3.0, 50.0, 60.0])
        self.assertIsNone(self.h.series("unknown"))

    def test_only_what_fits_newest_first(self):
        added = self.h.backfill([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], {"usage": [1, 2, 3, 4, 5, 6]})
        self.assertEqual(added, 4)
        self.assertEqual(list(self.h.times), [3.0, 4.0, 5.0, 6.0, 10.0, 11.0])
        self.assertEqual(self.h.room(), 0)
        self.assertEqual(self.h.backfill([0.5], {"usage": [1]}), 0)

    def test_never_overlaps_what_it_holds(self):
        self.assertEqual(self.h.backfill([10.0, 12.0], {"usage": [1, 2]}), 0)


class AveragingTest(unittest.TestCase):
    """Long Graph Time Ranges: each point averages several samples."""

    def test_averager(self):
        a = Averager(3)
        self.assertIsNone(a.push({"x": 1.0, "y": None}))
        self.assertIsNone(a.push({"x": 2.0, "y": None}))
        self.assertEqual(a.push({"x": 6.0, "y": None}), {"x": 3.0, "y": None})
        self.assertEqual(Averager(1).push({"x": 1.0}), {"x": 1.0})

    def test_history_points_average_samples(self):
        h = History(10)
        h.set_plan(10, 2, 2.0)
        self.assertEqual((h.every, h.step_s), (2, 2.0))
        h.add(1.0, {"usage": 10.0}, {"usage": "%"})
        self.assertEqual(len(h), 0)                         # half a point
        self.assertIsNotNone(h.series("usage"))            # defined at once
        h.add(2.0, {"usage": 20.0})
        self.assertEqual((list(h.times), list(h.series("usage").values)), ([2.0], [15.0]))
        h.add(3.0, {"usage": 99.0})
        h.add_gap(4.0)                                      # drops the half point
        h.add(5.0, {"usage": 1.0})
        h.add(6.0, {"usage": 3.0})
        self.assertEqual(list(h.series("usage").values), [15.0, None, 2.0])
        self.assertEqual(h.keys(), [("usage", "%")])


class HistoryDbTest(TempFolder):
    def setUp(self):
        super().setUp()
        self.db = HistoryDb(self.path)
        self.addCleanup(self.db.close)

    def write(self, tbl, cols, start_ms, count, step_ms, value=lambda i: 50.0):
        with self.db.transaction():
            for i in range(count):
                self.db.insert(tbl, start_ms + i * step_ms,
                               {c: to_fixed(value(i), s) for c, s in cols.values()})

    def test_private_file_and_folder(self):
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o700)
        self.assertEqual(self.db.conn.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(self.db.conn.execute("PRAGMA auto_vacuum").fetchone()[0], 2)

    def test_new_readings_are_new_columns(self):
        with self.db.transaction():
            tbl = self.db.ensure_device("cpu", "Processor", "cpu")
            self.db.ensure_columns(tbl, {"usage": "%"})
            self.db.insert(tbl, 1000, {"usage_percent": 1234})
            cols = self.db.ensure_columns(tbl, {"usage": "%", "cpu0": "%"})
            self.db.insert(tbl, 2000, {"usage_percent": 1, "cpu0_percent": 2})
        self.assertEqual(cols["cpu0"], ("cpu0_percent", 100))
        self.assertEqual([r["col"] for r in self.db.readings(tbl)],
                         ["usage_percent", "cpu0_percent"])
        self.assertEqual(self.db.rows(tbl, ["usage_percent", "cpu0_percent"], 0, 10_000),
                         [(1000, 1234, None), (2000, 1, 2)])
        self.assertEqual(self.db.devices(), [{"table": "d_cpu", "id": "cpu",
                                              "name": "Processor", "kind": "cpu"}])

    def test_a_clock_set_back_overwrites_its_own_time_only(self):
        with self.db.transaction():
            tbl = self.db.ensure_device("cpu")
            self.db.ensure_columns(tbl, {"usage": "%"})
            for t, v in ((1000, 1), (2000, 2), (1000, 3)):
                self.db.insert(tbl, t, {"usage_percent": v})
        self.assertEqual(self.db.rows(tbl, ["usage_percent"], 0, 5000), [(1000, 3), (2000, 2)])

    def test_roll_up_minutes_and_hours(self):
        with self.db.transaction():
            tbl = self.db.ensure_device("cpu")
            cols = self.db.ensure_columns(tbl, {"usage": "%"})
        # Two hours at one reading a second: 0, 1, 2, … 99, 0, …
        self.write(tbl, cols, 0, 7200, 1000, value=lambda i: i % 100)
        with self.db.transaction():
            self.db.roll_up(2 * HOUR_MS + 1)
        minutes = self.db.rows(tbl, ["usage_percent_avg", "usage_percent_min",
                                     "usage_percent_max"], 0, DAY_MS, "_m")
        self.assertEqual(len(minutes), 120)
        self.assertEqual(minutes[0], (0, to_fixed(29.5, 100), 0, to_fixed(59, 100)))
        hours = self.db.conn.execute("SELECT time, n, usage_percent_avg, usage_percent_min, "
                                     "usage_percent_max FROM d_cpu_h").fetchall()
        self.assertEqual(hours, [(0, 3600, to_fixed(49.5, 100), 0, to_fixed(99, 100)),
                                 (HOUR_MS, 3600, to_fixed(49.5, 100), 0, to_fixed(99, 100))])
        # Again: nothing changes (idempotent), and an unfinished minute waits.
        self.write(tbl, cols, 7200_000, 30, 1000)
        with self.db.transaction():
            self.db.roll_up(7200_000 + 30_000)
        self.assertEqual(self.db.count(tbl, "_m"), 120)

    def test_expiry_keeps_what_is_not_summarised(self):
        with self.db.transaction():
            tbl = self.db.ensure_device("cpu")
            cols = self.db.ensure_columns(tbl, {"usage": "%"})
        self.write(tbl, cols, 0, 180, MINUTE_MS)                 # 3 hours of minutes
        with self.db.transaction():
            self.db.expire(3 * HOUR_MS, HOUR_MS, HOUR_MS)          # nothing rolled up yet
        self.assertEqual(self.db.count(tbl), 180)
        with self.db.transaction():
            self.db.roll_up(3 * HOUR_MS)
            self.db.expire(3 * HOUR_MS, HOUR_MS, HOUR_MS)
        self.assertEqual(self.db.oldest(tbl), 2 * HOUR_MS)
        self.assertEqual(self.db.oldest(tbl, "_m"), 2 * HOUR_MS)
        self.assertEqual(self.db.count(tbl, "_h"), 3)

    def test_cap_cuts_hours_then_minutes_never_the_last_hour_of_detail(self):
        with self.db.transaction():
            tbl = self.db.ensure_device("cpu")
            cols = self.db.ensure_columns(tbl, {f"cpu{i}": "%" for i in range(16)})
        now = 400 * DAY_MS
        rnd = random.Random(1)
        with self.db.transaction():
            for h in range(300 * 24):                               # 300 days of hours
                self.db.conn.execute("INSERT INTO d_cpu_h (time, n, cpu0_percent_avg) "
                                     "VALUES (?, 60, ?)", (h * HOUR_MS, rnd.randrange(10000)))
        self.write(tbl, cols, now - 2 * HOUR_MS, 7200, 1000, value=lambda i: rnd.random() * 100)
        before = self.db.size_bytes()
        with self.db.transaction():
            self.assertTrue(self.db.enforce_cap(before // 2, now))
        self.assertLessEqual(self.db.size_bytes(), before // 2)
        self.assertEqual(self.db.count(tbl, "_h"), 0)               # all hours went first
        self.assertGreater(self.db.count(tbl), 0)
        with self.db.transaction():
            self.db.enforce_cap(1, now)                             # can't be met
        self.assertEqual(self.db.oldest(tbl), now - HOUR_MS)          # the last hour stays
        self.db.vacuum()

    def test_buckets_average_each_point(self):
        with self.db.transaction():
            tbl = self.db.ensure_device("cpu")
            cols = self.db.ensure_columns(tbl, {"usage": "%"})
            self.db.conn.execute("INSERT INTO d_cpu_m (time, n, usage_percent_avg) "
                                 "VALUES (0, 60, 100)")        # before the detail
        self.write(tbl, cols, 120_000, 8, 1000, value=lambda i: i)   # 0..7 at 1 s
        points = self.db.buckets(tbl, ["usage_percent"], 0, 70, 2000)
        self.assertEqual(points[0], (100.0,))                  # a minute average
        self.assertEqual(points[60], (50.0,))                  # 0 and 1 %
        self.assertEqual(points[63], (650.0,))                 # 6 and 7 %
        self.assertNotIn(1, points)                            # nothing there: a gap
        self.assertNotIn(64, points)
        self.assertEqual(self.db.buckets(tbl, ["usage_percent"], 0, 0, 1000), {})

    def test_readings_that_drift_fill_every_slot(self):
        """A recorder's ticks 1005 ms apart leave a 1-s slot empty every
        200 readings; those holes aren't gaps. A stopped recorder's are."""
        with self.db.transaction():
            tbl = self.db.ensure_device("cpu")
            cols = self.db.ensure_columns(tbl, {"usage": "%"})
        self.write(tbl, cols, 0, 600, 1005, value=lambda i: i % 100)
        self.write(tbl, cols, 603_000 + 71_000, 10, 1000, value=lambda i: 5)
        points = self.db.buckets(tbl, ["usage_percent"], 0, 700, 1000)
        self.assertEqual([i for i in range(602) if i not in points], [])     # 2 holes before
        self.assertEqual([i for i in range(604, 674) if i in points], [])    # the 71-s gap stays

    def test_mend_drift(self):
        b = 1000
        # A reading at 1999 and the next at 3001: slot 2 is empty; 3001 is
        # 1 ms past slot 2's end, 1999 1 ms before its start: the earlier is
        # as near, and wins the tie.
        self.assertEqual(mend_drift({1: (1999, 1999, (1,)), 3: (3001, 3001, (3,))}, 0, b),
                         {1: (1,), 2: (1,), 3: (3,)})
        self.assertEqual(mend_drift({1: (1600, 1600, (1,)), 3: (3001, 3001, (3,))}, 0, b)[2],
                         (3,))                                   # the later is nearer
        gap = {1: (1000, 1000, (1,)), 3: (3600, 3600, (3,))}     # 2.6 steps apart
        self.assertEqual(mend_drift(gap, 0, b), {1: (1,), 3: (3,)})
        two = {1: (1999, 1999, (1,)), 4: (4001, 4001, (4,))}     # two empty slots
        self.assertEqual(mend_drift(two, 0, b), {1: (1,), 4: (4,)})
        self.assertEqual(mend_drift({}, 0, b), {})

    def test_series_uses_minutes_where_detail_is_gone(self):
        with self.db.transaction():
            tbl = self.db.ensure_device("cpu")
            cols = self.db.ensure_columns(tbl, {"usage": "%"})
            self.db.conn.execute("INSERT INTO d_cpu_m (time, n, usage_percent_avg) "
                                 "VALUES (0, 60, 100)")
        self.write(tbl, cols, MINUTE_MS, 3, 1000)
        self.assertEqual(self.db.series(tbl, ["usage_percent"], 0, HOUR_MS),
                         [(0, 100), (60000, 5000), (61000, 5000), (62000, 5000)])


class FakeSnapshot(Snapshot):
    """A device with ``readings`` percentages (like a CPU's threads)."""

    def __init__(self, time, values):
        super().__init__(time, usage=values.get("usage"))
        self.values = values

    def history_values(self):
        return dict(self.values)

    def history_units(self):
        return {n: "%" for n in self.values}


class Device(Discoverer):
    kind = DeviceKind.CPU

    def __init__(self, readings=("usage",), values=None):
        self.readings = list(readings)
        self.values = values or (lambda now, name: 25.0)

    def discover(self, sysroot, settings):
        return [DeviceInfo("cpu", DeviceKind.CPU, "Processor")]

    def create_monitor(self, info, sysroot, settings):
        device = self

        class M(Monitor):
            def sample(self, now):
                return FakeSnapshot(now, {n: device.values(now, n) for n in device.readings})
        return M(info, 61)


class MemoryDevice(Discoverer):
    kind = DeviceKind.MEMORY

    def discover(self, sysroot, settings):
        return [DeviceInfo("memory", DeviceKind.MEMORY, "Memory")]

    def create_monitor(self, info, sysroot, settings):
        class M(Monitor):
            def sample(self, now):
                return MemorySnapshot(now, usage=25.0, total=16 * 2**30, used=4 * 2**30,
                                      swap_total=0, swap_used=0)
        return M(info, 61)


class StoreCase(TempFolder):
    STORE = HistoryStore

    def make(self, *discoverers, idle=None, import_dir=None, **settings):
        self.settings = Settings.for_tests(settings)
        self.devices = DeviceManager(SysRoot("/nonexistent"), self.settings)
        for d in discoverers or (MemoryDevice(),):
            self.devices.register(d)
        if not hasattr(self, "clock"):
            self.clock = [T0]
        self.store = self.STORE(self.devices, self.settings, self.path, "9.9",
                                lambda: self.clock[0], idle=idle, import_dir=import_dir)
        self.addCleanup(self.store.shutdown)
        self.devices.start()

    def tick(self, n=1, step=1.0):
        for _ in range(n):
            self.devices.refresh(MONO + self.clock[0] - T0)
            self.clock[0] += step

    def monitor(self, device_id):
        return next(m for m in self.devices.monitors() if m.info.id == device_id)


class HistoryStoreTest(StoreCase):
    def test_on_by_default_and_commits_every_ten_seconds(self):
        self.make()
        self.assertTrue(self.settings.get("history"))
        self.assertEqual(self.settings.get("history-max-size"), 512)
        self.assertEqual(self.settings.get("history-detail-hours"), 24)
        self.tick(5)
        self.assertEqual(self.store.db.devices(), [])                    # buffered
        self.tick(6)
        self.assertEqual(self.store.db.count("d_memory"), 11)
        rows = self.store.db.rows("d_memory", ["usage_percent", "used_bytes"], 0, 2**62)
        self.assertEqual(rows[0], (1795470085154, 2500, 4 * 2**30))
        self.assertEqual(self.store.db.sessions(), [(1795470085154, 1795470095154)])

    def test_quitting_writes_out_and_ends_the_session(self):
        self.make()
        self.tick(3)
        self.store.shutdown()
        db = HistoryDb(self.path)
        self.addCleanup(db.close)
        self.assertEqual(db.count("d_memory"), 3)
        self.assertEqual(db.sessions(), [(1795470085154, 1795470088154)])
        self.assertEqual(db.devices()[0]["name"], "Memory")
        self.tick()                                                      # not followed
        self.assertEqual(db.count("d_memory"), 3)

    def test_turning_it_off_stops_recording(self):
        self.make()
        self.tick(2)
        self.settings.set("history", False)
        self.assertIsNone(self.store.db)                               # written and closed
        self.tick(20)
        self.settings.set("history", True)
        self.tick(11)
        db = self.store.db
        self.assertEqual(db.count("d_memory"), 13)
        self.assertEqual(len(db.sessions()), 2)

    def test_delete(self):
        self.make()
        self.tick(11)
        self.assertGreater(self.store.size_on_disk(), 0)
        self.store.delete()
        self.assertFalse(self.path.exists())
        self.assertEqual(self.store.size_on_disk(), 0)
        self.tick(11)                                                    # starts again
        self.assertEqual(self.store.db.count("d_memory"), 11)

    def test_new_readings_appear_later(self):
        device = Device(["usage"])
        self.make(device)
        self.tick(11)
        device.readings.append("cpu0")
        self.tick(11)
        rows = self.store.db.rows("d_cpu", ["usage_percent", "cpu0_percent"], 0, 2**62)
        self.assertEqual(rows[0][2], None)
        self.assertEqual(rows[-1][2], 2500)

    def test_unwritable_place_is_logged_not_raised(self):
        self.path = Path("/proc/no-such-place/history.sqlite3")
        with self.assertLogs("proccoli.core.history_store", "WARNING"):
            self.make()
            self.tick(12)
        self.tick(12)                                                    # gives up quietly

    def test_a_simulated_week_keeps_each_level_for_its_time(self):
        rnd = random.Random(2)
        self.make(Device(["usage", "cpu0"], lambda now, n: rnd.random() * 100))
        self.tick(7 * 24 * 12, step=300.0)                    # a week at 5 minutes
        self.store.housekeeping()
        db, now = self.store.db, int(self.clock[0] * 1000)
        self.assertGreaterEqual(db.oldest("d_cpu"), now - 24 * HOUR_MS - MINUTE_MS)
        self.assertLess(db.oldest("d_cpu"), now - 23 * HOUR_MS)
        self.assertLess(db.oldest("d_cpu", "_m"), now - 6 * 24 * HOUR_MS)
        self.assertGreater(db.count("d_cpu", "_h"), 6 * 24)
        self.assertEqual(db.count("d_cpu", "_m"), 7 * 24 * 12)           # one per reading

    def test_detail_hours_setting(self):
        self.make()
        self.tick(4 * 12, step=300.0)                          # four hours
        self.settings.set("history-detail-hours", 1)
        self.tick()
        self.assertGreaterEqual(self.store.db.oldest("d_memory"),
                                int(self.clock[0] * 1000) - HOUR_MS - 600_000)


class SmallStore(HistoryStore):
    max_bytes = 256 * 1024


class ThreeYearsTest(StoreCase):
    STORE = SmallStore

    def test_three_years_stay_under_the_cap(self):
        rnd = random.Random(3)
        self.make(Device([f"cpu{i}" for i in range(24)], lambda now, n: rnd.random() * 100))
        with self.assertLogs("proccoli.core.history_store", "INFO") as logs:
            self.tick(3 * 365 * 4, step=6 * 3600.0)           # 3 years at 6 hours
            self.store.housekeeping()
        db, now = self.store.db, int(self.clock[0] * 1000)
        self.assertLessEqual(db.size_bytes(), SmallStore.max_bytes)
        self.assertTrue(any("oldest data removed" in m for m in logs.output))
        self.assertGreater(db.count("d_cpu", "_h"), 0)                 # recent hours stay
        self.assertGreater(db.oldest("d_cpu", "_h"), now - 3 * 365 * DAY_MS)  # oldest went
        self.assertGreaterEqual(db.oldest("d_cpu", "_m"), now - 30 * DAY_MS - DAY_MS)


class BackfillTest(StoreCase):
    def test_a_new_run_shows_the_last_one_at_once(self):
        self.make(Device(values=lambda now, n: now % 100))
        self.tick(40)
        self.store.shutdown()
        self.clock[0] += 5                                      # 5 s later: a new run
        self.make(Device(values=lambda now, n: 1.0))
        history = self.monitor("cpu").history
        self.assertEqual(len(history), 0)
        self.tick()                                             # the first reading
        self.assertEqual(len(history), 46)          # 40, a 5 s gap, the new one
        values = list(history.series("usage").values)
        self.assertEqual(values[-1], 1.0)
        self.assertEqual(values[-6:-1], [None] * 5)              # the gap between runs
        self.assertEqual(values[-7], (MONO + 39) % 100)          # the last run's last
        self.assertEqual(history.times[0], MONO)

    def test_widening_the_range_fills_from_the_database(self):
        self.make(Device())
        self.tick(130)
        history = self.monitor("cpu").history
        self.assertEqual(len(history), 61)
        self.settings.set("graph-time-range", "2-minutes")
        self.assertEqual(history.max_points, 121)
        self.assertEqual(len(history), 121)
        self.assertEqual(list(history.series("usage").values), [25.0] * 121)
        self.assertEqual(list(history.times), [MONO + 9 + i for i in range(121)])

    def test_long_ranges_fill_with_averages(self):
        # A run at 1 s, then one with a 1-hour range: 4 s points, averaged.
        self.make(Device(values=lambda now, n: float(int(now) % 2)))   # 0, 1, 0, 1, …
        self.tick(400)
        self.store.shutdown()
        self.clock[0] += 2
        self.make(Device(), **{"graph-time-range": "1-hour"})
        history = self.monitor("cpu").history
        self.assertEqual((history.max_points, history.every, history.step_s), (901, 4, 4.0))
        self.tick()                               # the first sample: no point yet
        added = list(history.series("usage").values)
        self.assertGreater(len(added), 95)
        self.assertTrue(all(v is None or abs(v - 0.5) < 1e-9 for v in added))
        self.assertGreater(sum(v is not None for v in added), 95)

    def test_a_custom_week_fills_from_minute_averages(self):
        # a 7-day custom range, past the day of detail kept.
        self.make(Device(), **{"history-detail-hours": 24})
        self.tick(6 * 24 * 60, step=60.0)                     # six days at 1 minute
        self.store.housekeeping()                             # older detail → minutes
        self.store.shutdown()
        self.clock[0] += 60
        self.make(Device(), **{"graph-time-range": "custom",
                               "graph-time-range-custom": 7 * 86400})
        history = self.monitor("cpu").history
        self.assertLessEqual(history.max_points, 1200)
        self.tick()
        values = [v for v in history.series("usage").values if v is not None]
        # Six of the seven days have readings: most of the points are filled.
        self.assertGreater(len(values), 0.8 * 6 / 7 * history.max_points)
        self.assertTrue(all(abs(v - 25.0) < 1e-9 for v in values))

    def test_a_details_tab_fills_too(self):
        from proccoli.gpu.intel_gpu_top.history import History as IgtHistory
        target = IgtHistory(61)
        target.set_plan(61, 1, 1.0)

        class GpuDevice(Device):
            def create_monitor(self, info, sysroot, settings):
                monitor = Device.create_monitor(self, info, sysroot, settings)
                monitor.detail_history = lambda: target
                return monitor

        key = "detail/engines/Render/3D/0"
        self.make(GpuDevice(["usage", key]))
        self.tick(30)
        self.store.shutdown()
        self.clock[0] += 3
        target.add({"engines": {"Render/3D/0": {"busy": 5.0}}}, timestamp=self.clock[0])
        self.make(GpuDevice(["usage", key]))
        self.tick()
        values = list(target.series[("engines", "Render/3D/0")].values)
        self.assertEqual(values[-1], 5.0)
        self.assertEqual(values.count(25.0), 30)              # the last run's readings
        self.assertEqual(target.times[0], T0)                 # wall clock times

    def assert_evenly_spaced(self, history, span_s):
        times = list(history.times)
        step = history.step_s
        self.assertTrue(times)
        for a, b in zip(times, times[1:]):
            self.assertAlmostEqual(b - a, step, places=6)
        self.assertLessEqual(times[-1] - times[0], span_s + step)

    def test_range_changes_never_stretch_old_points(self):
        # 3 hours of readings, then 1 minute → 1 hour → 6 hours →
        # 1 day. Each graph's points are its own step apart and cover the
        # 3 hours, not the whole axis.
        self.make(Device(), **{"update-interval": "10-seconds"})
        self.tick(1080, step=10.0)                               # 3 hours
        history = self.monitor("cpu").history
        for nick in ("1-hour", "6-hours", "1-day"):
            with self.subTest(range=nick):
                self.settings.set("graph-time-range", nick)
                self.assert_evenly_spaced(history, 3 * 3600)
                self.assertGreater(history.times[-1] - history.times[0], 3 * 3600 - 2 * history.step_s
                                   if nick != "1-hour" else 3600 - 2 * history.step_s)
                # The oldest edge may hold the first minute's average a slot
                # early (it's timed at the minute's start); no gaps after it.
                self.assertNotIn(None, list(history.series("usage").values)[2:])

    def test_without_the_history_points_are_regrouped(self):
        self.make(Device(), history=False, **{"update-interval": "10-seconds"})
        self.settings.set("graph-time-range", "1-hour")
        self.tick(360, step=10.0)
        history = self.monitor("cpu").history
        self.settings.set("graph-time-range", "6-hours")           # 10 s → 20 s points
        self.assert_evenly_spaced(history, 3600)
        self.assertEqual(history.step_s, 20.0)
        self.settings.set("graph-time-range", "1-minute")          # back to 10 s: dropped
        self.assertEqual(len(history), 0)

    def test_time_between_runs_is_offline(self):
        self.make(Device())
        self.tick(40)
        self.store.shutdown()                                     # ends at T0 + 40
        self.clock[0] += 5
        self.make(Device())
        history = self.monitor("cpu").history
        self.tick()
        offline = list(history.offline)
        self.assertEqual(len(offline), len(history))
        self.assertEqual(offline[-6:], [False, True, True, True, True, False])
        self.assertEqual(offline.count(True), 4)
        self.assertIs(history.series("usage").offline, history.offline)

    def test_a_reading_missing_while_running_is_not_offline(self):
        self.make(Device(values=lambda now, n: None if 10 <= now - MONO < 20 else 1.0))
        self.tick(30)
        self.settings.set("graph-time-range", "2-minutes")
        history = self.monitor("cpu").history
        self.assertIn(None, list(history.series("usage").values))
        self.assertNotIn(True, list(history.offline))

    def test_one_device_per_idle_call(self):
        pending = []
        self.make(Device(), MemoryDevice(), idle=pending.append)
        self.tick()
        self.assertEqual(len(pending), 1)                       # one callback, two devices
        self.assertTrue(pending[0]())
        self.assertFalse(pending[0]())

    def test_nothing_from_a_store_that_is_off(self):
        self.make(history=False)
        self.tick(3)
        self.assertIsNone(self.store.db)
        self.assertFalse(self.path.exists())


class ImportTest(StoreCase):
    def write_old(self, name, header, rows):
        folder = self.dir / "stats"
        folder.mkdir(exist_ok=True)
        with open(folder / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\r\n")
            w.writerow(header)
            w.writerows(rows)
        return folder

    def test_old_statistics_files_are_imported_once(self):
        header = ["time_utc", "usage_percent", "used_bytes"]
        old = [[iso_utc(T0 - 100 + i), "12.5", "1024"] for i in range(3)]
        self.write_old("memory.csv.1", header, old[:1])
        folder = self.write_old("memory.csv", header, old[1:] + [["bad", "1", "2"]])
        self.write_old("gpu-0000-02-00.0.csv", ["time_utc", "vram_used_bytes"],
                       [[iso_utc(T0 - 50), ""]])
        with self.assertLogs("proccoli.core.history_store", "INFO") as logs:
            self.make(import_dir=folder)
            self.tick()
            self.store.commit()
        self.assertFalse(folder.exists())
        self.assertTrue(any("imported 4 rows from 3" in m for m in logs.output))
        db = self.store.db
        self.assertEqual(db.rows("d_memory", ["usage_percent", "used_bytes"],
                                 0, ms(T0 - 50)), [(ms(T0 - 100 + i), 1250, 1024)
                                                   for i in range(3)])
        self.assertEqual(db.rows("d_gpu_0000_02_00_0", ["vram_used_bytes"], 0, 2**62),
                         [(ms(T0 - 50), None)])
        names = {d["table"]: d["name"] for d in db.devices()}
        self.assertEqual(names["d_memory"], "Memory")               # the live device's
        self.assertEqual(names["d_gpu_0000_02_00_0"], "gpu-0000-02-00.0")

    def test_a_file_without_the_header_is_skipped(self):
        db = HistoryDb(self.path)
        self.addCleanup(db.close)
        folder = self.write_old("x.csv", ["when", "a"], [["1", "2"]])
        self.assertEqual(import_csv(db, folder / "x.csv"), 0)


def ms(t):
    return int(round(t * 1000))


class ExportTest(StoreCase):
    def test_the_session_one_file_per_device_and_a_manifest(self):
        self.make(MemoryDevice())
        self.tick(12)
        self.store.commit()
        out = self.dir / "out"
        out.mkdir()
        progress = []
        result = export_session(self.path, out, self.store.session, ms(self.clock[0]), "9.9",
                                now_s=T0, progress=lambda d, t: progress.append((d, t)))
        self.assertEqual(result.folder, out / "proccoli-statistics-20261123T214125Z")
        self.assertEqual(result.files, ["memory.csv", "devices.csv", "export.json"])
        self.assertEqual(progress, [(1, 1)])
        rows = read_rows(result.folder / "memory.csv")
        self.assertEqual(rows[0], ["time_utc", "usage_percent", "swap_percent", "used_bytes",
                                   "total_bytes", "swap_used_bytes", "swap_total_bytes"])
        self.assertEqual(rows[1], ["2026-11-23T21:41:25.154Z", "25", "", str(4 * 2**30),
                                   str(16 * 2**30), "0", "0"])
        self.assertEqual(len(rows), 13)
        manifest = json.loads((result.folder / "export.json").read_text())
        self.assertEqual(manifest["version"], "9.9")
        self.assertEqual(manifest["session"]["start_utc"], "2026-11-23T21:41:25.154Z")
        self.assertEqual(manifest["files"][0]["kind"], "memory")
        self.assertEqual(manifest["files"][0]["columns"][1],
                         {"column": "usage_percent", "reading": "usage", "unit": "%"})
        # Never over an earlier export.
        again = export_session(self.path, out, self.store.session, ms(self.clock[0]),
                               now_s=T0)
        self.assertEqual(again.folder.name, "proccoli-statistics-20261123T214125Z (2)")

    def test_a_session_longer_than_the_detail_adds_minutes(self):
        self.make(Device(), **{"history-detail-hours": 1})
        self.tick(3 * 60, step=60.0)                            # three hours
        self.store.housekeeping()
        out = self.dir / "out"
        out.mkdir()
        result = export_session(self.path, out, self.store.session, ms(self.clock[0]))
        self.assertEqual(result.files, ["cpu-minutes.csv", "cpu.csv", "devices.csv", "export.json"])
        minutes = read_rows(result.folder / "cpu-minutes.csv")
        self.assertEqual(minutes[0], ["time_utc", "usage_percent_avg", "usage_percent_min",
                                      "usage_percent_max"])
        self.assertEqual(minutes[1][1:], ["25", "25", "25"])
        detail = read_rows(result.folder / "cpu.csv")
        self.assertGreater(parse_iso_utc(detail[1][0]), parse_iso_utc(minutes[-1][0]))
        self.assertEqual(len(minutes) - 1 + len(detail) - 1, 3 * 60)   # nothing twice
        manifest = json.loads((result.folder / "export.json").read_text())
        self.assertEqual([f["level"] for f in manifest["files"]], ["minutes", "detail"])


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


class OpenRunTest(unittest.TestCase):
    """The newest run, still being recorded, runs until now."""

    def test_a_run_committed_seconds_ago_runs_until_now(self):
        self.assertEqual(open_run([(0, 100), (200, 5_000)], 12_000, 1000),
                         [(0, 100), (200, 12_000)])

    def test_a_run_that_ended_long_ago_stays_ended(self):
        sessions = [(0, 100), (200, 5_000)]
        self.assertEqual(open_run(sessions, 60_000, 1000), sessions)

    def test_a_session_in_the_future_is_left_alone(self):
        sessions = [(200, 50_000)]                  # the clock was set back
        self.assertEqual(open_run(sessions, 10_000, 1000), sessions)

    def test_no_sessions(self):
        self.assertEqual(open_run([], 10_000, 1000), [])


class RangeChangeWhileRecordingTest(StoreCase):
    """A window that reads the history another process records: changing
    the time range refills its graphs, and the seconds the recorder holds
    in memory (up to its commit interval) aren't time it wasn't running."""

    def make_recorder(self):
        """The recorder: it writes the history but draws no graphs, so a
        range change doesn't make it write."""
        self.make(Device())
        self.store.shutdown()
        self.store = HistoryStore(self.devices, self.settings, self.path, "9.9",
                                  lambda: self.clock[0], graphs=False)
        self.addCleanup(self.store.shutdown)

    def make_window(self):
        devices = DeviceManager(SysRoot("/nonexistent"), self.settings)
        devices.register(Device(values=lambda now, n: 99.0))     # its live points: 99
        window = HistoryStore(devices, self.settings, self.path, "9.9",
                              lambda: self.clock[0], read_only=True)
        self.addCleanup(window.shutdown)
        devices.start()
        return devices, window

    def tick_both(self, window_devices, n):
        for _ in range(n):
            now = MONO + self.clock[0] - T0
            self.devices.refresh(now)
            window_devices.refresh(now)
            self.clock[0] += 1.0

    def test_the_last_seconds_are_not_shaded_after_a_range_change(self):
        self.make_recorder()
        window_devices, _window = self.make_window()
        self.tick_both(window_devices, 26)                      # last commit at 20 s
        self.assertGreater(len(self.store._buffer), 0)          # 5 s not written yet
        self.settings.set("graph-time-range", "30-seconds")
        history = next(m for m in window_devices.monitors() if m.info.id == "cpu").history
        self.assertGreater(len(history), 0)
        self.assertNotIn(True, list(history.offline)[-10:])

    def test_the_refill_waits_for_the_recorder_to_write_out(self):
        self.make_recorder()
        window_devices, window = self.make_window()
        asked = []
        window_devices.flush = lambda then: asked.append(then)  # answers later
        self.tick_both(window_devices, 26)
        history = next(m for m in window_devices.monitors() if m.info.id == "cpu").history
        self.settings.set("graph-time-range", "30-seconds")
        self.assertEqual(len(asked), 1)
        self.assertEqual(set(history.series("usage").values), {99.0})   # not refilled yet
        self.store.commit()                                     # the recorder flushes
        asked[0]()
        values = list(history.series("usage").values)
        self.assertEqual(set(values[-5:]), {25.0})              # the flushed seconds, from the file


class OfflineSlotsTest(unittest.TestCase):
    def test_slots_outside_every_session(self):
        sessions = [(100, 200), (500, 600)]
        starts = [0, 100, 190, 250, 400, 450, 600, 700]
        self.assertEqual(offline_slots(starts, 50, sessions),
                         [True, False, False, True, True, True, False, True])

    def test_no_sessions_is_all_offline(self):
        self.assertEqual(offline_slots([0, 10], 10, []), [True, True])


class ConstantsTest(unittest.TestCase):
    def test_timers(self):
        self.assertEqual(history_store.COMMIT_EVERY_S, 10)
        self.assertEqual(history_store.HOUSEKEEPING_EVERY_S, 600)


if __name__ == "__main__":
    unittest.main()


class DeviceInfoDbTest(TempFolder):
    """The history keeps what each device is, when it changes."""

    def db(self, path=None, readonly=False):
        db = HistoryDb(path or self.path, readonly=readonly)
        self.addCleanup(db.close)
        return db

    def test_written_only_when_it_changes(self):
        db = self.db()
        tbl = db.ensure_device("gpu", "GPU", "gpu")
        self.assertTrue(db.record_info(tbl, 1000, "Radeon", {"Driver Used": "amdgpu"}))
        self.assertFalse(db.record_info(tbl, 2000, "Radeon", {"Driver Used": "amdgpu"}))
        self.assertTrue(db.record_info(tbl, 3000, "Radeon", {"Driver Used": "amdgpu 2"}))
        rows = db.device_info(tbl, 0, 10_000)
        self.assertEqual([r["time"] for r in rows], [1000, 3000])

    def test_a_new_connection_remembers_the_last_row(self):
        db = self.db()
        tbl = db.ensure_device("cpu", "Processor", "cpu")
        db.record_info(tbl, 1000, "", {"Sockets": "1"})
        self.assertFalse(self.db().record_info(tbl, 5000, "", {"Sockets": "1"}))

    def test_a_range_gets_the_row_in_effect_then_the_changes(self):
        db = self.db()
        tbl = db.ensure_device("d", "D", "drive")
        for t, model in ((1000, "a"), (5000, "b"), (9000, "c"), (20_000, "d")):
            db.record_info(tbl, t, "", {"Model": model})
        rows = db.device_info(tbl, 6000, 10_000)
        self.assertEqual([(r["time"], r["properties"]["Model"]) for r in rows],
                         [(5000, "b"), (9000, "c")])
        self.assertEqual(db.device_info(tbl, 0, 500), [])

    def test_a_version_1_database_gains_the_table(self):
        import sqlite3
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO meta VALUES ('schema', '1')")
        conn.commit()
        conn.close()
        self.assertEqual(self.db(readonly=True).device_info("d_x", 0, 1), [])   # no table yet
        db = self.db()
        self.assertEqual(db.meta("schema"), "2")
        tbl = db.ensure_device("x", "X", "drive")
        self.assertTrue(db.record_info(tbl, 1, "", {}))


class DescribedDevice(Discoverer):
    kind = DeviceKind.NETWORK

    def __init__(self):
        self.info = DeviceInfo("net", DeviceKind.NETWORK, "Wi-Fi", "wlp2s0",
                               properties={"Driver Used": "iwlwifi",
                                           "Hardware Address": "aa:bb:cc:dd:ee:ff"})

    def discover(self, sysroot, settings):
        return [self.info]

    def create_monitor(self, info, sysroot, settings):
        class M(Monitor):
            def sample(self, now):
                return Snapshot(now, usage=5.0)
        return M(info, 61)


class DeviceInfoExportTest(StoreCase):
    def export(self, **kwargs):
        out = self.dir / "out"
        out.mkdir(exist_ok=True)
        result = export_session(self.path, out, self.store.session, ms(self.clock[0]), "9.9",
                                now_s=T0, **kwargs)
        return result, json.loads((result.folder / "export.json").read_text())

    def test_the_store_records_details_once_per_change(self):
        self.make(DescribedDevice())
        self.tick(12)
        self.store.commit()
        self.tick(12)
        self.store.commit()
        self.assertEqual(len(self.store.db.device_info("d_net", 0, 2**62)), 1)
        monitor = self.monitor("net")
        monitor.info = DeviceInfo("net", DeviceKind.NETWORK, "Wi-Fi", "wlp3s0",
                                  properties={"Driver Used": "iwlwifi"})
        self.tick(12)
        self.store.commit()
        self.assertEqual(len(self.store.db.device_info("d_net", 0, 2**62)), 2)

    def test_export_has_machine_device_details_and_changes(self):
        self.make(DescribedDevice())
        self.tick(12)
        self.store.commit()
        self.monitor("net").info = DeviceInfo("net", DeviceKind.NETWORK, "Wi-Fi", "wlp3s0",
                                              properties={"Driver Used": "iwlwifi 2"})
        self.tick(12)
        self.store.commit()
        result, manifest = self.export(machine={"kernel": "6.8.0", "computer": "LENOVO 82LM"})
        self.assertIn("devices.csv", result.files)
        self.assertEqual(manifest["machine"], {"proccoli_version": "9.9", "kernel": "6.8.0",
                                               "computer": "LENOVO 82LM"})
        device = manifest["devices"][0]
        self.assertEqual(device["device"], "net")
        self.assertEqual(device["files"], ["net.csv"])
        self.assertEqual(device["description"], "wlp3s0")              # at the end
        self.assertEqual(device["properties"], {"Driver Used": "iwlwifi 2"})
        self.assertEqual(device["as_of"], "history")
        self.assertEqual(device["since_utc"], "2026-11-23T21:41:25.154Z")
        change = device["changes"][0]
        self.assertEqual(change["description"], "wlp3s0")
        self.assertEqual(change["properties"], {"Driver Used": "iwlwifi 2"})
        self.assertNotIn("removed", change)            # the address was never shown

    def test_hardware_addresses_only_when_asked(self):
        self.make(DescribedDevice())
        self.tick(12)
        self.store.commit()
        result, manifest = self.export()
        self.assertNotIn("Hardware Address", manifest["devices"][0]["properties"])
        self.assertNotIn("aa:bb", (result.folder / "devices.csv").read_text())
        result, manifest = self.export(include_addresses=True)
        self.assertEqual(manifest["devices"][0]["properties"]["Hardware Address"],
                         "aa:bb:cc:dd:ee:ff")

    def test_devices_csv_one_row_per_property(self):
        self.make(DescribedDevice())
        self.tick(12)
        self.store.commit()
        result, _ = self.export(include_addresses=True)
        rows = read_rows(result.folder / "devices.csv")
        self.assertEqual(rows[0], ["device_id", "name", "kind", "description", "property",
                                   "value", "files"])
        self.assertEqual(rows[1:], [
            ["net", "Wi-Fi", "network", "wlp2s0", "Driver Used", "iwlwifi", "net.csv"],
            ["net", "Wi-Fi", "network", "wlp2s0", "Hardware Address", "aa:bb:cc:dd:ee:ff",
             "net.csv"]])

    def test_an_older_history_gets_the_details_as_they_are_now(self):
        self.make(DescribedDevice())
        self.tick(12)
        self.store.commit()
        self.store.db.conn.execute("DELETE FROM device_info")    # as an older history
        _, manifest = self.export(current={"net": {"description": "wlp2s0",
                                                   "properties": {"Driver Used": "x"}}})
        device = manifest["devices"][0]
        self.assertEqual(device["as_of"], "export")
        self.assertEqual(device["properties"], {"Driver Used": "x"})
        self.assertNotIn("changes", device)


class MachineInfoTest(unittest.TestCase):
    def test_os_kernel_architecture_and_model(self):
        from helpers import FakeRoot, FakeSystem
        from proccoli.core.machine_info import machine_info
        root = FakeRoot(self, {
            "/etc/os-release": 'NAME="Ubuntu"\nPRETTY_NAME="Ubuntu 24.04.1 LTS"\n',
            "/proc/sys/kernel/osrelease": "6.8.0-48-generic\n",
            "/sys/class/dmi/id/sys_vendor": "LENOVO\n",
            "/sys/class/dmi/id/product_name": "82LM\n",
            "/sys/class/dmi/id/product_version": "IdeaPad 5 14ARE05\n"})
        system = FakeSystem()
        self.assertEqual(machine_info(root.sysroot, system), {
            "operating_system": "Ubuntu 24.04.1 LTS", "kernel": "6.8.0-48-generic",
            "architecture": system.machine(), "computer": "LENOVO 82LM IdeaPad 5 14ARE05"})

    def test_placeholders_and_missing_files_are_left_out(self):
        from helpers import FakeRoot
        from proccoli.core.machine_info import machine_info
        root = FakeRoot(self, {"/usr/lib/os-release": "NAME=Debian\n",
                               "/sys/class/dmi/id/sys_vendor": "To Be Filled By O.E.M.\n"})
        self.assertEqual(machine_info(root.sysroot, None), {"operating_system": "Debian"})


class ExportPrivacyTest(unittest.TestCase):
    """Every property Proccoli shows has been looked at for whether it
    identifies the machine: a new one fails here until it's added to
    REVIEWED (fine to share) or to history_export.IDENTIFYING."""

    REVIEWED = {"Architecture", "Battery Health", "Capacity", "Charge Cycles",
                "Design Capacity", "Detailed Statistics", "Device", "Driver Used",
                "Form Factor", "Interface", "Link", "Logical Cores", "Manufacturer",
                "Max Frequency", "Model", "Model Name", "PCI Slot", "Physical Cores",
                "Removable", "Slots Used", "Sockets", "Source", "Speed", "Technology", "Type",
                "Type Detail", "Virtualization", "Writable"}

    def test_every_property_key_is_reviewed(self):
        from helpers import FIXTURES, LAPTOP, RENOIR, make_context
        from proccoli.core.history_export import IDENTIFYING
        keys = set()
        for root in (LAPTOP, RENOIR, os.path.join(FIXTURES, "nvidia")):
            for demo in (False, True):
                ctx = make_context(self, demo=demo, sysroot=SysRoot(root))
                ctx.start()
                for monitor in ctx.devices.monitors():
                    keys |= set(monitor.described_properties())
                ctx.stop()
        self.assertIn("Hardware Address", keys)          # the check sees real devices
        self.assertEqual(keys - self.REVIEWED - IDENTIFYING, set())
        self.assertEqual(self.REVIEWED & IDENTIFYING, set())


class OneWriterTest(StoreCase):
    """whoever holds the lock writes; the other reads, fills its
    graphs, and takes over when the writer stops."""

    def locked_store(self, system, program="proccoli", **settings):
        from proccoli.core.history_lock import HistoryLock, lock_path
        lock = HistoryLock(system, lock_path(self.path))
        store = HistoryStore(self.devices, self.settings, self.path, "9.9",
                             lambda: self.clock[0], lock=lock, program=program)
        self.addCleanup(store.shutdown)
        return store

    def setUp(self):
        super().setUp()
        from helpers import FakeSystem
        self.make(Device())                       # the plain store: no lock, stays out
        self.store.shutdown()
        delete_files(self.path)
        locks = {}
        self.a, self.b = FakeSystem(), FakeSystem()
        self.a.locks = self.b.locks = locks         # one machine

    def rows(self):
        db = HistoryDb(self.path, readonly=True)
        try:
            return db.count("d_cpu")
        finally:
            db.close()

    def test_only_the_lock_holder_writes(self):
        writer = self.locked_store(self.a, "proccoli")
        self.tick()
        reader = self.locked_store(self.b)
        self.tick(11)
        writer.commit()
        reader.commit()
        self.assertTrue(writer.writer)
        self.assertFalse(reader.writer)
        self.assertEqual(self.rows(), 12)                 # once each, not twice
        self.assertEqual(reader.writer_info()["program"], "proccoli")
        self.assertIsNone(reader.session)

    def test_the_reader_fills_graphs_from_the_writers_rows(self):
        writer = self.locked_store(self.a)
        self.tick(20)
        writer.commit()
        reader = self.locked_store(self.b)
        history = History(61)
        history.define("usage", "%")
        reader._offsets["cpu"] = 0.0
        reader._clock["cpu"] = self.clock[0]
        self.assertGreater(reader._fill(history, "d_cpu", 0.0, self.clock[0]), 15)

    def test_the_reader_takes_over_when_the_writer_stops(self):
        writer = self.locked_store(self.a, "proccoli")
        self.tick(12)
        reader = self.locked_store(self.b)
        self.tick(2)
        writer.shutdown()                                 # quits: commits, frees the lock
        before = self.rows()
        self.tick(12)                                     # the reader's next commit
        self.assertTrue(reader.writer)
        self.tick(12)
        self.assertGreater(self.rows(), before)
        self.assertEqual(reader.writer_info()["program"], "proccoli")
        self.assertEqual(len(reader.db.sessions()), 2)

    def test_the_window_never_writes(self):
        # read_only, with nobody holding the lock: still no writing.
        writer = self.locked_store(self.a, "proccoli")
        self.tick(12)
        writer.shutdown()                                 # the collector stops
        before = self.rows()
        window = HistoryStore(self.devices, self.settings, self.path, "9.9",
                              lambda: self.clock[0], read_only=True)
        self.addCleanup(window.shutdown)
        self.tick(30)
        window.commit()
        self.assertFalse(window.writer)
        self.assertEqual(self.rows(), before)
        self.assertIsNone(window.session)
        self.assertIsNotNone(window.session_start())       # the collector's last run, for exports

    def test_a_reader_exports_the_run_being_recorded(self):
        writer = self.locked_store(self.a, "proccoli")
        self.tick(12)
        reader = self.locked_store(self.b)
        self.assertIsNone(reader.session)
        self.assertEqual(reader.session_start(), writer.session)

    def test_a_writer_starts_again_after_delete_history_from_a_reader(self):
        writer = self.locked_store(self.a)
        self.tick(12)
        reader = self.locked_store(self.b)
        reader.delete()
        self.assertFalse(self.path.exists())
        self.tick(12)                                     # the writer's next commit
        self.assertTrue(self.path.exists())
        self.assertGreater(self.rows(), 0)
        self.assertTrue(writer.writer)

    def test_a_newer_schema_is_never_written(self):
        db = HistoryDb(self.path)
        db.set_meta("schema", "99")
        db.close()
        with self.assertLogs("proccoli.core.history_store", "WARNING"):
            store = self.locked_store(self.a)
            self.tick(12)
        self.assertFalse(store.writer)
        self.assertNotIn(str(lock_path_of(self.path)), self.a.locks)   # let go for others


def lock_path_of(path):
    from proccoli.core.history_lock import lock_path
    return lock_path(path)


class RealLockTest(TempFolder):
    """The real flock: one holder at a time, freed on release."""

    def test_flock(self):
        from proccoli.core.history_lock import HistoryLock
        from proccoli.core.system import System
        path = self.dir / "state" / "history.lock"
        one, two = HistoryLock(System(), path), HistoryLock(System(), path)
        self.assertTrue(one.acquire())
        self.assertFalse(two.acquire())
        one.release()
        self.assertTrue(two.acquire())
        two.release()
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
