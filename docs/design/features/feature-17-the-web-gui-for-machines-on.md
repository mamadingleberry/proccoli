# Feature 17: The Web GUI for machines on the local network (brainstorm)

Plan: [plan/features/feature-17-the-web-gui-for-machines-on.md](../../plan/features/feature-17-the-web-gui-for-machines-on.md)


*[PLAN.md, Feature 17](../../plan/features/feature-17-the-web-gui-for-machines-on.md).* Several machines, each running `proccoli`
with its API on the network; one Web GUI (the hub) pulls from them:

```mermaid
sequenceDiagram
    participant U as User (browser)
    participant H as Hub (a proccoli web view)
    participant M as Machine B (proccoli)
    M-->>H: mDNS announce _proccoli._tcp (Avahi, via Gio D-Bus)
    U->>H: Add machine B
    H->>M: pairing request (HTTPS, self-signed)
    M-->>U: shows code 4-7-2-9 (its GUI or --pair)
    H-->>U: shows code 4-7-2-9
    U->>H: codes match: confirm
    M->>H: token, H pins B's certificate fingerprint
    loop showing B
        H->>M: GET /api/history, /api/live (token, pinned TLS)
        M-->>H: buckets, live readings (SSE)
        H-->>U: B's cards and charts, beside the others
    end
```

- **Pull first:** each machine keeps its own history; the hub stores
  only paired machines (name, address, token, fingerprint).
- **Times line up** because everything is UTC epoch milliseconds; the hub
  warns about a machine whose clock is off.
- **Off by default** on every machine; listening only on chosen
  interfaces, never on a public network.
