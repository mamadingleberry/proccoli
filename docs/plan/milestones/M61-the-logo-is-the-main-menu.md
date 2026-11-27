# Milestone 61: The logo is the main menu; hover in the user's units

*✅ Done.* Burger gone; *About Proccoli* first in the menu. Hover text now uses `core.units` (M60's default printed "1.23e+06 B/s")

Requested: make the Proccoli icon the menu button and remove the burger
menu, with an entry for *About Proccoli*.

| Step | Create / change | Test |
|---|---|---|
| 61.1 | `ui/page.py`: `main_menu_button` is now a flat `Gtk.MenuButton` whose child is the 24 px logo (`primary`, so F10 opens it; tooltip *Main Menu*). `app_logo_button` and the window's and page headers' `logo_button` are gone: the corner holds just the logo, in the sidebar header and in every page header | UI: `assert_corner` (the logo alone, a menu button with the window's model, F10); every test that found the corner through `logo_button` uses `menu_button` |
| 61.2 | `primary_menu`: *About Proccoli* (`app.about`) moves from the last section to the first, a section of its own, then *Go To*, *Sidebar*, and *Show All Details…*, *Preferences*, *Keyboard Shortcuts* | UI: the first item is *About Proccoli*; `app.about` appears once in the whole menu; the *Sidebar* section is now third |
| 61.3 | Hover text in the user's units: `core.units.format_reading(value, unit, base, bits, temperature)` (by unit: %, B/s, W, °C, Hz; other units as a short number). `Graph`'s default uses it; `DevicePage.add_graph` passes the page's preferences, read when the box shows, so a change applies at once; `RATES_IN_BITS` is set on network pages only | Unit: `FormatReadingTest`; UI: a demo page's Read graph follows *Data Units* and ignores *Network Speeds in Bits* |
| 61.4 | README (the logo menu, F10), [DESIGN §9.2](../../design/09.2-window-behaviour.md) corner and modes, the window tree and the sidebar state diagram | – |

**Found while doing 61:** M60's default hover text for graphs that
aren't percentages was `f"{v:.3g} {unit}"`, so the drive and network
pages would have shown "1.23e+06 B/s", ignoring *Data Units*. Fixed in
61.3. Taking stock of every graph for Idea 4 is what found it.
