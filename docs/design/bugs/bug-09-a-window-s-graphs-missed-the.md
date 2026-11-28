# Bug 9: A window's graphs missed the collector's last seconds

Plan: [plan/bugs/bug-09-a-window-s-graphs-miss-the.md](../../plan/bugs/bug-09-a-window-s-graphs-miss-the.md)


*[PLAN.md, Bug 9](../../plan/bugs/bug-09-a-window-s-graphs-miss-the.md). Fixed in v0.5.0.* The collector commits every 10 s and a
window fills its graphs from the database as it subscribes; `Subscribe`
now commits first.
