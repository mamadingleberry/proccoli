# Feature 13: Record the history in the background

Plan: [plan/features/feature-13-record-the-history-in-the-background.md](../../plan/features/feature-13-record-the-history-in-the-background.md)


*[PLAN.md, Feature 13](../../plan/features/feature-13-record-the-history-in-the-background.md). Done as v0.5.0; as built (the diagrams are the
design, unchanged).*
`proccoli` records while the window is closed; a lock decides
who writes. PLAN.md has the scope, settings table, failure cases, cost
targets and steps; this section has the structure.

**Processes and what starts them:**

```mermaid
flowchart LR
    subgraph SD["the user's systemd (log-in; boot with loginctl enable-linger)"]
        U["proccoli.service<br/>(user unit, disabled until turned on)<br/>Nice=10 · IOSchedulingClass=idle · Restart=on-failure"]
    end
    U --> M["proccoli.metrics<br/>GLib.MainLoop · no Gtk"]
    M --> C["build_metrics_context()<br/>DeviceManager · Ticker · HistoryStore<br/>Profile.metrics(): no processes, icons, helper;<br/>GPU details never elevated"]
    W["Proccoli window<br/>(build_context, as today)"] --> HS2["HistoryStore"]
    C --> HS1["HistoryStore"]
    HS1 & HS2 --> L{"flock<br/>history.lock"}
    L -->|"holder: WRITER"| DB[("history.sqlite3 (WAL)<br/>meta.writer = program, pid, version, since")]
    L -.->|"others: READER<br/>read-only, backfill only,<br/>retry every 10 s"| DB
    S[("dconf")] -->|"change notifications (session bus)"| M
    S -->|"change notifications"| W
    P["Preferences → History<br/>Record in the Background · Start at Boot · Status"] -->|"systemctl --user · loginctl<br/>(System.run_async)"| SD
    P -->|"reads meta.writer"| DB
```

**A `HistoryStore`'s role over time** (the same class in both
processes; the lock is the only difference):

```mermaid
stateDiagram-v2
    [*] --> Reader: start, lock taken
    [*] --> Writer: start, lock free
    Reader --> Writer: retry every 10 s, lock free (open read-write, start a session, meta.writer)
    Writer --> Off: Keep History off (commit, end session, close)
    Off --> Writer: Keep History on, lock free
    Off --> Reader: Keep History on, lock taken
    Writer --> [*]: quit or SIGTERM (commit, end session, the kernel frees the lock)
    Reader --> [*]: quit
    Writer --> Reader: newer schema found (never writes, logged)
```

**A day with both** (the window opens and closes while the collector
records):

```mermaid
sequenceDiagram
    participant SD as systemd --user
    participant M as proccoli
    participant DB as history.sqlite3
    participant W as Proccoli window
    SD->>M: start at log-in
    M->>DB: lock → WRITER, session starts, meta.writer
    loop every update interval
        M->>DB: buffered rows, committed every 10 s
    end
    W->>DB: lock taken → READER (read-only)
    DB-->>W: backfill: the graphs fill at once
    Note over W: live points from its own readings
    W->>W: Preferences: Maximum Size → 256 MiB
    Note over M: dconf notifies, applied at next housekeeping
    W-->>W: quit (nothing to write)
    SD->>M: log-out: SIGTERM
    M->>DB: commit, session ends, lock freed
```

- **New and changed parts:** `core/history_lock.py` (`System.try_lock`,
  fakeable), `HistoryStore(role)`, `Profile.metrics()`,
  `context.build_metrics_context`, `proccoli/metrics.py` (main loop,
  signals, `--once`, `--status`, `--version`),
  `data/proccoli.service`, Preferences' three rows. Nothing in
  `ui/` is imported by the collector (a static test walks its imports).
- **Interfaces between the two:** the database (the lock and
  `meta.writer`) and dconf, never Python calls or D-Bus, so either can
  run alone (and Feature 15 can package them separately).
- **As built:** `HistoryStore(lock=HistoryLock(system, lock_path(path)),
  program=…, graphs=…)`; a store without a lock writes, as before (tests).
  A reader opens the file read-only only once the writer has made it;
  `record` opens on the first reading, so the role is settled before
  anything is buffered. `commit` is where a reader retries the lock and a
  writer notices a deleted file. `session_start()` gives a reader the
  writer's run, for *Export Statistics…*. `Profile.metrics()` has
  `gpu_elevate=False`, which `GpuController` turns into "Detailed
  statistics need administrator rights" without ever calling `pkexec`.
  `MetricsContext.start()` starts the ticker itself. Preferences' rows
  come from `core/background.py` (`BackgroundService`, `status_text`),
  which runs `systemctl --user` and `loginctl` through `System.run_async`.
- **Where it shows (v0.5.0):** the unit runs in the desktop's app slice for
  Proccoli (`Slice=app-<app ID>.slice`, cgroup
  `…/app.slice/app-<app ID>.slice/proccoli.service`), so the Apps
  page (`app_id_for_cgroup`) and other process lists group it with the
  window; the Processes page names it `proccoli` (Bug 7).
- **Measured:** 15.6 MiB private memory; 1.08 % of one core at 1 s on the
  Ryzen 3 4300U (half of it the GPU's per-process `fdinfo`).
