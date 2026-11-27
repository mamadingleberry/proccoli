# Idea 2: Metrics history in a SQLite database (replaces the statistics files)

Design note: [design/ideas/idea-02-metrics-history-in-a-sqlite-database.md](../../design/ideas/idea-02-metrics-history-in-a-sqlite-database.md)

*Done as Milestone 62* (its deviations are listed there).

**Goal:** keep a history of every reading Proccoli shows, cheaply and for
as long as Proccoli runs (years without a restart included), without it
growing without bound; let graphs show that history at once; and let the
user export the running session's readings to files of their own.

**Decision: a SQLite database instead of files.** When this idea is
built, the statistics files of Milestone 58 (CSV per device) go away:
Proccoli no longer writes metrics to files on its own. The only metric
files are the ones the user asks for (export, below). Python's built-in
`sqlite3` is used, so nothing new to install (Ubuntu 24.04: SQLite
3.45). Measured on this machine (Ubuntu 24.04, the hybrid laptop: 61
readings per refresh across CPU with 24 threads, memory, two GPUs, a drive,
two network interfaces and a battery), one simulated hour at 1 s:

| Storage | Bytes per second | Per day | Per year, if all kept |
|---|---|---|---|
| CSV files (M58, measured from a real run) | 452 | 37 MiB | 13 GiB |
| SQLite, one row per reading (`series, time, value`) | 916 | 76 MiB | 27 GiB |
| SQLite, one table per device, readings as real numbers | 356 | 29 MiB | 10 GiB |
| **SQLite, one table per device, readings as scaled integers** | **239** | **20 MiB** | **7 GiB** |

- **Disk:** the chosen layout (last row) takes about half of what the CSV
  files take, and, unlike files, it can summarise old data in place.
- **Memory:** about the same. `sqlite3` with a 512 KiB page cache adds
  about 0.9 MiB of private memory (its library, 1.5 MiB more, is shared
  with other programs); the `csv` module alone added about 1 MiB.
- **Reading back:** the last 10 minutes of three devices took 6 ms, by an
  indexed time range, instead of parsing file tails.
- **Writing:** one transaction every 10 s in WAL mode: about as many bytes
  written to disk a day as the CSV files.

So SQLite is the lighter option overall, and much the lighter for anything
that reads the history back.

**Keeping years of history realistic.** Even the compact layout would
reach 7 GiB a year at full detail, far above the 1 GB limit, so full
detail isn't kept. Older readings are rolled up into summaries, as RRDtool,
Prometheus and netdata do:

| Level | What | Kept for | Typical size (this machine, 1 s) | Worst case |
|---|---|---|---|---|
| Detail | every reading, every refresh | 24 hours | 19.7 MiB | 185 MiB |
| Minutes | per minute: average, minimum, maximum of each reading | 30 days | 25 MiB (0.83 MiB a day) | 59 MiB |
| Hours | per hour: average, minimum, maximum | until the size cap | 7.5 MiB a year (21 KiB a day) | 18 MiB a year |

- **A day** writes about 20.6 MiB (detail, plus 0.83 MiB of minutes and
  21 KiB of hours). Kept as it is, a year would be 7 GiB: too much, hence
  the levels.
- **Steady state, typical:** 19.7 + 25 = 45 MiB plus 7.5 MiB per year:
  **about 52 MiB after a year, 120 MiB after ten.**
- **Upper bound.** Halving the yearly figure (as suggested) gives a lower
  number, not an upper bound, so the bound is a worst case instead: a
  machine with 64 logical CPUs and more devices (about 110 readings, ×1.8),
  busy (values that compress worse, ×1.3), at the fastest refresh (0.25 s,
  ×4, which affects only the detail level): **about 260 MiB after a year,
  420 MiB after ten.**
- **Size cap:** `history-max-size` (MiB, default **512**, up to 4096). Even
  the worst case stays under it for ten years, so the cap is a safety net:
  if the database ever exceeds it, the oldest hours go first, then the
  oldest minutes; detail is never cut below 1 hour. I'd keep 1 GB as the
  most it may ever take (512 MiB default, with room to raise it): 1 GB
  is a lot for a system monitor's history, and typical use stays near
  50–120 MiB.

**Design ([Idea 2's design](../../design/ideas/idea-02-metrics-history-in-a-sqlite-database.md)):**

- **Where:** `$XDG_STATE_HOME/proccoli/history.sqlite3` (state, like the
  log), 0600, in the 0700 folder. WAL mode, `auto_vacuum=INCREMENTAL`,
  a 512 KiB page cache.
- **Layout:** one table per device (`device` table maps device IDs to
  table names, names and kinds), `time` (UTC, integer seconds; milliseconds
  where the refresh is faster than 1 s) as the primary key, one integer
  column per reading in fixed-point units (hundredths of a percent and of
  a degree, milliwatts, kHz, bytes). A new reading (a GPU's details
  starting, CPU threads appearing) is an `ALTER TABLE … ADD COLUMN`, which
  SQLite does without rewriting. Summary tables mirror each device table
  with `<reading>_avg/_min/_max` and a sample count. A `session` table
  records each run's start and end (UTC).
- **Writing:** `HistoryStore` follows the monitors' `updated` signal like
  `StatsLog` does now, buffers rows and commits every 10 s on the main
  loop (a few milliseconds); on quit it commits what's left and records
  the session's end.
- **Housekeeping** every 10 minutes, so it works without ever quitting:
  roll finished minutes up from detail and finished hours up from minutes
  (`INSERT … SELECT avg/min/max … GROUP BY`), delete what's past its level,
  `PRAGMA incremental_vacuum` to give the space back, and enforce the cap.
  Times are UTC epochs, so time zone and daylight-saving changes don't
  matter; a clock set backwards only overwrites its own seconds
  (`INSERT OR REPLACE`).
- **Graphs from history** (what this idea was before): widening *Graph
  Time Range*, or starting Proccoli, fills each graph from the database at
  once: detail rows for the range (minute averages beyond 24 hours),
  converted from UTC to the monitor's clock, resampled to the refresh
  speed, with gaps where Proccoli wasn't running. On idle, one device at a
  time, so the window never stalls. Longer ranges (an hour, a day) can
  then be offered without keeping them in memory, which suits Idea 1.
- **Export of the running session** (required): main menu → *Export
  Statistics…* (and Preferences → *History*): the user picks a folder
  (`Gtk.FileDialog`, so it works through the desktop portal), and Proccoli
  writes, for **this session** (since Proccoli started):
  - one CSV file per device (RFC 4180, UTF-8; `time_utc` in ISO 8601 UTC
    with milliseconds, then `<reading>_<unit>` columns, values in their
    real units: the M58 format, now made only on request);
  - if the session is longer than the detail level (more than 24 hours),
    the older part from the minute level, in `<device>-minutes.csv` with
    `_avg`/`_min`/`_max` columns;
  - `export.json`: Proccoli's version, the session's start and end (UTC),
    each file's device name, kind and columns with units.

  It runs off the main loop (reads in chunks on idle, or a worker thread
  with its own connection), reports progress in a toast, and never
  overwrites files without asking. A range other than "this session"
  (the last hour, day, week) is an easy extension of the same query.
- **Settings:** `history` (on), `history-max-size` (MiB, 512), and
  `history-detail-hours` (24; 1–168). `stats-log` and
  `stats-log-max-size` are removed.
- **From the M58 files:** on the first start with the database, any
  existing `stats/*.csv` are imported (they become detail or minute rows
  by age) and the folder is removed, logged once.
- **Never** in `--demo` (made-up data), and nothing kept with `history`
  off (turning it off offers to delete the database).
- **Lightweight mode (Idea 1):** keeps the database (it costs about 1 MiB)
  but writes every 60 s instead of 10 s.

| Step | Create / change | Test |
|---|---|---|
| I2.1 | `core/history_store.py`: schema, fixed-point conversion per unit, `HistoryStore(devices, settings, path, wall_clock)`: buffered writes, 10 s commits, sessions, new columns | Unit in a temp folder with a fake clock: rows, units round-trip, a new column, a clock set back, commit on quit |
| I2.2 | Housekeeping: roll-ups, expiry, incremental vacuum, size cap (oldest hours first, never detail under 1 hour) | Unit: a simulated week and a simulated 3 years (fake clock, small cap) end within the cap with the right levels |
| I2.3 | `tests/ui/history_size.py`: the measurement above, recorded in this plan | Run on the real machine |
| I2.4 | Graphs from history on range change and at start-up (`History.backfill`: UTC → monotonic, resample, gaps) | Unit with fixture rows; UI: a widened range shows old data at once |
| I2.5 | *Export Statistics…*: per-device CSV + `export.json` for the session, minute file when longer than the detail level; off the main loop | Unit: files, headers, UTC times, units, the long-session case; UI: menu and dialog with a fake file chooser |
| I2.6 | Preferences → *History* (switch, size cap, detail hours, size used, *Export…*, *Delete History…*); remove *Statistics Files* and `core/statslog.py`; one-time import of old CSV files | Dialog tests; import test |
| I2.7 | README (*Files Proccoli keeps*, *Exporting statistics*), [DESIGN §11](../../design/11-cross-cutting-concerns.md) and [Idea 2's design](../../design/ideas/idea-02-metrics-history-in-a-sqlite-database.md) as built | – |

**Done when:** Proccoli keeps a full day of detail, a month of minutes
and years of hours in one database that stays under its cap (measured
and simulated), graphs fill from it at once, and *Export Statistics…*
writes the session to the user's chosen folder.
