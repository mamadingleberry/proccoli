# Idea 10: Shade the time Proccoli wasn't running

Design note: [design/ideas/idea-10-shade-the-time-proccoli-wasn-t.md](../../design/ideas/idea-10-shade-the-time-proccoli-wasn-t.md)

*Done as Milestone 68* (its decisions are listed there).

**Goal:** where a graph has no data because Proccoli was closed, it
shows a **dithered dark vertical bar** over that stretch, so a gap reads
as "not recording" and not as zero or a lost line.

**Why:** with the history database (M62), a long graph spans earlier
runs. Today the time between them is just a break in the line, which
looks the same as a sensor with no reading, and on an area chart it's
easy to miss. The user can't tell "the machine was idle" from "nothing
was watching".

**Which gaps get the bar:** only time **outside every recorded session**
(`HistoryDb.sessions()`: each run's start and end; the end moves forward
with every commit, so a crash loses at most `COMMIT_EVERY_S`). A `None`
inside a session (a reading a device didn't give, a monitor failing for
a while, `add_gap`) stays a plain break in the line, as now. Time before
the first session ever recorded counts as not recording too.

**Design ([Idea 10's design](../../design/ideas/idea-10-shade-the-time-proccoli-wasn-t.md)):**

- **The data:** `History` gets an `offline` deque beside `times` (a bool
  per point, same `maxlen`). `HistoryStore._fill` marks each backfilled
  slot whose time span lies outside every session (one read of the
  session table, merged with the slots in one pass); live points are
  never offline. `History.offline_runs()` gives the runs as
  `(first index, last index)`, so the graph doesn't scan per frame. The
  regrouping of Bug 1 carries the flags along (a slot is offline only if
  all its points were).
- **Without the history** (*Keep History* off, `--demo`) nothing is ever
  offline: the graph only holds this run.
- **Drawing (`ui/widgets/graph.py`):** after the grid and before the
  lines, each offline run is filled with a **2×2 device-pixel checker
  pattern** (`cairo.SurfacePattern` from a small `ImageSurface`,
  `EXTEND_REPEAT`, built once per scale factor), black at about 35 %
  alpha, clipped to the plot area. Pixel-aligned with `snap_to_device`
  so the dither stays crisp at fractional scales. Its x range uses the
  same index-to-x mapping as `graph_runs`, so bars and lines line up.
- **Hover:** over a bar the hover heading says "Proccoli not running"
  with the span ("2 h 10 min"), instead of empty readings.
- **Small graphs** (sidebar meters, `GraphStyle.SMALL`) skip the bars:
  they show at most a minute, always this run.
- Same for the GPU Details charts (`chart_grid.py`), which draw through
  the same `Graph`.

| Step | Create / change | Test |
|---|---|---|
| I10.1 | `core/history.py`: `offline` deque, `offline_runs()`, kept through `set_max_points`, `backfill`, `clear` (and the Intel `History`) | Unit: flags stay aligned with `times`; runs merge neighbours; live `add` / `add_gap` are never offline |
| I10.2 | `core/history_store.py`: `_fill` marks slots outside every session | Unit (temporary database, fixed clock): two sessions an hour apart; the slots between them are offline, a `None` inside a session isn't |
| I10.3 | `ui/widgets/graph.py`: the dither pattern over offline runs; hover heading | Unit: the bars' x ranges from runs (display-free helper); UI: screenshot with a gap, at scale 1 and 2 |
| I10.4 | README *Graphs* ("shaded: Proccoli wasn't running"), [Idea 10's design](../../design/ideas/idea-10-shade-the-time-proccoli-wasn-t.md) as built | Run |

**Done when:** after closing Proccoli for a while and opening it again,
a graph whose range covers the gap shows a dithered bar exactly over the
closed time, in light and dark styles, and a missing reading inside a run
still shows as a plain break.

**Open questions for the user:**
1. Black reads well on light styles but barely on dark ones (midnight,
   twilight). Use black on light styles and the text color (light) on
   dark ones, or black everywhere?
2. Should time before the very first recording (the left of a long graph
   on a new install) be shaded too, or left blank?
3. Mark the time the machine was suspended (within a session, no
   readings) the same way, or only when Proccoli was closed?
