# Feature 30: Network graphs scaled to the link speed

Plan: [plan/features/feature-30-network-graphs-scaled-to-link-speed.md](../../plan/features/feature-30-network-graphs-scaled-to-link-speed.md)

*Proposed.*

```mermaid
flowchart LR
    S["/sys/class/net/IF/speed"] -->|"> 0"| T["top = link speed"]
    S -->|"-1 (Wi-Fi)"| W{"iw bitrate?"}
    W -- yes --> T
    W -- no --> P["top = next step above the peak<br/>1 · 10 · 100 Mb/s · 1 · 10 Gb/s"]
```

Both directions share one top, so receive and send read on the same
axis.
