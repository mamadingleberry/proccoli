# Milestone 39: Overview page

*✅ Done.* Pinned first; one chart card per charted entry, in sidebar order and colors

| Step | Create / change | Test |
|---|---|---|
| 39.1 | `PageKind.OVERVIEW` (first); `OVERVIEW_ICON` (our own symbolic dashboard icon); pinned and uncharted in the sidebar | Rank test; window tests: first, can't be moved or minimised, not in Preferences → Sidebar |
| 39.2 | `SidebarSummary.text()` and `has_chart()`: the usage line, shared by sidebar rows and cards | Unit |
| 39.3 | `StackSidebar.entries()` (charted `(page, color)` in display order) and `entries-changed`, emitted by `assign_colors()` | Window test: cards follow moves and removals |
| 39.4 | `ui/pages/overview.py`: `OverviewCard` (icon, name, usage, detail, chart in the entry color; follows `summary-changed`) and `OverviewPage(settings, navigate)` (FlowBox, `sync`, `order`, click → `navigate`); placeholders get no card | UI tests with fake pages: order, color, updates, replace, shutdown, axes |
| 39.5 | `MainWindow` adds the page and connects `entries-changed` → `sync`; screenshot scenes `wide-overview`, `portrait-overview`, `real-overview` | Window tests; screenshots |

**Done when:** the Overview entry at the top shows a live chart card for
every device, in the sidebar's order and colors, and clicking one opens
it.
