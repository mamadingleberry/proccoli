# Proccoli: high-level UML

The overview to open first: the two programs, the packages, and the main
classes. Each section file has the detail ([§4](04-architecture-overview.md)
architecture, [§5](05-core-layer.md) core, [§6](06-devices-layer-monitors-and-snapshots.md)
devices, [§7](07-the-gpu-carve-out.md) GPU, [§9](09-ui-layer.md) UI,
[§10](10-runtime-flow.md) runtime). The database is in
[DESIGN_DB.md](DESIGN_DB.md).

**Keep it current:** a change that adds, removes or renames a program, a
package, a class shown here, or a link between them updates this file
in the same change.

## Deployment: two programs, two packages

```mermaid
flowchart LR
    subgraph User["The user's session"]
        subgraph Rec["proccoli (package proccoli)<br/>systemd user service"]
            Collector --> Store["HistoryStore (writer)"]
            Collector --> Svc["MetricsService<br/>D-Bus: APP_ID.Metrics"]
        end
        subgraph Win["proccoli-gui (package proccoli-gui)"]
            RDM["RemoteDeviceManager"] --> UI["MainWindow and pages"]
            RStore["HistoryStore (read-only)"] --> UI
            PM["ProcessMonitor"] --> UI
        end
        Svc -- "Readings, DeviceAdded/Removed (signals)" --> RDM
        RDM -- "Devices(), Subscribe(), Flush()" --> Svc
    end
    Sys[("/proc, /sys,<br/>GPU tools")] --> Collector
    Sys --> PM
    Store --> DB[("history.sqlite3<br/>$XDG_STATE_HOME/proccoli")]
    DB --> RStore
    UI -. "pkexec" .-> Helper["proccoli-helper (root)"]
```

The recorder reads every device; the window reads processes itself (they
change too fast and are too many to send) and everything else from the
recorder and the history.

## Packages and layers

```mermaid
flowchart TB
    subgraph gui["proccoli-gui"]
        app["app.py · ui/ · ui/pages · ui/widgets · ui/dialogs"]
        procs["processes/"]
    end
    subgraph metrics["proccoli (no Gtk)"]
        rec["metrics.py · metrics_service.py"]
        ctx["context.py (composition roots)"]
        dev["devices/ · gpu/"]
        core["core/ (SysRoot, System, Settings, Ticker,<br/>HistoryDb, HistoryStore, Units)"]
        helper["helper/"]
    end
    app --> ctx & dev & procs & core
    rec --> ctx --> dev --> core
    procs --> core
```

UI → Domain → Core, never back. Nothing in the `proccoli` package imports
Gtk or the GUI (`tests/test_static.py`, `InstallSplitTest`).

## Main classes

```mermaid
classDiagram
    direction TB
    class AppContext { settings; ticker; system; sysroot; devices; processes; actions; grouper; theme }
    class MetricsContext { settings; ticker; system; sysroot; devices }
    class DeviceSource { <<abstract>> device-added; device-removed; refresh(now); flush(then) }
    class DeviceManager
    class RemoteDeviceManager
    class Monitor { <<abstract>> sample(now); updated; history }
    class GpuController
    class GpuBackend { <<strategy>> SUMMARY / DETAIL roles }
    class HistoryStore { record; backfill; housekeeping }
    class HistoryDb { SQL only }
    class MetricsService { Devices(); Subscribe(); Flush(); Readings }
    class Collector
    class MainWindow
    class NavigationController { back; forward; mouse buttons; Go To }
    class PageFactory
    class DevicePage
    class OverviewPage
    class GroupPage { a sidebar group: cards per device, totals }
    class ChartCard
    DeviceSource <|-- DeviceManager
    DeviceSource <|-- RemoteDeviceManager
    DeviceSource o-- Monitor
    Monitor <|-- GpuController
    GpuController o-- GpuBackend
    HistoryStore --> HistoryDb
    HistoryStore ..> DeviceSource : follows updated
    Collector --> MetricsContext
    Collector --> HistoryStore
    Collector --> MetricsService
    MetricsService ..> DeviceManager : reads monitors
    RemoteDeviceManager ..> MetricsService : D-Bus
    AppContext o-- RemoteDeviceManager
    MainWindow --> AppContext
    MainWindow --> PageFactory
    MainWindow *-- NavigationController
    PageFactory ..> DevicePage : builds
    OverviewPage <|-- GroupPage
    MainWindow ..> GroupPage : one per grouped kind with a device
    DevicePage o-- ChartCard
    DevicePage ..> Monitor : shows
```

## Classes made of parts

Some big classes are made of parts, each its own class and module, so
each can be read and tested on its own (Feature 21). The callers see one
object.

```mermaid
classDiagram
    direction LR
    class System
    System --|> Programs
    System --|> Locks
    System --|> ProcessControl
    System --|> ChildProcesses
    System --|> AppLauncher
    System --|> ShellIntegration
    AppLauncher --|> SessionBus
    ShellIntegration --|> SessionBus
    class StackSidebar
    StackSidebar --|> SidebarArrangement : order, minimised, hidden details
    StackSidebar --|> SidebarRowMenu : menu, keys, drag and drop
    class PreferencesDialog
    PreferencesDialog --|> RowBuilders
    PreferencesDialog --|> AppearanceRows
    PreferencesDialog --|> HistoryRows
    PreferencesDialog --|> SystemRows
    class Graph { AXES: PaneAxes or SidebarAxes }
    Graph *-- GraphHover : readout
    class TablePage
    TablePage *-- ColumnSet
    class Runtime { file log; watchdog; exception hook }
```

