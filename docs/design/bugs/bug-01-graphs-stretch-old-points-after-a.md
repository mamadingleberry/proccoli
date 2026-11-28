# Bug 1: Graphs stretch old points after a time range change

Plan: [plan/bugs/bug-01-graphs-stretch-old-points-after-a.md](../../plan/bugs/bug-01-graphs-stretch-old-points-after-a.md)


*[PLAN.md, Bug 1](../../plan/bugs/bug-01-graphs-stretch-old-points-after-a.md). Fixed in v0.4.0; kept as the record.* `History` holds points without a per-point spacing;
`graph_runs` draws them evenly, `step_s` apart. A range change updates
`step_s` but keeps the points taken at the old step, and backfill only
fills the room in front:

```mermaid
sequenceDiagram
    participant S as Settings
    participant H as History (graph)
    participant St as HistoryStore
    participant G as Graph
    S->>H: set_plan(1184 points, step 73 s) (was 1137 at 19 s)
    Note over H: keeps its 1137 points, 19 s apart (and 4 s, 1 s ones)
    S->>St: backfill_all()
    St->>H: backfill(room = 47 points)
    H->>G: 1184 points
    Note over G: drawn 73 s apart: ~3 h of data fills a 24 h axis
```

**The fix (v0.4.0):** `History.set_plan` regroups the held points into a
longer step's slots by their times (`core.history.regroup`) and empties
the history for a shorter step. With the history database on, the
store's `backfill_all` then empties each history and fills it again in
full from `HistoryDb.buckets`, its slots ending at "now". The Intel
Details `History` does the same.

```mermaid
sequenceDiagram
    participant S as Settings
    participant H as History (graph)
    participant St as HistoryStore
    S->>H: set_plan(1184 points, step 73 s)
    Note over H: regroup: held points averaged into 73 s slots
    S->>St: backfill_all() (idle)
    St->>H: clear(), _fill(through_now): every slot from the database
    Note over H: points 73 s apart, offline slots flagged
```
