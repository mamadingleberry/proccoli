# Feature 25: A recorder for the whole machine

Design note: [design/features/feature-25-a-recorder-for-the-whole-machine.md](../../design/features/feature-25-a-recorder-for-the-whole-machine.md)

*Open.* Option C of [Feature 22](feature-22-recording-from-boot.md), kept for
later (Feature 22 was built as option A, lingering offered per person).

**Goal:** one recorder that runs from boot for the whole machine,
whoever is logged in, with one history every window reads: no gaps at
boot or between people, and a single history for a server or for the
Web GUI ([Feature 16](feature-16-a-web-gui-hosted-locally.md),
[Feature 17](feature-17-the-web-gui-for-machines-on.md)).

**Sketch:** a system unit (`proccoli-system.service`) running as its own
user (`DynamicUser=`, `StateDirectory=proccoli`), writing
`/var/lib/proccoli/history.sqlite3`; windows read it (read-only, as they
read the per-user history now), and per-user recorders stand down when
it runs (the same "another one serves" exit as Bug 15, keyed on the
system bus name).

**Questions to settle before it's planned:**

1. Settings: the update interval and the history limits are per user
   today; a machine-wide recorder needs machine-wide ones (a file in
   `/etc/proccoli/`?), and Preferences has to say which apply.
2. Per-user process names and command lines: readable by a dedicated
   user only with `CAP_SYS_PTRACE` or `hidepid` off; what to record for
   other users' processes.
3. Who may read the history: every local user, or a group.
4. Both at once: what happens to a person's own history when the
   machine recorder is installed (import it, or keep reading both).

**Why not now:** a second history location and its permissions,
settings that stop being per user, and a system service to package and
secure: a large change, best made together with the Web GUI, where one
machine-wide history is the point.
