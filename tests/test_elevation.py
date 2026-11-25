"""ui.elevation: optional authentication, one prompt at a time."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.ui.elevation import ElevationOffer, ElevationRunner, collect_offers  # noqa: E402


class Pending:
    """An offer whose action finishes when the test says so."""

    def __init__(self, oid, log):
        self.id, self.log, self.done = oid, log, None

    def offer(self):
        return ElevationOffer(self.id, self.id, "", self.run)

    def run(self, done):
        self.log.append(("start", self.id))
        self.done = done


class RunnerTest(unittest.TestCase):
    def test_runs_one_at_a_time_in_order(self):
        log, results = [], []
        a, b = Pending("a", log), Pending("b", log)
        runner = ElevationRunner([a.offer(), b.offer()], results.append)
        runner.start()
        self.assertEqual(log, [("start", "a")])          # b waits for a's prompt
        a.done(True)
        self.assertEqual(log, [("start", "a"), ("start", "b")])
        self.assertFalse(runner.done)
        b.done(False)                                     # cancelled: still finishes
        self.assertTrue(runner.done)
        self.assertEqual(results, [{"a": True, "b": False}])

    def test_a_failure_or_broken_offer_doesnt_stop_the_rest(self):
        log = []

        def broken(done):
            raise RuntimeError("boom")
        c = Pending("c", log)
        results = []
        ElevationRunner([ElevationOffer("x", "", "", broken), c.offer()],
                        results.append).start()
        self.assertEqual(log, [("start", "c")])
        c.done(True)
        self.assertEqual(results, [{"x": False, "c": True}])

    def test_reporting_twice_counts_once(self):
        log, results = [], []
        a, b = Pending("a", log), Pending("b", log)
        ElevationRunner([a.offer(), b.offer()], results.append).start()
        a.done(True)
        a.done(False)                                      # late duplicate
        self.assertEqual(log, [("start", "a"), ("start", "b")])
        b.done(True)
        self.assertEqual(results, [{"a": True, "b": True}])

    def test_nothing_to_do(self):
        results = []
        ElevationRunner([], results.append).start()
        self.assertEqual(results, [{}])

    def test_collect_offers_skips_pages_without_one(self):
        class Page:
            def __init__(self, offer):
                self.offer = offer

            def elevation_offer(self):
                return self.offer
        o = ElevationOffer("p", "", "", lambda done: None)
        self.assertEqual(collect_offers([Page(None), Page(o), Page(None)]), [o])


if __name__ == "__main__":
    unittest.main()
