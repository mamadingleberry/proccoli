# Bug 22: The window freezes after unlocking or waking from suspend

Design note: [design/bugs/bug-22-the-window-freezes-after-unlocking-or.md](../../design/bugs/bug-22-the-window-freezes-after-unlocking-or.md)

*Open.*

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
| B22.1 | A churn reproduction (a script, not shipped) and timing in the debug log for `update_rows` | Manual: the counts and times over a locked night, before and after |
| B22.2 | `ui/pages/table.py`: `update_rows` as one `splice` with a key → row index | Unit/UI: 2 000 rows with 500 replaced per refresh stay under a set time; selection and scrolling survive as now |
| B22.3 | Pause table refreshes while the window isn't shown, one refresh on return | UI smoke: a hidden window's table doesn't refresh; shown again, it does, once |
| B22.4 | [Bug 22's design](../../design/bugs/bug-22-the-window-freezes-after-unlocking-or.md) | — |

**Done when:** a window left on Processes overnight while processes come
and go answers at once after unlocking or waking, and its memory stays
near where it started.
