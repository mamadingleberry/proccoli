# Milestone 48: Go To submenu

*✅ Done.* Every pane from the main menu, current one marked; identical names told apart. Placeholder text no longer mentions planning documents

| Step | Create / change | Test |
|---|---|---|
| 48.1 | `ui/navigation.py` (no display): `goto_labels` (title, or "title (description)" when titles repeat), `fill_goto_menu` (refills in place, `win.go-to` with a string target), `menu_targets` | Unit |
| 48.2 | `StackSidebar.display_order()` (by rank, right during `add_item`) | Window tests |
| 48.3 | `primary_menu(goto)`: *Go To* submenu first; `MainWindow`: stateful `win.go-to`, refilled on `entries-changed`, state from `_on_visible_page` (also for the first page) | UI tests: lists every pane in order, switches and marks, follows moves and removals |
| 48.4 | *Found while checking 48:* demo mode's placeholder pages showed "Coming soon (PLAN.md, Milestone 4)". Now `placeholder_reason(demo)`: "Not available in demo mode." or "…on this system."; `PlaceholderPage(…, reason)` | UI test; static test: no user-visible string mentions Milestone, PLAN.md or DESIGN.md (docstrings excepted) |
