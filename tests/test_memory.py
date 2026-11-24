import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from helpers import LAPTOP, FakeRoot  # noqa: E402

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.sysroot import SysRoot  # noqa: E402
from proccoli.devices.base import DeviceInfo, DeviceKind  # noqa: E402
from proccoli.devices.memory import (  # noqa: E402
    UDEV_DMI, MemoryDiscoverer, MemoryModule, MemoryMonitor, memory_description,
    memory_speed, memory_type, parse_dmidecode_memory, parse_meminfo, parse_udev_memory,
    summarize_modules)

MEMINFO = """MemTotal:       16000000 kB
MemFree:         2000000 kB
MemAvailable:    6000000 kB
SwapTotal:       4000000 kB
SwapFree:        3000000 kB
HugePages_Total:       0
"""

DMIDECODE = """# dmidecode 3.6
Getting SMBIOS data from sysfs.
SMBIOS 3.4.0 present.

Handle 0x0040, DMI type 17, 92 bytes
Memory Device
\tArray Handle: 0x003F
\tSize: 8 GB
\tForm Factor: SODIMM
\tLocator: Controller0-ChannelA-DIMM0
\tType: DDR4
\tType Detail: Synchronous
\tSpeed: 3200 MT/s
\tConfigured Memory Speed: 3200 MT/s

Handle 0x0041, DMI type 17, 92 bytes
Memory Device
\tSize: No Module Installed
\tForm Factor: Unknown
\tLocator: Controller0-ChannelA-DIMM1
\tType: Unknown
\tType Detail: None
\tSpeed: Unknown

Handle 0x0042, DMI type 17, 92 bytes
Memory Device
\tSize: 8192 MB
\tForm Factor: SODIMM
\tLocator: Controller1-ChannelA-DIMM0
\tType: DDR4
\tType Detail: Synchronous
\tSpeed: 3200 MT/s
\tConfigured Memory Speed: 2933 MT/s

Handle 0x0050, DMI type 19, 31 bytes
Memory Array Mapped Address
\tStarting Address: 0x00000000000
"""


class ParsingTest(unittest.TestCase):
    def test_meminfo_in_bytes(self):
        mi = parse_meminfo(MEMINFO)
        self.assertEqual(mi["MemTotal"], 16000000 * 1024)
        self.assertEqual(mi["HugePages_Total"], 0)

    def test_dmidecode(self):
        mods = parse_dmidecode_memory(DMIDECODE)
        self.assertEqual(len(mods), 3)          # the type 19 record is ignored
        self.assertEqual(mods[0].size, 8 * 2 ** 30)
        self.assertEqual(mods[2].size, 8 * 2 ** 30)
        self.assertIsNone(mods[1].size)
        self.assertEqual(mods[2].speed, "2933 MT/s")   # configured speed wins
        self.assertEqual(mods[1].speed, "")

    def test_udev_laptop_fixture(self):
        modules = parse_udev_memory(SysRoot(LAPTOP).read_text(UDEV_DMI))
        self.assertEqual([m.locator for m in modules],
                         ["Controller0-ChannelA-DIMM0", "Controller1-ChannelA-DIMM0"])
        m = modules[0]
        self.assertEqual((m.size, m.type, m.form_factor, m.speed, m.type_detail),
                         (8 * 2 ** 30, "DDR4", "SODIMM", "2667 MT/s", "Synchronous"))
        self.assertEqual(summarize_modules(modules),
                         {"Slots Used": "2 of 2", "Speed": "2667 MT/s",
                          "Form Factor": "SODIMM", "Type": "DDR4",
                          "Type Detail": "Synchronous"})

    def test_udev_empty_slots_and_unknowns(self):
        text = ("E:MEMORY_DEVICE_0_PRESENT=0\nE:MEMORY_DEVICE_0_LOCATOR=DIMM A\n"
                "E:MEMORY_DEVICE_1_SIZE=17179869184\nE:MEMORY_DEVICE_1_TYPE=DDR5\n"
                "E:MEMORY_DEVICE_1_FORM_FACTOR=Unknown\nE:MEMORY_DEVICE_1_SPEED_MTS=0\n"
                "E:MEMORY_DEVICE_10_SIZE=17179869184\nE:MEMORY_DEVICE_10_TYPE=DDR4\n"
                "E:OTHER=1\n")
        modules = parse_udev_memory(text)
        self.assertEqual([m.size for m in modules], [None, 16 * 2 ** 30, 16 * 2 ** 30])
        self.assertEqual((modules[1].form_factor, modules[1].speed), ("", ""))
        self.assertEqual(memory_type(modules), "DDR4, DDR5")             # mixed
        self.assertEqual(summarize_modules(modules)["Slots Used"], "2 of 3")
        self.assertEqual(parse_udev_memory(""), [])
        self.assertEqual(memory_type(None), "")

    def test_description_size_type_and_speed(self):
        from proccoli.core.units import Base
        gb = 2 ** 30
        mods = [MemoryModule(size=8 * gb, type="DDR5", speed="4800 MT/s"),
                MemoryModule(size=8 * gb, type="DDR5", speed="5600 MT/s"),
                MemoryModule(size=None, type="DDR5", speed="6400 MT/s")]     # empty slot
        self.assertEqual(memory_speed(mods), "4800 MT/s")                  # the slowest
        self.assertEqual(memory_description(16_000_000_000, mods, Base.DECIMAL),
                         "16.0 GB DDR5 @ 4800 MT/s")
        self.assertEqual(memory_description(17179869184, mods, Base.BINARY),
                         "16.0 GiB DDR5 @ 4800 MT/s")
        self.assertEqual(memory_description(16_000_000_000, None, Base.DECIMAL), "16.0 GB")
        no_speed = [MemoryModule(size=gb, type="DDR4")]
        self.assertEqual(memory_description(8_500_000_000, no_speed, Base.DECIMAL), "8.5 GB DDR4")
        self.assertEqual(memory_description(None, None, Base.DECIMAL), "")

    def test_summary(self):
        props = summarize_modules(parse_dmidecode_memory(DMIDECODE))
        self.assertEqual(props["Slots Used"], "2 of 3")
        self.assertEqual(props["Speed"], "2933 MT/s, 3200 MT/s")
        self.assertEqual(props["Form Factor"], "SODIMM")
        self.assertEqual(props["Type"], "DDR4")
        self.assertEqual(props["Type Detail"], "Synchronous")
        self.assertEqual(summarize_modules([]), {})


class MonitorTest(unittest.TestCase):
    def test_laptop_discovery(self):
        d = MemoryDiscoverer()
        [info] = d.discover(SysRoot(LAPTOP), Settings.for_tests())
        self.assertEqual((info.id, info.name), ("memory", "Memory"))
        self.assertRegex(info.description, r"^\d+\.\d GB DDR4 @ 2667 MT/s$")
        monitor = d.create_monitor(info, SysRoot(LAPTOP), Settings.for_tests())
        self.assertEqual(len(monitor.modules), 2)                       # no password needed

    def test_without_udev_data_the_type_is_left_out(self):
        root = FakeRoot(self, {"/proc/meminfo": MEMINFO})
        d = MemoryDiscoverer()
        [info] = d.discover(root.sysroot, Settings.for_tests())
        self.assertTrue(info.description.endswith("GB"))
        self.assertIsNone(d.create_monitor(info, root.sysroot, Settings.for_tests()).modules)

    def test_sample(self):
        root = FakeRoot(self, {"/proc/meminfo": MEMINFO})
        m = MemoryMonitor(DeviceInfo("memory", DeviceKind.MEMORY, "Memory"), root.sysroot)
        m.refresh(1.0)
        s = m.latest
        self.assertEqual(s.used, 10000000 * 1024)
        self.assertAlmostEqual(s.usage, 62.5)
        self.assertAlmostEqual(s.swap_usage, 25.0)
        self.assertEqual(m.history.series("swap").latest(), 25.0)
        self.assertEqual(s.detail_text, "10.2 GB / 16.4 GB")

    def test_no_swap(self):
        root = FakeRoot(self, {"/proc/meminfo": "MemTotal: 1000 kB\nMemAvailable: 500 kB\n"})
        m = MemoryMonitor(DeviceInfo("memory", DeviceKind.MEMORY, "Memory"), root.sysroot)
        m.refresh(1.0)
        self.assertIsNone(m.latest.swap_usage)

    def test_laptop_fixture_samples(self):
        m = MemoryMonitor(DeviceInfo("memory", DeviceKind.MEMORY, "Memory"), SysRoot(LAPTOP))
        m.refresh(1.0)
        self.assertTrue(0 < m.latest.usage < 100)


if __name__ == "__main__":
    unittest.main()
