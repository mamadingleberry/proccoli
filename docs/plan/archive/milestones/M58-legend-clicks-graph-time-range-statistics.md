# Milestone 58: Legend clicks, graph time range, statistics files

*✅ Done.* Normalize Processor Usage kept (see 58.3); Features section added

| Step | Create / change | Test |
|---|---|---|
| 58.1 | Per-CPU legend: **left-click** an item hides or shows its line; **right-click** (long press on touch) shows only that line, and again brings every line back. `ui/series_visibility.py` (pure: `toggle`, `solo`); `Legend.shown/set_shown/toggle/solo`; hover text says so | Unit: the rules; UI: solo and back, left-click |
| 58.2 | *Graph Data Points* becomes **Graph Time Range** (`graph-time-range`: 30 s, 1, 2, 5, 10 min; default 1 min, what 60 points at 1 s showed). `core/ticker.py`: `TIME_RANGES_S`, `time_range_s`, `history_points` (now shared with the Intel backend), `graph_points(settings)`; every monitor and the NVIDIA backend size their history from it; `DeviceManager` resizes on either the range or the refresh speed; axes span = the range. Before, a faster refresh silently shortened what graphs showed | Unit: points per range and speed, every nick in the schema, the manager resizes on both keys, the span holds; UI: axes, Preferences combo |
| 58.3 | *Normalize Processor Usage* reviewed: **kept**. It decides whether the Apps/Processes processor column is a share of the whole processor (adds up to the total; default) or per core like `top` (one busy core = 100 %). On a 24-thread machine a stuck single-threaded process reads 4.2 % or 100 %: both are wanted. Its subtitle and schema text said something else ("divide the total usage of all cores…"); now they say what it does | – |
| 58.4 | `core/statslog.py`: **statistics files**. One RFC 4180 CSV per device in `$XDG_STATE_HOME/proccoli/stats/`, `time_utc` (ISO 8601 UTC, ms) then `<reading>_<unit>` columns (`usage_percent`, `read_bytes_per_second`, …), empty for no reading; each file capped at `stats-log-max-size` (KiB, default 4096) with one older file; a new file when the columns change; continues an earlier run's file when they match; 0600 files, 0700 folder; buffered 10 rows, written out on quit. `Snapshot.stats_values/stats_units` (memory and GPU add byte figures). `core.units.iso_utc` (shared with the log's `UtcFormatter`). Schema `stats-log` (on), `stats-log-max-size`. `Application(stats_dir=...)` starts it (not in `--demo`); Preferences → General → *Statistics Files* | Unit: names, values, rollover, header change, resume, buffering, recording, on/off, live size, shutdown, unwritable folder; UI: Preferences rows and *Open Folder*. Checked on the real machine: 8 files, one row per second each |
| 58.5 | *Features* section (below): the lightweight mode (was Milestone 56) and filling graphs from the statistics files | – |

*Found while doing 58:*
- A CPU row with 24 logical CPUs is about 140 bytes, so the default 4 MiB
  holds about 8 hours at 1 s refresh (plus the older file); a network row
  about 50 bytes, about a day.
- The screenshot harness failed one scene now and then (a different one
  each full run, never on its own): right after a page switch the window
  could have nothing painted yet. `shoot.py`'s `snapshot` now waits (up
  to 3 s) for a painted frame; two full runs afterwards passed every
  scene.
