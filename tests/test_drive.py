import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from helpers import LAPTOP, FakeRoot  # noqa: E402

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.sysroot import SysRoot  # noqa: E402
from proccoli.devices.drive import (  # noqa: E402
    DriveDiscoverer, DriveMonitor, drive_type, parse_disk_stat)
from proccoli.devices.manager import DeviceManager  # noqa: E402


def block(root, name, size="1000", rot="0", removable="0", ro="0", model=None,
          stat="0 0 0 0 0 0 0 0 0 0 0"):
    b = f"/sys/block/{name}"
    for f, v in (("size", size), ("queue/rotational", rot), ("removable", removable),
                 ("ro", ro), ("stat", stat)):
        root.write(f"{b}/{f}", v + "\n")
    if model:
        root.write(f"{b}/device/model", model + "\n")


class DiscoveryTest(unittest.TestCase):
    def test_laptop(self):
        [info] = DriveDiscoverer().discover(SysRoot(LAPTOP), Settings.for_tests())
        self.assertEqual(info.id, "drive-sda")
        self.assertEqual(info.name, "Solid State Drive")
        self.assertEqual(info.description, "FPT310M8SSD512G")
        p = info.properties
        self.assertEqual(p["Capacity"], "512.1 GB")
        self.assertEqual((p["Device"], p["Writable"], p["Removable"]), ("/dev/sda", "Yes", "No"))

    def test_types_and_filtering(self):
        root = FakeRoot(self)
        block(root, "nvme0n1", model="Samsung SSD 980")
        block(root, "sdb", rot="1")
        block(root, "sdc", removable="1")
        block(root, "loop0")
        block(root, "zram0")
        block(root, "mmcblk0", size="0")          # empty card reader
        block(root, "dm-0")
        root.write("/sys/block/dm-0/dm/name", "cryptroot\n")
        settings = Settings.for_tests()
        found = {i.id: i for i in DriveDiscoverer().discover(root.sysroot, settings)}
        self.assertEqual(set(found), {"drive-nvme0n1", "drive-sdb", "drive-sdc"})
        self.assertEqual(found["drive-nvme0n1"].name, "NVMe Drive")
        self.assertEqual(found["drive-sdb"].name, "Hard Disk Drive")
        self.assertEqual(found["drive-sdc"].name, "Removable Drive")
        settings.set("show-virtual-drives", True)
        found = {i.id: i for i in DriveDiscoverer().discover(root.sysroot, settings)}
        self.assertEqual(found["drive-dm-0"].description, "cryptroot")
        self.assertEqual(drive_type(root.sysroot, "sr0")[0], "Optical Drive")

    def test_stat_parsing(self):
        self.assertEqual(parse_disk_stat("1 2 300 4 5 6 700 8 0 900 11"), (300, 700, 900))
        self.assertIsNone(parse_disk_stat("1 2 3"))


class MonitorTest(unittest.TestCase):
    def test_speeds_and_busy(self):
        root = FakeRoot(self)
        block(root, "sda", stat="0 0 1000 0 0 0 2000 0 0 100 0")
        [info] = DriveDiscoverer().discover(root.sysroot, Settings.for_tests())
        m = DriveMonitor(info, root.sysroot)
        m.refresh(10.0)
        self.assertIsNone(m.latest)
        # 2 s later: +4096 sectors read, +2048 written, +500 ms busy.
        root.write("/sys/block/sda/stat", "0 0 5096 0 0 0 4048 0 0 600 0\n")
        m.refresh(12.0)
        s = m.latest
        self.assertEqual(s.read_bps, 4096 * 512 / 2)
        self.assertEqual(s.write_bps, 2048 * 512 / 2)
        self.assertAlmostEqual(s.usage, 25.0)
        self.assertEqual(s.total_read, 5096 * 512)
        self.assertEqual(m.history.series("write").unit, "B/s")


class HotplugTest(unittest.TestCase):
    def test_plug_and_unplug(self):
        root = FakeRoot(self)
        block(root, "sda")
        settings = Settings.for_tests()
        manager = DeviceManager(root.sysroot, settings)
        manager.register(DriveDiscoverer())
        events = []
        manager.connect("device-added", lambda _m, mon: events.append(("+", mon.info.id)))
        manager.connect("device-removed", lambda _m, i: events.append(("-", i)))
        manager.start()
        block(root, "sdb", removable="1")
        manager.rescan()
        root.remove("/sys/block/sdb")
        manager.rescan()
        self.assertEqual(events, [("+", "drive-sda"), ("+", "drive-sdb"), ("-", "drive-sdb")])

    def test_virtual_setting_rescans_immediately(self):
        root = FakeRoot(self)
        block(root, "dm-0")
        settings = Settings.for_tests()
        manager = DeviceManager(root.sysroot, settings)
        manager.register(DriveDiscoverer())
        manager.start()
        self.assertEqual(manager.monitors(), [])
        settings.set("show-virtual-drives", True)
        self.assertEqual([m.info.id for m in manager.monitors()], ["drive-dm-0"])


if __name__ == "__main__":
    unittest.main()
