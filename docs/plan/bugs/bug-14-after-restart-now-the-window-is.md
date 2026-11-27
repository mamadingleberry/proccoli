# Bug 14: After *Restart Now* the window is listed as "python3"

Design note: [design/bugs/bug-14-restart-now-renamed-the-window-python3.md](../../design/bugs/bug-14-restart-now-renamed-the-window-python3.md)

*Fixed in Milestone 84.*

**Seen:** "i see a process named `python3` with a Proccoli logo icon in
Overview pane's Processes table".

**Cause:** *Restart Now* (after switching Lightweight Mode off) replaced
the process with `execv(python3, [python3, /usr/bin/proccoli])`. The
kernel names a process after the program it runs; started normally, it
runs the launcher, whose `#!` line names it after the launcher. The icon
was right: the process stays in Proccoli's app group.

**Fix:** restart by running the launcher itself when it's executable.

| Step | Create / change | Test |
|---|---|---|
| B14.1 | `core/system.py` (`restart_command`) | `test_profile.RestartTest` |
