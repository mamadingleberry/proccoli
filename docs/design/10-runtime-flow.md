# 10. Runtime flow

Two programs run: the recorder (`proccoli`) reads the devices and keeps
the history; the window (`proccoli-gui`) shows them. See
[DESIGN_UML.md](DESIGN_UML.md) for the deployment picture.

## 10.1 The recorder starts

```mermaid
sequenceDiagram
    participant SD as systemd (user)
    participant R as metrics.main / run
    participant C as build_metrics_context
    participant DM as DeviceManager
    participant GC as GpuController
    participant HS as HistoryStore (writer)
    participant MS as MetricsService
    SD->>R: start proccoli.service (at log-in, or at boot when lingering)
    R->>R: Runtime.start(): log file, stall watchdog, exception hook
    R->>C: build_metrics_context(settings)
    C-->>R: MetricsContext (System, SysRoot, DeviceManager, Ticker)
    R->>DM: devices.start(ticker): discover CPU, memory, GPUs, drives, network, batteries
    DM->>GC: a GpuController per GPU: best SUMMARY source, DETAIL source unless it needs a password
    R->>HS: open history.sqlite3, take the HistoryLock (one writer)
    R->>MS: own APP_ID.Metrics on the session bus
    Note over MS: another recorder already owns it: leave (one per user)
```

## 10.2 The window starts

```mermaid
sequenceDiagram
    participant A as Application
    participant C as build_context(remote=True)
    participant RDM as RemoteDeviceManager
    participant MS as MetricsService (recorder)
    participant HS as HistoryStore (read-only)
    participant W as MainWindow
    A->>A: Runtime.start(); Settings; the profile (Lightweight Mode or not)
    A->>C: build_context(settings, remote=True)
    C-->>A: AppContext (RemoteDeviceManager, ProcessMonitor, ProcessActions, helper)
    RDM->>MS: watch the bus name (starts the recorder if it's away), Devices()
    MS-->>RDM: every device's description → a RemoteMonitor each
    RDM->>MS: Subscribe() (the recorder commits its buffer first)
    A->>HS: open the history read-only
    A->>W: create the window
    RDM-->>W: device-added × N → a page each (ctx.pages), sidebar groups, the Overview
    HS-->>W: each device's graphs filled from the history (one per idle call)
```

## 10.3 Each update

```mermaid
sequenceDiagram
    participant T as Ticker (recorder)
    participant M as Monitors
    participant HS as HistoryStore (writer)
    participant MS as MetricsService
    participant RM as RemoteMonitor (window)
    participant P as visible page
    participant SB as StackSidebar
    T->>M: refresh(now): sample() → Snapshot, history.add()
    M-->>HS: updated → buffered, committed every 10 s (one transaction)
    T->>MS: send_readings() (only while someone subscribes)
    MS-->>RM: Readings(time, readings) signal
    RM->>RM: feed(): snapshot, history.add() on the window's clock
    RM-->>P: updated (only a mapped page redraws)
    RM-->>SB: updated → the entry's summary and meter
```

- **Processes** are read by the window itself (`ProcessMonitor`): too
  many and too fast-changing to send. It scans only while Apps,
  Processes or the Overview's busiest tables are on screen; Apps and
  Processes also stop while the window is suspended (screen locked,
  minimised). Each table refresh is one splice.
- **A time range change:** the window asks the recorder to `Flush()`,
  then refills its graphs from the history at the new step.
- **Hidden pages** keep their history but don't redraw; a page drawn again
  shows its full history at once.
- **The recorder goes away:** the window shows a banner with *Try Again*,
  and picks the readings up when the recorder is back.
