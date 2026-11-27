"""core.background: turning proccoli on and off, with a fake System."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from helpers import FakeSystem  # noqa: E402
from proccoli.core.background import (BackgroundService, BackgroundState, linger_on,  # noqa: E402
                                      parse_enabled, should_offer_linger, start_at_boot,
                                      status_text)

UNIT = "proccoli.service"


def system(*results):
    s = FakeSystem(programs={"systemctl": "/usr/bin/systemctl",
                             "loginctl": "/usr/bin/loginctl"})
    s.run_results = list(results)
    return s


class ParseTest(unittest.TestCase):
    def test_states(self):
        self.assertEqual(parse_enabled(0, "enabled\n", ""), (True, True, ""))
        self.assertEqual(parse_enabled(1, "disabled\n", ""), (True, False, ""))
        available, enabled, reason = parse_enabled(
            1, "", "Failed to get unit file state for proccoli.service: "
                   "No such file or directory")
        self.assertFalse(available)
        self.assertEqual(reason, "proccoli isn't installed")
        available, _, reason = parse_enabled(1, "", "Failed to connect to bus")
        self.assertFalse(available)
        self.assertIn("No user systemd", reason)


class ServiceTest(unittest.TestCase):
    def test_refresh_asks_systemd_and_logind(self):
        s = system((0, "enabled\n", ""), (0, "active\n", ""), (0, "yes\n", ""))
        states = []
        BackgroundService(s).refresh(states.append)
        self.assertEqual(states[0], BackgroundState(True, True, True, True))
        self.assertEqual(s.runs, [["systemctl", "--user", "is-enabled", UNIT],
                                  ["systemctl", "--user", "is-active", UNIT],
                                  ["loginctl", "show-user", "1000", "--property=Linger",
                                   "--value"]])

    def test_not_installed_stops_early(self):
        s = system((1, "", "No such file or directory"))
        states = []
        BackgroundService(s).refresh(states.append)
        self.assertFalse(states[0].available)
        self.assertEqual(len(s.runs), 1)

    def test_without_systemctl(self):
        s = FakeSystem()
        states = []
        BackgroundService(s).refresh(states.append)
        self.assertEqual(states[0].reason, "systemctl isn't available")
        self.assertEqual(s.runs, [])

    def test_turning_on_and_at_boot(self):
        s = system()
        BackgroundService(s).set_enabled(True, lambda st: None)
        self.assertEqual(s.runs[0], ["systemctl", "--user", "enable", "--now", UNIT])
        s = system()
        BackgroundService(s).set_enabled(False, lambda st: None)
        self.assertEqual(s.runs[0], ["systemctl", "--user", "disable", "--now", UNIT])
        s = system()
        BackgroundService(s).set_linger(True, lambda st: None)
        self.assertEqual(s.runs[0], ["loginctl", "enable-linger", "1000"])


class StartAtBootTest(unittest.TestCase):
    """Recording from boot: when the window asks, and the command line."""

    def test_when_to_offer(self):
        on = BackgroundState(available=True, enabled=True)
        self.assertTrue(should_offer_linger(on, offered=False, history_on=True))
        self.assertFalse(should_offer_linger(on, offered=True, history_on=True))   # once
        self.assertFalse(should_offer_linger(on, offered=False, history_on=False))
        for state in (BackgroundState(available=True, enabled=True, linger=True),
                      BackgroundState(available=True, enabled=False),
                      BackgroundState()):
            self.assertFalse(should_offer_linger(state, offered=False, history_on=True), state)

    def test_linger_on(self):
        s = system((0, "no\n", ""))
        self.assertIs(linger_on(s), False)
        self.assertEqual(s.runs, [["loginctl", "show-user", "1000", "--property=Linger",
                                   "--value"]])
        self.assertIs(linger_on(system((0, "yes\n", ""))), True)
        self.assertIsNone(linger_on(system((1, "", "no logind"))))
        self.assertIsNone(linger_on(FakeSystem()))                    # no loginctl

    def test_turning_it_on_and_off(self):
        s = system((0, "", ""), (0, "enabled\n", ""))
        ok, text = start_at_boot(s, True)
        self.assertTrue(ok)
        self.assertIn("from boot", text)
        self.assertNotIn("itself is off", text)
        self.assertEqual(s.runs[0], ["loginctl", "enable-linger", "1000"])
        s = system((0, "", ""))
        ok, text = start_at_boot(s, False)
        self.assertTrue(ok)
        self.assertEqual(s.runs, [["loginctl", "disable-linger", "1000"]])

    def test_says_when_the_recorder_itself_is_off(self):
        ok, text = start_at_boot(system((0, "", ""), (1, "disabled\n", "")), True)
        self.assertTrue(ok)
        self.assertIn(f"systemctl --user enable --now {UNIT}", text)

    def test_failures(self):
        ok, text = start_at_boot(FakeSystem(), True)
        self.assertFalse(ok)
        self.assertIn("loginctl isn't available", text)
        ok, text = start_at_boot(system((1, "", "Access denied")), True)
        self.assertFalse(ok)
        self.assertIn("Access denied", text)


class StatusTextTest(unittest.TestCase):
    def test_lines(self):
        self.assertEqual(status_text(None, False, False), "Not recording: Keep History is off")
        self.assertEqual(status_text(None, True, True), "Recording while Proccoli is open")
        writer = {"program": "proccoli", "since": 1795600000000}
        self.assertEqual(status_text(writer, False, True),
                         "Recording in the background since 2026-11-25 09:46 UTC")
        self.assertEqual(status_text(None, False, True,
                                     BackgroundState(True, True, False)),
                         "Background recording is on but not running")


if __name__ == "__main__":
    unittest.main()
