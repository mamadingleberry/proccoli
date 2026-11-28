# Milestone 29: Axes on percentage graphs

*✅ Done.* Round time steps; sidebar charts grow to fit labels

| Step | Create / change | Test |
|---|---|---|
| 29.1 | `ui/axes.py` (pure): `percent_ticks(height)` (0/25/50/75/100, labelled where they fit), `time_ticks(span_s, width)` ("60 s", "30 s", "now"), `format_span(s)` | Unit |
| 29.2 | `Graph` draws a left gutter of y labels with tick marks and a bottom row of time labels with ticks, around the plot, when all its series are percentages and axes are on; compact labels for small graphs (sidebar, per-thread CPU) | Pixel tests: gutter present/absent |
| 29.3 | The time span comes from the history length and refresh speed (`DevicePage` and the sidebar set it; they follow both settings) | UI test |
| 29.4 | Schema `show-graph-axes` (default on); Preferences → *Show Graph Axes* | Dialog test |
