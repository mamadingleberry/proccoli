# Milestone 59: Reusable many-line chart; a chart never shows nothing

*✅ Done.* `LegendChart`, used by the Processor and NVIDIA Details pages

Requested: if only one CPU core is selected and the user deselects it,
show every core, and make this chart code reusable for future charts.

| Step | Create / change | Test |
|---|---|---|
| 59.1 | `series_visibility.never_empty(shown, available)`: every change ends with at least one line shown; if none would be, every line with data comes back. `toggle` and `solo` use it; lines without data (`available`) never count as shown | Unit: solo then deselect → all; hiding one by one → all; lines without data |
| 59.2 | `Legend`: a click on an item (which toggles itself) now goes through the rules (`_on_item_toggled`); `set_shown` applies `never_empty`; `set_available(i, on)` hides an item without data and keeps it out of the rules | UI: on the Processor page and standalone |
| 59.3 | `ui/widgets/legend_chart.py`: **`LegendChart`**, the reusable many-line chart: a `GraphBox` whose graph draws lines only, each in a distinct color, with the `Legend` inside its card; `set_lines(series, names)`, `set_values(texts)`, `legend_height(width)`, `fit_legend()` (compact legend when values would cramp the graph, `comfort`). Works standalone | UI: standalone lines, colors, values, the rules, lines without data |
| 59.4 | `DevicePage.add_legend_chart(group, title, …)`: adds a `LegendChart` fitted like any page graph, its legend counted in its area; `DevicePage.fit` ends with `fit_legends()`, `fit_key` includes the legends' heights. The fitting moved here from `CpuPage`, which now only calls `add_legend_chart` and `set_lines`/`set_values` | Existing area and compact-legend tests, now through the chart |
| 59.5 | NVIDIA Details tab: its two- and three-line graphs are `LegendChart`s (legend inside the card, same rules); unreported measures via `set_available` | UI: NVIDIA views |
