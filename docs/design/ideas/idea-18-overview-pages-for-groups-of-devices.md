# Idea 18: Overview pages for groups of devices

Plan: [plan/ideas/idea-18-overview-pages-for-groups-of-devices.md](../../plan/ideas/idea-18-overview-pages-for-groups-of-devices.md)


*[PLAN.md, Idea 18](../../plan/ideas/idea-18-overview-pages-for-groups-of-devices.md).* Kinds with several devices get a group entry, a
group page and indented children:

```mermaid
flowchart TB
    subgraph SB["Sidebar"]
        O["Overview"] --- A["Apps · Processes"] --- P["Processor · Memory"]
        G["▾ GPUs (group page)"] --> G1["Intel Graphics"]
        G --> G2["AMD Radeon Graphics"]
        D["▾ Drives"] --> D1["NVMe SSD"]
        D --> D2["USB drive"]
        N["▾ Network"] --> NE["Ethernet: enp3s0"]
        N --> NW["Wi-Fi: wlp2s0"]
        N --> NO["Other: tun0"]
    end
    R["ui/sidebar_groups.py (pure)<br/>which kinds group (2+ devices; Network by type)<br/>order of groups and children · collapsed groups"] --> SB
    GP["GroupPage<br/>the Overview's cards for the group's devices<br/>+ totals where they add up (network, drives)"]
    G -.-> GP
    D -.-> GP
    N -.-> GP
```

- A kind with one device stays a plain entry, as now.
- Children reorder within their group; groups move as a whole
  (`reorder.py` per list). Collapsed groups are remembered.
- Group pages reuse `OverviewPage`'s cards and planner; totals only where
  summing means something (bytes per second), never for percentages.
