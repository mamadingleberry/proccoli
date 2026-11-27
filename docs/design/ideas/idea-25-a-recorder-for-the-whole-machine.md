# Idea 25: A recorder for the whole machine

Plan: [plan/ideas/idea-25-a-recorder-for-the-whole-machine.md](../../plan/ideas/idea-25-a-recorder-for-the-whole-machine.md)

*Open.* Option C of [Idea 22's design](idea-22-recording-from-boot.md).

```mermaid
flowchart LR
    B["boot"] --> S["proccoli-system.service<br/>(system unit, DynamicUser)"]
    S --> H[("/var/lib/proccoli/history.sqlite3")]
    S --> N["system bus name<br/>(readings for windows)"]
    H --> W1["a person's window<br/>(read-only)"]
    H --> W2["another person's window"]
    H --> WEB["Web GUI (Ideas 16, 17)"]
    U["per-user proccoli"] -. "machine recorder serves:<br/>stands down" .-> N
```

- One writer for the machine; per-user recorders find its bus name and
  leave, as a second per-user recorder does now (Bug 15).
- Open design points: machine-wide settings, other users' process
  details, read access to the history (see the plan's questions).
