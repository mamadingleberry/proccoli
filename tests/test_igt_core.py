import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.gpu.intel_gpu_top.history import History, flatten_sample  # noqa: E402
from proccoli.core.jsonstream import JsonStreamParser  # noqa: E402

# Abridged real output of `intel_gpu_top -J` (igt 1.28).
STREAM = """[
{
	"period": {
		"duration": 1000.290045,
		"unit": "ms"
	},
	"frequency": {
		"requested": 349.899050,
		"actual": 349.899050,
		"unit": "MHz"
	},
	"interrupts": {
		"count": 174.915270,
		"unit": "irq/s"
	},
	"rc6": {
		"value": 81.548720,
		"unit": "%"
	},
	"power": {
		"GPU": 0.425093,
		"Package": 4.938290,
		"unit": "W"
	},
	"engines": {
		"Render/3D": {
			"busy": 10.234030,
			"sema": 0.000000,
			"wait": 0.000000,
			"unit": "%"
		},
		"Video": {
			"busy": 0.000000,
			"sema": 0.000000,
			"wait": 0.000000,
			"unit": "%"
		}
	},
	"clients": {
		"4293188474": {
			"name": "Xorg",
			"pid": "1876",
			"engine-classes": {
				"Render/3D": {
					"busy": "9.871340",
					"unit": "%"
				}
			}
		}
	}
},
{
	"period": {
		"duration": 1000.1,
		"unit": "ms"
	},
	"rc6": {
		"value": 90.0,
		"unit": "%"
	},
	"engines": {
		"Render/3D": {"busy": 3.0, "sema": 0.0, "wait": 0.0, "unit": "%"}
	}
}"""


class ParserTest(unittest.TestCase):
    def test_whole_stream(self):
        objs = JsonStreamParser().feed(STREAM)
        self.assertEqual(len(objs), 2)
        self.assertAlmostEqual(objs[0]["rc6"]["value"], 81.54872)

    def test_byte_by_byte(self):
        p = JsonStreamParser()
        objs = []
        for ch in STREAM:
            objs += p.feed(ch)
        self.assertEqual(len(objs), 2)

    def test_garbage_prefix(self):
        objs = JsonStreamParser().feed("warning: blah\n[\n{\"a\": 1},\n{\"a\": 2}")
        self.assertEqual([o["a"] for o in objs], [1, 2])


class HistoryTest(unittest.TestCase):
    def test_flatten(self):
        sample = JsonStreamParser().feed(STREAM)[0]
        g = flatten_sample(sample)
        self.assertEqual(g["engines"][0], "%")
        self.assertEqual(set(g["engines"][1]), {"Render/3D", "Video"})
        self.assertEqual(g["power"][1]["Package"], 4.93829)
        self.assertNotIn("period", g)
        self.assertNotIn("clients", g)

    def test_alignment_and_csv(self):
        a, b = JsonStreamParser().feed(STREAM)
        h = History(max_points=3)
        h.add(b, 1.0)          # Video / power unknown yet
        h.add(a, 2.0)
        h.add(b, 3.0)
        h.add(a, 4.0)          # rolls over max_points
        self.assertEqual(len(h.times), 3)
        for s in h.series.values():
            self.assertEqual(len(s.values), 3, s.name)
        self.assertEqual(list(h.series[("engines", "Video")].values), [0.0, None, 0.0])
        h.add_gap(5.0)
        self.assertIsNone(h.series[("rc6", "value")].values[-1])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.csv")
            h.write_csv(path)
            with open(path) as fh:
                lines = fh.read().splitlines()
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[0].startswith("timestamp,"))


if __name__ == "__main__":
    unittest.main()
