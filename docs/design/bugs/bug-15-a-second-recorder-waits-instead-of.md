# Bug 15: A second recorder waits instead of leaving

Plan: [plan/bugs/bug-15-a-second-recorder-waits-around-instead.md](../../plan/bugs/bug-15-a-second-recorder-waits-around-instead.md)


*[PLAN.md, Bug 15](../../plan/bugs/bug-15-a-second-recorder-waits-around-instead.md). Fixed in v0.6.0.* Since the window stopped writing (Feature 19)
there's always one recorder per user, run by systemd; one that finds the
D-Bus name owned should exit instead of waiting to take over the
history. As built: `MetricsService._name_lost` → `owner_pid` →
`on_superseded`; `metrics.run` quits and returns `EXIT_SUPERSEDED` (3);
see [Feature 19's design](../features/feature-19-the-window-reads-nothing-proccoli-serves.md).
