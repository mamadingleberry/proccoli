# Bug 1: Graphs stretch old points after a time range change

Design note: [design/bugs/bug-01-graphs-stretch-old-points-after-a.md](../../design/bugs/bug-01-graphs-stretch-old-points-after-a.md)

*Fixed in v0.4.0.* As built: a shorter step empties the history
instead of regrouping it (what lay between the old points is gone), and
the store refills it from the database.

**Seen:** on 0.3.0, about 3 hours after first running it, the graphs on
*1 Day* were full from edge to edge, as if they held 24 hours of data.
The history database held 3.2 hours (15:03 to 18:15).

**Cause:** a graph has no time per point. `graph_runs` draws its points
evenly by index, newest at the right, and treats them as `step_s` apart.
`step_s` depends on the range (at 1 s updates: 1 minute 1 s, 1 hour
4 s, 6 hours 19 s, 1 day 73 s). When the range changes,
`History.set_plan()` keeps the points it holds, at their old spacing,
and the history store's `backfill_all()` only fills the room *in front
of* them. The log showed it exactly when the range went from 1 minute to
1 hour to 6 hours to 1 day: 840 points backfilled (901 − 61), then 236
(1137 − 901), then 47 (1184 − 1137). The 1-day graph then held about a
minute of 1 s points, an hour of 4 s points and 75 minutes of 19 s
points, drawn 73 s apart. The time axis and the hover's "… ago" are
wrong for everything but the newest minute. The Intel GPU Details history
(`gpu/intel_gpu_top/history.py`) has the same flaw.

The database side is right: backfilling an empty graph on *1 Day* from
the same database fills only the right-hand 3.2 hours (159 points).

**Fix:**

- When `set_plan` changes `step_s` (or `every`), the history is
  **regrouped**: its points are put into the new step's slots by their
  own times (averaging where several fall into one slot, gaps where none
  does), so it's right even without the database.
- Then, with *Keep History* on, `backfill_all()` refills it **in full**
  from the database instead of just the room in front: clear, then
  `_fill` with the whole plan. The database has every reading at full
  detail for `history-detail-hours`, so nothing is lost, and the newest
  half-made point carries over.
- The same for the Details histories (`detail_history()`).

| Step | Create / change | Test |
|---|---|---|
| B1.1 | `core/history.py`: `History.regroup(step_s)` called from `set_plan` when the step changes; the same in `gpu/intel_gpu_top/history.py` | Unit: 60 points 1 s apart regrouped to 4 s give 15 averaged points with the right times; a longer step never leaves points closer than it |
| B1.2 | `core/history_store.py`: a plan change refills the whole history from the database | Unit (temporary database, fixed clock): 3 hours of rows; switch 1 minute → 1 hour → 6 hours → 1 day; the 1-day graph covers 3 hours (no more points than 3 h / 73 s, the oldest time 3 hours ago) |
| B1.3 | UI smoke test: the same range changes on a live window; the hover heading at the left edge of the data says about 3 h | UI |
| B1.4 | [DESIGN §14](../../DESIGN.md) as fixed; the Progress row moves to done | Run |

**Done when:** after any sequence of range changes, every graph's
points are `step_s` apart in time and the axis matches the data.
