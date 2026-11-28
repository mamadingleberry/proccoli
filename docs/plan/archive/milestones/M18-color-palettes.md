# Milestone 18: Color palettes

*✅ Done.* Screenshots now render the whole window (a dark page background was missing)

Eight palettes for graphs, meters and the accent color, after GNOME
Terminal's built-in schemes.

| Step | Create / change | Test |
|---|---|---|
| 18.1 | `core/palette.py` (no GTK): `Palette(id, name, light, dark, follows_accent)` and `PALETTES`: **System** (the desktop accent plus the current color-blind-friendly steps; default), **GNOME**, **Tango**, **Solarized**, **Linux Console**, **XTerm**, **Rxvt**, **Nord**. Each has a light and a dark variant (the terminal's normal and bright colors), in series order blue, red, green, yellow, magenta, cyan. `series_colors(palette, dark, accent)`; `palette_without()` moves here. | Unit: 8 palettes, ids unique, every color valid hex, contrast against the surface, no adjacent duplicates, accent handling |
| 18.2 | Schema: `palette` (enum of the 8 ids) | Settings tests |
| 18.3 | `Theme`: `series_rgb(i)`, `accent_rgb()`, `accent_css()`, `changed` signal (palette, dark/light or accent change) | Unit with fake style manager |
| 18.4 | `Graph` gets its theme from its window (`root.theme`, re-read on map) and redraws on `changed`; without one it uses a default theme. The accent CSS (`--accent-bg-color`, `--accent-color`) is installed for non-System palettes, so switches and progress bars match. | Widget test: a graph in a window with a fake theme draws its colors |
| 18.5 | Preferences → General → Appearance: *Color Palette* combo with a color-swatch preview per entry | Dialog test |

**Done when:** picking a palette recolors every graph, meter and accent at
once, in both light and dark styles.
