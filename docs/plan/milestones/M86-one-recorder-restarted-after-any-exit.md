# Milestone 86: One recorder per user, restarted after any exit

*✅ Done.* Fixes Bug 15 (a second recorder waited around, reading every
device again) and Bug 16 (a recorder ended by a signal stayed stopped)

| Step | Create / change | Test |
|---|---|---|
| 86.1 | Bug 15: `metrics_service.py`: *name lost* with a bus → `owner_pid` (the bus daemon's `GetConnectionUnixProcessID`) → `on_superseded(pid)`; `metrics.py`: `run` quits, writes out, returns `EXIT_SUPERSEDED` (3); from a terminal it names `proccoli-gui` | Unit, on a private bus: a second service reports the first's PID and the first keeps serving; `run` returns 3 and logs why; without a bus it stays (all three fail on the old code) |
| 86.2 | Bug 16: `data/proccoli.service`: `Restart=always`, `SuccessExitStatus=3`, `RestartPreventExitStatus=3` | Unit: the installed unit has them |
| 86.3 | `test_the_unit_verifies` ignores `systemd-analyze`'s warnings about other units on the machine (it failed on `spice-vdagent.service`) | The test passes here; a bad key in Proccoli's own unit is still reported (checked by hand) |
| 86.4 | Light refactor: a docstring in `Collector` named a milestone across a line break, which the static check can't see; reworded | — |

**Deviation:** Bug 15 proposed exit status 0. With `Restart=always`, a
unit-run recorder that found a stray one serving would exit 0 and be
restarted every 10 s for as long as the stray ran; status 3 is a success
the unit doesn't restart on. When the stray goes, the window's name
watcher starts the unit again through D-Bus activation.

**Done when:** `proccoli` run beside a running recorder says who serves
and exits; `pkill proccoli` is followed by a new recorder within 10 s.
