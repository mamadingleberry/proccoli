# Bug 18: A Time Range change shows the last seconds as "not running"

Plan: [plan/bugs/bug-18-changing-the-time-range-shows-the.md](../../plan/bugs/bug-18-changing-the-time-range-shows-the.md)


*[PLAN.md, Bug 18](../../plan/bugs/bug-18-changing-the-time-range-shows-the.md). Fixed.*

```mermaid
sequenceDiagram
    participant R as proccoli (recorder)
    participant H as history.sqlite3
    participant W as proccoli-gui
    R->>H: commit (every 10 s)
    Note over R: readings buffered (0–10 s)
    W->>W: Time Range changed: charts emptied
    W->>H: refill through now
    H-->>W: rows up to the last commit; the run "ends" there
    Note over W: last 0–10 s: no data, shaded "not running"
    W->>R: Flush()
    R->>H: commit
    R-->>W: done
    W->>H: refill through now
```

The fix: on a range change the window's `HistoryStore.backfill_all` calls
`devices.flush(then)`. A `RemoteDeviceManager` asks the recorder's
`Flush()` (which commits) and refills when it answers; a local
`DeviceManager` refills at once, since its own store just committed. As a
second guard, `open_run()` treats the newest session as running until now
while its recorded end is within the commit interval, so seconds not yet
written are a gap at most, never "not running".
