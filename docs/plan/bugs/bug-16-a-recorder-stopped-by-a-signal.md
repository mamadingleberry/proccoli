# Bug 16: A recorder stopped by a signal isn't started again

Design note: [design/bugs/bug-16-a-recorder-stopped-by-a-signal.md](../../design/bugs/bug-16-a-recorder-stopped-by-a-signal.md)

*Fixed in Milestone 86.* As proposed, plus `SuccessExitStatus=3` and
`RestartPreventExitStatus=3` for a recorder that leaves because another
one serves (Bug 15).

**Seen:** after the stray of Bug 15 was stopped, the real recorder was
stopped too (16:53:28, "stopping on a signal"); nothing recorded until
the window was opened again 70 s later and D-Bus activation started it.
That was a gap in the history while the machine ran.

**Cause:** the unit has `Restart=on-failure`; a recorder that exits
cleanly on SIGTERM (a `kill`, `pkill proccoli`) isn't a failure, so
systemd leaves it stopped until the next log-in or window.

**Fix (proposed):** `Restart=always` (with `RestartSec=10`): any exit but
`systemctl --user stop proccoli` (which systemd doesn't restart after)
brings it back within 10 s.

| Step | Create / change | Test |
|---|---|---|
| B16.1 | `data/proccoli.service` | Unit: the installed unit says `Restart=always` |
