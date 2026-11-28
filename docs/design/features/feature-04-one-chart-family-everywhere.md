# Feature 4: One chart family everywhere

Plan: [plan/features/feature-04-one-chart-family-everywhere.md](../../plan/features/feature-04-one-chart-family-everywhere.md)


*Built in v0.3.0; [§9.1](../09.1-widgets.md) describes it as built (PLAN.md lists the
deviations). Kept as the design record.* v0.3.0 made every graph the shared `Graph`. What's
still done several ways is what surrounds it: settings (five ways, one
of them never live), layout (three fitting systems, none on the NVIDIA
tab), the card (three), number formats (three), colors (four
mechanisms) and when a legend appears. The design gives each concern
one owner in `ui/`:

```mermaid
classDiagram
    direction LR
    class ChartSettings {
        +bind(graph, kind)
        +release()
        axes, grids, time range,
        unit preferences, hover format
    }
    class ChartCard {
        title + info line
        Graph or LegendChart body
        +set_compact(on)
    }
    class ChartGrid {
        <<Gtk.Widget>>
        columns + height sharing
        (arithmetic in ui/layout.py)
    }
    class Graph
    class LegendChart
    class FormatReading["core.units.format_reading"]
    ChartGrid o-- "n" ChartCard
    ChartCard *-- Graph
    ChartCard *-- LegendChart
    ChartSettings ..> Graph : configures
    ChartSettings ..> FormatReading : hover and axis text
    DevicePage ..> ChartSettings
    OverviewPage ..> ChartSettings
    StackSidebar ..> ChartSettings
    IntelGraphsView ..> ChartGrid
    NvidiaDetailsView ..> ChartGrid
```

- Detail sources record readings in base units at the history boundary,
  so `format_reading` (and *Data Units*, *Temperature Unit*) formats
  every number, including axis labels (a short form).
- Device pages keep Resources' preference-group rows (`GraphBox`);
  the Overview and the Details tabs use `ChartCard`s. Both use
  `GraphPane`, so spacing matches.
- `test_static` enforces it: only `ChartSettings` reads the chart keys
  for graphs; `Graph(` is built only in `ui/widgets/`.
