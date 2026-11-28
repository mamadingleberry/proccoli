# Milestone 82: Palettes, padlocks, steady tables, no stray collectors

*✅ Done.* 13 more palettes (five color-blind safe first after System); Lightweight Mode's fixed settings get a padlock and each page a notice; the Overview's tables keep their size (Bug 13); tests and the window can no longer start a collector by accident (Bug 12)

Asked for after M81: "find and add a lot more color palettes, consider
color palettes for colorblind"; a notice at the top of Preferences and a
mark beside each setting Lightweight Mode fixes, with the explanation as
its tooltip ("a buster … or if there's a better one"); "what does this
debug log imply? … can't serve … no session bus, or another collector";
"why do the table widths shift back and forth … on the Overview page?"

| Step | Create / change | Test |
|---|---|---|
| 82.1 | `core/palette.py`: Okabe–Ito, Tol Bright, Tol Vibrant, Tol Muted, Viridis (named "(Color-Blind Safe)", right after System), Tableau 10, Matplotlib, ColorBrewer Set 1 and Dark 2, Catppuccin, Gruvbox, One, Tokyo Night; the schema's `Palette` enum in the same order (existing values kept) | Unit: ids and names unique and in the schema's order; the color-blind safe ones first; Okabe–Ito's colors the published set; every palette passes the existing rules (6+ colors, light and dark lengths match, visible on their surface, starts blue, 24 distinct entry colors) |
| 82.2 | Preferences in Lightweight Mode: a notice at the top of each page with a fixed setting ("Some settings are fixed in Lightweight Mode…"), and a padlock (`changes-prevent-symbolic`) before each fixed setting's title whose tooltip explains, replacing the row tooltip; `shoot.py` `lightweight-preferences` | UI: the padlock and its tooltip on a fixed row, none on a free one; notices only on pages with fixed settings; none in the full window |
| 82.3 | Bug 12: the tests' private bus has no service folders (`PrivateBus.CONFIG`); the window's calls to the collector carry `NO_AUTO_START` (only the name watcher may start it) | Unit: the tests' bus starts nothing; every window call carries the flag (fails without it) |
| 82.4 | Bug 13: the Overview's tables: the name column's natural width capped, value columns fixed at their widest value | UI: a long name and the widest values leave the table's size unchanged (342 → 547 px without the fix) |

**Decision:** the padlock rather than a prohibition sign
(`action-unavailable-symbolic`, the "buster"): GNOME uses the padlock for
settings locked for now, which is what these are; a prohibition sign
reads as an error. The other is a one-word change.
