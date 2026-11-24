import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.sysroot import SysRoot  # noqa: E402

MINIMAL = os.path.join(os.path.dirname(__file__), "fixtures", "minimal")


class SysRootTest(unittest.TestCase):
    def setUp(self):
        self.root = SysRoot(MINIMAL)

    def test_paths_resolve_inside_root(self):
        self.assertEqual(self.root.path("/proc/stat"),
                         self.root.root / "proc" / "stat")
        self.assertEqual(self.root.path("/"), self.root.root)

    def test_read_text_and_line(self):
        self.assertTrue(self.root.read_text("/proc/stat").startswith("cpu "))
        self.assertEqual(self.root.read_line("/sys/class/net/eth0/type"), "1")

    def test_read_int(self):
        self.assertEqual(self.root.read_int("/sys/class/net/eth0/type"), 1)
        self.assertEqual(self.root.read_int("/sys/class/net/eth0/device/vendor", 0),
                         0x8086)

    def test_bad_values_return_none(self):
        self.assertIsNone(self.root.read_int("/sys/class/net/eth0/mtu"))
        self.assertIsNone(self.root.read_int("/sys/class/net/eth0/empty"))

    def test_missing_files_return_none_instead_of_raising(self):
        self.assertIsNone(self.root.read_text("/proc/nope"))
        self.assertIsNone(self.root.read_line("/proc/nope"))
        self.assertIsNone(self.root.read_int("/proc/nope"))
        self.assertIsNone(self.root.readlink("/proc/nope"))
        self.assertEqual(self.root.listdir("/sys/nope"), [])
        self.assertFalse(self.root.exists("/sys/nope"))

    def test_directories_and_listing(self):
        self.assertEqual(self.root.listdir("/sys/class/net"), ["eth0"])
        self.assertTrue(self.root.is_dir("/sys/class/net/eth0"))
        self.assertFalse(self.root.is_dir("/proc/stat"))

    def test_symlinks(self):
        link = "/sys/class/net/eth0/device/driver"
        self.assertTrue(self.root.exists(link))
        self.assertTrue(self.root.readlink(link).endswith("drivers/e1000e"))
        self.assertEqual(self.root.link_name(link), "e1000e")

    def test_reading_a_directory_returns_none(self):
        self.assertIsNone(self.root.read_text("/sys/class/net"))


if __name__ == "__main__":
    unittest.main()
