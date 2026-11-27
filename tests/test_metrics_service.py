"""the collector serves every reading over D-Bus.
The snapshot codec, and the service on a private bus (``Gio.TestDBus``),
with a client the way the window will be one. No display needed."""

import json
import os
import shutil
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from gi.repository import Gio, GLib  # noqa: E402

from helpers import FIXTURES, LAPTOP, RENOIR, FakeSystem  # noqa: E402
from proccoli import metrics  # noqa: E402
from proccoli.context import build_metrics_context  # noqa: E402
from proccoli.core import pciids  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.sysroot import SysRoot  # noqa: E402
from proccoli.core.ticker import Ticker  # noqa: E402
from proccoli.devices import snapshot_codec  # noqa: E402
from proccoli.devices.cpu import CpuSnapshot  # noqa: E402
from proccoli.gpu.amdgpu.backend import demo_sample  # noqa: E402
from proccoli.metrics_service import (BUS_NAME, INTERFACE, OBJECT_PATH,  # noqa: E402
                                      MetricsService, watch)


def collector_context(test, root=LAPTOP):
    timers = []
    ticker = Ticker(timeout_add=lambda ms, cb: timers.append(cb) or len(timers),
                    source_remove=lambda _s: None, clock=iter(range(100, 10_000)).__next__)
    ctx = build_metrics_context(metrics.metrics_settings(Settings.for_tests()),
                                system=FakeSystem(), sysroot=SysRoot(root),
                                pci=pciids.load(os.path.join(FIXTURES, "pci", "pci.ids")),
                                connection_name=None, ticker=ticker)
    test.addCleanup(ctx.stop)
    return ctx


def pump(until, timeout=5.0):
    ctx = GLib.MainContext.default()
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        while ctx.pending():
            ctx.iteration(False)
        if until():
            return True
        time.sleep(0.005)
    return until()


class CodecTest(unittest.TestCase):
    def test_every_snapshot_of_two_fixture_machines_round_trips(self):
        seen = set()
        for root in (LAPTOP, RENOIR):
            ctx = collector_context(self, root)
            ctx.devices.start()
            ctx.devices.refresh(1.0)
            ctx.devices.refresh(2.0)
            for monitor in ctx.devices.monitors():
                snap = monitor.latest
                if snap is None:
                    continue
                back = snapshot_codec.loads(snapshot_codec.dumps(snap))
                self.assertEqual(type(back), type(snap), monitor.info.id)
                self.assertEqual(back, snap, monitor.info.id)
                seen.add(type(snap).__name__)
        self.assertTrue({"CpuSnapshot", "MemorySnapshot", "GpuSnapshot"} <= seen, seen)

    def test_detail_samples_and_none(self):
        sample = demo_sample(12.0)
        self.assertEqual(snapshot_codec.loads(snapshot_codec.dumps(sample)), sample)
        snap = CpuSnapshot(1.0, usage=None, per_thread=[1.0, None], temperature_c=float("nan"))
        back = snapshot_codec.loads(snapshot_codec.dumps(snap))
        self.assertEqual(back.per_thread, [1.0, None])
        self.assertIsNone(back.temperature_c)             # NaN isn't JSON: none

    def test_only_known_types_are_built(self):
        data = {"__type__": "Popen", "args": ["rm", "-rf", "/"]}
        self.assertEqual(snapshot_codec.decode(data), {"args": ["rm", "-rf", "/"]})

    def test_newer_and_older_collectors(self):
        data = snapshot_codec.encode(CpuSnapshot(1.0, usage=5.0))
        data["from_the_future"] = 1                        # dropped
        del data["frequency_hz"]                           # defaulted
        back = snapshot_codec.decode(data)
        self.assertEqual((back.usage, back.frequency_hz), (5.0, None))


@unittest.skipUnless(shutil.which("dbus-daemon"), "no dbus-daemon")
class ServiceTest(unittest.TestCase):
    """On a private bus of its own (a dbus-daemon reached by address), so
    the process's session bus, which GTK applications in other tests use,
    is never touched (Gio.TestDBus would replace it for the whole run)."""

    @classmethod
    def setUpClass(cls):
        from helpers import PrivateBus
        cls.bus = PrivateBus()                 # nothing can be auto-started on it
        cls.address = cls.bus.address

    @classmethod
    def tearDownClass(cls):
        cls.bus.stop()

    def connect(self):
        conn = Gio.DBusConnection.new_for_address_sync(
            self.address,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
        self.addCleanup(lambda: conn.is_closed() or conn.close_sync(None))
        return conn

    def setUp(self):
        self.ctx = collector_context(self, RENOIR)
        self.ctx.start()
        self.service = MetricsService(self.ctx.devices, self.ctx.ticker, settings=self.ctx.settings)
        self.service.start(self.connect())
        self.addCleanup(self.service.stop)
        self.client = self.connect()
        self.assertTrue(pump(lambda: self.owner() is not None))

    def owner(self):
        try:
            reply = self.client.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus",
                                          "org.freedesktop.DBus", "GetNameOwner",
                                          GLib.Variant("(s)", (BUS_NAME,)), None,
                                          Gio.DBusCallFlags.NONE, 1000, None)
            return reply.unpack()[0]          # (the bus daemon answers: no deadlock)
        except GLib.Error:
            return None

    def call(self, method, conn=None):
        """Asynchronously: the service answers from this same main loop."""
        conn = conn or self.client
        box = []
        conn.call(BUS_NAME, OBJECT_PATH, INTERFACE, method, None, None,
                  Gio.DBusCallFlags.NONE, 2000, None,
                  lambda c, res: box.append(c.call_finish(res)))
        self.assertTrue(pump(lambda: box), method)
        reply = box[0]
        return reply.unpack()[0] if reply is not None and reply.n_children() else None

    def readings(self, conn=None):
        got = []
        (conn or self.client).signal_subscribe(
            BUS_NAME, INTERFACE, "Readings", OBJECT_PATH, None, Gio.DBusSignalFlags.NONE,
            lambda *a: got.append(a[5].unpack()))
        return got

    def test_devices(self):
        devices = json.loads(self.call("Devices"))
        ids = [d["id"] for d in devices]
        self.assertIn("cpu", ids)
        gpu = next(d for d in devices if d["kind"] == "gpu")
        self.assertEqual(gpu["name"], "GPU")
        self.assertIn("Driver Used", gpu["properties"])            # as the page lists them
        self.assertIn("Detailed Statistics", gpu["described"])     # as the history keeps them

    def test_readings_only_while_subscribed(self):
        got = self.readings()
        self.ctx.ticker.tick_now()
        pump(lambda: False, 0.2)
        self.assertEqual(got, [])                          # nobody subscribed
        self.assertEqual(self.service.sent, 0)
        self.call("Subscribe")
        for _ in range(2):
            self.ctx.ticker.tick_now()
        self.assertTrue(pump(lambda: len(got) == 2))
        time_ms, _mono, text = got[-1]
        self.assertGreater(time_ms, 1_700_000_000_000)
        payload = json.loads(text)
        # (The Renoir fixture is the GPU's files only: the processor and
        # memory have nothing to read, so the GPU is the one reading.)
        self.assertEqual(list(payload), ["gpu-0000:03:00.0"])
        snap = snapshot_codec.decode(payload["gpu-0000:03:00.0"]["snapshot"])
        self.assertEqual(type(snap).__name__, "GpuSnapshot")
        self.assertIsNotNone(snap.summary.usage)
        gpu = payload["gpu-0000:03:00.0"]["gpu"]
        self.assertEqual(gpu["detail_state"], "RUNNING")
        self.assertEqual(gpu["detail_source"], "amdgpu")
        self.assertEqual(snapshot_codec.decode(gpu["detail_sample"]).__class__.__name__,
                         "AmdgpuSample")
        self.call("Unsubscribe")
        self.ctx.ticker.tick_now()
        pump(lambda: False, 0.2)
        self.assertEqual(len(got), 2)

    def test_a_client_that_leaves_is_forgotten(self):
        other = self.connect()
        self.call("Subscribe", other)
        self.assertTrue(pump(lambda: len(self.service.subscribers) == 1))
        other.close_sync(None)
        self.assertTrue(pump(lambda: len(self.service.subscribers) == 0))

    def test_gpu_devices_carry_what_the_window_needs(self):
        from proccoli.gpu.info import GpuInfo, GpuVendor
        devices = json.loads(self.call("Devices"))
        gpu = next(d for d in devices if d["kind"] == "gpu")["gpu"]
        info = snapshot_codec.decode(gpu["info"])
        self.assertIsInstance(info, GpuInfo)
        self.assertEqual(info.vendor, GpuVendor.AMD)
        self.assertEqual(gpu["detail_source"], "amdgpu")
        self.assertIn("amdgpu", gpu["plan_explain"])
        self.assertFalse(gpu["needs_elevation"])

    def test_the_collector_follows_turning_details_off(self):
        gpu = self.ctx.devices.monitor("gpu-0000:03:00.0")
        self.assertEqual(gpu.detail_state.name, "RUNNING")
        self.ctx.settings.set("gpu-details-disabled", ["0000:03:00.0"])     # from the window
        self.assertEqual(gpu.detail_state.name, "OFF")
        self.ctx.settings.set("gpu-details-disabled", [])
        self.assertIn(gpu.detail_state.name, ("STARTING", "RUNNING"))

    def test_subscribing_writes_out_the_buffered_readings(self):
        # a window fills its graphs from the history as it connects;
        # the collector's last seconds must be in it by then.
        import tempfile
        from pathlib import Path
        from proccoli.core.history_db import HistoryDb
        from proccoli.core.history_store import HistoryStore
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "history.sqlite3"
        clock = [1_795_600_000.0]
        store = HistoryStore(self.ctx.devices, self.ctx.settings, path, "9.9",
                             lambda: clock[0])
        self.addCleanup(store.shutdown)
        self.service.store = store
        for _ in range(3):                                # under the 10 s commit
            self.ctx.ticker.tick_now()
            clock[0] += 1
        self.assertGreater(len(store._buffer), 0)
        self.call("Subscribe")
        self.assertEqual(store._buffer, [])
        db = HistoryDb(path, readonly=True)
        self.addCleanup(db.close)
        self.assertEqual(db.count("d_gpu_0000_03_00_0"), 3)

    def test_status(self):
        status = json.loads(self.call("Status"))
        self.assertEqual(status["update_interval_ms"], 1000)
        self.assertEqual(status["devices"], 3)             # the Renoir fixture
        self.assertEqual(status["subscribers"], 0)

    def test_a_second_service_hands_over_to_the_first(self):
        first = self.owner()
        lost = []
        second_ctx = collector_context(self, RENOIR)
        second = MetricsService(second_ctx.devices, second_ctx.ticker,
                                on_superseded=lost.append)
        second.start(self.connect())
        self.addCleanup(second.stop)
        self.assertTrue(pump(lambda: lost))
        self.assertEqual(lost, [os.getpid()])        # both connections are this process's
        self.assertEqual(self.owner(), first)        # the first keeps serving
        self.assertIn("cpu", [d["id"] for d in json.loads(self.call("Devices"))])

    def test_a_second_recorder_leaves(self):
        """``run`` returns (its own status) once it finds the readings served,
        writes out and frees the history, and says why."""
        import tempfile
        from pathlib import Path
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "history.sqlite3"
        ctx = collector_context(self, RENOIR)
        loop = GLib.MainLoop()
        timed_out = []
        GLib.timeout_add(5000, lambda: timed_out.append(1) or loop.quit())
        with self.assertLogs("proccoli.metrics", "INFO") as logs:
            code = metrics.run(ctx, path, loop=loop, signals=lambda *_a: None,
                               bus=self.connect(), interactive=True)
        self.assertEqual(code, metrics.EXIT_SUPERSEDED)
        self.assertEqual(timed_out, [])
        text = "\n".join(logs.output)
        self.assertIn("one recorder per user is enough", text)
        self.assertIn("the window is proccoli-gui", text)
        self.assertIsNotNone(self.owner())          # the first still serves

    def test_without_a_bus_it_stays(self):
        lost = []
        service = MetricsService(self.ctx.devices, self.ctx.ticker, on_superseded=lost.append)
        conn = self.connect()
        conn.close_sync(None)
        with self.assertLogs("proccoli.metrics_service", "WARNING"):
            service._name_lost(conn)
        self.assertEqual(lost, [])

    def test_watch_prints_each_update(self):
        lines = []
        loop = GLib.MainLoop()
        GLib.timeout_add(50, lambda: self.ctx.ticker.tick_now() or True)
        n = watch(lines.append, loop=loop, connection=self.client, count=2)
        self.assertEqual(n, 2)
        self.assertEqual(lines[0], "3 devices: cpu, memory, gpu-0000:03:00.0")
        self.assertRegex(lines[1], r"^\d{4}-\d\d-\d\dT[\d:.]+Z  .*GPU \d")


if __name__ == "__main__":
    unittest.main()
