# Milestone 41: Busiest apps and processes on the Overview

*✅ Done.* Top 10 of each by processor or memory; System Processes not ranked as an app

| Step | Create / change | Test |
|---|---|---|
| 41.1 | `processes/top.py` (pure): `TopMetric` (cpu, memory), `rank_key`, `top`, `top_apps` (no System Processes), `top_processes`; `TOP_COUNT = 10` | Unit: both orders, tie-breaks, limit, nicks match the schema |
| 41.2 | Schema `overview-top-by` (enum `TopMetric`, default `cpu`) | Settings tests |
| 41.3 | `ui/widgets/top_table.py`: `TopTable` / `TopRow` (rank, icon, name, processor, memory; rows refilled in place; highlighted ranking column) | UI test |
| 41.4 | `TopTables` in `OverviewPage(settings, navigate, processes, grouper)`: Processor/Memory toggle bound to the setting, acquires the monitor only while mapped, rows open Apps/Processes; side by side or stacked | UI tests with a fixture monitor: ranking, toggle, acquire/release, updates, navigation, no monitor → no tables |
| 41.5 | Screenshot scenes `real-overview-tables`, `real-overview-portrait` (`_scroll: end` in `shoot.py`) | Screenshots |

**Done when:** the Overview lists the ten busiest apps and processes,
live, ranked by the chosen measure.
