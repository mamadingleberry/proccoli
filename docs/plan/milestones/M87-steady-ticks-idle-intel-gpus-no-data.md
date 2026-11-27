# Milestone 87: Steady ticks, idle Intel GPUs, "No data"

*✅ Done.* Fixes Bug 17 (one-point gaps every few minutes in graphs from
the history), Bug 19 (an idle Intel GPU's Overview card was a blank
chart) and Bug 20 (a chart with no readings was drawn blank)

| Step | Create / change | Test |
|---|---|---|
| 87.1 | Bug 17: `core/ticker.py`: each tick due at `start + n × interval`, a one-shot timer for the time left; late ticks aren't made up; an early timer never ticks twice; a handler that stops or re-arms leaves at most one timer | Unit: 1000 ticks with 5 ms of work end within 1 ms of `start + 1000 s` (5 s late before); a late tick, an early timer, handlers that re-arm and stop |
| 87.2 | Bug 17: `core/history_db.py`: `buckets` reads each detail slot's first and last time; `mend_drift` fills a one-slot hole between readings under 1.5 steps apart with the nearer one | Unit: 600 readings 1005 ms apart fill every 1-s slot (holes at 201 and 402 before); a 71-s gap stays; the nearer neighbor; two empty slots stay |
| 87.3 | Bug 19: `gpu/generic_drm.py`: `Residency`, `residency_paths`; usage from GT 0's idle residency when fdinfo has nothing; GT 1's as the video figure; 0 MHz is a reading; `gpu/backend.frequency_text` ("Idle"), used by the controller and the GPU page | Unit: residency to percent (reset, clamp, gap); an idle i915 and xe GPU read 0 % and "Idle"; fdinfo engines still win; an older GPU without the files unchanged |
| 87.4 | Bug 20: `core/history.Series.has_values()`; `SidebarSummary.has_chart()` uses it | Unit: no points, only gaps, a reading aged out; UI: a card without readings shows "No data", then the chart after its first |
| 87.5 | README: an Intel GPU nothing is using | — |

**Done when:** graphs loaded from the history have no one-point breaks;
an idle Intel GPU's card shows 0 %; a device without readings says "No
data".
