"""The common base of the two device managers."""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.sysroot import SysRoot  # noqa: E402
from proccoli.devices.manager import DeviceManager  # noqa: E402
from proccoli.devices.remote import RemoteDeviceManager  # noqa: E402
from proccoli.devices.source import DeviceSource  # noqa: E402

SRC = os.path.join(os.path.dirname(__file__), "..", "src", "proccoli")


class DeviceSourceTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings.for_tests()

    def test_both_managers_are_device_sources(self):
        local = DeviceManager(SysRoot("/nonexistent"), self.settings)
        remote = RemoteDeviceManager(self.settings, auto_start=False)
        self.addCleanup(remote.stop)
        for source in (local, remote):
            self.assertIsInstance(source, DeviceSource)
            self.assertEqual(source.monitors(), [])
            self.assertIsNone(source.monitor("cpu"))
        self.assertEqual((local.remote, remote.remote), (False, True))

    def test_reading_devices_itself_is_always_connected(self):
        local = DeviceManager(SysRoot("/nonexistent"), self.settings)
        self.assertTrue(local.connected)
        local.reconnect()                     # nothing to do, no error
        self.assertTrue(local.connected)

    def test_status_changes_are_announced_once(self):
        source = DeviceSource(self.settings)
        seen = []
        source.connect("connection-changed", lambda s: seen.append((s.connected, s.status)))
        source._set_status(False, "gone")
        source._set_status(False, "gone")
        source._set_status(True, "back")
        self.assertEqual(seen, [(False, "gone"), (True, "back")])

    def test_what_each_kind_does_is_left_to_it(self):
        source = DeviceSource(self.settings)
        for call in (source.start, source.stop, lambda: source.refresh(0), source.rescan,
                     lambda: source.retry("cpu")):
            with self.assertRaises(NotImplementedError):
                call()

    def test_nothing_tells_the_kinds_apart_by_their_attributes(self):
        # ``devices.remote`` says which kind it is; probing for attributes
        # that only one kind has would break silently when they change.
        pattern = re.compile(r"hasattr\([^)]*devices[^)]*\)")
        for dirpath, _dirs, files in os.walk(SRC):
            for name in files:
                if name.endswith(".py"):
                    with open(os.path.join(dirpath, name), encoding="utf-8") as fh:
                        self.assertIsNone(pattern.search(fh.read()), name)



class DescribeTest(unittest.TestCase):
    """Each monitor says what a window needs to know about it; the window
    reads it back into a stand-in of the same kind."""

    def setUp(self):
        from helpers import LAPTOP
        from proccoli.devices import snapshot_codec
        self.settings = Settings.for_tests()
        self.sysroot = SysRoot(LAPTOP)
        self.encode = snapshot_codec.encode

    def round_trip(self, monitor):
        import json
        from proccoli.devices.remote import monitor_for
        return monitor_for(json.loads(json.dumps(monitor.describe(self.encode))), self.settings)

    def build(self, discoverer):
        info = discoverer.discover(self.sysroot, self.settings)[0]
        return discoverer.create_monitor(info, self.sysroot, self.settings)

    def test_every_monitor_has_the_common_fields(self):
        from proccoli.devices.cpu import CpuDiscoverer
        cpu = self.build(CpuDiscoverer("x86_64"))
        out = cpu.describe(self.encode)
        for key in ("id", "kind", "name", "description", "icon", "properties", "described",
                    "sort_name", "history"):
            self.assertIn(key, out)
        self.assertEqual(out["history"], {"usage": "%", "temperature": "°C"})

    def test_the_processor_adds_its_cpus_and_sensor(self):
        from proccoli.devices.cpu import CpuDiscoverer
        cpu = self.build(CpuDiscoverer("x86_64"))
        cpu.refresh(1.0)
        out = cpu.describe(self.encode)
        self.assertEqual(out["cpu"]["thread_names"], cpu.thread_names())
        self.assertTrue(out["cpu"]["thread_names"])
        remote = self.round_trip(cpu)
        self.assertEqual(remote.thread_names(), cpu.thread_names())
        self.assertEqual(remote.temperature_path is None, cpu.temperature_path is None)

    def test_memory_adds_its_modules_once_known(self):
        from proccoli.devices.memory import MemoryDiscoverer, MemoryModule
        memory = self.build(MemoryDiscoverer())
        memory.modules = None
        self.assertNotIn("memory_modules", memory.describe(self.encode))
        memory.modules = [MemoryModule(size=8 << 30, type="DDR5", speed="4800 MT/s")]
        self.assertEqual(self.round_trip(memory).modules, memory.modules)

    def test_a_failed_device_keeps_its_message(self):
        from proccoli.devices.base import DeviceInfo, DeviceKind, FailedMonitor
        failed = FailedMonitor(DeviceInfo("cpu", DeviceKind.CPU, "Processor"), "broke", "trace")
        remote = self.round_trip(failed)
        self.assertIsInstance(remote, FailedMonitor)
        self.assertEqual((remote.message, remote.details), ("broke", "trace"))

    def test_no_reading_before_the_first_sample(self):
        from proccoli.devices.cpu import CpuDiscoverer
        cpu = self.build(CpuDiscoverer("x86_64"))
        self.assertIsNone(cpu.reading(self.encode))

    def test_the_service_asks_instead_of_probing(self):
        # The recorder's service leaves the fields to each monitor.
        import ast
        from proccoli import metrics_service
        with open(metrics_service.__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        probes = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                  and getattr(n.func, "id", "") in ("hasattr", "getattr")]
        self.assertEqual(probes, [])


if __name__ == "__main__":
    unittest.main()
