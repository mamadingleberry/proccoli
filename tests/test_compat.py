"""Fallbacks for the oldest supported libadwaita (``ui/compat.py``)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk  # noqa: E402

from proccoli.ui import compat  # noqa: E402

HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()


class FakeGtkSettings:
    """Just the ``props.gtk_xft_dpi`` that ``Gtk.Settings`` has."""

    def __init__(self, dpi: int) -> None:
        self.props = type("Props", (), {"gtk_xft_dpi": dpi})()


class FontDpiTest(unittest.TestCase):
    def test_unset_dpi_becomes_96(self):
        settings = FakeGtkSettings(-1)
        self.assertTrue(compat.ensure_font_dpi(settings))
        self.assertEqual(settings.props.gtk_xft_dpi, 96 * 1024)

    def test_a_desktop_dpi_is_left_alone(self):
        settings = FakeGtkSettings(120 * 1024)
        self.assertFalse(compat.ensure_font_dpi(settings))
        self.assertEqual(settings.props.gtk_xft_dpi, 120 * 1024)

    def test_no_settings(self):
        self.assertFalse(compat.ensure_font_dpi(None))


class CssVariablesTest(unittest.TestCase):
    def test_gtk_versions(self):
        def gtk(minor):
            return type("Gtk", (), {"get_major_version": staticmethod(lambda: 4),
                                    "get_minor_version": staticmethod(lambda: minor)})
        self.assertFalse(compat.has_css_variables(gtk(14)))     # Ubuntu 24.04
        self.assertTrue(compat.has_css_variables(gtk(16)))
        self.assertTrue(compat.has_css_variables(gtk(20)))

    def test_root_rules_are_dropped_and_the_rest_kept(self):
        css = (":root { --accent-bg-color: #3465a4; }\n"
               "@define-color accent_bg_color #3465a4;\n"
               ":root { --window-bg-color: #fff; --view-bg-color: #eee; }\n"
               ".entry-color-0 > trough > progress { background-color: #3465a4; }\n")
        out = compat.without_css_variables(css)
        self.assertNotIn(":root", out)
        self.assertNotIn("--", out)
        self.assertIn("@define-color accent_bg_color #3465a4;", out)
        self.assertIn(".entry-color-0 > trough > progress", out)
        self.assertEqual(compat.without_css_variables("a { b: c; }"), "a { b: c; }")


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class SpinnerTest(unittest.TestCase):
    def test_without_adw_spinner_a_spinning_gtk_spinner(self):
        old_adw = type("OldAdw", (), {})          # libadwaita 1.5: no Spinner
        widget = compat.spinner(adw=old_adw, width_request=32)
        self.assertIsInstance(widget, Gtk.Spinner)
        self.assertTrue(widget.get_spinning())
        self.assertEqual(widget.get_property("width-request"), 32)

    def test_with_adw_spinner_it_is_used(self):
        made = []

        class NewAdw:
            @staticmethod
            def Spinner(**props):              # noqa: N802 (a class in libadwaita)
                made.append(props)
                return Gtk.Label()
        compat.spinner(adw=NewAdw, visible=False)
        self.assertEqual(made, [{"visible": False}])


if __name__ == "__main__":
    unittest.main()
