"""gpu.intel_gpu_top.labels: the Intel Details tab's legend names. Its
numbers are formatted by core.units since Idea 4 (test_units)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.gpu.intel_gpu_top.labels import display_name  # noqa: E402


class DisplayNameTest(unittest.TestCase):
    def test_known_and_unknown(self):
        self.assertEqual(display_name("value"), "Residency")
        self.assertEqual(display_name("Render/3D"), "Render/3D")


if __name__ == "__main__":
    unittest.main()
