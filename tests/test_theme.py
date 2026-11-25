"""ui.theme.Theme: light/dark style."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from helpers import FakeStyleManager  # noqa: E402

import gi  # noqa: E402

gi.require_version("Adw", "1")
from gi.repository import Adw  # noqa: E402

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.ui.theme import COLOR_SCHEMES, Theme  # noqa: E402


class ColorSchemeTest(unittest.TestCase):
    def make(self, scheme="system", system_dark=False):
        self.settings = Settings.for_tests({"color-scheme": scheme})
        self.sm = FakeStyleManager(system_dark=system_dark)
        theme = Theme(self.settings, self.sm)
        self.addCleanup(theme.shutdown)
        return theme

    def test_every_style_is_a_setting_with_a_scheme(self):
        from proccoli.core.styles import STYLES
        self.assertEqual([s.id for s in STYLES], self.settings_choices())
        for s in STYLES:
            self.assertIn(s.base, COLOR_SCHEMES, s.id)

    def settings_choices(self):
        return Settings.for_tests().spec.keys["color-scheme"].choices

    def test_default_follows_the_system(self):
        self.assertEqual(Settings.for_tests().get("color-scheme"), "system")
        theme = self.make(system_dark=True)
        self.assertEqual(self.sm.scheme, Adw.ColorScheme.DEFAULT)
        self.assertTrue(theme.dark)
        changes = []
        theme.connect("changed", lambda *_: changes.append(theme.dark))
        self.sm.set_system_dark(False)               # the desktop switches
        self.assertEqual(changes, [False])

    def test_override_and_live_changes(self):
        theme = self.make("dark")
        self.assertEqual(self.sm.scheme, Adw.ColorScheme.FORCE_DARK)
        self.assertTrue(theme.dark)
        self.settings.set("color-scheme", "light")
        self.assertEqual(self.sm.scheme, Adw.ColorScheme.FORCE_LIGHT)
        self.assertFalse(theme.dark)
        self.sm.set_system_dark(True)                # ignored while forced
        self.assertFalse(theme.dark)
        self.settings.set("color-scheme", "system")
        self.assertTrue(theme.dark)

    def test_shutdown_disconnects(self):
        theme = Theme(Settings.for_tests(), sm := FakeStyleManager())
        self.assertTrue(sm.active)
        theme.shutdown()
        self.assertEqual(sm.active, set())
        theme.settings.set("color-scheme", "dark")
        self.assertEqual(sm.scheme, Adw.ColorScheme.DEFAULT)   # no longer followed



class StylesTest(unittest.TestCase):
    """Plain and tinted styles."""

    def test_the_styles(self):
        from proccoli.core.styles import STYLES
        self.assertEqual([s.name for s in STYLES[:7]],
                         ["Follow System", "Light", "Dark", "Sand", "Sky", "Mint", "Rose"])
        self.assertEqual(len({s.id for s in STYLES}), len(STYLES))
        self.assertEqual(len({s.name for s in STYLES}), len(STYLES))
        self.assertTrue(all(s.tinted for s in STYLES[3:]))

    def test_light_styles_come_before_dark_ones(self):
        # Easier to pick from: every light tint, then every dark one.
        from proccoli.core.styles import STYLES
        bases = [s.base for s in STYLES[3:]]
        self.assertEqual(bases, sorted(bases, key=lambda b: b != "light"))
        self.assertGreaterEqual(bases.count("light"), 10)
        self.assertGreaterEqual(bases.count("dark"), 12)

    def test_high_contrast_styles_are_black_on_white_and_white_on_black(self):
        from proccoli.core.styles import style_by_id
        light, dark = style_by_id("high-contrast-light"), style_by_id("high-contrast-dark")
        self.assertEqual((light.colors["view-bg-color"], light.colors["view-fg-color"]),
                         ("#ffffff", "#000000"))
        self.assertEqual((dark.colors["view-bg-color"], dark.colors["view-fg-color"]),
                         ("#000000", "#ffffff"))

    def test_text_is_readable_on_every_surface(self):
        from proccoli.core.styles import STYLES, SURFACES, contrast_ratio
        for s in STYLES:
            if not s.tinted:
                continue
            self.assertEqual(set(s.colors), set(SURFACES), s.id)
            for name, bg in s.colors.items():
                if name.endswith("-bg-color"):
                    fg = s.colors[name.replace("-bg-", "-fg-")]
                    self.assertGreaterEqual(contrast_ratio(fg, bg), 7.0, (s.id, name))

    def test_light_styles_are_light_and_dark_ones_dark(self):
        from proccoli.core.palette import hex_to_rgb, relative_luminance
        from proccoli.core.styles import STYLES
        for s in STYLES:
            if s.tinted:
                lum = relative_luminance(hex_to_rgb(s.colors["window-bg-color"]))
                self.assertEqual(lum > 0.5, s.base == "light", s.id)

    def test_css(self):
        from proccoli.core.styles import style_by_id, style_css
        self.assertEqual(style_css(style_by_id("dark")), "")
        css = style_css(style_by_id("midnight"))
        self.assertIn("--window-bg-color: #0f1420;", css)
        self.assertIn("@define-color window_bg_color #0f1420;", css)
        self.assertIn("@define-color headerbar_fg_color #dde4f0;", css)
        self.assertEqual(style_by_id("nope").id, "system")

    def test_theme_applies_base_and_surfaces(self):
        settings = Settings.for_tests({"color-scheme": "twilight"})
        sm = FakeStyleManager()
        theme = Theme(settings, sm)
        self.addCleanup(theme.shutdown)
        self.assertEqual(sm.scheme, Adw.ColorScheme.FORCE_DARK)
        self.assertTrue(theme.dark)
        self.assertIn("#2a2438", theme.css())
        changes = []
        theme.connect("changed", lambda *_: changes.append(1))
        settings.set("color-scheme", "midnight")          # dark to dark
        self.assertEqual(changes, [1])                     # surfaces still redraw
        self.assertIn("#0f1420", theme.css())
        settings.set("color-scheme", "sand")
        self.assertEqual(sm.scheme, Adw.ColorScheme.FORCE_LIGHT)
        self.assertEqual(len(changes), 2)                  # once, not twice
        settings.set("color-scheme", "light")
        self.assertNotIn("--window-bg-color", theme.css())

if __name__ == "__main__":
    unittest.main()
