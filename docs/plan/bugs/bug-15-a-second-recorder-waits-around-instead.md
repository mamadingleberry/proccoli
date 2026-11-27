# Bug 15: A second recorder waits around instead of leaving

Design note: [design/bugs/bug-15-a-second-recorder-waits-instead-of.md](../../design/bugs/bug-15-a-second-recorder-waits-instead-of.md)

*Fixed in Milestone 86.* As built: a recorder that finds the name taken
logs the owner's PID and exits with status 3 (`EXIT_SUPERSEDED`), not
0 as proposed: the unit counts 3 as success and doesn't restart on it,
which `Restart=always` (Bug 16) needs, or a unit started beside a stray
recorder would restart every 10 s.

**Seen:** "in top i see two `proccoli` and one `proccoli-gui` processes,
why two of the former?" Two seconds after the 0.5.0 upgrade, GNOME
Shell launched the dock icon with its cached, pre-0.5.0 entry
(`Exec=proccoli`, the window's old name), which now starts the
recorder. That copy found the history and the D-Bus name taken, logged
"another process writes it; waiting to take over" and "can't serve …
another collector", and stayed: reading every device a second time, for
nothing. Bug 12's stray was the same kind.

**Cause:** the recorder still behaves as in the time before Idea 19,
when the window could be the writer and a recorder had reason to stand
by. Now systemd runs exactly one per user and restarts it; a second has
no job.

**Fix (proposed):** a recorder that can't own the D-Bus name because
another one does exits (status 0) with a log line saying who serves it;
started from a terminal, it also says the window is `proccoli-gui`.
`--once`, `--status` and `--watch` are unaffected.

| Step | Create / change | Test |
|---|---|---|
| B15.1 | `metrics.py`, `metrics_service.py`: on losing the name to another owner, quit the main loop | Unit, on a private bus: a second recorder exits and leaves the first serving; the first one is unaffected |
