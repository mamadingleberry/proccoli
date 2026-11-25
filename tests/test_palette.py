"""core.palette and the Theme's colors."""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from helpers import FakeStyleManager  # noqa: E402

from proccoli.core.palette import (PALETTES, accent_of, entry_colors,  # noqa: E402
                                  hex_to_rgb, mix, offline_rgba, palette_by_id, palette_without,
                                  relative_luminance, rgb_to_hex, secondary, series_colors)
from proccoli.core.settings import Settings  # noqa: E402

ADWAITA_BLUE = hex_to_rgb("#3584e4")
UBUNTU_ORANGE = hex_to_rgb("#e95420")


class PaletteDataTest(unittest.TestCase):
    def test_palettes_have_unique_ids_matching_the_schema(self):
        ids = [p.id for p in PALETTES]
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(ids, Settings.for_tests().spec.keys["palette"].choices)
        self.assertEqual(Settings.for_tests().get("palette"), "system")
        self.assertEqual(len(set(p.name for p in PALETTES)), len(PALETTES))

    def test_color_blind_safe_palettes_come_first(self):
        # Right after System, where people looking for them see them first.
        safe = [p.id for p in PALETTES if "Color-Blind Safe" in p.name]
        self.assertEqual(safe, ["okabe-ito", "tol-bright", "tol-vibrant", "tol-muted", "viridis"])
        self.assertEqual([p.id for p in PALETTES[1:6]], safe)

    def test_okabe_ito_is_the_published_set(self):
        okabe = palette_by_id("okabe-ito")
        published = {"#e69f00", "#56b4e9", "#009e73", "#f0e442", "#0072b2", "#d55e00", "#cc79a7"}
        self.assertTrue(set(okabe.light + okabe.dark) <= published)

    def test_colors_are_valid_and_light_dark_match(self):
        for p in PALETTES:
            self.assertEqual(len(p.light), len(p.dark), p.id)
            self.assertGreaterEqual(len(p.light), 6, p.id)
            for h in p.light + p.dark:
                self.assertRegex(h, r"^#[0-9a-f]{6}$", p.id)

    def test_no_adjacent_duplicates(self):
        for p in PALETTES:
            for colors in (p.light, p.dark):
                for a, b in zip(colors, colors[1:]):
                    self.assertNotEqual(a, b, p.id)

    def test_colors_show_on_their_surface(self):
        # Light variants avoid near-white, dark variants near-black.
        for p in PALETTES:
            for h in p.light:
                self.assertLess(relative_luminance(hex_to_rgb(h)), 0.8, (p.id, h))
            for h in p.dark:
                self.assertGreater(relative_luminance(hex_to_rgb(h)), 0.04, (p.id, h))

    def test_terminal_palettes_start_blue(self):
        for p in PALETTES[1:]:
            r, g, b = hex_to_rgb(p.light[0])
            self.assertGreater(b, max(r, g), p.id)

    def test_unknown_id_falls_back_to_system(self):
        self.assertEqual(palette_by_id("nope").id, "system")
        self.assertEqual(palette_by_id("nord").name, "Nord")

    def test_hex_round_trip(self):
        self.assertEqual(hex_to_rgb("#ff0000"), (1.0, 0.0, 0.0))
        self.assertEqual(hex_to_rgb("000000"), (0.0, 0.0, 0.0))
        for p in PALETTES:
            for h in p.light:
                self.assertEqual(rgb_to_hex(hex_to_rgb(h)), h)
        self.assertEqual(rgb_to_hex((2.0, -1.0, 0.5)), "#ff0080")    # clamped

    def test_luminance(self):
        self.assertAlmostEqual(relative_luminance((1.0, 1.0, 1.0)), 1.0)
        self.assertAlmostEqual(relative_luminance((0.0, 0.0, 0.0)), 0.0)


class SeriesColorsTest(unittest.TestCase):
    def test_system_puts_the_accent_first_and_skips_clashes(self):
        system = palette_by_id("system")
        colors = series_colors(system, False, UBUNTU_ORANGE)
        self.assertEqual(colors[0], UBUNTU_ORANGE)
        self.assertNotIn(hex_to_rgb("#eb6834"), colors)      # orange step dropped
        self.assertEqual(accent_of(system, True, ADWAITA_BLUE), ADWAITA_BLUE)

    def test_terminal_palettes_ignore_the_accent(self):
        tango = palette_by_id("tango")
        self.assertEqual(series_colors(tango, False, UBUNTU_ORANGE)[0], hex_to_rgb("#3465a4"))
        self.assertEqual(series_colors(tango, True, UBUNTU_ORANGE)[0], hex_to_rgb("#729fcf"))
        self.assertEqual(accent_of(tango, True, UBUNTU_ORANGE), hex_to_rgb("#729fcf"))

    def test_palette_without(self):
        light = palette_by_id("system").light
        kept = palette_without(UBUNTU_ORANGE, light)
        self.assertNotIn(hex_to_rgb("#eb6834"), kept)
        self.assertIn(hex_to_rgb("#1baf7a"), kept)
        kept = palette_without(ADWAITA_BLUE, light)
        self.assertNotIn(hex_to_rgb("#6250d6"), kept)        # blue-purple dropped
        self.assertIn(hex_to_rgb("#eb6834"), kept)
        self.assertTrue(palette_without((0.5, 0.5, 0.5), ["#808080"], 1.0))  # never empty


class EntryColorsTest(unittest.TestCase):
    def test_distinct_for_every_palette_up_to_24_entries(self):
        for p in PALETTES:
            for dark in (False, True):
                colors = entry_colors(series_colors(p, dark, UBUNTU_ORANGE), 24)
                hexes = [rgb_to_hex(c) for c in colors]
                self.assertEqual(len(set(hexes)), 24, (p.id, dark))

    def test_palette_colors_first_then_shades(self):
        base = series_colors(palette_by_id("tango"), False, UBUNTU_ORANGE)
        colors = entry_colors(base, 8)
        self.assertEqual(colors[:6], base)
        self.assertEqual(colors[6], mix(base[0], (1.0, 1.0, 1.0), 0.45))
        self.assertEqual(entry_colors(base, 8), colors)                  # deterministic

    def test_secondary_moves_towards_the_surface(self):
        blue = hex_to_rgb("#3465a4")
        self.assertGreater(relative_luminance(secondary(blue, False)), relative_luminance(blue))
        self.assertLess(relative_luminance(secondary(blue, True)), relative_luminance(blue))


class OfflineColorTest(unittest.TestCase):
    """The "wasn't running" dither."""

    def test_near_black_in_the_palettes_hue(self):
        for p in PALETTES:
            for dark in (False, True):
                accent = accent_of(p, dark, (0.2, 0.4, 0.9))
                r, g, b, a = offline_rgba(accent, dark)
                with self.subTest(palette=p.id, dark=dark):
                    self.assertLess(relative_luminance((r, g, b)), 0.05)
                    self.assertGreater(a, 0.0)
                    self.assertLessEqual(a, 1.0)
                    # a shade of the accent: same channel order
                    order = sorted(range(3), key=lambda i: accent[i])
                    self.assertEqual(order, sorted(range(3), key=lambda i: (r, g, b)[i]))

    def test_denser_on_dark_surfaces(self):
        self.assertGreater(offline_rgba((1, 0, 0), True)[3], offline_rgba((1, 0, 0), False)[3])

    def test_the_theme_follows_palette_and_style(self):
        from proccoli.ui.theme import Theme
        sm = FakeStyleManager()
        theme = Theme(Settings.for_tests({"palette": "nord"}), sm)
        self.addCleanup(theme.shutdown)
        self.assertEqual(theme.accent_rgb(), hex_to_rgb("#5e81ac"))   # Nord's light blue
        self.assertEqual(theme.offline_rgba(), offline_rgba(theme.accent_rgb(), False))
        sm.set_system_dark(True)
        self.assertEqual(theme.offline_rgba(), offline_rgba(hex_to_rgb("#88c0d0"), True))


class ThemeColorsTest(unittest.TestCase):
    def setUp(self):
        from proccoli.ui.theme import Theme
        self.settings = Settings.for_tests()
        self.sm = FakeStyleManager(accent=UBUNTU_ORANGE)
        self.theme = Theme(self.settings, self.sm)
        self.addCleanup(self.theme.shutdown)
        self.changes = 0

        def count(*_):
            self.changes += 1
        self.theme.connect("changed", count)

    def test_system_palette_follows_the_desktop_accent(self):
        self.assertEqual(self.theme.series_rgb(0), UBUNTU_ORANGE)
        self.assertEqual(self.theme.accent_css(), "")
        self.sm.set_accent(ADWAITA_BLUE)
        self.assertEqual(self.changes, 1)
        self.assertEqual(self.theme.accent_rgb(), ADWAITA_BLUE)

    def test_picking_a_palette_recolors_and_signals(self):
        self.settings.set("palette", "solarized")
        self.assertEqual(self.changes, 1)
        self.assertEqual(self.theme.series_rgb(0), hex_to_rgb("#268bd2"))
        self.assertEqual(self.theme.series_rgb(6), self.theme.series_rgb(0))   # wraps
        css = self.theme.accent_css()
        self.assertIn("--accent-bg-color: #268bd2", css)
        self.assertRegex(css, re.compile(r"@define-color accent_bg_color #268bd2"))

    def test_entry_colors_and_css(self):
        self.settings.set("palette", "tango")
        self.assertEqual(self.theme.entry_rgb(0), hex_to_rgb("#3465a4"))
        self.assertEqual(self.theme.entry_rgb(1), hex_to_rgb("#cc0000"))
        self.assertEqual(self.theme.entry_rgb(0, series=1), secondary(hex_to_rgb("#3465a4"), False))
        css = self.theme.css()
        self.assertIn(".entry-color-0 > trough > progress { background-color: #3465a4; }", css)
        self.assertIn(".entry-color-23 ", css)

    def test_dark_style_uses_the_bright_colors(self):
        self.settings.set("palette", "gnome")
        self.settings.set("color-scheme", "dark")
        self.assertEqual(self.changes, 2)
        self.assertEqual(self.theme.series_rgb(0), hex_to_rgb("#2a7bde"))
        self.assertIn("#2a7bde", self.theme.accent_css())


def css_has_color(css: str, hex_color: str) -> bool:
    """GTK prints a loaded provider back in its own form: GTK 4.14 (Ubuntu
    24.04) drops ``:root`` custom properties it can't parse and writes
    ``@define-color`` as ``rgb(r,g,b)``; newer GTK keeps the hex."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return hex_color in css or f"rgb({r},{g},{b})" in css


class ThemeCssTest(unittest.TestCase):
    def test_color_match_accepts_both_forms(self):
        self.assertTrue(css_has_color("a: #3465a4;", "#3465a4"))
        self.assertTrue(css_has_color("@define-color x rgb(52,101,164);", "#3465a4"))
        self.assertFalse(css_has_color("rgb(52,101,165)", "#3465a4"))

    def test_variables_only_where_gtk_reads_them(self):
        import gi
        gi.require_version("Gtk", "4.0")
        from proccoli.ui.style import ThemeCss
        from proccoli.ui.theme import Theme
        settings = Settings.for_tests({"palette": "tango"})
        theme = Theme(settings, FakeStyleManager())
        self.addCleanup(theme.shutdown)
        old = ThemeCss(theme, display=None, css_variables=False)   # GTK 4.14
        self.addCleanup(old.shutdown)
        self.assertIn(":root", theme.css())                       # what newer GTK gets
        self.assertNotIn(":root", old.provider.to_string())
        self.assertTrue(css_has_color(old.provider.to_string(), "#3465a4"))

    def test_provider_follows_the_palette(self):
        import gi
        gi.require_version("Gtk", "4.0")
        from proccoli.ui.style import ThemeCss
        from proccoli.ui.theme import Theme
        settings = Settings.for_tests()
        theme = Theme(settings, FakeStyleManager())
        css = ThemeCss(theme)
        self.addCleanup(theme.shutdown)
        self.assertNotIn("accent", css.provider.to_string())          # System
        settings.set("palette", "tango")
        self.assertTrue(css_has_color(css.provider.to_string(), "#3465a4"))
        css.shutdown()
        settings.set("palette", "nord")
        self.assertFalse(css_has_color(css.provider.to_string(), "#5e81ac"))  # no longer followed


if __name__ == "__main__":
    unittest.main()
