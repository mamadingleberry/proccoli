# Milestone 3: Graph widgets

*✅ Done.* Sidebar meter now lives in the sidebar (1.9)

*Goal: the reusable Resources-style widgets, demonstrated on a fake data
source.*

| # | Create | Test |
|---|---|---|
| 3.1 | `ui/widgets/graph.py`: `Graph` (Cairo; port `snap_to_device` and the palettes from intel_gpu_top_gui; rounded clip; fill; optional grid; normal and small styles) | Unit: the pure helpers (`snap_to_device`, `nice_ceiling`). Smoke: draws with 0, 1 and 60 points. |
| 3.2 | `ui/widgets/graph_box.py`: `GraphBox(Adw.PreferencesRow)` | Smoke |
| 3.3 | `ui/widgets/double_graph_box.py`: `DoubleGraphBox` | Smoke |
| 3.4 | `ui/widgets/info_row.py`: `InfoRow` (`set_value(None)` hides the row) | Smoke: visibility follows the value |
| 3.5 | `ui/widgets/meter.py`: `Meter` (progress bar or mini graph) | Smoke for both modes |
| 3.6 | `devices/base.py`: `DeviceKind`, `DeviceInfo`, `Snapshot`, abstract `Monitor` (history, `refresh()` → `sample()` → `updated`) | Unit: a fake `SineMonitor` produces snapshots, and the history grows to `max_points` |
| 3.7 | `--demo` mode: a `DemoPage` driven by `SineMonitor`, with a sidebar meter ✅ (meter shown as an in-page preview until step 1.9) | UI smoke test: page follows monitor and settings; manual screenshot |

**Done:** `make demo` shows a live animated graph page and a sidebar meter.
