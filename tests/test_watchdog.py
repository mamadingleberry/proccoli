"""core.watchdog: a frozen main loop is logged with stacks."""

import logging
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.watchdog import SAMPLES, StallWatchdog, format_stacks  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class WatchdogTest(unittest.TestCase):
    def make(self):
        self.clock = Clock()
        self.slept = []
        logger = logging.getLogger("proccoli.test-watchdog")
        dog = StallWatchdog(logger, timeout_s=3.0, clock=self.clock,
                            stacks=lambda: "STACKS", sleep=self.slept.append)
        return dog, logger

    def test_quiet_while_the_heartbeat_comes(self):
        dog, _ = self.make()
        for _ in range(20):
            self.clock.t += 0.25
            dog.beat()
            self.assertIsNone(dog.check())

    def test_stall_is_logged_once_with_samples_then_recovery(self):
        dog, logger = self.make()
        dog.beat()
        self.clock.t += 2.9
        self.assertIsNone(dog.check())
        self.clock.t += 0.2
        with self.assertLogs(logger, "ERROR") as logs:
            self.assertEqual(dog.check(), "stalled")
        text = logs.output[0]
        self.assertIn("stalled for 3.1 s", text)
        self.assertEqual(text.count("STACKS"), SAMPLES)
        self.assertEqual(len(self.slept), SAMPLES - 1)
        self.clock.t += 10
        self.assertIsNone(dog.check())                       # once per stall
        dog.beat()
        with self.assertLogs(logger, "WARNING") as logs:
            self.assertEqual(dog.check(), "recovered")
        self.assertIn("after 13.1 s", logs.output[0])

    def test_format_stacks_lists_threads_main_first(self):
        text = format_stacks()
        self.assertTrue(text.startswith("Thread MainThread:"))
        self.assertIn("test_format_stacks_lists_threads_main_first", text)
        done = threading.Event()
        t = threading.Thread(target=done.wait, name="worker-x")
        t.start()
        try:
            self.assertIn("Thread worker-x:", format_stacks())
        finally:
            done.set()
            t.join()

    def test_start_schedules_the_heartbeat_and_stop_ends_the_thread(self):
        scheduled = []
        dog = StallWatchdog(schedule=lambda ms, cb: scheduled.append((ms, cb)) or 0)
        dog.start()
        self.assertEqual(scheduled[0][0], 250)
        self.assertTrue(scheduled[0][1]())                    # keeps beating
        dog.stop()
        dog._thread.join(timeout=2)
        self.assertFalse(dog._thread.is_alive())


if __name__ == "__main__":
    unittest.main()
