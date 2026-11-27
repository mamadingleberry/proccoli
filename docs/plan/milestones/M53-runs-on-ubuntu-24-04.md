# Milestone 53: Runs on Ubuntu 24.04 (bug)

*✅ Done.* Start-up crashed: `GLibUnix.signal_add` (GLib 2.82+) and `Adw.Spinner` (libadwaita 1.6). Also breakpoints, CSS and tests fixed for GTK 4.14 / libadwaita 1.5

Reported: Proccoli wouldn't start on Ubuntu 24.04, the oldest system the
README supports. Development had moved to newer GTK, libadwaita and GLib,
and the test suite mocked out the code that failed. Reproduced and fixed
on a 24.04.5 machine (GTK 4.14.2, libadwaita 1.5.0, GLib 2.80.0).

| Step | Create / change | Test |
|---|---|---|
| 53.1 | `app.signal_adder(glib_unix, glib)`: GLib 2.80 has `GLibUnix` but only `signal_add_full`; `signal_add` came later. The `AttributeError` killed `main()` before any window. Picks `signal_add`, then `signal_add_full`, then the old `GLib.unix_signal_add` | Unit with fake modules for each GLib generation; an unmocked `on_sigint` on this system |
| 53.2 | `ui/compat.py`: `spinner(adw=Adw)` uses `Adw.Spinner` (1.6) or a spinning `Gtk.Spinner`. The GPU page built `Adw.Spinner` unguarded, so every GPU page crashed | Unit: both branches with injected `adw` |
| 53.3 | `test_static.PlatformFloorTest`: an `Adw.` class newer than 1.5 needs `hasattr(Adw, ...)` in its file (one guard covers its siblings from the same release) | Static; checked against the old GPU page (flags `Adw.Spinner`) |
| 53.4 | `compat.ensure_font_dpi`: with no font DPI (`gtk-xft-dpi` −1: X11 without an XSETTINGS daemon, or Broadway), libadwaita 1.5 never matches `sp`/`pt` breakpoints, so narrow windows didn't fold the sidebar away. Set 96 dpi, as newer libadwaita assumes. Called by `Application` and `MainWindow`, and by `tests/helpers.py` on the headless display | Unit with a fake `Gtk.Settings`; the narrow-window UI test |
| 53.5 | `InfoRow` keeps the raw value: libadwaita 1.5's `get_subtitle()` returns the text with the markup removed, newer versions the markup, so comparing with it re-set the subtitle every tick on 1.5 and `get_value()` returned escaped text on 1.6+ | UI: shown text, `get_value`, set only on change |
| 53.6 | `ThemeCss` leaves out `:root { --var }` rules on GTK < 4.16 (`compat.has_css_variables`, `without_css_variables`); GTK 4.14 warned at each one. The `@define-color` names do the work there | Unit: version check, stripping; `ThemeCss(css_variables=False)` |
| 53.7 | `core/system.py`: the `GioUnix.DesktopAppInfo` fallback also catches `AttributeError` | Existing tests |
| 53.8 | Tests made version-independent: `helpers.resize_window` (GTK 4.14's Broadway ignores `set_default_size` on a shown window, so it re-shows it), `resize_or_skip` (it also can't make windows bigger than its 1024×768 screen: 3 portrait tests skip there, with the reason), the palette test accepts `rgb()` as GTK 4.14 prints it, the icon PNG test allows librsvg's off-by-one rounding | Whole suite on 24.04 |

**Done when:** `make run` starts on Ubuntu 24.04 and `make ui-test` passes
there.

*Found while doing 53:* the old `on_sigint` test mocked the function away,
so the crash couldn't show up in the suite. The new test calls the real
one.

**Housekeeping (with 53):** DESIGN.md and PLAN.md moved to `docs/`; a
`CLAUDE.md` and the `proccoli-change` skill (`.claude/skills/`) hold the
rules for every change: design for testing, add tests, update the docs,
refactor lightly.
