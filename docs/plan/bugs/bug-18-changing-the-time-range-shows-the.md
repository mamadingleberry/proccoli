# Bug 18: Changing the Time Range shows the last seconds as "not running"

Design note: [design/bugs/bug-18-a-time-range-change-shows-the.md](../../design/bugs/bug-18-a-time-range-change-shows-the.md)

*Fixed in v0.6.0.* Also the *Bugs that Require Human Input* item "Graphs include a small area of 'Proccoli wasn't running' whenever the Time Range is adjusted": the same symptom.

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

**Fix:**

1. **Ask the recorder to commit before refilling:** a `Flush` method on
   the D-Bus interface (what `Subscribe` already does first); the
   window's store refills when it answers (asynchronously, so the window
   never waits).
2. **The open run isn't "not running":** while the window receives
   readings, slots after the newest run's recorded end are gaps at most,
   never offline.
3. *(Superseded by 1.)* Keeping the window's live points through the
   refill isn't needed once the recorder writes them out first.

| Step | Create / change | Test |
|---|---|---|
| B18.1 | `metrics_service.py`: `Flush()` (commits); `devices/source.py`: `DeviceSource.flush(then)` (local: at once); `devices/remote.py`: `RemoteDeviceManager.flush(then)` calls `Flush` with `NO_AUTO_START`, then `then` (also on an error or when away) | `test_metrics_service`: rows buffered before `Flush` are readable after it; `test_remote`: `flush` waits for the answer, and calls back at once without a collector |
| B18.2 | `core/history_store.py`: `backfill_all` asks `devices.flush`, then refills; `open_run()` extends the newest session to now while its end is within the commit interval | `OpenRunTest`; `RangeChangeWhileRecordingTest`: a separate recorder with 5 s unwritten, *30 Seconds*: no offline slot (fails without `open_run`), and the refill waits for the flush and shows the flushed seconds (fails without the flush) |

**Found while doing it:** the first regression test passed without the
fix: its "recorder" store also drew graphs, so it wrote out its own
buffer when the range changed. The real recorder draws none
(`graphs=False`); with that, the test fails without the fix and passes
with it.
