"""core.applog: the size-capped diagnostics log."""

import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from helpers import FakeRoot  # noqa: E402

from proccoli.core.applog import (BACKUPS, FileLog, PerformanceLog, UtcFormatter,  # noqa: E402
                                 disk_budget, log_path, read_own_stats)
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.ticker import Ticker  # noqa: E402

STAT = "4242 (proccoli (x)) S 1 2 3 4 5 6 7 8 9 10 {utime} {stime} 0 0 20 0 7 0 100\n"
STATUS = "Name:\tproccoli\nVmRSS:\t  51200 kB\nThreads:\t7\n"


class PathTest(unittest.TestCase):
    def test_xdg_state_home(self):
        self.assertEqual(log_path({"XDG_STATE_HOME": "/s"}), Path("/s/proccoli/proccoli-gui.log"))
        self.assertEqual(log_path({}, home=Path("/h")),
                         Path("/h/.local/state/proccoli/proccoli-gui.log"))


class UtcTest(unittest.TestCase):
    def record(self, created):
        rec = logging.LogRecord("proccoli", logging.INFO, __file__, 1, "msg %s", ("x",), None)
        rec.created, rec.msecs = created, (created % 1) * 1000
        return rec

    def test_iso_utc_with_milliseconds(self):
        # 2026-11-23 21:41:25.154 UTC, whatever this machine's time zone.
        line = UtcFormatter().format(self.record(1795470085.154))
        self.assertTrue(line.startswith("2026-11-23T21:41:25.154Z INFO proccoli: msg x"), line)

    def test_independent_of_the_local_zone(self):
        import os
        import time as _time
        old = os.environ.get("TZ")
        self.addCleanup(lambda: (os.environ.pop("TZ", None) if old is None
                                 else os.environ.__setitem__("TZ", old), _time.tzset()))
        stamps = []
        for zone in ("UTC", "America/New_York", "Asia/Kolkata"):
            os.environ["TZ"] = zone
            _time.tzset()
            stamps.append(UtcFormatter().format(self.record(0.5)))
        self.assertEqual(len(set(stamps)), 1)
        self.assertTrue(stamps[0].startswith("1970-01-01T00:00:00.500Z"))


class DefaultLevelTest(unittest.TestCase):
    def test_everything_by_default(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        settings = Settings.for_tests()
        self.assertEqual(settings.get("log-level"), "debug")
        logger = logging.getLogger("proccoli.test-default")
        logger.propagate = False
        log = FileLog(settings, Path(tmp.name) / "p.log", logger)
        self.addCleanup(log.shutdown)
        self.assertEqual(log.level, logging.DEBUG)
        logger.debug("the smallest detail")
        text = (Path(tmp.name) / "p.log").read_text()
        self.assertIn("the smallest detail", text)
        self.assertRegex(text, r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z DEBUG ")


class FileLogTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "deep" / "proccoli.log"
        self.settings = Settings.for_tests({"log-level": "info", "log-max-size": 64})
        self.logger = logging.getLogger("proccoli.test-" + self.id())
        self.logger.propagate = False
        self.log = FileLog(self.settings, self.path, self.logger)
        self.addCleanup(self.log.shutdown)

    def test_writes_and_creates_the_folder(self):
        self.logger.info("hello %s", "world")
        self.logger.debug("not at info level")
        text = self.path.read_text()
        self.assertIn("INFO", text)
        self.assertIn("hello world", text)
        self.assertNotIn("not at info level", text)

    def test_never_more_than_the_budget(self):
        for i in range(4000):                               # ~400 KiB of messages
            self.logger.info("line %05d %s", i, "x" * 80)
        files = list(self.path.parent.iterdir())
        self.assertEqual(len(files), BACKUPS + 1)           # current + one older
        total = sum(f.stat().st_size for f in files)
        self.assertLessEqual(total, disk_budget(64))
        self.assertIn("line 03999", self.path.read_text())   # newest kept

    def test_files_are_private(self):
        # they can name processes and devices.
        for i in range(4000):                               # forces a rollover
            self.logger.info("line %05d %s", i, "x" * 80)
        for f in self.path.parent.iterdir():
            self.assertEqual(f.stat().st_mode & 0o777, 0o600, f)
        self.assertEqual(self.path.parent.stat().st_mode & 0o777, 0o700)

    def test_level_and_size_follow_settings(self):
        self.settings.set("log-level", "error")
        self.logger.warning("quiet now")
        self.logger.error("loud")
        text = self.path.read_text()
        self.assertNotIn("quiet now", text)
        self.assertIn("loud", text)
        self.settings.set("log-level", "off")
        self.assertIsNone(self.log.handler)
        self.logger.error("nowhere")
        self.assertNotIn("nowhere", self.path.read_text())
        self.settings.set("log-level", "debug")
        self.settings.set("log-max-size", 128)
        self.assertEqual(self.log.handler.maxBytes, 128 * 1024)

    def test_unwritable_folder_doesnt_crash(self):
        blocker = self.path.parent.parent / "file"
        blocker.write_text("")
        FileLog(self.settings, blocker / "sub" / "proccoli.log", self.logger).shutdown()


class PerformanceLogTest(unittest.TestCase):
    def make(self, interval=1):
        self.root = FakeRoot(self, {"/proc/self/stat": STAT.format(utime=100, stime=50),
                                    "/proc/self/status": STATUS})
        self.now = [0.0]
        ticker = Ticker(1000, timeout_add=lambda *_: 1, source_remove=lambda *_: None,
                        clock=lambda: self.now[0])
        self.settings = Settings.for_tests({"log-performance-interval": interval})
        self.records = []
        logger = logging.getLogger("proccoli.perf-test-" + self.id())
        logger.propagate = False
        logger.setLevel(logging.INFO)
        handler = logging.Handler()
        handler.emit = lambda r: self.records.append(r.getMessage())
        logger.addHandler(handler)
        self.perf = PerformanceLog(self.root.sysroot, 100, ticker, self.settings,
                                   clock=lambda: self.now[0], logger=logger)
        self.addCleanup(self.perf.shutdown)
        return ticker

    def test_reads_own_stats(self):
        self.make()
        s = read_own_stats(self.root.sysroot)
        self.assertEqual((s.cpu_ticks, s.rss_bytes, s.threads), (150, 50 * 2 ** 20, 7))

    def test_a_line_every_interval(self):
        ticker = self.make(interval=1)
        ticker.tick_now()                                    # baseline at t=0
        self.root.write("/proc/self/stat", STAT.format(utime=130, stime=60))
        for t in (30.0, 61.0):
            self.now[0] = t
            ticker.tick_now()
        self.assertEqual(len(self.records), 1)
        line = self.records[0]
        self.assertIn("cpu 0.7 %", line)                     # 40 ticks / 100 Hz / 61 s
        self.assertIn("memory 50.0 MiB", line)
        self.assertIn("threads 7", line)
        self.assertIn("refreshes 3", line)

    def test_times_the_slowest_refresh(self):
        ticker = self.make()
        ticker.connect("tick", lambda *_: self.now.__setitem__(0, self.now[0] + 0.25))
        ticker.tick_now()
        self.assertAlmostEqual(self.perf.slowest_s, 0.25)

    def test_off(self):
        ticker = self.make(interval=0)
        for t in (0.0, 1000.0, 5000.0):
            self.now[0] = t
            ticker.tick_now()
        self.assertEqual(self.records, [])


if __name__ == "__main__":
    unittest.main()
