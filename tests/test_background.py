"""core.background: turning proccoli on and off, with a fake System."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from helpers import FakeSystem  # noqa: E402
from proccoli.core.background import (BackgroundService, BackgroundState, parse_enabled,  # noqa: E402
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
