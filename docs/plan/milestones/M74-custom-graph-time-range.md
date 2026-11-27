# Milestone 74: Custom graph time range

*✅ Done.* Was Idea 9. *Custom…* in Preferences and the toolbar's *Time Range*: a number and a unit, 10 seconds to 30 days, clamped to two update intervals; axes in days past 48 h; every re-planning listener follows the custom key; Lightweight Mode caps it at a minute. Memory flat: 351 KiB filled at 1 day, 354 KiB at 30 days (8 lines)

Was Idea 9 (kept below with its design). Steps I9.1–I9.5 as planned,
plus the toolbar.

| Step | Create / change | Test |
|---|---|---|
| 74.1 | `custom` nick and `graph-time-range-custom` (seconds, 10–2592000, default 7200); `core/ticker.py`: `time_range_s(settings)`, `clamp_range_s`, `preset_s`, `RANGE_KEYS`, `PLAN_KEYS`; every caller (`graph_plan`, `ChartSettings`, the Intel source) and every re-planning listener (`DeviceManager`, `HistoryStore`, the AMD and NVIDIA sources) switched | Unit: presets unchanged; custom seconds; clamped at both ends and to two update intervals; 30 days stays under 1200 points and covers the range; the listeners' keys include the custom one |
| 74.2 | `core/profile.py`: a custom choice stays custom, its seconds pinned to at most 60 in Lightweight Mode | Unit: a 2-hour custom range reads as a minute and comes back without the mode; 30 s stays 30 s |
| 74.3 | `ui/axes.py`: days past 48 hours; 2-day and 7-day steps | Unit: labels for 3 h, 2 d, 3 d, 30 d |
| 74.4 | `ui/time_range.py` (number and unit, `describe`, `limit_note`); `widgets/range_editor.py`; Preferences: *Custom…* in *Graph Time Range* and its row; toolbar: *Custom…* in the *Time Range* menu, an `Adw.AlertDialog` with the editor, the button naming the range | Unit: split, round trip, labels, notes; UI: the row only for *Custom…*, 90 minutes stores 5400, 90 days stops at 30 with a note, greyed out in Lightweight Mode; the toolbar dialog sets and names the range, clamps, and *Cancel* keeps the old one |
| 74.5 | Backfill at long ranges; memory measured; README *Charts*, *Toolbar*, *Preferences*; [DESIGN §4.1](../../design/04-architecture-overview.md), [§11](../../design/11-cross-cutting-concerns.md), [Idea 9's design](../../design/ideas/idea-09-custom-graph-time-range.md); `shoot.py` `custom-range-3-days` | Unit: a custom week fills from minute averages; run |

**Decisions on Idea 9's open questions** (with the design's leanings):
(1) 30 days stays the ceiling: past it only hour averages are left,
coarser than a point; (2) yes, on the charts too: the toolbar's *Time
Range* menu has *Custom…* (the toolbar was built in M72 since the idea
was written); (3) no list of recent custom ranges: the one custom value
is kept and shown in the button.

**Deviations from Idea 9, and why:**
- **No "each point: 36 min" in the hover heading:** the hover already
  says how long ago a point was; the axis and the README explain the
  averaging. Left for later if wanted.
- **A typed value past the limits stays in the editor** with the note
  ("At most 30 Days") while the clamped value is stored, so the user
  sees what they typed and why it wasn't taken.

**Measured** (`History` filled to its plan, 8 lines, 1 s readings,
`tracemalloc`): 1 minute 28 KiB; 1 day 351 KiB (1184 points of 73
readings); 7 days 354 KiB (1198 of 505); 30 days 354 KiB (1199 of
2162). `tests/ui/mem.py` doesn't apply: it runs without a history
database, so graphs never fill there.

*Found while doing 74:* without the history (`--demo`, *Keep History*
off), a long range's points appear only once their readings are in: at
3 days every 3.6 minutes, at 30 days every 36. That was already true of
a day (73 s); the README now says so.
