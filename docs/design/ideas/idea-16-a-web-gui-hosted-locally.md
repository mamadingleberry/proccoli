# Idea 16: A Web GUI, hosted locally (brainstorm)

Plan: [plan/ideas/idea-16-a-web-gui-hosted-locally.md](../../plan/ideas/idea-16-a-web-gui-hosted-locally.md)


*[PLAN.md, Idea 16](../../plan/ideas/idea-16-a-web-gui-hosted-locally.md).* A browser view served by `proccoli`,
localhost-only by default, read-only, from the same monitors and
database as the GTK window:

```mermaid
flowchart LR
    subgraph PM["proccoli (Idea 13)"]
        MON["Monitors<br/>(devices, GPU summaries)"] --> HS["HistoryStore"]
        HS --> DB[("history.sqlite3")]
        WEB["web server<br/>http.server or Gio.SocketService<br/>127.0.0.1, token, GET only"]
        MON -->|"live readings"| WEB
        DB -->|"buckets: ready-to-draw points"| WEB
    end
    WEB -->|"/api/devices · /api/history<br/>/api/live (Server-Sent Events)"| B["Browser<br/>static HTML + JS modules + canvas<br/>(shipped with Proccoli, no CDN)"]
    GUI["GTK window"] -.->|"Open in Browser (URL with token)"| B
```

- No new dependencies: `http.server` or Gio, `json`, `ssl` later; no
  JavaScript framework or build step.
- Security first: localhost, a per-user token, `Host` checks, no CORS,
  read-only, process names off by default.
