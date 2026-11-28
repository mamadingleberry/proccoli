# Bug 22: The window freezes after unlocking or waking from suspend

Design note: [design/bugs/bug-22-the-window-freezes-after-unlocking-or.md](../../design/bugs/bug-22-the-window-freezes-after-unlocking-or.md)

*Fixed in v0.6.0.* The *Done when* check (a locked night on the reporting machine) is still to be done.

**Seen:** "the app freezes when unlocking or waking up from suspend
mode".

**Found so far** (the window that froze on 2026-11-27 at 13:27, from
its log and the journal):

- It had run for 26 hours (started at 11:20 the day before, just after
  an unlock) and used 16 h 13 min of CPU in that time; systemd reported
  866 MiB at its peak, and its last performance line said 94 % of a
  core, 1110.7 MiB, slowest refresh 24.1 s (a healthy window: about
  117 MiB, 15 % of a core).
- It wasn't fine until the unlock: the watchdog's first stall was at
  19:07 the night before, about 18 hours earlier, and from then on the
  main loop stalled for 9–24 s at a time, every few seconds, all night
  (126 stall reports in the first hour, about 460 an hour by 22:00).
  The machine hadn't been suspended in that time (the last suspend was
  on the 24th); the screen was locked.
- All 585 sampled stacks are in a table page's `update_rows`, on the
  process monitor's `updated` signal: 378 in `self.store.append(row)`,
  206 in `self.store.remove(pos)` (after `self.store.find(row)`).
- The whole time, a Docker container was restarting every 15 s, so
  processes came and went all night.

So the unlock is when the freeze was seen; what started it is likely
the row churn on a table page that stayed on screen (mapped, and so
scanning) all night, not the lock or the wake themselves. Why one
append or remove costs seconds is still to be measured. Suspects, to
confirm or rule out:

1. **One change at a time:** each `append` and `remove` is its own
   `items-changed`, so the filter, the sorter (re-sorted again with
   `SorterChange.DIFFERENT`) and the column view react per row, and
   `store.find` is a scan; with many rows changing, the cost multiplies.
2. **Work piling up while nothing is drawn:** with the screen locked
   (or the window hidden) the compositor sends no frames, so the column
   view never lays out; if removed rows' widgets are only reclaimed at
   layout, every tick adds more, which would also explain the memory.
3. **Something in `rows` or the store that only grows** (the store
   longer than `rows`), to rule out with a count.

**Fix (proposed):** reproduce first: a loop that starts and ends a few
short processes every 15 s, the window left on Processes or Apps for
some hours, once visible and once locked, logging the store's length,
`len(rows)` and each `update_rows`'s time. Then, depending on what that
shows:

- diff the rows into the store as one `splice` per refresh (removals
  and additions together), with positions from a key → row index rather
  than `find`;
- while the window isn't shown (the screen locked, minimized, hidden
  behind Lightweight Mode), stop refreshing the tables, as an unmapped
  page already does, and refresh once when it's shown again (the
  toplevel's state where GTK reports it, feature-checked; otherwise
  `is-active` and visibility);
- whatever the counts show grows.

| Step | Create / change | Test |
|---|---|---|
| B22.1 | A churn benchmark (a script, not shipped) and a debug-log line for a refresh over 100 ms (rows, gone, new) | `RowChurnTest`: the log line; the benchmark below; a locked night still to run |
| B22.2 | `ui/table_diff.py` (`plan_splice`, pure); `ui/pages/table.py`: `update_rows` as one `splice` (from the first gone row: the kept rows, then the new); `self.rows` mirrors the store's order, so no `find` | `test_table_diff` (random cases); `RowChurnTest`: 500 scattered gone + 500 new is one `items-changed` (fails on the old code), only new rows is one append, a selected row stays selected |
| B22.3 | `ui/compat.py`: `toplevel_suspended(state)` (`Gdk.ToplevelState.SUSPENDED`, GTK ≥ 4.12, feature-checked); `TablePage.set_window_suspended()` on the surface's `notify::state`: releases the process monitor while suspended, acquires it again when shown | `ToplevelSuspendedTest`; `RowChurnTest`: suspended stops the scans once, shown starts them; an unmapped page isn't started |
| B22.4 | [Bug 22's design](../../design/bugs/bug-22-the-window-freezes-after-unlocking-or.md) | — |

**Done when:** a window left on Processes overnight while processes come
and go answers at once after unlocking or waking, and its memory stays
near where it started.

**Found while doing it:**

- Measured on the headless display (`ProcessesPage`, 10 refreshes each):

  | Rows, replaced per refresh | Before | After |
  |---|---|---|
  | 2 000, 500 | 335 ms | 30 ms |
  | 2 000, 50 | 53 ms | 22 ms |
  | 500, 20 | 46 ms | 16 ms |

  The same whether or not the window draws. The profile of one refresh
  before the fix: about 54 000 cell `bind`/`unbind` calls, since the
  column view rebinds every visible cell on each `items-changed`, which
  confirms suspect 1. After: about 113 000 function calls in all, 44 ms.
- Suspects 2 and 3 weren't seen in the benchmark: the store and `rows`
  stayed the same length. Whether memory still grows over a locked night
  is part of the check still to do.
