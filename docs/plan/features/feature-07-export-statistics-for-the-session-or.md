# Feature 7: Export Statistics for the session or the whole saved history

Design note: [design/features/feature-07-export-any-part-of-the-history.md](../../design/features/feature-07-export-any-part-of-the-history.md)

**Goal:** *Export Statistics…* lets the user choose what to export: **this
session** (since Proccoli started, what it does now) or **the saved
history** (everything in the database, across every run), plus a few
ranges in between.

**Why:** today the export always covers the running session only
(v0.3.0). The database usually holds much more: a day of every
reading, a month of minute summaries, and hours going back as far as the
size cap allows. To get at the rest, a user has to query
`history.sqlite3` with their own tools.

**Design ([Feature 7's design](../../design/features/feature-07-export-any-part-of-the-history.md)):**

- **A choice before the folder picker:** an `Adw.Dialog` *Export
  Statistics* with a *What to Export* combo:
  - *This Session* (the default, today's behaviour);
  - *Last Hour*, *Last Day*, *Last Week*;
  - *All Saved History*.

  Under it, what that covers and an estimate ("about 3 days, 2 sessions,
  about 40 MB of CSV"), then *Export…*, which opens the folder picker as
  now.
- **One export function for any range:** `export_session` becomes
  `export_range(db_path, parent, start_ms, end_ms, scope)`. Each level
  goes in its own file per device, and only for the part of the range
  that level holds, so no time appears twice:
  - `<device>.csv`: every reading, where detail is kept;
  - `<device>-minutes.csv`: minute average, minimum and maximum, where
    only minutes are kept;
  - `<device>-hours.csv`: the same per hour, older than that.
- **`export.json`** gains the scope, the range (UTC), every session in it
  (start and end, so gaps where Proccoli wasn't running can be told from
  missing data), and each file's level and time span.
- **Big exports:** *All Saved History* can be hundreds of MB of CSV (the
  database is capped at 512 MiB by default, and CSV takes about 2–3 times
  the space). So:
  - the estimate comes from row counts per level, in one quick query;
  - files are written in hour-sized chunks on the worker thread, as now;
  - the toast shows progress and has *Cancel* (a `threading.Event`
    checked between chunks; a cancelled export removes its folder);
  - an export that would be larger than the free space in the chosen
    folder says so before it starts.
- **The menu and Preferences** open the same dialog (*Export…* in
  Preferences → *History*). The folder naming stays as it is
  (`proccoli-statistics-<UTC>Z`), so nothing is ever overwritten.

| Step | Create / change | Test |
|---|---|---|
| F7.1 | `core/history_export.py`: `ExportScope` (session, hour, day, week, all), `scope_range(scope, now, session_start, oldest)`, `export_range` with detail / minutes / hours files that don't overlap, hours files, sessions in `export.json`, a cancel event | Unit: each scope's range; levels split without overlap (fake rows over a week); hours file; sessions listed; cancel removes the folder |
| F7.2 | `estimate(db, start, end)`: rows per level and an approximate size from average row widths; a free-space check through `System` | Unit with fixture rows; the not-enough-space case with a fake `System` |
| F7.3 | `ui/export.py`: the *Export Statistics* dialog (scope combo, what it covers, estimate), then the folder picker; the toast with progress and *Cancel* | UI: the default is *This Session*; changing the scope updates the estimate; *Cancel* stops it and removes the folder |
| F7.4 | README (*Exporting statistics*), [Feature 7's design](../../design/features/feature-07-export-any-part-of-the-history.md) as built | – |

**Done when:** *Export Statistics…* can write this session, the last
hour, day or week, or all saved history, each level in its own file with
no time appearing twice, shows how big it will be first, and can be
cancelled.

**Open questions for the user:**
1. Are the in-between ranges (last hour, day, week) worth having, or just
   *This Session* and *All Saved History*?
2. One CSV per device and level (simple, opens in any spreadsheet), or
   also an option to write everything into a single `.zip`?
3. For *All Saved History*, should the export also be able to include the
   database file itself (`history.sqlite3`, the most compact and complete
   copy), for people who'd rather query it with their own tools?
