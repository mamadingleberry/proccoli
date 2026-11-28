# Milestone 63: One chart family everywhere

*✅ Done.* Was Feature 4. `ChartSettings` gives every graph its preferences live; both GPU *Details* tabs are `ChartCard`s in a `ChartGrid`; readings in the user's units everywhere; value axes on every graph with a unit

Was Feature 4 (kept below with the stock-taking that motivated it). M60 made
every graph the shared `Graph`; this does the same for what surrounds it.
Feature 4's open questions were settled with its own recommendations: drive
and network speeds get value axes, and device pages keep Resources' rows
(cards only on the Overview and the *Details* tabs).

| Step | Create / change | Test |
|---|---|---|
| 63.1 | `ui/chart_settings.py`: `ChartSettings(settings)` with `bind(graph, PAGE/CARD/METER, rates_in_bits, gutter, show_axes)`, `unbind`, `release`, `set_entry_base`, `format_value`, `format_reading`. `DevicePage`, `OverviewPage` and the sidebar use it; their own handlers, `DevicePage._set_axes/_set_grid` and `axes.history_span_s` go | Unit (`test_chart_settings`, fake graphs): each kind's keys, live changes, units, entry color, unbind and release. Existing page tests unchanged |
| 63.2 | Detail tabs: `DetailServices.charts`, a new `ChartSettings` per set of views, released when the GPU page drops them; the NVIDIA tab follows every chart preference live; the Intel tab stops re-reading at each sample | UI: toggling *Show Graph Axes*, *Show Graph Grids* and *Graph Time Range* changes both Details tabs at once |
| 63.3 | `ui/widgets/chart_grid.py`: `ChartGrid` (was `gpu/intel_gpu_top/grid.py`'s `GraphGrid`; arithmetic into `ui/layout.py` as `GridItem`, `split_columns`, `extra_heights`, `graph_cap`, `layout_quality`, `choose_columns`) and `ChartGridView` (caption, grid, placeholder, compact breakpoints), used by both tabs | `test_igt_grid` → `test_chart_grid`; UI: the NVIDIA tab fills a 1024×768 window in two or more columns; screenshots |
| 63.4 | `ui/widgets/chart_card.py`: `ChartCard` (a card around a `LegendChart`, `set_compact`); `GroupChart` and the NVIDIA rows become `ChartCard`s; the one-legend rule (one line: no legend, its value in the info line) | UI: one-line cards have no legend on both tabs, many-line ones do |
| 63.5 | Base units at the history boundary: Intel MiB/s → B/s, MHz → Hz (`history.to_base_unit`), NVIDIA clocks in Hz. `core.units.format_axis_label` (short form) and `nice_max_in_units`; value axes on every `PAGE` graph with a unit. `labels.format_value`, `format_axis`, `nice_max_for` and the NVIDIA `_format` removed | Unit: conversions, short forms, rounding in the shown unit; UI: Intel bandwidth "2 GiB/s" with binary units and "2.15 GB/s" with decimal; network axes in bits when chosen |
| 63.6 | The GPU entry's color for the Details tabs (`GpuPage.set_entry_color` forwards it) | UI: the first Details line has the GPU entry's color |
| 63.7 | `test_static`: graph keys only in `chart_settings.py` (and Preferences) among views; `gpu/` builds no `Graph`, `GraphBox`, `GraphPane`, `LegendChart`. [DESIGN §9.1](../../../design/09.1-widgets.md) (the chart family diagram), [§4](../../../design/04-architecture-overview.md), [§7.3](../../../design/07.3-the-page.md), [§11](../../../design/11-cross-cutting-concerns.md), [Feature 4's design](../../../design/features/feature-04-one-chart-family-everywhere.md); README | Static tests; whole suite; screenshots |

**Deviations from Feature 4, and why:**

- **`ChartCard` always holds a `LegendChart`** and hides its legend for
  one line, rather than having two kinds of body: one code path for
  spacing, hover and compact mode.
- **`ChartGridView`** (not in the plan): the caption, grid, placeholder
  and compact breakpoints both tabs had or needed, in one place.
- **The `Graph(` rule covers `gpu/` only**, not "only `ui/widgets/`":
  the Overview card builds its graph in `ui/pages/overview.py`, and moving
  it would be churn with no gain. What matters (vendor code can't build
  its own charts) is enforced.
- **One-line Intel cards** show their value in the info line; their
  description moved to the card's tooltip.
- **The Intel tab's *Export as CSV*** now writes base units (B/s, Hz),
  since that's what its history holds.

**Found while doing 63.2:** the NVIDIA tab never showed grids at all, and
ignored *Show Graph Axes* and *Graph Time Range* changes until it was
rebuilt. Both now follow live (tested).
