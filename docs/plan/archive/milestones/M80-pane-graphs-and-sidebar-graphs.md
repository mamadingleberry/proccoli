# Milestone 80: Pane graphs and sidebar graphs

*✅ Done.* `PaneGraph` and `SidebarGraph` (both `Graph`): sidebar charts never have a grid, show the time axis whenever axes are on (network ones too, which had none) and only the minimum and maximum on a value axis; pane charts as before. Also: 19 lines of Mermaid fixed for GitHub (semicolons, quotes in class members, `PK, FK`)

Asked for after M79: "sidebar graphs have the unique characteristics:
graph grids don't appear on them, x-axis appears on all graphs (currently
not on internet devices on the sidebar), y-axis (if provided for the
graph) only includes the min/max values and tick marks", with subclasses
for pane graphs and sidebar ("toolbar") graphs.

| Step | Create / change | Test |
|---|---|---|
| 80.1 | `ui/widgets/graph.py`: `PaneGraph` and `SidebarGraph` (both `Graph`). `SidebarGraph`: `set_show_grid` keeps it off; `has_axes` is just *Show Graph Axes* (the time axis on network meters too, which had no axes because they have no percentage); `y_tick_labels` only the minimum and maximum, and none without a value axis (a percentage or an `axis_format`). `Graph.plot_rect` leaves no left margin when there are no value labels | UI: the kinds and who uses them; no grid on the sidebar, a grid on pane charts; a network meter's time axis with no value labels (and what it was: none); min and max only; off means the whole widget |
| 80.2 | `GraphBox` makes a `PaneGraph`, `Meter` a `SidebarGraph`, the Overview's cards one or the other (small charts in Lightweight Mode are the sidebar's) | UI: the toolbar's *Graph Grid* reaches pane charts and not the sidebar (it reached both since M72.8) |
| 80.3 | DESIGN's chart class diagram; Mermaid fixes (below) | – |

**Decision:** "Toolbar Graphs" read as the sidebar's (the request
describes them); a network meter still has no *value* axis ("if provided
for the graph"): only pane charts get value labels in units. Giving
sidebar meters one too is a small change if wanted.

**Mermaid on GitHub** (asked for at the same time, after reading GitHub's
*Creating diagrams* page, which documents only third-party plugins as a
cause of errors and an `info` block to show its Mermaid version): every
diagram was checked by hand for constructs Mermaid's grammar rejects,
since running Mermaid itself locally was declined. 19 lines in DESIGN.md
changed: semicolons in sequence messages, notes, state transitions and
class members (Mermaid's statement separator: they cut lines in two),
double quotes inside class members, and two `PK, FK` key pairs in the
entity diagram (older renderers take one key; the foreign key is now in
the column's comment). None of the 62 diagrams has been rendered to
confirm.
