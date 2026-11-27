# Bug 16: A recorder stopped by a signal isn't started again

Plan: [plan/bugs/bug-16-a-recorder-stopped-by-a-signal.md](../../plan/bugs/bug-16-a-recorder-stopped-by-a-signal.md)


*[PLAN.md, Bug 16](../../plan/bugs/bug-16-a-recorder-stopped-by-a-signal.md). Fixed in M86.* `Restart=on-failure` doesn't cover a clean exit
on SIGTERM; proposed `Restart=always` (systemd still honours
`systemctl --user stop`). As built, with `SuccessExitStatus=3` and
`RestartPreventExitStatus=3`, the status of a recorder that left
because another serves.
