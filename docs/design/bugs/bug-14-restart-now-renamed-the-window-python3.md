# Bug 14: *Restart Now* renamed the window "python3"

Plan: [plan/bugs/bug-14-after-restart-now-the-window-is.md](../../plan/bugs/bug-14-after-restart-now-the-window-is.md)


*[PLAN.md, Bug 14](../../plan/bugs/bug-14-after-restart-now-the-window-is.md). Fixed in M84.* *Restart Now* replaced the process with
`execv(python3, [python3, /usr/bin/proccoli, …])`; the kernel names a
process after the program it runs, so the window showed as `python3`
in process lists (with Proccoli's icon, from its app group). It now runs
the launcher itself when it's executable (`restart_command`), so the
kernel reads its `#!` line and keeps the launcher's name; a checkout
still restarts as `python3 -m proccoli`.
