# Milestone 68: Honest graph time

*✅ Done.* Fixes Bug 1 (a range change regroups or refills, never stretches) and was Feature 10 (dithered bars, near-black in the palette's accent, over time Proccoli wasn't running). "Colour" spelled "color" everywhere

Fixes Bug 1 and builds Feature 10 (both kept below as the design record):
a graph's points are always its step apart, and the time Proccoli wasn't
running is shaded rather than left as a plain break.

| Step | Create / change | Test |
|---|---|---|
| 68.1 | `core/history.py`: `regroup` (points into a new step's slots, by their times) and `offline_runs`; `History.set_plan` regroups for a longer step and empties for a shorter one; the Intel `History` does the same | Unit: averaging into slots, gaps, the newest that fit; a longer step keeps points a step apart; a shorter one empties |
| 68.2 | `core/history_store.py`: a range or interval change empties each history and fills it again in full (`_refill`, `through_now`) | Unit (Bug 1's regression test): 3 hours, then 1 minute → 1 hour → 6 hours → 1 day: points a step apart, covering 3 hours; without the history, regrouped. Both fail on the old code |
| 68.3 | `History.offline` (a flag per point, shared by every series as `Series.offline`); `offline_slots` marks backfilled slots outside every session; `backfill(…, offline)` | Unit: slots against sessions; the gap between two runs is offline, a reading missing while running isn't; flags stay aligned through `set_max_points`, `clear`, `add_gap` |
| 68.4 | `core/palette.py`: `offline_rgba` (the accent mixed 80 % to black; alpha 0.4 light, 0.75 dark); `Theme.offline_rgba` | Unit: near-black in every palette, the accent's hue, denser on dark; follows palette and style |
| 68.5 | `ui/widgets/graph.py`: `offline_spans`, `dither_pattern` (2×2 checker, one pattern pixel per device pixel), drawn under the lines on every graph; `ui/hover.py`: `offline_text` ("Proccoli wasn't running (2.5 h)") as the hover heading | Unit: spans, the checker at scale 1 and 2, the heading; UI: the checker over offline time only, the hover; screenshots `offline-light`, `offline-dark`, `offline-nord-dark` |
| 68.6 | "Colour" → "color" in code, UI text, tests and docs (the user's choice); the change skill says so | `make test` |
| 68.7 | [DESIGN §9.3](../../../design/09.3-appearance.md), [Feature 10's design](../../../design/features/feature-10-shade-the-time-proccoli-wasn-t.md), [§14](../../../DESIGN.md); README *Charts* | – |

**Decisions on Feature 10's open questions:** the color is a near-black
shade of the palette's accent (not plain black, which vanishes on dark
styles, and not a series color, which would read as data); it's denser
on dark styles. Time before the first recording isn't shaded: a graph
starts where its data starts. Time the machine was suspended isn't
either: Proccoli was running, so it's a plain break. Small graphs
(sidebar, Overview) get the bars too, since they follow the same range.

**Found while doing 68:**

- Python's `round` rounds halves to even, which made regrouped slots
  uneven; `regroup` uses `floor(x + 0.5)`.
- With a refill, the newest reading is only in the database (the live
  averager was reset), so a refill's slots end at "now"; a first-run
  backfill keeps ending a step before, as the live point is already held.
- `HistoryDb.buckets` puts the first minute's average at the start of
  its minute, which can be a few seconds before the first reading, so a
  long graph's oldest edge can show one point, a gap, then the rest.
  Harmless; left as is.
