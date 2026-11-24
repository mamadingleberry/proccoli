import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.gpu.intel_gpu_top.graph import (  # noqa: E402
    PALETTE_DARK, PALETTE_LIGHT, GraphView, _fmt_duration, _runs, display_name,
    format_axis, format_value, hex_to_rgb, nice_ceiling, snap_to_device,
    time_tick, y_divisions)


class PaletteTest(unittest.TestCase):
    def test_hex_to_rgb(self):
        self.assertEqual(hex_to_rgb("#ff0000"), (1.0, 0.0, 0.0))
        self.assertEqual(hex_to_rgb("000000"), (0.0, 0.0, 0.0))

    def test_palettes_are_valid_and_same_length(self):
        self.assertEqual(len(PALETTE_LIGHT), len(PALETTE_DARK))
        for h in PALETTE_LIGHT + PALETTE_DARK:
            self.assertRegex(h, r"^#[0-9a-f]{6}$")


class FormatValueTest(unittest.TestCase):
    def test_units(self):
        cases = [
            (None, "%", "–"),
            (12.345, "%", "12.3 %"),
            (349.9, "MHz", "350 MHz"),
            (0.425, "W", "0.42 W"),
            (800, "MiB/s", "800 MiB/s"),
            (2048, "MiB/s", "2.00 GiB/s"),
            (174.9, "irq/s", "175 irq/s"),
            (123.4, "foo", "123 foo"),
            (1.234, "foo", "1.23 foo"),
            (1.234, "", "1.23"),
            (-150, "", "-150"),
        ]
        for v, unit, expected in cases:
            self.assertEqual(format_value(v, unit), expected, (v, unit))


class FormatAxisTest(unittest.TestCase):
    def test_units(self):
        cases = [
            (50, "%", "50 %"),
            (2048, "MiB/s", "2 GiB/s"),
            (1500, "MHz", "1.5k MHz"),
            (2.5, "W", "2.5 W"),
            (2.0, "W", "2 W"),
            (0, "W", "0 W"),
            (250, "irq/s", "250 irq/s"),
        ]
        for v, unit, expected in cases:
            self.assertEqual(format_axis(v, unit), expected, (v, unit))


class NiceCeilingTest(unittest.TestCase):
    def test_values(self):
        cases = [(0, 1.0), (-5, 1.0), (1, 1), (1.1, 2), (2.2, 2.5), (3, 5),
                 (6, 10), (10, 10), (11, 20), (0.03, 0.05), (2600, 5000)]
        for v, expected in cases:
            self.assertAlmostEqual(nice_ceiling(v), expected, msg=v)

    def test_never_below_input(self):
        v = 0.001
        while v < 1e6:
            self.assertGreaterEqual(nice_ceiling(v) + 1e-9, v)
            v *= 1.37


class DurationTest(unittest.TestCase):
    def test_values(self):
        self.assertEqual(_fmt_duration(0), "0 s")
        self.assertEqual(_fmt_duration(59.4), "59 s")
        self.assertEqual(_fmt_duration(60), "1 min")
        self.assertEqual(_fmt_duration(90), "1:30")
        self.assertEqual(_fmt_duration(605), "10:05")

    def test_time_tick(self):
        self.assertEqual(time_tick(6), 1.0)
        self.assertEqual(time_tick(119), 20.0)
        self.assertEqual(time_tick(1800), 300.0)
        self.assertEqual(time_tick(10 ** 6), 3600.0)

    def test_time_tick_follows_width(self):
        # Narrow graph: fewer, wider ticks; wide graph: more of them.
        self.assertEqual(time_tick(60, 2.5), 30.0)
        self.assertEqual(time_tick(60, 12), 5.0)
        # Never fewer than two intervals' worth of target.
        self.assertEqual(time_tick(60, 0.5), 30.0)

    def test_y_divisions(self):
        self.assertEqual(y_divisions(200, 14), 4)
        self.assertEqual(y_divisions(70, 14), 2)
        self.assertEqual(y_divisions(30, 14), 1)
        # Large text needs more room per label.
        self.assertEqual(y_divisions(120, 28), 2)

    def test_snap_to_device(self):
        # 1x: odd-width lines sit on pixel centres.
        self.assertEqual(snap_to_device(10.2, 1.0, 1), 10.5)
        # 2x: a 2-device-pixel line sits on a pixel boundary.
        self.assertEqual(snap_to_device(10.2, 2.0, 2), 10.0)
        # Fractional 1.25x: lands on a device pixel centre.
        v = snap_to_device(10.0, 1.25, 1)
        self.assertAlmostEqual((v * 1.25) % 1, 0.5)


class RunsTest(unittest.TestCase):
    def test_splits_on_none(self):
        pts = [None, (0, 0), (1, 1), None, None, (2, 2), (3, 3), None, (4, 4)]
        self.assertEqual(list(_runs(pts)),
                         [[(0, 0), (1, 1)], [(2, 2), (3, 3)], [(4, 4)]])

    def test_empty(self):
        self.assertEqual(list(_runs([])), [])
        self.assertEqual(list(_runs([None, None])), [])


class DisplayNameTest(unittest.TestCase):
    def test_known_and_unknown(self):
        self.assertEqual(display_name("value"), "Residency")
        self.assertEqual(display_name("Render/3D"), "Render/3D")


class YMaxTest(unittest.TestCase):
    """GraphView._y_max only touches plain attributes, so call it unbound."""

    def _y_max(self, unit, values, fixed=None):
        stub = type("Stub", (), {})()
        stub.fixed_max, stub.unit = fixed, unit
        s = type("S", (), {})()
        s.values = values
        return GraphView._y_max(stub, [s])

    def test_fixed(self):
        self.assertEqual(self._y_max("%", [500], fixed=100.0), 100.0)

    def test_auto_with_headroom(self):
        self.assertEqual(self._y_max("W", [None, 0.9, 4.6]), 10)
        self.assertEqual(self._y_max("W", []), 1.0)
        self.assertEqual(self._y_max("W", [None, 0]), 1.0)

    def test_bandwidth_rounds_in_gib(self):
        self.assertEqual(self._y_max("MiB/s", [2000]), 2.5 * 1024)


if __name__ == "__main__":
    unittest.main()
