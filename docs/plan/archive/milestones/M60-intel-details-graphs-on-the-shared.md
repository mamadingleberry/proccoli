# Milestone 60: Intel Details graphs on the shared chart code

*✅ Done.* Was Feature 3. Every graph gains the hover crosshair; *History Length* replaced by *Graph Time Range*

Was *Feature 3* (its design and reasons are kept there and in [Feature 3's design](../../../design/features/feature-03-intel-details-graphs-on-the-shared.md)).
The Intel *Details* tab drew with its own copy of the graph code ported
from intel_gpu_top_gui in Milestone 9; now it's built from `Graph`,
`Legend` and `LegendChart` like every other chart, and the copy is gone.
The open question was settled as the plan proposed: the tab's *History
Length* is replaced by the app's *Graph Time Range*; its *Update
Interval* (intel_gpu_top's sampling rate) stays.

| Step | Create / change | Test |
|---|---|---|
| 60.1 | `Graph.set_hover(on, value_format)`, `set_names`: a crosshair at the pointer, a marker per shown line and a box with the time and each line's value; on for every `NORMAL` graph (page graphs, Overview cards), off for the sidebar's. The arithmetic is in the new `ui/hover.py` (`hover_point`, `ago_text`, `box_origin`). `ui/axes.py` gains `AxisGutter` (the old `AxisGroup`, with an injected `schedule`), `value_divisions` and `value_ticks`; `Graph.set_axis_format(fmt, gutter)` gives non-percentage graphs value axes; `Graph.nice_max` rounds an automatic maximum in the shown unit | Unit: `test_hover` (hover maths, time text, box placement, value ticks, the gutter); UI: hover on a page graph, hidden lines skipped, value axes lined up by a shared gutter |
| 60.2 | `IntelGraphsView` builds one `GroupChart` per group: a card holding a `LegendChart` (one line per engine or measure; percentages on 0–100, the rest scaled to the data), still laid out by `GraphGrid` (its `graph_cap` and legend-in-the-area sizing unchanged). Compact layout: a shorter floor, no subtitle, the legend's compact mode | UI: every group is a `LegendChart`, legend solo / never-empty, compact on and off; screenshots `demo-gpu-details`, `narrow-gpu-details`, `portrait-gpu-details` |
| 60.3 | Colors from the `Theme` (distinct colors per line), axes from `ui/axes.py` and *Show Graph Axes*, grids from *Show Graph Grids*, time span and history length from *Graph Time Range* (`IntelGpuTopBackend._points`). `intel-gpu-top-history` removed from the schema, the Preferences GPU page and the tab's menu | UI: palette change recolors the tab; the backend's history follows the time range; the dialog no longer has the row |
| 60.4 | Deleted `gpu/intel_gpu_top/graph.py` (`GraphView`, `GraphSection`, `LegendItem`, `Swatch`, `AxisGroup`, and the copies of `nice_ceiling`, `snap_to_device`, the palette and the rounded rectangle). Its number formats and names moved to the display-free `gpu/intel_gpu_top/labels.py`; `nice_ceiling` moved to `core/units.py` (still importable from the graph widget). The Intel `Series` is now the shared `core.history.Series` plus its group. `test_static` checks that no module outside `ui/` draws its own graph | `test_igt_labels` (ported from `test_igt_graph_helpers`); static test; whole suite |
| 60.5 | [DESIGN §2](../../../design/02-what-resources-does-and-what-proccoli.md) (graph drawing), [§4.1](../../../design/04-architecture-overview.md), [§7.3](../../../design/07.3-the-page.md), [§9.1](../../../design/09.1-widgets.md) (hover, value axes, gutter), [§11](../../../design/11-cross-cutting-concerns.md) settings, [Feature 3's design](../../../design/features/feature-03-intel-details-graphs-on-the-shared.md) marked done; README | – |

**Found while doing 60:**
- A value axis measured its labels for a shorter plot than it drew, so it
  could pick more ticks than it had made room for (clipped "3.75 GiB/s").
  `plot_rect` now uses the drawn plot height.
- Bandwidth rounded in MiB/s and showed in GiB/s ("4.88281 GiB/s"):
  hence `Graph.nice_max` and `labels.nice_max_for`.
- With axes on, the old 40 px compact floor left almost no plot between
  the labels (the old graphs dropped their time labels instead); the
  compact floor is now 56 px.
- `GraphGrid` could measure a chart narrower than its legend's minimum
  width; the column width is now never below the narrowest section.
