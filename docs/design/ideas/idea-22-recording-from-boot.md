# Idea 22: Recording from boot (lingering)

Plan: [plan/ideas/idea-22-recording-from-boot.md](../../plan/ideas/idea-22-recording-from-boot.md)


*[PLAN.md, Idea 22](../../plan/ideas/idea-22-recording-from-boot.md).* When the recorder runs, per choice:

```mermaid
flowchart LR
    B["boot"] --> L{"lingering on<br/>for the user?"}
    L -- yes --> U["user's systemd starts<br/>proccoli.service"]
    L -- no --> W["waits for log-in"]
    W --> U
    U --> R["records the history<br/>(~/.local/state/proccoli)"]
    B -. "option C" .-> S["proccoli-system.service<br/>(system unit, DynamicUser)"]
    S -.-> V["/var/lib/proccoli/history.sqlite3<br/>read by every window"]
```

- **A (built in M89):** offer lingering once (a dialog, and
  `proccoli --start-at-boot`); the decision is pure
  (`should_offer_linger`), the call goes through `System`.

```mermaid
sequenceDiagram
    participant A as Application.do_activate
    participant B as BackgroundService
    participant D as RecordFromBootDialog
    participant L as loginctl
    A->>A: linger-offered? → stop
    A->>B: refresh (systemctl is-enabled, is-active; loginctl Linger)
    B-->>A: state
    A->>A: should_offer_linger(state, offered, history on)<br/>and no other dialog up
    A->>D: present
    D->>D: any answer → linger-offered = true
    D->>L: Turn On → enable-linger <uid>
```

  The command line (`--start-at-boot`, `--no-start-at-boot`) calls
  `background.start_at_boot`, through `System.run` (synchronous: no
  main loop there); `--status` adds a line when `linger_on` is False.
- **B:** `postinst` turns lingering on for people with a login; it
  starts all of their user services at boot, not only Proccoli's.
- **C:** kept as [Idea 25](idea-25-a-recorder-for-the-whole-machine.md): a system-wide recorder and history; pairs with the Web GUI
  ideas ([Idea 16's design](idea-16-a-web-gui-hosted-locally.md), [Idea 17's design](idea-17-the-web-gui-for-machines-on.md)).
