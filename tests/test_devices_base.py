import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from proccoli.devices.base import DeviceInfo, DeviceKind, Monitor, Snapshot  # noqa: E402
from proccoli.devices.demo import DemoSnapshot, SineMonitor  # noqa: E402


class ScriptedMonitor(Monitor):
    """Returns queued results; an Exception instance is raised."""

    def __init__(self, results):
        super().__init__(DeviceInfo("x", DeviceKind.CPU, "X"), history_points=5)
        self.results = list(results)

    def sample(self, now):
        r = self.results.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class DeviceInfoTest(unittest.TestCase):
    def test_frozen_and_hashable(self):
        a = DeviceInfo("cpu", DeviceKind.CPU, "Processor", properties={"Cores": "8"})
        b = DeviceInfo("cpu", DeviceKind.CPU, "Processor", properties={"Cores": "16"})
        self.assertEqual(a, b)            # properties don't take part
        self.assertEqual(len({a, b}), 1)
        with self.assertRaises(Exception):
            a.name = "other"

    def test_kind_from_string(self):
        self.assertIs(DeviceKind("gpu"), DeviceKind.GPU)


class MonitorTest(unittest.TestCase):
    def test_base_sample_is_abstract(self):
        m = Monitor(DeviceInfo("x", DeviceKind.CPU, "X"))
        with self.assertLogs("proccoli.devices.base", logging.ERROR):
            m.refresh(1.0)              # NotImplementedError is caught and logged
        self.assertEqual(m.failures, 1)

    def test_refresh_records_and_emits(self):
        m = ScriptedMonitor([Snapshot(1.0, usage=10.0), Snapshot(2.0, usage=20.0)])
        seen = []
        m.connect("updated", lambda _m, snap: seen.append(snap.usage))
        m.refresh(1.0)
        m.refresh(2.0)
        self.assertEqual(seen, [10.0, 20.0])
        self.assertEqual(list(m.history.series("usage").values), [10.0, 20.0])
        self.assertEqual(m.history.series("usage").unit, "%")
        self.assertEqual(m.latest.usage, 20.0)

    def test_none_records_nothing(self):
        m = ScriptedMonitor([None, Snapshot(2.0, usage=5.0)])
        seen = []
        m.connect("updated", lambda *_: seen.append(1))
        m.refresh(1.0)
        self.assertEqual((len(m.history), seen), (0, []))
        m.refresh(2.0)
        self.assertEqual(len(m.history), 1)

    def test_failure_becomes_a_gap_and_is_logged_once(self):
        m = ScriptedMonitor([Snapshot(1.0, usage=1.0), OSError("gone"), OSError("gone"),
                             Snapshot(4.0, usage=4.0)])
        m.refresh(1.0)
        with self.assertLogs("proccoli.devices.base", logging.ERROR) as logs:
            m.refresh(2.0)
            m.refresh(3.0)
        self.assertEqual(len(logs.records), 1)
        self.assertEqual(m.failures, 2)
        m.refresh(4.0)
        self.assertEqual(m.failures, 0)
        self.assertEqual(list(m.history.series("usage").values), [1.0, None, None, 4.0])

    def test_history_points(self):
        m = ScriptedMonitor([Snapshot(float(t), usage=float(t)) for t in range(8)])
        for t in range(8):
            m.refresh(float(t))
        self.assertEqual(len(m.history), 5)
        m.set_history_points(3)
        self.assertEqual(list(m.history.series("usage").values), [5.0, 6.0, 7.0])


class SineMonitorTest(unittest.TestCase):
    def test_values_stay_in_range_and_fill_history(self):
        m = SineMonitor(period_s=10, history_points=60)
        for t in range(100):
            m.refresh(t * 0.5)
        self.assertEqual(len(m.history), 60)
        self.assertIsInstance(m.latest, DemoSnapshot)
        for v in m.history.series("usage").values:
            self.assertTrue(0 <= v <= 100)
        self.assertEqual(set(m.history.names()), {"usage", "read", "write"})
        self.assertEqual(m.history.series("read").unit, "B/s")

    def test_deterministic(self):
        a, b = SineMonitor(), SineMonitor()
        self.assertEqual(a.sample(3.0), b.sample(3.0))


class DemoGpuTest(unittest.TestCase):
    def test_demo_gpu_never_reads_the_system(self):
        from unittest import mock

        from proccoli.core.settings import Settings
        from proccoli.core.sysroot import SysRoot
        from proccoli.devices.demo import DemoGpuDiscoverer
        settings = Settings.for_tests({"gpu-details-disabled": ["0000:00:02.0"]})
        from helpers import FakeSystem
        d = DemoGpuDiscoverer(FakeSystem())
        [info] = d.discover(SysRoot("/"), settings)
        real_path = SysRoot.path
        resolved = []

        def path(self, p):
            resolved.append(str(self.root))
            return real_path(self, p)
        with mock.patch.object(SysRoot, "path", path):
            c = d.create_monitor(info, SysRoot("/"), settings)
            c.start()
            self.assertIsNone(c.detail_backend)              # details turned off
            self.assertEqual(c.summary_backend.id, "generic")
            c.refresh(3.0)
            self.assertIsNotNone(c.latest.usage)
            self.assertEqual(c.process_usage(), {})
        self.assertNotIn("/", resolved)


if __name__ == "__main__":
    unittest.main()
