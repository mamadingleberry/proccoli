# Bug 9: A window's graphs miss the collector's last seconds

Design note: [design/bugs/bug-09-a-window-s-graphs-missed-the.md](../../design/bugs/bug-09-a-window-s-graphs-missed-the.md)

*Fixed in Milestone 81.*

**Seen:** "why are there gaps in data when I reinstall Proccoli? Shouldn't
it be reading from the running service?" Before Idea 19 each window
restart (Lightweight Mode's *Restart Now* included) ended the recording
for 3–22 s. With the collector, restarts no longer stop the recording
(reinstalling restarts the collector: 0.3 s), but every window still
showed a gap where it opened.

**Cause:** the collector commits every 10 s; a window fills its graphs
from the database as it connects, so the rows still in the collector's
buffer weren't there, and the history shows that stretch as nothing
recording; the graphs never fill it in later.

**Fix:** the collector commits when a window subscribes, before it
answers, so the window's first fill has everything.

| Step | Create / change | Test |
|---|---|---|
| B9.1 | `metrics_service.MetricsService` (`Subscribe`) | `test_metrics_service`: `test_subscribing_writes_out_the_buffered_readings` |
