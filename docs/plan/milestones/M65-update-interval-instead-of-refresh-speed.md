# Milestone 65: Update Interval instead of Refresh Speed

*✅ Done.* Was Idea 6. 1, 2, 3, 5 or 10 s, never faster; an old choice carries over once

Was Idea 6 (below): *Refresh Speed* could go too fast (0.25 s refreshed
every device and every process four times a second).

| Step | Create / change | Test |
|---|---|---|
| 65.1 | Schema `update-interval` (enum `UpdateInterval`: 1, 2, 3, 5, 10 s; default 1 s). `core.ticker`: `UPDATE_INTERVALS_MS`, `REFRESH_SPEED_TO_INTERVAL`, `interval_for` (either nick), `update_interval_ms(settings)`. The ticker, device manager, history store, `ChartSettings`, Processes and the Intel and NVIDIA backends read it | Unit: intervals (none under 1 s), old nicks, the ticker and the manager follow it |
| 65.2 | `core.settings.migrate(settings)`: `refresh-speed` → `update-interval` and old Intel nicks, once (the old key is reset); `Application` runs it after loading and logs what it did | Unit: every old value; a second run and a fresh install do nothing |
| 65.3 | Preferences *Update Interval* (and *intel_gpu_top Update Interval*), the Intel tab's *Update Interval* menu with the same choices | Dialog test; the Intel menu has nothing under a second |
| 65.4 | README, [DESIGN §4](../../design/04-architecture-overview.md), [§11](../../design/11-cross-cutting-concerns.md) | – |

**Tests that relied on 0.25 s** (to draw a stretch of graph in a few
seconds) set the ticker's interval directly (`ticker.set_interval(250)`):
the screenshot script's demo scenes and three UI tests. Nothing a user
can choose goes under a second.
