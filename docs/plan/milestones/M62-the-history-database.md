# Milestone 62: The history database

*✅ Done.* Was Idea 2. SQLite replaces the M58 statistics files (imported once): a day of detail, a month of minutes, hours after that, under a 512 MiB cap; graphs fill from it at start-up; *Export Statistics…*

Was Idea 2 (kept below with its measurements and reasoning). Every reading
goes into one SQLite file, `$XDG_STATE_HOME/proccoli/history.sqlite3`,
instead of the CSV files of Milestone 58. As it ages it's summarised, so
years of running stay small. Graphs show it at once, even from an earlier
run, and *Export Statistics…* writes the running session to files.

| Step | Create / change | Test |
|---|---|---|
| 62.1 | `core/history_db.py`: `HistoryDb(path, readonly)`, the SQL only. Tables `meta`, `device` (with each device's roll-up marks), `reading` (column → name, unit, scale), `session`; per device `d_<id>` (time in UTC ms, one integer column per reading), `d_<id>_m` and `d_<id>_h` (`n`, `<col>_avg/_min/_max`). Scaled integers per unit (`SCALES`); a new reading is `ALTER TABLE … ADD COLUMN` on all three. WAL, `synchronous=NORMAL`, `auto_vacuum=INCREMENTAL`, 512 KiB cache, 0600 file in a 0700 folder. Column names are the M58 ones (`column_name` moved here) | Unit in a temporary folder: file modes and pragmas, new columns, a clock set back, fixed-point round trips |
| 62.2 | Housekeeping in `HistoryDb`: `roll_up` (minutes from detail, hours from minutes weighted by `n`, from each device's mark, idempotent), `expire` (never what isn't summarised yet), `enforce_cap` (hours a month at a time, then minutes a day at a time, then detail an hour at a time, never the last hour), `vacuum` | Unit: two hours rolled up exactly; expiry; the cap; through `HistoryStore`, a simulated week (every level for its time) and 3 years with a 256 KiB cap (ends under it, recent hours kept, oldest gone) |
| 62.3 | `core/history_store.py`: `HistoryStore(devices, settings, path, version, wall_clock, idle, import_dir)` follows each device's `updated`, buffers rows, commits every 10 s and tidies every 10 minutes, both timed by the readings themselves; records sessions; logs errors and stops rather than raising. Settings `history`, `history-max-size` (MiB, 512, 16–4096), `history-detail-hours` (24, 1–168); `stats-log*` removed with `core/statslog.py`. `Application(history_path=, import_dir=)` starts it (never in `--demo`) | Unit: buffering, commit on quit, on/off (a new session), delete, unwritable folder, the detail-hours setting |
| 62.4 | Graphs from history: `History.room/backfill` and `history.resample` (replaced by per-point averages in 64.2). On each device's first reading of a run, and when *Graph Time Range* or *Refresh Speed* changes, `HistoryStore.backfill` reads the rows before the oldest sample held (minute averages where detail is gone), moves them from UTC to the monitor's clock, puts each on the nearest refresh slot, with gaps where nothing was recorded. One device per idle call | Unit: a new run shows the last one with the gap between; widening the range fills from the database; one device per idle call; nothing when off. Checked on this machine: a restart showed 31 older samples per device at once |
| 62.5 | `core/history_export.py`: `export_session` writes a new folder `proccoli-statistics-<UTC>Z` in the chosen one: a CSV per device (the M58 format), `<device>-minutes.csv` for the part older than the detail, `export.json`; its own read-only connection. `ui/export.py`: `StatisticsExport` (folder via `Gtk.FileDialog`, work on a thread, progress and result in toasts, *Open Folder*); main menu → *Export Statistics…* (`app.export-statistics`) | Unit: files, header, UTC times, real units, manifest, a second export beside the first, the long-session case; UI: cancel, one at a time, progress, failure, nothing recorded yet. Checked on this machine: 6 files and the manifest from a real session |
| 62.6 | Preferences → General → *History* (replaces *Statistics Files*): *Keep History*, *Keep Every Reading For*, *Maximum Size*, *Size on Disk* with *Delete History…* (a confirmation, also offered when *Keep History* is turned off), *Export…*. M58's `stats/*.csv` imported once, on idle, then the folder removed | Dialog tests with a fake store; import test (both files of a device, a bad row, a device not present, the folder removed) |
| 62.7 | `tests/ui/history_size.py`: the measurement, on this machine (below). README, [DESIGN §4.1](../../design/04-architecture-overview.md), [§11](../../design/11-cross-cutting-concerns.md), [Idea 2's design](../../design/ideas/idea-02-metrics-history-in-a-sqlite-database.md) | – |

**Measured with 62.7** on this machine (6 devices, 37 readings per
refresh, 1 s): **207 bytes a second of detail (17 MiB a day)**, 0.66 MiB a
day of minutes and hours; a commit (10 s of rows) 0.3 ms; rolling up an
hour 12 ms; the last 10 minutes of three devices read back in 1.5 ms.
Steady state about 37 MiB, plus about 4 MiB of hours a year. That's in
line with Idea 2's figures for the larger hybrid laptop (61 readings).

**Deviations from Idea 2, and why:**

- **Times are always milliseconds**, not seconds with milliseconds only at
  fast refresh speeds: one rule, and SQLite's variable-length integers
  make the difference about a byte per row.
- **No timers of its own:** commits and housekeeping run when a reading
  arrives and their time has come. Readings arrive every refresh anyway,
  and tests need no main loop.
- **An export never overwrites** because it always writes a new folder
  (`… (2)` if the name is taken), so there's nothing to ask.
- **The old files are imported as detail** whatever their age; the first
  housekeeping summarises and expires them like any other rows.
- **Not done yet:** longer *Graph Time Range* choices (an hour, a day)
  drawn from the database and the Intel *Details* tab's own history (both
  done in Milestone 64), and Idea 1's slower commits (Idea 1 isn't built).
