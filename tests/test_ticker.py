import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.ticker import UPDATE_INTERVALS_MS, Ticker, interval_for  # noqa: E402


class FakeLoop:
    """Stands in for GLib.timeout_add() / source_remove and the clock."""

    def __init__(self):
        self.now = 100.0
        self.sources = {}       # id -> (interval_ms, callback)
        self.next_id = 1

    def timeout_add(self, interval, cb):
        sid = self.next_id
        self.next_id += 1
        self.sources[sid] = (interval, cb)
        return sid

    def source_remove(self, sid):
        del self.sources[sid]

    def clock(self):
        return self.now

    def fire(self):
        """Advance time by each source's interval and run it."""
        for sid, (interval, cb) in list(self.sources.items()):
            self.now += interval / 1000
            if not cb():
                del self.sources[sid]


def make(interval=1000):
    loop = FakeLoop()
    t = Ticker(interval, timeout_add=loop.timeout_add,
               source_remove=loop.source_remove, clock=loop.clock)
    ticks = []
    t.connect("tick", lambda _t, now: ticks.append(now))
    return t, loop, ticks


class TickerTest(unittest.TestCase):
    def test_start_ticks_immediately_then_every_interval(self):
        t, loop, ticks = make(1000)
        t.start()
        self.assertEqual(ticks, [100.0])
        loop.fire()
        loop.fire()
        self.assertEqual(ticks, [100.0, 101.0, 102.0])
        self.assertTrue(t.running)

    def test_start_twice_is_harmless(self):
        t, loop, ticks = make()
        t.start()
        t.start()
        self.assertEqual(len(loop.sources), 1)
        self.assertEqual(len(ticks), 1)

    def test_stop(self):
        t, loop, ticks = make()
        t.start()
        t.stop()
        loop.fire()
        self.assertEqual(len(ticks), 1)
        self.assertFalse(t.running)
        self.assertEqual(loop.sources, {})

    def test_set_interval_rearms_a_running_timer(self):
        t, loop, ticks = make(1000)
        t.start()
        t.set_interval(250)
        self.assertEqual([i for i, _ in loop.sources.values()], [250])
        loop.fire()
        self.assertEqual(ticks[-1], 100.25)

    def test_set_interval_when_stopped(self):
        t, loop, _ = make(1000)
        t.set_interval(500)
        self.assertEqual(loop.sources, {})
        t.start()
        self.assertEqual([i for i, _ in loop.sources.values()], [500])

    def test_invalid_interval(self):
        with self.assertRaises(ValueError):
            Ticker(0)
        t, _, _ = make()
        with self.assertRaises(ValueError):
            t.set_interval(-1)

    def test_follows_the_update_interval(self):
        settings = Settings.for_tests({"update-interval": "2-seconds"})
        t, loop, _ = make(1000)
        t.follow(settings)
        self.assertEqual(t.interval_ms, 2000)
        settings.set("update-interval", "10-seconds")
        self.assertEqual(t.interval_ms, 10000)

    def test_every_schema_interval_has_milliseconds(self):
        settings = Settings.for_tests()
        nicks = settings.spec.keys["update-interval"].choices
        self.assertEqual(sorted(nicks), sorted(UPDATE_INTERVALS_MS))
        self.assertEqual(interval_for("bogus"), 1000)
        self.assertEqual(min(UPDATE_INTERVALS_MS.values()), 1000)     # never faster

    def test_old_refresh_speeds_map_to_intervals(self):
        self.assertEqual(interval_for("very-fast"), 1000)
        self.assertEqual(interval_for("fast"), 1000)
        self.assertEqual(interval_for("slow"), 2000)
        self.assertEqual(interval_for("very-slow"), 5000)


class TimeRangeTest(unittest.TestCase):
    """Graphs keep a time range, not a number of points."""

    def test_points_follow_range_and_refresh(self):
        from proccoli.core.settings import Settings
        from proccoli.core.ticker import TIME_RANGES_S, graph_points, history_points
        self.assertEqual(history_points(60, 1000), 61)
        self.assertEqual(history_points(60, 250), 241)
        self.assertEqual(history_points(600, 4000), 151)
        self.assertEqual(history_points(0, 1000), 2)
        s = Settings.for_tests()
        self.assertEqual(graph_points(s), 61)                    # 1 minute at 1 s
        for nick, seconds in TIME_RANGES_S.items():
            s.set("graph-time-range", nick)                      # every nick is in the schema
            if seconds <= 600:
                self.assertEqual(graph_points(s), seconds + 1)
            else:
                self.assertLessEqual(graph_points(s), 1200)        # averaged

    def test_long_ranges_average_samples(self):
        # History follow-ups: at most MAX_GRAPH_POINTS points per graph.
        from proccoli.core.settings import Settings
        from proccoli.core.ticker import graph_plan, history_plan
        self.assertEqual(history_plan(600, 1000), (601, 1))
        self.assertEqual(history_plan(600, 250), (801, 3))         # 2401 samples
        self.assertEqual(history_plan(86400, 1000), (1184, 73))     # a day at 1 s
        self.assertEqual(history_plan(3600, 1000), (901, 4))
        s = Settings.for_tests({"graph-time-range": "1-hour", "update-interval": "2-seconds"})
        self.assertEqual(graph_plan(s), (901, 2, 4.0))

    def test_unknown_nick_is_one_minute(self):
        from proccoli.core.ticker import preset_s
        self.assertEqual(preset_s("forever"), 60)
        self.assertEqual(preset_s("custom"), 60)


class CustomRangeTest(unittest.TestCase):
    """any range from 10 seconds to 30 days."""

    def range_s(self, **overrides):
        from proccoli.core.ticker import time_range_s
        return time_range_s(Settings.for_tests(overrides))

    def test_presets_unchanged(self):
        self.assertEqual(self.range_s(), 60)
        self.assertEqual(self.range_s(**{"graph-time-range": "6-hours"}), 21600)
        # A stored custom value doesn't matter until Custom is chosen.
        self.assertEqual(self.range_s(**{"graph-time-range-custom": 999}), 60)

    def test_custom_seconds(self):
        self.assertEqual(self.range_s(**{"graph-time-range": "custom",
                                         "graph-time-range-custom": 5400}), 5400)

    def test_clamped_at_both_ends_and_to_two_intervals(self):
        from proccoli.core.ticker import MAX_RANGE_S, clamp_range_s
        self.assertEqual(clamp_range_s(3), 10)
        self.assertEqual(clamp_range_s(40 * 86400), MAX_RANGE_S)
        self.assertEqual(clamp_range_s(10, 10_000), 20)            # 10 s interval
        self.assertEqual(self.range_s(**{"graph-time-range": "custom",
                                         "graph-time-range-custom": 10,
                                         "update-interval": "10-seconds"}), 20)

    def test_thirty_days_stays_under_the_point_cap(self):
        from proccoli.core.ticker import MAX_GRAPH_POINTS, MAX_RANGE_S, graph_plan, history_plan
        for interval in (1000, 2000, 10000):
            points, every = history_plan(MAX_RANGE_S, interval)
            self.assertLessEqual(points, MAX_GRAPH_POINTS)
        s = Settings.for_tests({"graph-time-range": "custom",
                                "graph-time-range-custom": MAX_RANGE_S})
        points, every, step_s = graph_plan(s)
        self.assertLessEqual(points, MAX_GRAPH_POINTS)
        # Covers the range to within one point, as every long range does.
        self.assertGreater(step_s * points, MAX_RANGE_S)

    def test_every_listener_follows_the_custom_key(self):
        from proccoli.core.ticker import CUSTOM_KEY, PLAN_KEYS, RANGE_KEYS
        from proccoli.ui.chart_settings import GRAPH_KEYS
        self.assertIn(CUSTOM_KEY, RANGE_KEYS)
        self.assertTrue(set(PLAN_KEYS) <= set(GRAPH_KEYS))


if __name__ == "__main__":
    unittest.main()
