# Idea 3: Intel Details graphs on the shared chart code

Design note: [design/ideas/idea-03-intel-details-graphs-on-the-shared.md](../../design/ideas/idea-03-intel-details-graphs-on-the-shared.md)

*Done as Milestone 60. Kept as the design record.*

**Goal:** the Intel GPU's *Details* tab looks and behaves like every other
graph in Proccoli, using the same objects, instead of the graph code
ported from intel_gpu_top_gui in Milestone 9.

**Why:** the tab still has its own copy of everything a graph needs, and it
has drifted from the rest of the app:

| Intel Details tab (`gpu/intel_gpu_top/graph.py`, `grid.py`) | Shared since then (`ui/`) |
|---|---|
| `GraphView`: its own Cairo graph | `Graph` (`ui/widgets/graph.py`) |
| `GraphSection`: graph + legend outside a card | `LegendChart` (M59): legend inside the card, chart and legend one area |
| `LegendItem`, `Swatch`: toggles only | `Legend`: left-click toggles, right-click shows only that line, never empty (M58, M59); compact legend when space is tight (M57) |
| `series_color`, `hex_to_rgb`, `is_dark` | the window's `Theme`: palettes, distinct colors per line (`entry_colors`) |
| `AxisGroup`, `format_axis`, `time_tick`, `y_divisions` | `ui/axes.py`: percent ticks, round time steps, *Show Graph Axes* |
| `nice_ceiling`, `snap_to_device`, `_rounded_rect` | the same helpers in `ui/widgets/graph.py` (duplicates today) |
| its own update interval and history length | *Graph Time Range* (M58) for every other graph |

So a palette, axis or legend change has to be made twice, and the Details
tab misses the newer behaviour (right-click solo, never-empty, compact
legend, time range). It's about 840 lines (`graph.py` 640, `grid.py` 204)
that could mostly go.

**What the Intel tab has that the shared code doesn't** (kept, by moving
it into the shared code so every graph gains it):

- **Hover crosshair:** the values of every line at the pointer's time.
  Becomes `Graph.set_hover(True)`, on for page graphs, Overview cards and
  the Details tab.
- **One y-axis width per group** (`AxisGroup`), so the plots in a column
  line up. Becomes an optional shared gutter width on `Graph`.
- **Per-GT groups** on multi-tile GPUs and the *compact* layout below
  720×600: kept in the Intel views, built from shared parts.
- **Pause, Export as CSV, Clear History** in the header: unchanged.

**Open question:** the Details tab's own *Update Interval* and *History
Length* (from intel_gpu_top_gui) versus *Graph Time Range*. The plan keeps
the update interval (it's intel_gpu_top's sampling rate, `-s`) and
replaces *History Length* with the app's *Graph Time Range*, so all graphs
show the same span. Keeping both is also possible.

| Step | Create / change | Test |
|---|---|---|
| I3.1 | `Graph.set_hover(on)`: crosshair and values at the pointer (ported from `GraphView._draw_hover`), and an optional shared axis gutter (`AxisGroup` moved to `ui/axes.py`) | Unit: hover maths on a fixed series; UI: hover on a page graph |
| I3.2 | Each Intel graph group becomes a `LegendChart` (one line per engine or measure; percent groups 0–100, others auto-scaled), keeping `GraphGrid` for the columns but sizing each chart with `graph_cap` and its legend counted in (like `DevicePage.reserve`) | Port `test_igt_graph_helpers.py` / `test_igt_grid.py` to the shared objects; UI: every group, compact layout, per-GT groups |
| I3.3 | Colors from the `Theme` (palettes, distinct colors), axes from `ui/axes.py`; *History Length* → *Graph Time Range* (open question above) | UI: palette change recolors the Details tab; screenshots `demo-gpu-details` before/after |
| I3.4 | Delete `GraphView`, `GraphSection`, `LegendItem`, `Swatch` and the duplicate helpers; `test_static` gains a check that no module outside `ui/` defines its own `Gtk.DrawingArea` graph | Whole suite; static test |
| I3.5 | [DESIGN §7.3](../../design/07.3-the-page.md) and [§9.1](../../design/09.1-widgets.md) (one chart family), README (Details tab: right-click, hover everywhere) | – |

**Done when:** the Intel Details tab is built only from `Graph`,
`Legend` and `LegendChart`, behaves like the other charts (palettes, axes,
legend clicks, time range), every graph has the hover crosshair, and the
ported graph classes are gone.
