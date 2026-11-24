import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from helpers import LAPTOP, FakeRoot  # noqa: E402

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.sysroot import SysRoot  # noqa: E402
from proccoli.devices.base import DeviceInfo, DeviceKind, Monitor  # noqa: E402
from proccoli.devices.cpu import (  # noqa: E402
    CpuDiscoverer, CpuMonitor, busy_percent, cpu_model, find_temperature_input,
    parse_cpuinfo, parse_proc_stat)
from proccoli.devices.manager import DeviceManager, Discoverer  # noqa: E402

STAT0 = ("cpu  100 0 100 800 0 0 0 0 0 0\n"
         "cpu0 50 0 50 400 0 0 0 0 0 0\n"
         "cpu1 50 0 50 400 0 0 0 0 0 0\n"
         "intr 1\nbtime 1795366838\n")
# +100 jiffies per CPU; cpu0 busy 75 of them, cpu1 busy 25.
STAT1 = ("cpu  175 0 125 900 0 0 0 0 0 0\n"
         "cpu0 100 0 75 425 0 0 0 0 0 0\n"
         "cpu1 75 0 50 475 0 0 0 0 0 0\n"
         "intr 2\nbtime 1795366838\n")


class ParsingTest(unittest.TestCase):
    def test_proc_stat(self):
        stat = parse_proc_stat(STAT0)
        self.assertEqual(set(stat), {"cpu", "cpu0", "cpu1"})
        self.assertEqual(stat["cpu0"][:4], [50, 0, 50, 400])

    def test_busy_percent(self):
        a, b = parse_proc_stat(STAT0), parse_proc_stat(STAT1)
        self.assertAlmostEqual(busy_percent(a["cpu0"], b["cpu0"]), 75.0)
        self.assertAlmostEqual(busy_percent(a["cpu1"], b["cpu1"]), 25.0)
        self.assertAlmostEqual(busy_percent(a["cpu"], b["cpu"]), 50.0)
        self.assertIsNone(busy_percent(a["cpu"], a["cpu"]))   # no time passed

    def test_iowait_counts_as_idle(self):
        self.assertAlmostEqual(busy_percent([0, 0, 0, 0, 0], [0, 0, 0, 50, 50]), 0.0)

    def test_cpuinfo_and_model(self):
        with open(os.path.join(LAPTOP, "proc/cpuinfo")) as fh:
            cpus = parse_cpuinfo(fh.read())
        self.assertEqual(len(cpus), 12)
        self.assertEqual(cpu_model(cpus), "12th Gen Intel(R) Core(TM) i5-12450H")
        self.assertEqual(cpu_model([]), "Processor")


class DiscoveryTest(unittest.TestCase):
    def test_laptop_properties(self):
        [info] = CpuDiscoverer("x86_64").discover(SysRoot(LAPTOP), Settings.for_tests())
        self.assertEqual(info.id, "cpu")
        self.assertEqual(info.description, "12th Gen Intel(R) Core(TM) i5-12450H")
        p = info.properties
        self.assertEqual(p["Logical Cores"], "12")
        self.assertEqual(p["Physical Cores"], "8")   # 4 P-cores (HT) + 4 E-cores
        self.assertEqual(p["Sockets"], "1")
        self.assertEqual(p["Max Frequency"], "4.40 GHz")
        self.assertEqual(p["Virtualization"], "Intel VT-x")
        self.assertEqual(p["Architecture"], "x86_64")

    def test_amd_virtualization(self):
        root = FakeRoot(self, {"/proc/cpuinfo": "processor : 0\nmodel name : AMD Ryzen\n"
                                                "flags : fpu svm\n\n",
                               "/proc/stat": "cpu 1 1 1 1\ncpu0 1 1 1 1\n"})
        [info] = CpuDiscoverer("x86_64").discover(root.sysroot, Settings.for_tests())
        self.assertEqual(info.properties["Virtualization"], "AMD-V")
        self.assertNotIn("Max Frequency", info.properties)   # no cpufreq


class TemperatureTest(unittest.TestCase):
    def test_coretemp_package(self):
        path = find_temperature_input(SysRoot(LAPTOP))
        self.assertTrue(path.startswith("/sys/class/hwmon/hwmon3/"))
        self.assertEqual(SysRoot(LAPTOP).read_line(path.replace("_input", "_label")),
                         "Package id 0")

    def test_k10temp_tctl(self):
        root = FakeRoot(self, {"/sys/class/hwmon/hwmon0/name": "k10temp\n",
                               "/sys/class/hwmon/hwmon0/temp1_input": "40000\n",
                               "/sys/class/hwmon/hwmon0/temp1_label": "Tccd1\n",
                               "/sys/class/hwmon/hwmon0/temp2_input": "55000\n",
                               "/sys/class/hwmon/hwmon0/temp2_label": "Tctl\n"})
        self.assertEqual(find_temperature_input(root.sysroot),
                         "/sys/class/hwmon/hwmon0/temp2_input")

    def test_none(self):
        root = FakeRoot(self, {"/sys/class/hwmon/hwmon0/name": "acpi_fan\n"})
        self.assertIsNone(find_temperature_input(root.sysroot))


class MonitorTest(unittest.TestCase):
    def make(self):
        root = FakeRoot(self, {
            "/proc/stat": STAT0, "/proc/uptime": "3725.5 1000.0\n",
            "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq": "2000000\n",
            "/sys/devices/system/cpu/cpu1/cpufreq/scaling_cur_freq": "3000000\n",
            "/sys/class/hwmon/hwmon0/name": "coretemp\n",
            "/sys/class/hwmon/hwmon0/temp1_input": "47000\n",
            "/sys/class/hwmon/hwmon0/temp1_label": "Package id 0\n"})
        info = DeviceInfo("cpu", DeviceKind.CPU, "Processor")
        return root, CpuMonitor(info, root.sysroot, 10)

    def test_first_sample_records_nothing(self):
        _, m = self.make()
        m.refresh(0.0)
        self.assertIsNone(m.latest)
        self.assertEqual(len(m.history), 0)

    def test_second_sample(self):
        root, m = self.make()
        m.refresh(0.0)
        root.write("/proc/stat", STAT1)
        m.refresh(1.0)
        s = m.latest
        self.assertAlmostEqual(s.usage, 50.0)
        self.assertEqual([round(v) for v in s.per_thread], [75, 25])
        self.assertEqual(s.frequency_hz, 2.5e9)
        self.assertEqual(s.temperature_c, 47.0)
        self.assertEqual(s.uptime_s, 3725.5)
        self.assertEqual(s.usage_text, "50 %")
        self.assertEqual(s.detail_text, "2.50 GHz")
        self.assertEqual(m.history.series("cpu1").latest(), 25.0)
        self.assertEqual(m.history.series("temperature").unit, "°C")
        self.assertEqual(m.thread_names(), ["cpu0", "cpu1"])

    def test_missing_proc_stat_becomes_a_gap(self):
        root, m = self.make()
        m.refresh(0.0)
        root.write("/proc/stat", STAT1)
        m.refresh(1.0)
        root.remove("/proc/stat")
        with self.assertLogs("proccoli.devices.base"):
            m.refresh(2.0)
        self.assertIsNone(m.history.series("usage").latest())


class FakeDiscoverer(Discoverer):
    kind = DeviceKind.DRIVE
    rescan = True

    def __init__(self):
        self.found = ["a"]
        self.created = []

    def discover(self, sysroot, settings):
        return [DeviceInfo(i, DeviceKind.DRIVE, i) for i in self.found]

    def create_monitor(self, info, sysroot, settings):
        class M(Monitor):
            def sample(self, now):
                return None
        self.created.append(info.id)
        return M(info)


class ManagerTest(unittest.TestCase):
    def make(self, interval=5.0):
        settings = Settings.for_tests()
        manager = DeviceManager(SysRoot("/nonexistent"), settings, interval)
        d = FakeDiscoverer()
        manager.register(d)
        events = []
        manager.connect("device-added", lambda _m, mon: events.append(("+", mon.info.id)))
        manager.connect("device-removed", lambda _m, i: events.append(("-", i)))
        return settings, manager, d, events

    def test_start_adds_each_device_once(self):
        _, manager, d, events = self.make()
        manager.start()
        manager.rescan()
        self.assertEqual(events, [("+", "a")])
        self.assertEqual([m.info.id for m in manager.monitors()], ["a"])

    def test_rescan_adds_and_removes(self):
        _, manager, d, events = self.make()
        manager.start()
        d.found = ["b"]
        manager.rescan()
        self.assertEqual(events, [("+", "a"), ("-", "a"), ("+", "b")])
        self.assertIsNone(manager.monitor("a"))

    def test_refresh_rescans_on_interval(self):
        _, manager, d, events = self.make(interval=5.0)
        manager.start()
        d.found = ["a", "c"]
        manager.refresh(100.0)       # first tick only sets the clock
        manager.refresh(103.0)
        self.assertEqual(len(events), 1)
        manager.refresh(105.0)
        self.assertEqual(events[-1], ("+", "c"))

    def test_graph_points_setting_resizes_histories(self):
        settings, manager, _, _ = self.make()
        manager.start()
        settings.set("graph-data-points", 30)
        self.assertEqual(manager.monitor("a").history.max_points, 30)

    def test_broken_discoverer_does_not_stop_others(self):
        _, manager, d, events = self.make()

        class Broken(Discoverer):
            kind = DeviceKind.GPU

            def discover(self, sysroot, settings):
                raise OSError("boom")
        manager.discoverers.insert(0, Broken())
        with self.assertLogs("proccoli.devices.manager"):
            manager.start()
        self.assertEqual(events, [("+", "a")])


if __name__ == "__main__":
    unittest.main()
