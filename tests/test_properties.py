"""Randomized invariant tests (fixed seeds, so failures reproduce)."""

import json
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from helpers import FakeRoot  # noqa: E402

from proccoli.core import units  # noqa: E402
from proccoli.core.history import History  # noqa: E402
from proccoli.core.jsonstream import JsonStreamParser  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.devices.cpu import busy_percent  # noqa: E402
from proccoli.gpu.fdinfo import FdinfoReader  # noqa: E402
from proccoli.ui.layout import split_columns  # noqa: E402
from proccoli.processes.apps import app_id_for_cgroup  # noqa: E402
from proccoli.processes.model import parse_stat  # noqa: E402
from proccoli.ui.widgets.graph import graph_runs, nice_ceiling, snap_to_device  # noqa: E402

TRIALS = 300


def random_json(rnd, depth=0):
    kind = rnd.choice(["int", "float", "str", "dict", "list"] if depth < 3 else ["int", "str"])
    if kind == "int":
        return rnd.randint(-10**6, 10**6)
    if kind == "float":
        return rnd.uniform(-1e6, 1e6)
    if kind == "str":
        return "".join(rnd.choice('ab ,[]{}:"\\\n/é') for _ in range(rnd.randint(0, 12)))
    if kind == "list":
        return [random_json(rnd, depth + 1) for _ in range(rnd.randint(0, 4))]
    return {f"k{i}": random_json(rnd, depth + 1) for i in range(rnd.randint(0, 4))}


class StreamParserProperties(unittest.TestCase):
    def test_any_chunking_yields_the_same_objects(self):
        rnd = random.Random(1)
        for _ in range(TRIALS):
            objs = [{"n": i, "v": random_json(rnd)} for i in range(rnd.randint(1, 6))]
            text = "[\n" + "".join(json.dumps(o) + ",\n" for o in objs)
            p, out, i = JsonStreamParser(), [], 0
            while i < len(text):
                step = rnd.randint(1, 40)
                out += p.feed(text[i:i + step])
                i += step
            self.assertEqual(out, objs)


class GraphProperties(unittest.TestCase):
    def test_runs_stay_inside_the_plot(self):
        rnd = random.Random(2)
        for _ in range(TRIALS):
            cap = rnd.randint(2, 120)
            values = [None if rnd.random() < 0.15 else rnd.uniform(-50, 250)
                      for _ in range(rnd.randint(0, cap))]
            w, h, ymax = rnd.uniform(10, 1000), rnd.uniform(10, 500), rnd.uniform(1, 200)
            runs = graph_runs(values, cap, w, h, ymax)
            self.assertEqual(sum(len(r) for r in runs), sum(v is not None for v in values))
            for run in runs:
                xs = [x for x, _ in run]
                self.assertEqual(xs, sorted(xs))
                for x, y in run:
                    self.assertTrue(-1e-6 <= x <= w + 1e-6 and -1e-6 <= y <= h + 1e-6)

    def test_nice_ceiling_is_a_nice_upper_bound(self):
        rnd = random.Random(3)
        for _ in range(TRIALS):
            v = 10 ** rnd.uniform(-3, 12)
            c = nice_ceiling(v)
            self.assertGreaterEqual(c * (1 + 1e-9), v)
            self.assertLessEqual(c, v * 2.5 * (1 + 1e-9))
            mantissa = c / 10 ** math.floor(math.log10(c) + 1e-9)
            self.assertTrue(any(abs(mantissa - m) < 1e-6 for m in (1, 2, 2.5, 5, 10)))

    def test_snapped_lines_land_on_the_pixel_grid(self):
        rnd = random.Random(4)
        for _ in range(TRIALS):
            scale = rnd.choice([1, 1.25, 1.5, 1.75, 2, 3])
            width = rnd.choice([1, 2, 3])
            frac = (snap_to_device(rnd.uniform(0, 2000), scale, width) * scale) % 1
            self.assertAlmostEqual(frac, 0.5 if width % 2 else 0.0, places=6)


class HistoryProperties(unittest.TestCase):
    def test_series_stay_aligned_under_any_operations(self):
        rnd = random.Random(5)
        for _ in range(100):
            h = History(rnd.randint(2, 30))
            names = ["a", "b", "c", "d"]
            t = 0.0
            for _ in range(rnd.randint(0, 80)):
                op = rnd.random()
                t += 1
                if op < 0.6:
                    h.add(t, {n: rnd.random() for n in rnd.sample(names, rnd.randint(0, 4))})
                elif op < 0.7:
                    h.add_gap(t)
                elif op < 0.8:
                    h.set_max_points(rnd.randint(2, 30))
                elif op < 0.9:
                    h.define(rnd.choice(names))
                else:
                    h.clear()
                for s in h:
                    self.assertEqual(len(s.values), len(h.times))
                    self.assertEqual(s.capacity, h.max_points)
                self.assertLessEqual(len(h.times), h.max_points)


class UnitsProperties(unittest.TestCase):
    def test_formatters_never_fail(self):
        rnd = random.Random(6)
        values = [0, -0.0, 1e-12, -5, 1e30, -1e30, 999.999, 1023.99] + \
                 [rnd.uniform(-1e15, 1e15) for _ in range(TRIALS)]
        for v in values:
            for base in units.Base:
                self.assertTrue(units.format_bytes(v, base))
                self.assertTrue(units.format_rate(v, base, bits=rnd.random() < .5))
            for unit in units.TemperatureUnit:
                self.assertTrue(units.format_temperature(v, unit))
            for fn in (units.format_percent, units.format_frequency, units.format_power,
                       units.format_duration):
                self.assertTrue(fn(v))

    def test_scaled_numbers_stay_below_the_next_prefix(self):
        rnd = random.Random(7)
        for _ in range(TRIALS):
            v = 10 ** rnd.uniform(0, 17)
            text = units.format_bytes(v)
            number = float(text.split()[0])
            self.assertLess(number, 1000)


class ParsingProperties(unittest.TestCase):
    def test_stat_survives_any_command_name(self):
        rnd = random.Random(8)
        for _ in range(TRIALS):
            name = "".join(rnd.choice("ab ()x)(-:") for _ in range(rnd.randint(0, 15)))
            line = (f"77 ({name}) R 1 2 3 4 5 6 7 8 9 10 {rnd.randint(0, 999)} "
                    f"{rnd.randint(0, 999)} 0 0 20 {rnd.randint(-20, 19)} 1 0 555 0 0\n")
            p = parse_stat(line, 77)
            self.assertEqual((p.name, p.starttime), (name, 555))

    def test_cgroup_parsing_never_fails(self):
        rnd = random.Random(9)
        alphabet = "app-gnome.slice/scope_flatpak\\x2d@snap-0123456789."
        for _ in range(TRIALS * 3):
            cg = "".join(rnd.choice(alphabet) for _ in range(rnd.randint(0, 60)))
            result = app_id_for_cgroup(cg)
            self.assertTrue(result is None or isinstance(result, str))

    def test_cpu_busy_is_a_percentage(self):
        rnd = random.Random(10)
        for _ in range(TRIALS):
            prev = [rnd.randint(0, 10**6) for _ in range(8)]
            cur = [p + rnd.randint(0, 10**4) for p in prev]
            b = busy_percent(prev, cur)
            self.assertTrue(b is None or 0.0 <= b <= 100.0)


class FdinfoProperties(unittest.TestCase):
    def test_usage_is_always_a_percentage(self):
        rnd = random.Random(11)
        root = FakeRoot(self)
        reader = FdinfoReader(root.sysroot, "0000:00:02.0")
        counters = {pid: {"render": 0, "video": 0} for pid in range(100, 106)}
        for pid in counters:
            root.link(f"/proc/{pid}/fd/3", "/dev/dri/renderD128")
        now = 0.0
        for _ in range(40):
            now += rnd.uniform(0.1, 2.0)
            for pid, c in counters.items():
                for e in c:   # sometimes faster than real time (multi-instance engines)
                    c[e] += int(rnd.uniform(0, 1.5e9))
                root.write(f"/proc/{pid}/fdinfo/3",
                           f"drm-driver:\ti915\ndrm-client-id:\t{pid}\n"
                           f"drm-pdev:\t0000:00:02.0\ndrm-engine-render:\t{c['render']} ns\n"
                           f"drm-engine-video:\t{c['video']} ns\n")
            reader.read(now)
            for usage in reader.processes.values():
                for v in (usage.usage, usage.encode, usage.decode):
                    self.assertTrue(0.0 <= v <= 100.0)
            for v in reader.engines.values():
                self.assertTrue(0.0 <= v <= 100.0)


class ColumnSplitProperties(unittest.TestCase):
    def test_split_keeps_order_and_items(self):
        rnd = random.Random(12)
        for _ in range(TRIALS):
            heights = [rnd.randint(1, 500) for _ in range(rnd.randint(0, 8))]
            n = rnd.randint(1, 4)
            cols = split_columns(heights, n)
            self.assertEqual(sum(cols, []), list(range(len(heights))))
            self.assertLessEqual(len(cols), max(1, n))


class SettingsProperties(unittest.TestCase):
    def test_valid_values_round_trip_and_invalid_ones_change_nothing(self):
        rnd = random.Random(13)
        s = Settings.for_tests()
        for _ in range(TRIALS):
            key = rnd.choice(s.keys())
            spec = s.spec.keys[key]
            before = s.get(key)
            if spec.choices:
                value = rnd.choice(spec.choices + ["not-a-choice"])
            elif spec.type == "b":
                value = rnd.choice([True, False])
            elif spec.type in ("i", "u"):
                value = rnd.randint(-100, 2000)
            elif spec.type == "as":
                value = rnd.choice([[], [f"0000:0{rnd.randint(0, 9)}:00.0"], "a-string"])
            else:
                value = rnd.choice(["", "x", "very-fast"])
            try:
                s.set(key, value)
            except ValueError:
                self.assertEqual(s.get(key), before)
                continue
            self.assertEqual(s.get(key), value)


if __name__ == "__main__":
    unittest.main()
