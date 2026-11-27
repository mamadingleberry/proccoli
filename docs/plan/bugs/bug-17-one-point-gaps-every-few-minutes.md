# Bug 17: One-point gaps every few minutes in graphs from the history

Design note: [design/bugs/bug-17-graphs-from-the-history-miss-a.md](../../design/bugs/bug-17-graphs-from-the-history-miss-a.md)

*Fixed in Milestone 87.* As proposed. The detail query also returns each
slot's first and last reading time (`min(time)`, `max(time)`) so
`mend_drift` can tell drift from a gap.

**Seen:** "why are there still gaps in the GUI graphs for while the GUI
was closed, even though the proccoli background process was still
running?" Checked: the history had a reading every second through the
time the window was closed (19 in 18.6 s), and the window loaded them,
but a window built on a copy of the history showed short breaks in the
lines: one point missing about every 3½ minutes (two in 5 minutes).

**Cause:** the recorder's ticks are 1004–1006 ms apart, not 1000: the
ticker re-arms `GLib.timeout_add`, which counts each interval from when
the previous tick's work *finished* (reading the devices takes ~5 ms).
The readings drift about 5 ms a tick, a whole second every ~200 ticks.
The window lays the history out in slots one step wide, so every ~200
slots one gets no reading: a gap that isn't in the data. Live readings
don't show it (they're drawn as they arrive).

**Fix (proposed):**

1. **A ticker without drift:** each tick is scheduled for
   `start + n × interval` on the monotonic clock (a one-shot timeout for
   the time left), so readings stay one interval apart on average; a
   late tick is never made up twice.
2. **Slots that tolerate drift** for what's already recorded: a slot with
   no reading, between two that have one, takes the nearer neighbor's
   reading when the readings around it are less than 1½ steps apart
   (the recorder was running; the reading only slipped into the next
   slot). A real gap (a stopped recorder) is longer than that and stays.

| Step | Create / change | Test |
|---|---|---|
| B17.1 | `core/ticker.py`: drift-free scheduling | Unit, with the injected clock and `timeout_add`: 1000 ticks with 5 ms of work each stay within one interval of `start + n × interval` (drifts 5 s without the fix) |
| B17.2 | `core/history_db.buckets` (or a pure helper beside it): mend one-slot holes left by drift | Unit: readings 1005 ms apart fill every 1-s slot; a 71-s gap stays a gap; minute averages unaffected |
| B17.3 | [Bug 17's design](../../design/bugs/bug-17-graphs-from-the-history-miss-a.md) | — |
