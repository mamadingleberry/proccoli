# Bug 18: Changing the Time Range shows the last seconds as "not running"

Design note: [design/bugs/bug-18-a-time-range-change-shows-the.md](../../design/bugs/bug-18-a-time-range-change-shows-the.md)

*Open.*

**Seen:** "whenever I adjust the time range to 30s, it restarts new blank
section where it's 'Proccoli wasn't running'. Seems to only happens
whenever I adjust the Time Range."

**Cause:** a new range empties the window's charts and refills them
from the history through *now* (`HistoryStore.backfill`, `through_now`).
The recorder commits the history every `COMMIT_EVERY_S` (10 s), so the
file is 0–10 s behind (measured: 1.5–9.6 s). The refill finds no rows for
those seconds, and `offline_slots` marks them "not running", since the
recorder's current run ends, in the file, at its last commit. On *30
Seconds* that's up to a third of the chart; live readings then continue
after it, so it looks like a restart. Every range does it; on long ones
10 s is too thin to see. Opening a window doesn't, since Bug 9's fix
(the recorder commits on `Subscribe`).

**Fix (proposed):**

1. **Ask the recorder to commit before refilling:** a `Flush` method on
   the D-Bus interface (what `Subscribe` already does first); the
   window's store refills when it answers (asynchronously, so the window
   never waits).
2. **The open run isn't "not running":** while the window receives
   readings, slots after the newest run's recorded end are gaps at most,
   never offline.
3. **Keep what's already on screen:** points the window received live
   since the last commit are put back after the refill when the file
   doesn't have them yet.

| Step | Create / change | Test |
|---|---|---|
| B18.1 | `metrics_service.py`: `Flush()` (commits, returns the newest time written); `devices/remote.py`: `RemoteDeviceManager.flush(callback)` with `NO_AUTO_START` | Unit, on a private bus: rows buffered before `Flush` are readable after it |
| B18.2 | `core/history_store.py`: a range change flushes, then refills; `offline_slots` takes "running since" for the open run | Unit: after a range change with uncommitted readings, no slot in the last 10 s is offline; UI: *30 Seconds* after *1 Minute* has no shaded strip |
