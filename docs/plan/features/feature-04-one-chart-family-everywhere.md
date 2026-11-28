# Feature 4: One chart family everywhere

Design note: [design/features/feature-04-one-chart-family-everywhere.md](../../design/features/feature-04-one-chart-family-everywhere.md)

*Done as v0.3.0* (its deviations are listed there).

**Goal:** every chart in Proccoli is built, configured and laid out the
same way, so a change to how charts look or behave is made once. v0.3.0
made the Intel *Details* tab draw with the shared `Graph`, `Legend` and
`LegendChart`. This feature does the same for what sits around the graph:
how settings reach it, the card it's in, how cards are laid out, number
formats and colors.

**Why: what's still done more than one way** (taken stock during v0.3.0):

| Concern | Today | Problem |
|---|---|---|
| Settings reach graphs | Five ways: `DevicePage.add_graph` + `_set_axes` / `_set_grid` (live); Overview cards and the sidebar meters (axes and span, live, their own handlers); the NVIDIA Details tab (read **once** when it's built); the Intel Details tab (re-read at every sample, v0.3.0) | NVIDIA charts ignore *Show Graph Axes*, *Graph Time Range* and *Show Graph Grids* changes until the tab is rebuilt, and never show grids. Every new view must remember all three keys |
| Layout | Three fitting systems: `DevicePage` (`layout.fit_heights`), the Overview (`layout.plan_grid`), the Intel tab (`gpu/intel_gpu_top/grid.py`: `GraphGrid`, its own `split_columns`, `extra_heights`, `graph_cap`); the NVIDIA tab has none (a plain scrolling column of 120 px graphs) | The NVIDIA tab doesn't fill the window or use columns; the Intel grid lives in a vendor package although nothing in it is Intel's |
| The card | `GraphBox` / `DoubleGraphBox` / `LegendChart` rows in an `Adw.PreferencesGroup`; the Intel `GroupChart` (a `card` box around a `LegendChart` row, v0.3.0); `OverviewCard` (its own box) | Three ways to put a title, an info line and a graph in a card, with slightly different spacing |
| Number formats | `core.units` (pages, and the hover box since v0.3.0); `gpu/intel_gpu_top/labels.py` (`format_value`, `format_axis`); the NVIDIA view's `_format` | Intel bandwidth is always MiB/s and GiB/s, whatever *Data Units* says; Intel and NVIDIA clocks are formatted differently; the Intel temperatures (if any) don't follow *Temperature Unit* |
| Axes | Percentage axes everywhere; value axes (`axis_format`, v0.3.0) on the Intel tab only | NVIDIA clocks, power and temperature, and drive and network speeds, have no axes, while the Intel tab's do |
| Colors | `colors`, `entry_index`, `entry_base` + `color_offset`, `distinct`: four ways to pick a graph's colors | The GPU *Details* tabs don't get `entry_base`, so their first color isn't the GPU entry's color, unlike the GPU *Overview* tab beside them |
| Legend | `LegendChart` for some single-line graphs (Intel RC6, Interrupts), `GraphBox` for others (NVIDIA Temperature, Power) | A one-line chart has a legend on one tab and none on the other |

**Design ([Feature 4's design](../../design/features/feature-04-one-chart-family-everywhere.md)):**

- **`ChartSettings`** (`ui/chart_settings.py`): the one place graphs get
  *Show Graph Axes*, *Show Graph Grids*, *Graph Time Range* and the unit
  preferences. `bind(graph, kind)` applies them now and on every change;
  `kind` (`PAGE`, `CARD`, `METER`) says which apply (meters have no grid).
  It owns its settings handlers and `release()`s them, so a view without
  its own teardown (the detail tabs) gets one through `DetailViews`. It
  also sets the hover formatter (61.3's `format_reading` with the
  preferences). `DevicePage`, `OverviewPage`, the sidebar and both detail
  tabs use it; their own handlers go.
- **`ChartGrid`** (`ui/widgets/chart_grid.py`): `GraphGrid` moved out of
  `gpu/intel_gpu_top/` (its arithmetic into `ui/layout.py`, beside
  `fit_heights`, sharing `GraphLimits`). The NVIDIA tab lays its charts
  out with it, so it fills the window in columns like the Intel tab.
- **`ChartCard`** (`ui/widgets/chart_card.py`): a card with a title, an
  info line and either one graph or a `LegendChart` body, with a
  `compact` mode. `GroupChart` becomes a `ChartCard`; the detail tabs
  build only `ChartCard`s. (`GraphBox` rows in preference groups stay for
  device pages, which look like Resources'; `ChartCard` uses the same
  `GraphPane`, so spacing matches.)
- **One rule for legends:** a chart with two or more lines gets a
  `LegendChart`; a one-line chart gets none, its value in the info line.
- **Formats through `core.units`:** detail sources record readings in
  base units (bytes per second, hertz, watts, degrees Celsius) at the
  history boundary (the Intel `History.add`, the NVIDIA sample), so
  `format_reading` and *Data Units* / *Temperature Unit* apply
  everywhere. `format_reading` gains a short form for axis labels
  (`"2 GB/s"`, `"1.5 GHz"`); `labels.format_value` / `format_axis` and
  the NVIDIA `_format` go.
- **Value axes for every graph with a unit**, from that short form, in a
  shared gutter per column (`AxisGutter`, v0.3.0): drive and network speeds,
  NVIDIA clocks, power and temperature. *Show Graph Axes* turns them all
  off together.
- **Colors:** `DetailServices` gains the GPU entry's color index, so the
  detail tabs start at the GPU entry's color; `distinct` and
  `entry_base` stay the only ways a multi-line chart picks colors.
- **Enforced:** `test_static` checks that only `ui/chart_settings.py`
  reads `show-graph-axes`, `show-graph-grids` and `graph-time-range` for
  graphs, and that `Graph(` is constructed only inside `ui/widgets/`.

| Step | Create / change | Test |
|---|---|---|
| F4.1 | `ChartSettings` with `bind` / `release`; `DevicePage`, `OverviewPage` and the sidebar use it, their own handlers removed | Unit (fake graphs, `Settings.for_tests()`): every kind gets the right keys, live changes, release disconnects; existing page tests unchanged |
| F4.2 | Detail tabs: `DetailViews` carries a `ChartSettings` the page releases with the views; the NVIDIA tab follows changes live; the Intel tab stops re-reading at each sample | UI: toggling *Show Graph Axes* and *Graph Time Range* updates both Details tabs at once |
| F4.3 | `ChartGrid` in `ui/` (arithmetic in `ui/layout.py`); the Intel tab and the NVIDIA tab use it | Port `test_igt_grid.py` to `test_chart_grid.py`; UI: the NVIDIA tab fills a 1024×768 window in two columns; screenshots |
| F4.4 | `ChartCard`; `GroupChart` and the NVIDIA view's cards become `ChartCard`s; the one-legend rule | UI: one-line charts have no legend on both tabs, many-line charts do |
| F4.5 | Base units at the history boundary for Intel (MiB/s → B/s, MHz → Hz) and NVIDIA (MHz → Hz); `format_reading` short form; value axes on drive, network and NVIDIA graphs; `labels.format_value` / `format_axis` and NVIDIA `_format` removed (names stay) | Unit: conversions, short forms; UI: Intel bandwidth in KiB/MiB/GiB with *Data Units* binary, GB with decimal; axes on drive and network pages |
| F4.6 | GPU entry color for the detail tabs | UI: the first Details line has the GPU entry's color |
| F4.7 | `test_static` checks above; [DESIGN §9.1](../../design/09.1-widgets.md) (the chart family diagram: `ChartSettings`, `ChartCard`, `ChartGrid`), README (axes on rates; Details tabs follow every chart preference) | Static test; whole suite; screenshots |

**Done when:** every graph's settings come through `ChartSettings`;
both GPU *Details* tabs are `ChartCard`s in a `ChartGrid` and follow
every chart preference live; every reading is formatted by `core.units`
in the user's units; graphs with units have value axes; and the static
test keeps it that way.

**Open questions for the user:**
1. Value axes on drive and network speed graphs: the plan adds them
   (consistent with the Intel tab). Or keep page rate graphs axis-free,
   as Resources does?
2. Should device pages also move to `ChartCard` (cards in a grid instead
   of preference-group rows)? The plan keeps Resources' look on device
   pages and uses cards only on the Overview and the Details tabs.
