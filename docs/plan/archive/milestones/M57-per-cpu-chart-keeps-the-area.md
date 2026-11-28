# Milestone 57: Per-CPU chart keeps the area; readings on the Overview cards

*✅ Done.*

Two requests, done before the lightweight mode (then Milestone 56, now an
feature: see *Features*). (1) Switching the Processor page
between the total chart and the per-CPU chart must give a chart of the
same area, its legend counted in. (2) The Overview's processor and GPU
cards show the current temperature, and GPU cards the memory used / total.

| Step | Create / change | Test |
|---|---|---|
| 57.1 | `ui/layout.py`: `graph_in_area(area, reserve, floor)`, `MIN_GRAPH_IN_AREA` (32 px) | Unit |
| 57.2 | `DevicePage.reserve(graph, measure)`: pixels counted as part of a graph's area when fitting (`fit` shares out areas, then gives each graph its area less its reserve) | UI (through 57.3) |
| 57.3 | The per-CPU legend moves inside the chart's card (`GraphPane.set_footer`) and is reserved; `CpuPage.fit_key` adds the visible chart and the legend's height, and switching charts refits | UI: the per-CPU card is as tall as the total chart's card, both ways |
| 57.4 | Legend slots without FlowBox padding (`flowbox.graph-legend`, 12 per line at most); the tests' display installs the app's CSS like `Application` does | Measured: 12 CPUs' legend 120 → 63 px |
| 57.5 | `use_compact_legend(area, full_legend, comfort)` (`COMFORT_GRAPH` 96): when the legend with values would leave the chart under 96 px, items show swatch and name only, the value as hover text (`Legend.set_compact`). The area doesn't depend on the legend, so it can't flip back and forth; the full height is measured per width | Unit: the rule; UI: both ways, settles |
| 57.6 | `SidebarSummary.facts`; `core.units.device_facts` ("Temperature 48 °C", "Memory 598.7 MB / 8.5 GB", in the user's units; missing readings left out) and `format_used_total`; `CpuPage` and `GpuPage` fill them; `OverviewCard.facts_label` shows them; `OverviewPage.fit_key` refits when a card's line appears | Unit: formatting, units, missing readings; UI: cards, laptop fixture (CPU temperature; Intel iGPU none), NVIDIA fixture (both) |
| 57.7 | Screenshot scene `real-cpu-total` (next to `real-cpu`) | Screenshots |

*Found while doing 57:* with 24 logical CPUs in a 1024×768 window, the
legend with values took 5 rows and left the chart a few pixels: hence
57.4 and 57.5. In larger windows the values stay.
