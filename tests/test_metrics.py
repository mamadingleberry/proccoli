"""proccoli, the background collector:
what it builds, that it never touches Gtk, running on a fake loop, the
command line. No display needed."""

import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from helpers import FIXTURES, LAPTOP, RENOIR, FakeSystem  # noqa: E402
from proccoli import metrics  # noqa: E402
from proccoli.context import MetricsContext, build_metrics_context  # noqa: E402
from proccoli.core import pciids  # noqa: E402
from proccoli.core.history_db import HistoryDb  # noqa: E402
from proccoli.core.profile import Profile, profile_of  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.sysroot import SysRoot  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def context(test, root=LAPTOP, system=None, **overrides):
    settings = metrics.metrics_settings(Settings.for_tests(overrides))
    ctx = build_metrics_context(settings, system=system or FakeSystem(), sysroot=SysRoot(root),
                                pci=pciids.load(os.path.join(FIXTURES, "pci", "pci.ids")),
                                connection_name=None)
    test.addCleanup(ctx.stop)
    return ctx


class ProfileTest(unittest.TestCase):
    def test_metrics_profile(self):
        p = Profile.metrics()
        self.assertEqual(p.name, "metrics")
        self.assertFalse(p.gpu_elevate)
        self.assertFalse(p.app_icons)
        self.assertEqual(dict(p.pins), {})             # the user's real settings

    def test_the_settings_carry_it_without_pins(self):
        settings = metrics.metrics_settings(Settings.for_tests({"graph-time-range": "1-day"}))
        self.assertEqual(profile_of(settings).name, "metrics")
        self.assertEqual(settings.get("graph-time-range"), "1-day")   # not pinned


class ContextTest(unittest.TestCase):
    def test_devices_only(self):
        ctx = context(self)
        self.assertIsInstance(ctx, MetricsContext)
        self.assertFalse(hasattr(ctx, "processes"))
        ctx.devices.start()
        kinds = {m.info.kind.value for m in ctx.devices.monitors()}
        self.assertTrue({"cpu", "memory", "gpu"} <= kinds)

    def test_gpu_details_never_elevate(self):
        # The Intel GPU's intel_gpu_top needs administrator rights here.
        ctx = context(self, system=FakeSystem(programs={"intel_gpu_top": "/usr/bin/x"}),
                      **{"gpu-elevate": True})
        ctx.devices.start()
        intel = ctx.devices.monitor("gpu-0000:00:02.0")
        self.assertTrue(intel.needs_elevation)
        self.assertEqual(intel.detail_state.name, "OFF")
        self.assertEqual(intel.detail_message, "Detailed statistics need administrator rights")
        self.assertEqual(ctx.system.runs, [])                  # no pkexec, ever

    def test_amd_details_start_without_a_password(self):
        ctx = context(self, root=RENOIR)
        ctx.devices.start()
        gpus = [m for m in ctx.devices.monitors() if m.info.kind.value == "gpu"]
        self.assertTrue(gpus)
        self.assertTrue(any(g.detail_backend is not None for g in gpus))


class NoGtkTest(unittest.TestCase):
    def test_nothing_reachable_imports_gtk(self):
        """In a fresh interpreter: import and build the collector, then
        check no Gtk, Gdk, Adw or proccoli.ui module was loaded."""
        code = (
            "import sys; sys.path.insert(0, 'src'); sys.path.insert(0, 'tests')\n"
            "from proccoli import metrics\n"
            "from proccoli.context import build_metrics_context\n"
            "from proccoli.core.settings import Settings\n"
            "from proccoli.core.sysroot import SysRoot\n"
            "from helpers import FakeSystem, LAPTOP\n"
            "ctx = build_metrics_context(metrics.metrics_settings(Settings.for_tests()),\n"
            "    system=FakeSystem(), sysroot=SysRoot(LAPTOP), connection_name=None)\n"
            "ctx.devices.start(); ctx.devices.refresh(1.0)\n"
            "bad = sorted(m for m in sys.modules if m.startswith(('proccoli.ui', 'proccoli.app'))\n"
            "    or m in ('gi.repository.Gtk', 'gi.repository.Gdk', 'gi.repository.Adw'))\n"
            "print(','.join(bad))\n")
        env = dict(os.environ, DISPLAY="", WAYLAND_DISPLAY="")
        # helpers.py installs the UI's CSS under the headless test runner;
        # this checks the collector alone.
        env.pop("PROCCOLI_UI_TESTS", None)
        out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "")


class FakeLoop:
    def __init__(self, ticks):
        self.ticks = ticks
        self.quit_called = False

    def run(self):
        self.ticks()

    def quit(self):
        self.quit_called = True


class RunTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "state" / "history.sqlite3"

    def test_records_until_a_signal_then_writes_everything_out(self):
        ctx = context(self)
        clock = [1_795_600_000.0]
        handlers = {}

        def ticks():
            for i in range(15):
                ctx.devices.refresh(100.0 + i)
                clock[0] += 1
            handlers[signal.SIGTERM]()                 # systemctl --user stop

        loop = FakeLoop(ticks)
        collector_store = {}
        original = metrics.Collector.__init__

        def init(self_, context_, path, **kw):
            original(self_, context_, path, wall_clock=lambda: clock[0], idle=None,
                     bus=kw.get("bus"))
            collector_store["store"] = self_.store
        metrics.Collector.__init__ = init
        self.addCleanup(setattr, metrics.Collector, "__init__", original)
        code = metrics.run(ctx, self.path, loop=loop,
                           signals=lambda sig, cb: handlers.__setitem__(sig, cb), bus=False)
        self.assertEqual(code, 0)
        self.assertTrue(loop.quit_called)
        self.assertEqual(set(handlers), {signal.SIGTERM, signal.SIGINT})
        db = HistoryDb(self.path, readonly=True)
        self.addCleanup(db.close)
        # Every reading, the buffered ones too (the processor's first has no
        # rate yet, so memory, read every time, counts them).
        self.assertEqual(db.count("d_memory"), 15)
        self.assertEqual(json.loads(db.meta("writer"))["program"], "proccoli")
        start, end = db.sessions()[0]
        self.assertGreater(end, start)
        self.assertFalse(collector_store["store"].lock.held)   # let go on the way out


class TickerDrivesItTest(unittest.TestCase):
    """The ticker, not the test, takes the readings: starting the context
    starts ticking (the window starts its own when it shows)."""

    def test_start_ticks(self):
        from proccoli.core.ticker import Ticker
        timers = []
        ticker = Ticker(timeout_add=lambda ms, cb: timers.append(cb) or len(timers),
                        source_remove=lambda _s: None, clock=iter(range(100, 200)).__next__)
        settings = metrics.metrics_settings(Settings.for_tests())
        ctx = build_metrics_context(settings, system=FakeSystem(), sysroot=SysRoot(LAPTOP),
                                    pci=pciids.load(os.path.join(FIXTURES, "pci", "pci.ids")),
                                    connection_name=None, ticker=ticker)
        self.addCleanup(ctx.stop)
        ctx.start()
        self.assertTrue(ticker.running)
        timers[-1]()                                   # one more interval
        memory = ctx.devices.monitor("memory")
        self.assertIsNotNone(memory.latest)


class CommandLineTest(unittest.TestCase):
    def test_once_reads_every_device(self):
        ctx = context(self)
        out = metrics.read_once(ctx, sleep=lambda s: None, clock=iter([1.0, 2.0]).__next__)
        self.assertIn("cpu", out)
        self.assertEqual(out["memory"]["readings"]["usage"][1], "%")

    def test_status(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "history.sqlite3"
        system = FakeSystem()
        code, text = metrics.status(path, system)
        self.assertEqual(code, 1)
        self.assertIn("Nothing recorded yet", text)
        db = HistoryDb(path)
        db.start_session(1_795_600_000_000, "9.9")
        db.set_meta("writer", json.dumps({"program": "proccoli", "pid": 42,
                                          "version": "9.9", "since": 1_795_600_000_000}))
        db.close()
        system.locks[str(path.with_name("history.lock"))] = object()   # someone holds it
        code, text = metrics.status(path, system, now_s=1_795_600_100)
        self.assertEqual(code, 0)
        self.assertIn("Recording: by proccoli 9.9 (process 42)", text)
        self.assertRegex(text, r"Size on disk: \d+(\.\d)? KiB")
        self.assertIn("Runs in the last day: 1", text)

    def test_status_suggests_recording_from_boot(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "history.sqlite3"
        db = HistoryDb(path)
        db.start_session(1_795_600_000_000, "9.9")
        db.close()
        system = FakeSystem(programs={"loginctl": "/usr/bin/loginctl"})
        system.run_results = [(0, "no\n", "")]
        _code, text = metrics.status(path, system, now_s=1_795_600_100)
        self.assertIn("proccoli --start-at-boot", text)
        system.run_results = [(0, "yes\n", "")]
        _code, text = metrics.status(path, system, now_s=1_795_600_100)
        self.assertNotIn("--start-at-boot", text)

    def test_start_at_boot_options(self):
        self.assertTrue(metrics.parse_args(["--start-at-boot"]).start_at_boot)
        self.assertTrue(metrics.parse_args(["--no-start-at-boot"]).no_start_at_boot)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            metrics.parse_args(["--start-at-boot", "--no-start-at-boot"])

    def test_version_and_help(self):
        with redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit):
            metrics.parse_args(["--version"])
        self.assertIn("proccoli", out.getvalue())


if __name__ == "__main__":
    unittest.main()
