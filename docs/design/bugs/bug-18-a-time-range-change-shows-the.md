# Bug 18: A Time Range change shows the last seconds as "not running"

Plan: [plan/bugs/bug-18-changing-the-time-range-shows-the.md](../../plan/bugs/bug-18-changing-the-time-range-shows-the.md)


*[PLAN.md, Bug 18](../../plan/bugs/bug-18-changing-the-time-range-shows-the.md). Open.*

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
    W->>R: (proposed) Flush, then refill
```

Proposed: the window asks the recorder to commit (`Flush`) before it
refills; slots after the open run's last commit count as running; live
points not yet in the file are kept.
