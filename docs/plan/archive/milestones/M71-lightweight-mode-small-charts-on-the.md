# Milestone 71: Lightweight Mode: small charts on the Overview, a minimal sidebar

*✅ Done.* Was Feature 8. Sidebar *Icons Only* or *Hidden*; Overview cards with the small chart and the 5 busiest apps and processes without icons; meters built only when shown. +1.7 MiB at start (37.1 MiB)

Was Feature 8 (kept below with its design). Its steps F8.1–F8.4 as planned.

| Step | Create / change | Test |
|---|---|---|
| 71.1 | `core/profile.py`: `sidebar-style` pinned to `icons`, the `sidebar-meter-type` pin dropped; `overview_chart` (`"full"`/`"small"`, was `overview_charts`), `overview_tables` true and `overview_top_count` 5 in Lightweight Mode | Unit: the pins and flags; a user's *Full* comes back with the full profile; the full count is `TOP_COUNT` |
| 71.2 | `ui/sidebar_style.py`: `menu_modes`, `choose(..., full_allowed)`; `ui/window.py`: `primary_menu(goto, modes)`; `ui/sidebar_visibility.py`: *Full* becomes *Icons Only* while pinned | Unit: the modes and choices; UI: the menu has no *Full*, a stale *Full* target and F9 give icons only |
| 71.3 | `ui/pages/overview.py`: `OverviewCard(chart="small")` bound as `METER`; `TopTables(count, icons)`; `ui/widgets/top_table.py`: rows without an image; `ui/sidebar.py`: `StackSidebarItem.meter` built on first use (`has_meter`) | UI: small graphs, no axes, entry colors; five rows each without icons, rows open their page, the scan only while shown; no meter widgets in an icons-only sidebar; the full profile still builds them |
| 71.4 | Measured; `tests/ui/shoot.py` `lightweight-overview`, `real-lightweight-overview`; README *Lightweight mode*; [DESIGN §9.6](../../../design/09.6-overview-page.md), [Feature 1's design](../../../design/features/feature-01-lightweight-mode.md), [Feature 8's design](../../../design/features/feature-08-lightweight-mode-small-charts-on-the.md) | Run |

**Decisions on Feature 8's open questions** (taken with the design's own
leanings, since the request was to build it): (1) the overlaid sidebar
of a narrow window is icons only too, as the pin applies everywhere;
(2) the small charts keep the sidebar's fill; (3) Lightweight Mode keeps
the user's shown or hidden choice, so it starts *Icons Only* unless the
sidebar was hidden; (4) five rows per table, not ten.

**Measured** (`tests/ui/mem.py`, Lightweight profile, RssAnon in MiB,
three runs each on this machine, against the same checkout without 71):

| | Before | After |
|---|---|---|
| Started, on the Overview | 34.9–36.1 | 37.0–37.2 |
| Every page visited, after `gc` + `malloc_trim` | 52.7–53.3 | 55.7–55.9 |

The Overview's tables (and the process list while they show) cost about
2 MiB; the meters saved are small. Still under half the full profile's
start (78–90 MiB, M66), so the README's "about half" stands.
