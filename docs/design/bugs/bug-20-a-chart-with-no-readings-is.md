# Bug 20: A chart with no readings is drawn blank

Plan: [plan/bugs/bug-20-a-chart-with-no-readings-is.md](../../plan/bugs/bug-20-a-chart-with-no-readings-is.md)


*[PLAN.md, Bug 20](../../plan/bugs/bug-20-a-chart-with-no-readings-is.md). Fixed in M87.* `SidebarSummary.has_chart()` is true whenever a
series exists, so an Overview card whose series is all `None` hides its
"No data" label and draws an empty frame. Built: `Series.has_values()` (from the newest point, stopping at the
first reading) and `has_chart()` asks it of each series.
