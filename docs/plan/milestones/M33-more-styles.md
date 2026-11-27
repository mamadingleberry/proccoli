# Milestone 33: More styles (ExpressVPN-like)

*✅ Done.* Sand, Sky, Twilight, Midnight with our own colors (ExpressVPN publishes names, not values)

ExpressVPN's apps offer System Default, Sand, Sky, Twilight and Midnight.
Proccoli's *Style* gets the same names, with our own colors.

| Step | Create / change | Test |
|---|---|---|
| 33.1 | `core/styles.py` (no GTK): `Style(id, name, base: system/light/dark, colors)`: Follow System, Light, Dark, Sand (warm light), Sky (cool light), Twilight (dusk purple, dark), Midnight (near-black navy, dark) | Unit: contrast of text on backgrounds ≥ 4.5 |
| 33.2 | `color-scheme` gains the new nicks; `Theme` applies the base scheme, and `ThemeCss` the style's libadwaita color variables (window, view, header bar, sidebar, cards, popovers, dialogs) | Unit with fake style manager |
| 33.3 | Preferences *Style* lists them with a preview swatch | Dialog test; screenshots |
