# Feature 9: Custom graph time range

Design note: [design/features/feature-09-custom-graph-time-range.md](../../design/features/feature-09-custom-graph-time-range.md)

*Done as v0.5.0* (its decisions and deviations are listed there).

**Goal:** besides the presets (30 seconds to 1 day), the user can type
any range: a number and a unit (seconds, minutes, hours or days), from
**10 seconds to 30 days**.

**Why:** the presets jump from 1 hour to 6 hours to 1 day. A range like
"the last 3 hours" (since lunch) or "the last 2 days" (since the weekend)
isn't on the list.

**What it costs in memory: nothing extra.** A graph never holds more
than `MAX_GRAPH_POINTS` (1200) points. A longer range doesn't keep more
points: each point averages more readings (`history_plan`: a day at 1 s
is 1184 points of 73 readings; 30 days would be 1200 points of 2160).
The averager keeps running sums, not the readings. So a series costs
about 40 KB at any range (1200 floats and their times in deques), and a
whole window a few MiB at most, the same as the 1-day preset today.
What a long range does cost:

- **Where the data comes from.** Graphs are filled from the history
  database (v0.3.0), and it keeps detail for `history-detail-hours` (24 h by
  default), minute averages for 30 days, and hour averages until the
  size cap. **30 days is the limit because that's how long minutes are
  kept.** At 30 days a point is 36 minutes, so minute averages are
  enough; hour averages would leave gaps between points. Going further
  is what *Export Statistics* (Feature 7) is for.
- **Without the history** (*Keep History* off, or `--demo`) a graph only
  fills while Proccoli runs. A long range then is mostly empty on the
  left; the Preferences row says so.
- **Filling a long graph** reads at most 1200 buckets per device from
  the minutes table in one grouped query (`HistoryDb.buckets`), a few
  milliseconds, on the idle queue one device at a time as now.
- **Resolution, not memory.** At 30 days, a spike shorter than a point
  (36 min) is averaged away. The hover's heading says how long a point
  is ("each point: 36 min").

**Design ([Feature 9's design](../../design/features/feature-09-custom-graph-time-range.md)):**

- **Settings:** `graph-time-range` gains a `custom` nick, and a new key
  `graph-time-range-custom` (`u`, seconds, default 7200) holds the value.
  `time_range_s(settings)` returns the custom seconds, clamped to
  `MIN_RANGE_S` (10 s, and at least 2 update intervals) and `MAX_RANGE_S`
  (30 days), when the nick is `custom`. All callers (`graph_plan`, the
  Intel backend, `ChartSettings`) go through it, so nothing else needs to
  know about custom ranges.
- **Preferences:** the *Graph Time Range* combo gets *Custom…*. Picking
  it shows a row below it with a `Gtk.SpinButton` (the number) and a
  `Gtk.DropDown` (seconds / minutes / hours / days). The value is
  clamped as you type, and the subtitle names the limit when you hit it.
  A custom range that matches a preset is still stored as custom (it's
  what the user typed).
- **Axes:** `span_unit` / `format_span` gain days ("2 d") above
  48 hours, and `NICE_STEPS` gets 2 d and 7 d, so the ticks
  stay round for any range.
- **Lightweight Mode** pins the range to at most 1 minute
  (`_at_most_one_minute`); it must treat `custom` by its seconds.
- **Depends on Bug 1** (below): changing the range has to refill the
  graphs, or each change shows the same stretching.

| Step | Create / change | Test |
|---|---|---|
| F9.1 | `data/…gschema.xml`: `custom` nick, `graph-time-range-custom`; `core/ticker.py`: `time_range_s(settings)` with clamping; callers switched | Unit: presets unchanged; custom seconds; clamped at both ends and to 2 update intervals; `history_plan` for 30 days stays at ≤ 1200 points |
| F9.2 | `core/profile.py`: the Lightweight pin handles `custom` | Unit: a 2-hour custom range reads as 1 minute in Lightweight Mode and comes back when it's off |
| F9.3 | `ui/axes.py`: days in labels and steps | Unit: tick labels for 3 h, 2 d, 30 d |
| F9.4 | `ui/dialogs/preferences.py`: *Custom…* with the number and unit row | UI: the row shows only for *Custom…*; typing 90 minutes stores 5400; 40 days stops at 30 |
| F9.5 | README *Graphs*, [Feature 9's design](../../design/features/feature-09-custom-graph-time-range.md) as built | Run |

**Done when:** a custom range from 10 seconds to 30 days can be set in
Preferences, every graph shows it with round axis labels, filled from
the history, and memory at 30 days is measured (`tests/ui/mem.py`) and
no higher than at 1 day.

**Open questions for the user:**
1. Is 30 days the right ceiling, or should it go further on hour
   averages (kept until the size cap) at the cost of gaps between points?
2. Should the custom range also be offered right on the charts (the
   chart's menu), or only in Preferences?
3. Should Proccoli remember a few recent custom ranges in the combo?
