# 10. Runtime flow

## 10.1 Start-up

```mermaid
sequenceDiagram
    participant A as Application
    participant S as Settings
    participant C as build_context
    participant DM as DeviceManager
    participant D as Discoverers
    participant GC as GpuController
    participant W as MainWindow
    participant T as Ticker
    A->>S: load (GSettings or fallback)
    A->>C: build_context(settings, demo)
    C-->>A: AppContext (System, SysRoot, DeviceManager, ProcessMonitor, ProcessActions, PrivilegedHelper)
    A->>DM: ctx.start() → devices.start(ticker)
    DM->>D: discover() for CPU, Memory, GPU, Drive, Network, Battery
    D-->>DM: DeviceInfo list → Monitors (GpuController for GPUs)
    GC->>GC: registry.best(SUMMARY).start(), best(DETAIL) started unless it needs a password
    A->>W: create window
    DM-->>W: device-added(monitor) × N
    W->>W: page = ctx.pages.create(monitor) (GPU: GpuPage with the detail TABS)
    W->>W: add PageContainer + StackSidebarItem
    W->>W: show_overview()
    A->>T: start(update interval)
```

## 10.2 Each tick

```mermaid
sequenceDiagram
    participant T as Ticker
    participant M as Monitor (each)
    participant GC as GpuController
    participant PM as ProcessMonitor
    participant P as visible page
    participant SB as StackSidebar
    T->>M: refresh(now)
    M->>M: sample() → Snapshot, history.add()
    M-->>P: updated(snapshot) (only the visible page redraws graphs)
    M-->>SB: updated → item.update(sidebar_summary)
    T->>GC: refresh(now)
    GC->>GC: summary() from the detail source while RUNNING, gaps filled by the summary source
    T->>PM: refresh(now)
    PM->>GC: process_usage()
    PM-->>P: updated (if Apps/Processes is visible)
```

**Performance:** the process scan runs only while Apps or Processes is
visible (pages acquire and release the `ProcessMonitor`). Hidden device
pages still record history, but they don't redraw.
Each page tracks `get_mapped()`; when it becomes visible again it draws once
with the full history. With the window hidden, the per-process scan drops to
every 5 s.
