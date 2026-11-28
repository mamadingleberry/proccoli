# Bug 8: Lightweight Mode froze the window at start

Plan: [plan/bugs/bug-08-lightweight-mode-froze-the-window-at.md](../../plan/bugs/bug-08-lightweight-mode-froze-the-window-at.md)


*[PLAN.md, Bug 8](../../plan/bugs/bug-08-lightweight-mode-froze-the-window-at.md). Fixed in v0.5.0.* A `RemoteMonitor` defined its history's
lines only with its first reading; Lightweight Mode's Overview charted
every device before that, so a `None` series reached `Graph` and every
draw raised (Ubuntu's crash reporter then froze the window ~20 s). Lines
now travel with `Devices()` (`history`), and `Graph.set_series` skips a
missing one with a warning.
