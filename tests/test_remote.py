"""the window's devices, read by proccoli.
A collector on a private bus, and the window's RemoteDeviceManager as its
client: the same devices, readings, GPU Details and failures as reading
locally. No display needed."""

import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from helpers import FIXTURES, LAPTOP, RENOIR, FakeSystem, PrivateBus, pump_until  # noqa: E402
from proccoli import metrics  # noqa: E402
from proccoli.context import build_metrics_context  # noqa: E402
from proccoli.core import pciids  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.sysroot import SysRoot  # noqa: E402
from proccoli.core.ticker import Ticker  # noqa: E402
from proccoli.devices.base import DeviceInfo, DeviceKind, FailedMonitor  # noqa: E402
from proccoli.devices.remote import (RemoteDetailBackend, RemoteDeviceManager,  # noqa: E402
                                     RemoteGpuController, RemoteMonitor)
from proccoli.gpu.controller import DetailState, GpuSnapshot  # noqa: E402
from proccoli.metrics_service import MetricsService  # noqa: E402


@unittest.skipUnless(shutil.which("dbus-daemon"), "no dbus-daemon")
class RemoteDevicesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bus = PrivateBus()

    @classmethod
    def tearDownClass(cls):
        cls.bus.stop()

    def collector(self, root=RENOIR, settings=None):
        ticker = Ticker(timeout_add=lambda ms, cb: 1, source_remove=lambda _s: None,
                        clock=iter(range(100, 100_000)).__next__)
        self.settings = settings or Settings.for_tests()
        ctx = build_metrics_context(metrics.metrics_settings(self.settings),
                                    system=FakeSystem(), sysroot=SysRoot(root),
                                    pci=pciids.load(os.path.join(FIXTURES, "pci", "pci.ids")),
                                    connection_name=None, ticker=ticker)
        ctx.start()
        self.addCleanup(ctx.stop)
        service = MetricsService(ctx.devices, ctx.ticker, settings=ctx.settings)
        service.start(self.bus.connect(self))
        self.addCleanup(service.stop)
        self.service = service
        return ctx

    def window(self, settings=None):
        clock = iter(range(5000, 1_000_000)).__next__
        devices = RemoteDeviceManager(settings or self.settings, self.bus.connect(self),
                                      clock=lambda: float(clock()), auto_start=False)
        self.addCleanup(devices.stop)
        added = []
        devices.connect("device-added", lambda _d, m: added.append(m))
        devices.start()
        self.assertTrue(pump_until(lambda: devices.connected), devices.status)
        return devices, added

    def tick(self, ctx, devices, n=1):
        before = devices.readings
        for _ in range(n):
            ctx.ticker.tick_now()
        self.assertTrue(pump_until(lambda: devices.readings >= before + n))

    def test_same_devices_as_the_collector(self):
        ctx = self.collector(LAPTOP)
        devices, added = self.window()
        self.assertEqual([m.info.id for m in devices.monitors()],
                         [m.info.id for m in ctx.devices.monitors()])
        self.assertEqual(len(added), len(ctx.devices.monitors()))
        local, remote = ctx.devices.monitor("net-wlp0s20f3") or ctx.devices.monitors(
            DeviceKind.NETWORK)[0], None
        remote = devices.monitor(local.info.id)
        self.assertEqual(remote.info, local.info)
        self.assertEqual(remote.sort_name(), local.sort_name())
        self.assertEqual(remote.described_properties(), local.described_properties())
        cpu = devices.monitor("cpu")
        self.assertEqual(cpu.thread_names(), ctx.devices.monitor("cpu").thread_names())
        self.assertIsNotNone(cpu.temperature_path)                 # the laptop has a sensor

    def test_chart_lines_exist_before_the_first_reading(self):
        # the sidebar and the Overview chart a device before any
        # reading; a local monitor defines its lines up front, so must these.
        ctx = self.collector(LAPTOP)
        devices, _ = self.window()
        for local in ctx.devices.monitors():
            remote = devices.monitor(local.info.id)
            with self.subTest(local.info.id):
                self.assertEqual(remote.history.keys(), local.history.keys())
        net = devices.monitors(DeviceKind.NETWORK)[0]
        self.assertIsNotNone(net.history.series("rx"))
        self.assertIsNotNone(devices.monitor("memory").history.series("usage"))

    def test_readings_become_history_and_updated(self):
        ctx = self.collector(LAPTOP)
        devices, _ = self.window()
        memory = devices.monitor("memory")
        updates = []
        memory.connect("updated", lambda _m, snap: updates.append(snap))
        self.tick(ctx, devices, 3)
        self.assertEqual(len(updates), 3)
        self.assertEqual(updates[-1].total, ctx.devices.monitor("memory").latest.total)
        self.assertEqual(len(memory.history), 3)
        # On the window's own clock, so its graphs and history filling line up.
        self.assertEqual(memory.latest.time, memory.history.times[-1])

    def test_a_gpu_with_its_details(self):
        ctx = self.collector(RENOIR)
        devices, _ = self.window()
        gpu = devices.monitor("gpu-0000:03:00.0")
        self.assertIsInstance(gpu, RemoteGpuController)
        self.assertEqual(gpu.gpu.pci_slot, "0000:03:00.0")
        self.assertEqual(gpu.sort_name(), "0000:03:00.0")
        self.assertEqual(gpu.detail_class.id, "amdgpu")
        self.assertIn("amdgpu", gpu.plan.explain())
        changes = []
        gpu.connect("detail-changed", lambda _g, state: changes.append(state))
        self.tick(ctx, devices, 2)
        self.assertEqual(gpu.detail_state, DetailState.RUNNING)
        self.assertEqual(changes, ["running"])
        backend = gpu.detail_backend
        self.assertIsInstance(backend, RemoteDetailBackend)
        self.assertEqual(type(backend.sample).__name__, "AmdgpuSample")
        self.assertEqual(backend.source_note, "amdgpu's statistics files")
        self.assertGreater(len(backend.history), 0)
        self.assertIs(gpu.detail_history(), backend.history)
        self.assertIsInstance(gpu.latest, GpuSnapshot)
        self.assertEqual(gpu.summary().usage, ctx.devices.monitor(gpu.info.id).summary().usage)

    def test_turning_details_off_goes_through_the_collector(self):
        ctx = self.collector(RENOIR)
        devices, _ = self.window()
        gpu = devices.monitor("gpu-0000:03:00.0")
        self.tick(ctx, devices)
        gpu.set_details_enabled(False)                    # the setting; the collector acts
        self.tick(ctx, devices)
        self.assertEqual(gpu.detail_state, DetailState.OFF)
        self.assertIsNone(gpu.detail_backend)
        self.assertFalse(gpu.details_enabled)

    def test_devices_come_and_go(self):
        ctx = self.collector(LAPTOP)
        devices, added = self.window()
        removed = []
        devices.connect("device-removed", lambda _d, i: removed.append(i))
        some = ctx.devices.monitors(DeviceKind.DRIVE)[0].info.id
        ctx.devices._remove(some)
        self.assertTrue(pump_until(lambda: removed == [some]))
        self.assertIsNone(devices.monitor(some))

    def test_a_failed_device_and_try_again(self):
        ctx = self.collector(LAPTOP)
        info = ctx.devices.monitor("memory").info
        ctx.devices._monitors["memory"] = FailedMonitor(info, "It broke", "trace")
        devices, _ = self.window()
        failed = devices.monitor("memory")
        self.assertIsInstance(failed, FailedMonitor)
        self.assertEqual((failed.message, failed.details), ("It broke", "trace"))
        self.assertTrue(devices.retry("memory"))
        self.assertTrue(pump_until(lambda: isinstance(devices.monitor("memory"), RemoteMonitor)))

    def test_the_collector_going_away_and_coming_back(self):
        settings = Settings.for_tests()
        ctx = self.collector(LAPTOP, settings)
        devices, _ = self.window(settings)
        changes = []
        devices.connect("connection-changed", lambda *_: changes.append(devices.connected))
        self.service.stop()
        self.assertTrue(pump_until(lambda: not devices.connected))
        self.assertIn("isn't running", devices.status)
        self.service.start(self.bus.connect(self))
        self.assertTrue(pump_until(lambda: devices.connected))
        self.assertEqual(changes, [False, True])
        self.tick(ctx, devices)                            # readings again

    def test_flush_asks_the_collector_then_calls_back(self):
        ctx = self.collector(LAPTOP)
        devices, _ = self.window()
        commits = []
        self.service.store = type("Store", (), {"commit": lambda _s: commits.append(1)})()
        done = []
        devices.flush(lambda: done.append(1))
        self.assertEqual(done, [])                           # waits for the answer
        self.assertTrue(pump_until(lambda: done))
        self.assertEqual(commits, [1])

    def test_flush_without_a_collector_calls_back_at_once(self):
        devices = RemoteDeviceManager(Settings.for_tests(), None, auto_start=False)
        done = []
        devices.flush(lambda: done.append(1))
        self.assertEqual(done, [1])

    def test_the_time_range_reaches_remote_histories(self):
        ctx = self.collector(LAPTOP)
        devices, _ = self.window()
        self.settings.set("graph-time-range", "1-hour")
        self.assertEqual(devices.monitor("memory").history.max_points, 901)



@unittest.skipUnless(shutil.which("dbus-daemon"), "no dbus-daemon")
class NoStrayCollectorTest(unittest.TestCase):
    """Nothing in the tests or the window may get a collector started by
    accident: a test once started the installed proccoli through
    its D-Bus activation file, which then kept running on the real
    history."""

    def test_the_tests_bus_starts_nothing(self):
        from gi.repository import Gio, GLib
        from proccoli.metrics_service import BUS_NAME, INTERFACE, OBJECT_PATH
        bus = PrivateBus()
        self.addCleanup(bus.stop)
        conn = bus.connect(self)
        box = []
        conn.call(BUS_NAME, OBJECT_PATH, INTERFACE, "Devices", None, None,
                  Gio.DBusCallFlags.NONE, 2000, None,
                  lambda c, r: box.append(self._error(c, r)))
        self.assertTrue(pump_until(lambda: box))
        self.assertIn("ServiceUnknown", box[0])          # not activated

    @staticmethod
    def _error(conn, result):
        from gi.repository import Gio, GLib
        try:
            conn.call_finish(result)
            return "answered"
        except GLib.Error as exc:
            return Gio.DBusError.get_remote_error(exc) or exc.message

    def test_the_windows_calls_never_start_a_collector(self):
        from gi.repository import Gio
        calls = []

        class Conn:
            def call(self, _name, _path, _iface, method, _params, _rtype, flags, *_rest):
                calls.append((method, flags))

            def is_closed(self):
                return False

            def signal_unsubscribe(self, _s):
                pass

        devices = RemoteDeviceManager(Settings.for_tests(), Conn(), auto_start=True)
        devices._appeared()                               # Devices
        devices.connected = True
        devices._monitors["memory"] = FailedMonitor(
            DeviceInfo("memory", DeviceKind.MEMORY, "Memory"), "broke")
        devices.retry("memory")                           # Retry
        devices.stop()                                    # Unsubscribe
        self.assertEqual([m for m, _f in calls], ["Devices", "Retry", "Unsubscribe"])
        for method, flags in calls:
            self.assertTrue(flags & Gio.DBusCallFlags.NO_AUTO_START, method)


if __name__ == "__main__":
    unittest.main()
