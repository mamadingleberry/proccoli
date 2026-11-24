import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.ui.window_state import restore_window_state, save_window_state  # noqa: E402


class FakeWindow:
    def __init__(self, size=(0, 0), maximized=False):
        self.size = size
        self.maximized = maximized

    def set_default_size(self, w, h):
        self.size = (w, h)

    def get_default_size(self):
        return self.size

    def maximize(self):
        self.maximized = True

    def is_maximized(self):
        return self.maximized


class WindowStateTest(unittest.TestCase):
    def test_round_trip(self):
        settings = Settings.for_tests()
        save_window_state(FakeWindow((1280, 800)), settings)
        win = FakeWindow()
        restore_window_state(win, settings)
        self.assertEqual(win.size, (1280, 800))
        self.assertFalse(win.maximized)

    def test_defaults_on_first_run(self):
        win = FakeWindow()
        restore_window_state(win, Settings.for_tests())
        self.assertEqual(win.size, (1000, 700))

    def test_maximized_keeps_the_unmaximized_size(self):
        settings = Settings.for_tests({"window-width": 900, "window-height": 600})
        save_window_state(FakeWindow((2560, 1400), maximized=True), settings)
        self.assertTrue(settings.get("is-maximized"))
        win = FakeWindow()
        restore_window_state(win, settings)
        self.assertEqual(win.size, (900, 600))
        self.assertTrue(win.maximized)

    def test_unset_size_is_not_saved(self):
        settings = Settings.for_tests()
        save_window_state(FakeWindow((0, 0)), settings)
        self.assertEqual(settings.get("window-width"), 1000)


if __name__ == "__main__":
    unittest.main()
