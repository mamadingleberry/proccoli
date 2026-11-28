# Milestone 64: History follow-ups

*✅ Done.* *Graph Time Range* up to a day (at most 1200 averaged points per graph); both GPU *Details* tabs recorded and filled from the database

The two things Milestone 62 left: *Graph Time Range* choices longer than
10 minutes, and the GPU *Details* tabs filled from the database too.

| Step | Create / change | Test |
|---|---|---|
| 64.1 | `core/ticker.py`: `MAX_GRAPH_POINTS` (1200), `history_plan(span, interval)` → `(points, every)`, `graph_plan(settings)` → `(points, every, step_s)`; ranges 30 minutes, 1 hour, 6 hours, 1 day (schema, Preferences). `core.history.Averager`; `History.set_plan`, `every`, `step_s`, `keys()`; `Monitor.set_history_plan`; `DeviceManager` applies the plan when a device is added and when the range or speed changes | Unit: plans (a day at 1 s: 1184 points of 73; 10 min at 0.25 s: 801 of 3; under 10 min unchanged), the averager, averaged points and gaps |
| 64.2 | `HistoryDb.buckets(table, columns, origin, count, bucket)`: the average per point slot in one grouped query per level (minutes where detail is gone). `HistoryStore._fill` replaces the nearest-row resample (`history.resample` removed); a history with no point yet is filled before "now" | Unit: buckets with minutes, detail and gaps; a 1-hour range after a 1 s run fills with 4 s averages at once. Checked on this machine: a second run with a 1-hour range at 0.25 s showed the first run's points on every device |
| 64.3 | The Details tabs: `DetailBackend.history_readings()` / `history_target()`; `GpuSnapshot.detail` recorded as `detail/<key>` columns; `Monitor.detail_history()` (the controller: the running source's history); the store fills it once per Details tab and after a range or speed change. Intel `History`: averaging, `WALL_TIMES`, `room`, `keys`, `readings`, `backfill`. The NVIDIA history now follows the range (it was sized once, at start) | Unit: Intel averaging, readings and backfill; snapshot prefix; a Details history filled from the last run in wall-clock times |
| 64.4 | [DESIGN §11](../../../design/11-cross-cutting-concerns.md), [Feature 2's design](../../../design/features/feature-02-metrics-history-in-a-sqlite-database.md); README | – |

**Choices made:** a point of a long range is the **average** of its
samples, so a short spike is smoothed out at an hour or a day (the
database keeps every reading for a day, and the export has them all).
The first point of a long range appears after `every` samples (73 s for a
day at 1 s); until then the graph shows what the database held. Not
checked on real Intel or NVIDIA hardware: this machine's Intel GPU has no
`intel_gpu_top` access, so the Details fill is covered by unit tests only.

**Found while doing 64.3:** the NVIDIA *Details* history was sized once,
when the tab started, and never followed a new *Graph Time Range* or
*Refresh Speed*. It does now.
