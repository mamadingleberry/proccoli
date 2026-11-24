import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from proccoli.gpu.intel_gpu_top.clients import ClientRow, _cmp  # noqa: E402


class ClientRowTest(unittest.TestCase):
    def test_update_parses_intel_gpu_top_client(self):
        row = ClientRow("4293188474")
        row.update({
            "name": "Xorg",
            "pid": "1876",
            "engine-classes": {
                "Render/3D": {"busy": "9.871340", "unit": "%"},
                "Video": {"busy": "0.5", "unit": "%"},
                "Bad": {"busy": "n/a"},
                "Junk": "x",
            },
        })
        self.assertEqual(row.name, "Xorg")
        self.assertEqual(row.pid, 1876)
        self.assertEqual(row.busy, {"Render/3D": 9.87134, "Video": 0.5})
        self.assertAlmostEqual(row.total, 10.37134)
        self.assertEqual(row.revision, 1)

    def test_update_tolerates_missing_or_bad_fields(self):
        row = ClientRow("1")
        row.update({"pid": "abc", "engine-classes": None})
        self.assertEqual((row.name, row.pid, row.busy, row.total), ("", 0, {}, 0))
        row.update({"engine-classes": ["x"]})
        self.assertEqual(row.busy, {})
        self.assertEqual(row.revision, 2)

    def test_update_replaces_busy(self):
        row = ClientRow("1")
        row.update({"engine-classes": {"A": {"busy": 1}}})
        row.update({"engine-classes": {"B": {"busy": 2}}})
        self.assertEqual(row.busy, {"B": 2.0})


class CmpTest(unittest.TestCase):
    def test_cmp(self):
        self.assertEqual(_cmp(1, 2), -1)
        self.assertEqual(_cmp(2, 2), 0)
        self.assertEqual(_cmp("b", "a"), 1)


if __name__ == "__main__":
    unittest.main()
