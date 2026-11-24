# Proccoli: Design

This document describes how Proccoli is put together: what it copies from
Resources, where it deliberately differs (the swappable GPU page), the layers
of the application, and the classes in each layer. [PLAN.md](PLAN.md) gives
the order in which to build it.

Diagrams use [Mermaid](https://mermaid.js.org/), which GitHub renders.

**The name.** Proccoli is a portmanteau of *process* and *broccoli*.

---

## 1. Goals and non-goals

**Goals**

1. Mirror the Resources user experience: sidebar of resources on the left,
   detail page on the right, Apps and Processes tables, a Preferences dialog,
   and the same page structure (Usage, Sensors and Properties groups).
2. **GPU carve-out:** the GPU page is chosen per GPU, at runtime, by a
   pluggable *GPU backend*. It can be switched while the app is running (for
   example after authenticating, or by choice in Preferences).
3. The first detailed backend is `intel_gpu_top`, reusing what
   intel_gpu_top_gui already does well.
4. Incremental: every milestone in PLAN.md ends with a runnable, tested app.
5. Testable without real hardware. Every data source reads from an injectable
   filesystem root or command runner, so tests use fixture files.

**Non-goals (for now)**

- NVIDIA and AMD detailed backends. The interfaces are designed for them, but
  they are not built yet.
- NPU pages. Resources has them, but they are out of scope.
- Copying Resources' code, icons or name. Proccoli re-implements the UX from
  scratch, because Resources is GPL and Proccoli is 0BSD (see §11, Licensing).

---

## 2. What Resources does, and what Proccoli changes

### 2.1 Resources' structure (from the Ubuntu 26.04 package, v1.10.2)

Taken from the UI definitions in `/usr/share/resources/resources.gresource`:

```
MainWindow (AdwApplicationWindow, min 360×240)
├── AdwBreakpoint  max-width: 780sp  →  split_view.collapsed = True
└── AdwOverlaySplitView #split_view
    ├── sidebar: AdwToolbarView
    │   ├── AdwHeaderBar (primary menu: Preferences, Keyboard Shortcuts, About)
    │   └── ResStackSidebar → GtkListBox of ResStackSidebarItem
    │         (icon, name, detail label, usage label, progress bar OR mini graph)
    └── content: GtkStack #content_stack (one page per sidebar entry)
        └── each page: AdwToolbarView
            ├── AdwHeaderBar (flat; sidebar toggle shown when collapsed —
            │                 Proccoli: logo + burger instead, M52;
            │                 search toggle on Apps/Processes)
            └── page widget (ResApplications, ResProcesses, ResCPU, ResMemory,
                             ResGPU, ResDrive, ResNetwork, ResBattery, ResNPU)
```

Device pages (GPU, Drive, Network, Battery) are added at runtime, one per
detected device. Each device page is `GtkScrolledWindow → AdwClamp →
AdwPreferencesGroup`s containing:

- `ResGraphBox`: an `AdwPreferencesRow` with a graph, a title and an info line
- `ResDoubleGraphBox`: two graphs side by side (for example encode and decode)
- `AdwActionRow`s for single values and properties

The pages contain:

| Page      | Usage group                                                                 | Sensors      | Properties |
|-----------|-----------------------------------------------------------------------------|--------------|------------|
| Processor | total usage graph, or a FlowBox of per-thread graphs (switch: logical CPUs) | temperature  | max frequency, logical/physical cores, sockets, uptime, virtualization, architecture |
| Memory    | memory graph, swap graph (with an auth banner for module info)              | –            | slots used, speed, form factor, type, type detail |
| GPU       | usage, encode/decode (double), combined enc/dec, VRAM; frequency, VRAM frequency, power rows | temperature | manufacturer, PCI slot, driver, max power cap, link |
| Drive     | busy %, read speed, write speed; total read/written                         | –            | type, device, capacity, writable, removable, link |
| Network   | receiving, sending; total received/sent                                     | –            | manufacturer, driver, interface, hardware address, network name, link, link speed |
| Battery   | charge, power usage                                                         | –            | health, design capacity, cycles, technology, manufacturer, model, device |

**Apps and Processes** are `GtkColumnView` tables with a search bar, a
toast overlay, and a bottom action bar: *Information*, *Options* (processes
only), and an *End* split button with *Kill / Halt / Continue*. Rows open an
**App Information** or **Process Information** dialog. *Process Options*
edits niceness, priority and CPU affinity.

**Preferences** (backed by GSettings `net.nokyan.Resources`) has four pages:

- *General:* unit prefix, network bits, temperature unit, refresh speed,
  graph grids, graph data points, sidebar details, descriptions and meter
  type, normalize CPU usage
- *Apps:* column toggles
- *Processes:* niceness option and column toggles
- *Devices:* virtual drives, virtual network interfaces

It also stores the window size, sort columns and last viewed page.

**Privileged work** goes through helper executables in
`/usr/libexec/resources/`:

- `resources-processes` streams process data, run via `pkexec` to see all
  users' processes
- `resources-kill` and `resources-adjust` signal or renice other users'
  processes

All three are authorised by a polkit policy.

### 2.2 The GPU gap

On an Intel iGPU, Resources' GPU page shows one usage graph, the video
engine, frequency and power. intel_gpu_top_gui shows much more:

| Metric                                         | Resources | intel_gpu_top page |
|------------------------------------------------|:---------:|:------------------:|
| Total GPU usage                                | ✔         | ✔ (derived)        |
| Per-engine busy: Render/3D, Blitter, Video, VideoEnhance, Compute | – | ✔ |
| Engine wait/semaphore time                     | –         | ✔ (optional series) |
| Requested vs actual frequency                  | actual only | ✔ both          |
| GPU vs package power                           | one value | ✔ both             |
| RC6 (idle power state) residency               | –         | ✔                  |
| IMC memory bandwidth (reads/writes)            | –         | ✔ (if reported)    |
| Interrupts per second                          | –         | ✔                  |
| Per-process usage per engine class             | GPU/enc/dec % | ✔ every engine class |
| Multi-tile GPUs (per-GT groups)                | –         | ✔                  |
| Hover crosshair with values, pause, CSV export | –         | ✔                  |
| VRAM usage, temperature                        | ✔ (dGPU)  | – (iGPU has none; the generic data stays available) |

The carve-out keeps Resources' simple summary for everything else (the
sidebar entry and the Apps/Processes GPU columns). Only the GPU **page** is
swapped for a detailed one when a backend can provide it.

---

## 3. Technology decisions

| Decision | Choice | Why |
|---|---|---|
| Language | Python 3 (system interpreter) + PyGObject | Same stack as intel_gpu_top_gui, so code can be reused directly. No build step and nothing from pip. |
| Toolkit | GTK ≥ 4.10, libadwaita ≥ 1.5 | `AdwOverlaySplitView`, `AdwBreakpoint`, `AdwToolbarView` (1.4) and `AdwDialog`, `AdwPreferencesDialog`, `AdwAboutDialog` (1.5). Ubuntu 24.04 ships 1.5. `AdwShortcutsDialog` (1.8) is used when present. |
| UI definitions | Built in Python (not `.ui` files) | Simple to review and test, and avoids a GResource compile step. `.ui` files can be added later. |
| Graph drawing | Cairo `Gtk.DrawingArea` | Ported from intel_gpu_top_gui's `GraphView` (crisp lines, adaptive axes). |
| Settings | GSettings with an installed schema, plus an in-memory fallback | Mirrors Resources. The fallback makes running from a source checkout and testing easy. |
| Dependency injection | By hand, in one composition root (`context.py`, §4.2) | No framework needed. Every OS service sits behind `System` and every file read behind `SysRoot`, so tests swap in fakes. |
| Data collection | `/proc` and `/sys` reads on the main loop, plus subprocess readers for streaming tools | `/proc` reads are cheap. `intel_gpu_top` and the privileged helper stream JSON on a worker thread and hand results to the main loop with `GLib.idle_add`. |
| D-Bus | `Gio.DBusProxy` to NetworkManager (Wi-Fi name, connection type) and UPower (battery) | No extra packages; `gir1.2-nm` is not installed by default. |
| Hotplug | Periodic rescans (every few seconds) for drives and network interfaces | GUdev's introspection data isn't installed by default; it can replace the rescans later. |
| Privilege | `pkexec` + polkit policy + one helper script (`proccoli-helper`) | Same model as Resources. |

---

## 4. Architecture overview

```mermaid
flowchart TB
    subgraph Root["Composition root (proccoli.context)"]
        Ctx["build_context() → AppContext"]
    end
    subgraph UI["UI layer (proccoli.ui)"]
        Window[MainWindow] --> Sidebar[StackSidebar]
        Window --> Stack["Gtk.Stack of PageContainers"]
        Window --> Factory[PageFactory]
        Factory --> DevicePages["DevicePage subclasses<br/>CpuPage · MemoryPage · DrivePage · NetworkPage · BatteryPage"]
        Factory --> GpuPages["GpuPage<br/>Overview + DetailHost tabs"]
        Window --> Tables["TablePage subclasses<br/>AppsPage · ProcessesPage"]
        Tables --> Dialogs["Dialogs: info · process options"]
        App[Application] --> Prefs["Preferences · About · Shortcuts"]
    end
    subgraph Domain["Domain layer"]
        DM[DeviceManager] --> Monitors["Monitor subclasses"]
        DM --> GpuCtl[GpuController]
        GpuCtl --> Registry[GpuBackendRegistry] --> Backends["GpuBackend strategies<br/>SUMMARY + DETAIL roles"]
        PM[ProcessMonitor]
        Actions[ProcessActions] --> Helper[PrivilegedHelper]
        Grouper[AppGrouper]
    end
    subgraph Core["Core layer (proccoli.core)"]
        Ticker
        Settings
        System["System (OS services)"]
        SysRoot["SysRoot (/proc, /sys)"]
        History
        Units
    end
    Ctx --> DM & PM & Actions & Grouper & Ticker & System & SysRoot
    App --> Ctx
    Window --> Ctx
    Monitors & Backends & PM --> SysRoot
    Backends & PM & Actions & Helper --> System
```

**Dependency rule:** UI → Domain → Core, and never the other way. Domain
objects tell the UI about changes through GObject signals (`device-added`,
`updated`, `detail-changed`, `elevated-io`). They never import Gtk at module
level, which `tests/test_static.py` enforces. The exceptions are the views
that ship with a detail backend (`DetailBackend.create_views()` and the
Intel backend's `views.py`, `graph.py`, `grid.py`, `clients.py`). They're
imported lazily, so the domain stays testable without a display.

### 4.1 Package layout

```
proccoli/
├── README.md  DESIGN.md  PLAN.md  LICENSE  Makefile
├── src/proccoli/
│   ├── __init__.py            # APP_ID, APP_NAME, version, icon names (the only place)
│   ├── __main__.py  app.py    # Application: actions, dialogs; asks context.py for services
│   ├── context.py             # the composition root (§4.2)
│   ├── core/       system.py  sysroot.py  settings.py  ticker.py  history.py  units.py
│   │               pciids.py  jsonstream.py  runner.py  privileged.py  palette.py
│   │               styles.py  applog.py  trust.py  watchdog.py
│   ├── devices/    base.py  manager.py  cpu.py  memory.py  drive.py  network.py  nm.py
│   │               battery.py  demo.py
│   ├── gpu/        info.py  backend.py  registry.py  controller.py  fdinfo.py  generic_drm.py
│   │               intel_gpu_top/  backend.py  history.py  views.py  graph.py  grid.py  clients.py
│   ├── processes/  model.py  monitor.py  apps.py  actions.py  top.py
│   ├── helper/     proccoli_helper.py    # installed as libexec/proccoli/proccoli-helper (root)
│   └── ui/         window.py  window_state.py  sidebar.py  page.py  style.py  theme.py
│                   layout.py  elevation.py  sidebar_order.py  sidebar_fields.py  axes.py
│                   sidebar_visibility.py
│       ├── widgets/  graph.py  graph_box.py  double_graph_box.py  info_row.py  meter.py
│       │             app_icon.py  top_table.py
│       ├── pages/    device.py  table.py  factory.py  cpu.py  memory.py  drive.py  network.py
│       │             battery.py  gpu.py  apps.py  processes.py  demo.py  overview.py
│       └── dialogs/  info.py  process_options.py  preferences.py  about.py  launch_auth.py
├── data/       .desktop  .metainfo.xml  .gschema.xml  .policy  icons/hicolor/...
├── packaging/  install.sh  build-deb.sh  make-logo.py  render-icons.py
└── tests/      helpers.py (FakeRoot, FakeSystem, make_context)  fixtures/  test_*.py
                ui/shoot.py (screenshots)  ui/perf.py (CPU use)  run-headless.sh
```

### 4.2 Dependency injection: the composition root

Everything is wired by hand in one place, `context.build_context()`, which
returns an `AppContext`. Nothing else creates services, and no module reaches
for the operating system on its own.

```mermaid
classDiagram
    direction LR
    class AppContext {
        <<dataclass>>
        +settings: Settings
        +ticker: Ticker
        +system: System
        +sysroot: SysRoot
        +pci: PciIds
        +devices: DeviceManager|None
        +processes: ProcessMonitor|None
        +actions: ProcessActions
        +grouper: AppGrouper
        +app_icons: AppIconLookup
        +helper: PrivilegedHelper|None
        +demo: bool
        +pages: PageFactory|None
        +theme: Theme|None
        +perf_log: PerformanceLog
        +start()
        +stop()
    }
    class build_context {
        <<function>>
        settings, demo, system?, sysroot?, pci?, ticker?, helper_command?, connection_name?, gpu_registry?
    }
    class Application {
        +context_factory(settings, demo) AppContext
        +ctx: AppContext
    }
    class MainWindow {
        +MainWindow(app, ctx)
    }
    build_context ..> AppContext : creates
    Application ..> build_context : default factory
    Application o-- AppContext
    MainWindow ..> AppContext : reads services
```

- **Seams:**
  - `SysRoot`: every `/proc` and `/sys` read.
  - `System`: everything else that touches the OS (§5).
  - `Settings.for_tests()`: in-memory settings.
  - `Ticker`: injectable timer and clock.
  - `PageFactory`: which page shows which device kind.
  - `GpuBackendRegistry` (`build_context(gpu_registry=...)`): which GPU
    backends exist.
  - `Application(context_factory=...)`: the whole graph.
  - `Theme(settings, style_manager)`: the look (§9.3). `Application` builds
    it with `Adw.StyleManager.get_default()`; tests pass a fake.
- **Tests** build the real graph with fakes: `tests/helpers.make_context()`
  passes `FakeSystem`, a fixture `SysRoot`, test settings, the test `pci.ids`,
  no helper and no NetworkManager.
- **Enforcement:** `tests/test_static.py` fails if a module outside the
  allowed set calls `os.kill`, `shutil.which`, `subprocess`, `pwd` and
  similar directly, or if a domain module imports Gtk.

## 5. Core layer

```mermaid
classDiagram
    direction LR
    class System {
        +which(name) str|None
        +geteuid() int
        +has_file_capabilities(path) bool
        +user_name(uid) str
        +clk_tck() int
        +machine() str
        +kill(pid, sig)
        +get_priority(pid) int
        +set_priority(pid, nice)
        +get_affinity(pid) set
        +set_affinity(pid, cpus)
        +stream_reader() StreamReader
        +run_async(argv, callback(rc, out, err))
        +desktop_app(app_id) AppInfo|None
        +app_switch_method(app_id) "dbus"|"launch"|None
        +activate_app(app_id) bool
    }
    class SysRoot {
        +root: Path
        +read_text(path) str|None
        +read_line(path) str|None
        +read_int(path, base) int|None
        +listdir(path) list
        +exists(path) bool
        +is_dir(path) bool
        +readlink(path) str|None
        +link_name(path) str|None
    }
    class Settings {
        +load()$ Settings
        +for_tests(overrides)$ Settings
        +in_memory_gio(dir)$ Settings
        +get(key) Any
        +set(key, value)
        +reset(key)
        +connect_changed(key, cb) int
        +disconnect(handler)
        +bind(key, obj, prop)
    }
    class Ticker {
        <<GObject>>
        +interval_ms: int
        +start()
        +stop()
        +set_interval(ms)
        +follow(settings)
        +signal tick(now)
    }
    class History {
        +define(name, unit) Series
        +add(now, values, units)
        +add_gap(now)
        +series(name) Series
        +set_max_points(n)
        +write_csv(path)
    }
    class Series {
        +name, unit
        +values: deque
        +latest()
        +peak()
    }
    class StreamReader {
        <<GObject>>
        +start(argv, elevate)
        +start_generator(make, interval)
        +stop()
        +signal record(obj)
        +signal exited(rc, stderr, count)
    }
    class PrivilegedHelper {
        +argv: list
        +signal(name, pids, cb)
        +renice(pid, nice, cb)
        +set_affinity(pid, cpus, cb)
        +dmidecode(cb)
        +io_stream(interval_ms) StreamReader
    }
    class HelperResult {
        <<dataclass>>
        +ok: bool
        +data: dict
        +error: str
        +cancelled: bool
    }
    class PciIds {
        +vendor(id) str|None
        +device(vendor, device) str|None
    }
    History *-- Series
    StreamReader ..> JsonStreamParser
    System ..> StreamReader : creates
    PrivilegedHelper o-- System
    PrivilegedHelper ..> HelperResult
```

- **`System`** is the only OS facade. Tests use `FakeSystem`
  (`tests/helpers.py`), which records signals, priorities and child
  processes, and answers `which` and the user and app lookups from
  attributes.
- **`PrivilegedHelper`** runs `pkexec proccoli-helper <subcommand>`
  asynchronously, since the password prompt takes time. It turns pkexec's 126
  and 127 into `cancelled`. The helper itself
  (`helper/proccoli_helper.py`) is a standalone script with strict argument
  validation and no shell. Only a root-owned installed helper is used, and
  processes are named by PID *and* start time (§11, *Security*).
- **`Ticker`:** one app-wide timer at the *Refresh Speed* setting (4 s, 2 s,
  1 s, 0.5 s or 0.25 s), so all graphs line up in time.
- **`Settings`:** GSettings when the schema is installed or can be compiled
  from the checkout, otherwise a dictionary with the same defaults and
  validation. A source checkout always uses its own compiled schema first.
  `choose_schema` skips any schema missing a key the app's schema
  describes (`schema_covers`): GSettings aborts the whole program on an
  unknown key. This happened once, when an installed package older than
  the checkout lacked `sidebar-shown`.

## 6. Devices layer: monitors and snapshots

Every sidebar entry except Apps and Processes is a **device**. A device has
an immutable `DeviceInfo`, discovered once, and a `Monitor` that produces a
`Snapshot` on every tick.

```mermaid
classDiagram
    direction TB
    class DeviceKind {
        <<enumeration>>
        CPU
        MEMORY
        GPU
        DRIVE
        NETWORK
        BATTERY
    }
    class DeviceInfo {
        <<dataclass, frozen>>
        +id: str
        +kind: DeviceKind
        +name: str
        +description: str
        +icon_name: str
        +properties: dict~str,str~
    }
    class Snapshot {
        <<dataclass>>
        +time: float
        +usage: float|None
        +usage_text: str
        +detail_text: str
    }
    class Monitor {
        <<abstract, GObject>>
        +info: DeviceInfo
        +history: History
        +latest: Snapshot|None
        +refresh(now)*
        +start()
        +stop()
        +signal updated(snapshot)
        #sample(now)* Snapshot
    }
    class CpuMonitor {
        -prev_jiffies: list
        +sample(now) CpuSnapshot
    }
    class MemoryMonitor {
        +sample(now) MemorySnapshot
        +load_modules(elevated) list~MemoryModule~
    }
    class DriveMonitor {
        -prev_stats: DiskStats
        +sample(now) DriveSnapshot
    }
    class NetworkMonitor {
        -prev_bytes: tuple
        +sample(now) NetworkSnapshot
    }
    class BatteryMonitor {
        +sample(now) BatterySnapshot
    }
    class CpuSnapshot {
        +total: float
        +per_thread: list~float~
        +frequency_hz: float
        +temperature_c: float|None
    }
    class MemorySnapshot {
        +used, total, available: int
        +swap_used, swap_total: int
    }
    class DriveSnapshot {
        +busy: float
        +read_bps, write_bps: float
        +total_read, total_written: int
    }
    class NetworkSnapshot {
        +rx_bps, tx_bps: float
        +total_rx, total_tx: int
    }
    class BatterySnapshot {
        +charge: float
        +power_w: float
        +state: str
    }
    class DeviceManager {
        <<GObject>>
        -sysroot: SysRoot
        -monitors: dict~str, Monitor~
        -discoverers: list~Discoverer~
        +register(discoverer)
        +start(ticker)
        +refresh(now)
        +rescan()
        +monitors_of(kind) list~Monitor~
        +signal device_added(monitor)
        +signal device_removed(id)
    }
    class Discoverer {
        <<interface>>
        +kind: DeviceKind
        +rescan: bool
        +settings_keys: tuple
        +discover(sysroot, settings) list~DeviceInfo~
        +create_monitor(info, sysroot, settings) Monitor
    }
    Monitor <|-- CpuMonitor
    Monitor <|-- MemoryMonitor
    Monitor <|-- DriveMonitor
    Monitor <|-- NetworkMonitor
    Monitor <|-- BatteryMonitor
    Monitor <|-- GpuController : GPU devices are monitors too
    Snapshot <|-- CpuSnapshot
    Snapshot <|-- MemorySnapshot
    Snapshot <|-- DriveSnapshot
    Snapshot <|-- NetworkSnapshot
    Snapshot <|-- BatterySnapshot
    Monitor o-- DeviceInfo
    DeviceManager o-- "many" Monitor
    DeviceManager o-- "many" Discoverer
    Discoverer ..> Monitor : creates
```

**Data sources per device** (all through `SysRoot`, so every one can be
tested with fixtures):

| Device | Discovery | Per-tick data | Properties |
|---|---|---|---|
| CPU | `/proc/cpuinfo` | `/proc/stat` deltas, `/sys/devices/system/cpu/cpu*/cpufreq` | `/proc/cpuinfo`, `lscpu`-style topology from `/sys/devices/system/cpu`, `/proc/uptime`; temperature from hwmon `coretemp` / `k10temp` |
| Memory | always; description "16.0 GB DDR4 @ 2667 MT/s" (`memory_description`: one decimal, the slowest module's speed) | `/proc/meminfo` | udev's SMBIOS record `/run/udev/data/+dmi:id` (`MEMORY_DEVICE_<n>_*`, readable by any user): slots, type, speed, form factor. Only without it: `dmidecode -t 17` through the helper (banner + Authenticate) |
| Drive | `/sys/block/*` (skip loop/ram; virtual drives optional) | `/sys/block/X/stat` deltas | size, `removable`, `ro`, rotational → HDD/SSD/NVMe, `device/model` |
| Network | `/sys/class/net/*` (skip `lo`; virtual optional: no `device` link) | `/sys/class/net/X/statistics/{rx,tx}_bytes` | MAC address, driver (`device/driver`), speed; SSID and type from NetworkManager over D-Bus; wireless if `X/wireless` exists |
| Battery | `/sys/class/power_supply/*` with `type=Battery` | `capacity`, `power_now` or `current_now × voltage_now` | `energy_full_design`, `cycle_count`, `technology`, `manufacturer`, `model_name` |
| GPU | see §7 | see §7 | see §7 |

**Sidebar naming** mirrors Resources: the Processor's description is its
model and Memory's its size, DDR type and speed; drives are
labelled "Drive" with the model as the description, and network interfaces are "Ethernet Connection",
"Wi-Fi Connection" or "VPN" with the interface name as the description.
These names come from `DeviceInfo.name` and `DeviceInfo.description`.

---

## 7. The GPU carve-out

This is the one place where Proccoli differs from Resources on purpose. Every
GPU gets **one page with up to three tabs**:

| Tab | Content | Comes from |
|---|---|---|
| **Overview** | Resources' GPU page (usage, video engine, VRAM, frequency, power, temperature, properties) | the GPU's **summary source**, which always runs |
| **Details** | the vendor's own view: for Intel, intel_gpu_top_gui's graph grid (per-engine utilisation, frequency, power, RC6, memory bandwidth, interrupts) | the GPU's **detail source**, if one exists |
| **Processes** | the vendor's per-process view: for Intel, engine-class use per client | the detail source |

The Overview is always first. The vendor tabs are a second level of
information for the same GPU, so they're **tabs, not a drill-down**:

- **Peer views, switched often.** Engine graphs and the summary are both
  "now" views that users flip between while monitoring. Tabs are one click
  each way with no back button.
- **intel_gpu_top_gui's own shape.** Its Resources | Processes switcher maps
  one-to-one onto Details | Processes.
- **No tabs without a vendor tool.** A GPU without a detail source shows no
  switcher, just the overview, exactly like Resources.
- **The overview links to the details.** It has a "Detailed Statistics"
  row, so they're discoverable from the Resources-style view.

### 7.1 Roles: summary and detail sources

A *GPU backend* (the strategy from §4) now has a **role**:

- **SUMMARY:** sysfs and fdinfo, works for any GPU, cheap, never needs
  privileges. It always runs, so the overview, the sidebar meter and the
  process GPU columns never go blank.
- **DETAIL:** a vendor tool (`intel_gpu_top`; later `nvidia-smi` or
  `amdgpu_top`). It may need administrator rights, may be switched off, and
  supplies the vendor tabs. While it runs, its numbers also feed the
  overview, because they cover every process, not just the user's own.

```mermaid
classDiagram
    direction TB
    class BackendRole {
        <<enumeration>>
        SUMMARY
        DETAIL
    }
    class GpuBackend {
        <<abstract, GObject>>
        +id: str
        +display_name: str
        +role: BackendRole
        +gpu: GpuInfo
        +deps: GpuDeps
        +probe(gpu, deps)$ Probe
        +start(elevate)
        +stop()
        +refresh(now)
        +summary() GpuSummary
        +has_data() bool
        +process_usage() dict~int, GpuProcessUsage~
        +signal updated()
        +signal failed(reason, can_elevate)
    }
    class DetailBackend {
        <<abstract>>
        +TABS: list~TabSpec~
        +create_views(controller, services) DetailViews
    }
    class GenericDrmBackend {
        role = SUMMARY
    }
    class IntelGpuTopBackend {
        role = DETAIL
        +history: History
        +interval_ms: int
        +restart()
    }
    class NvidiaSmiBackend {
        <<future, DETAIL>>
    }
    class AmdGpuTopBackend {
        <<future, DETAIL>>
    }
    class TabSpec {
        <<dataclass>>
        +name: str
        +title: str
        +icon_name: str
    }
    class DetailView {
        <<dataclass>>
        +name: str
        +widget: Gtk.Widget
        +header_widgets: list~Gtk.Widget~
    }
    class DetailServices {
        <<frozen dataclass, injected>>
        +settings
        +app_icon(pid) Gio.Icon|None
    }
    class GpuDeps {
        <<dataclass>>
        +sysroot
        +settings
        +system
    }
    GpuBackend <|-- GenericDrmBackend
    GpuBackend <|-- DetailBackend
    DetailBackend <|-- IntelGpuTopBackend
    DetailBackend <|-- NvidiaSmiBackend
    DetailBackend <|-- AmdGpuTopBackend
    GpuBackend --> BackendRole
    GpuBackend o-- GpuDeps
    DetailBackend ..> TabSpec : declares
    DetailBackend ..> DetailView : creates
    DetailBackend ..> DetailServices : uses
```

### 7.2 The controller

One `GpuController` per GPU (a `Monitor`, so the rest of the app treats it
like any device) owns both sources:

```mermaid
classDiagram
    direction LR
    class GpuController {
        <<GObject, Monitor>>
        +gpu: GpuInfo
        +summary_backend: GpuBackend
        +detail_class: type|None
        +detail_probe: Probe|None
        +detail_backend: DetailBackend|None
        +detail_state: DetailState
        +detail_message: str
        +start()
        +stop()
        +refresh(now)
        +summary() GpuSummary
        +process_usage() dict
        +start_details(elevate)
        +stop_details()
        +set_details_enabled(on)
        +signal detail-changed(state)
    }
    class DetailState {
        <<enumeration>>
        UNAVAILABLE
        OFF
        NEEDS_AUTH
        STARTING
        RUNNING
        FAILED
    }
    class GpuBackendRegistry {
        +summary_class(gpu, deps) type
        +detail_candidate(gpu, deps) tuple|None
    }
    GpuController o-- GpuBackendRegistry
    GpuController *-- GpuBackend : summary (always)
    GpuController *-- DetailBackend : detail (0..1)
    GpuController --> DetailState
```

- **Which source feeds what:** `summary()` and `process_usage()` come from
  the detail source while it's RUNNING and has data, otherwise from the
  summary source.
- **Preferences:**
  - `gpu-details-disabled` lists PCI slots whose details are turned off.
  - `gpu-elevate` starts details with pkexec at launch instead of waiting
    for the user.
  - `intel-gpu-top-interval` and `intel-gpu-top-history` are the Details
    tab's update interval and history length, as in intel_gpu_top_gui.

**Detail lifecycle.** A password prompt never appears unless the user asks
for it, either by clicking, or by turning on "Start with administrator
rights" in Preferences:

```mermaid
stateDiagram-v2
    [*] --> UNAVAILABLE: no detail tool for this GPU
    [*] --> OFF: turned off in Preferences
    [*] --> NEEDS_AUTH: needs administrator rights (and gpu-elevate is off)
    [*] --> STARTING: no rights needed, or gpu-elevate is on
    NEEDS_AUTH --> STARTING: user clicks "Show Detailed Statistics" (pkexec)
    STARTING --> RUNNING: first record arrives
    STARTING --> FAILED: tool exits / authentication cancelled
    RUNNING --> FAILED: tool exits unexpectedly
    FAILED --> STARTING: user clicks "Try Again" (elevated if that may help)
    RUNNING --> OFF: turned off in Preferences
    OFF --> STARTING: turned on again
    note right of FAILED
        The Details tabs show the reason
        and a button. The Overview keeps
        working from the summary source.
    end note
```

### 7.3 The page

```mermaid
classDiagram
    direction TB
    class GpuPage {
        <<DevicePage>>
        +controller: GpuController
        +stack: Adw.ViewStack
        +switcher: Adw.ViewSwitcher
        +switcher_bar: Adw.ViewSwitcherBar
        +overview: GpuOverview
        +hosts: dict~str, DetailHost~
        +title_widget() Gtk.Widget
        +header_widgets() list
        +show_tab(name)
    }
    class GpuOverview {
        Resources' GPU page: Usage, Sensors, Properties
        + a Detailed Statistics row
    }
    class DetailHost {
        <<Gtk.Stack>>
        +status: Adw.StatusPage
        +set_view(DetailView|None)
        +show_state(state, message)
    }
    class IntelGraphsView {
        <<Adw.BreakpointBin>>
        caption + GraphGrid of GraphSections
        compact below 720sp high / 600sp wide
    }
    class IntelClientsView {
        ClientsView: engine-class use per client
    }
    class IntelDetailHeader {
        pause toggle + menu: Update Interval,
        History Length, Export as CSV, Clear History
    }
    GpuPage *-- GpuOverview
    GpuPage *-- "0..n" DetailHost : one per TabSpec
    DetailHost o-- IntelGraphsView
    DetailHost o-- IntelClientsView
    GpuPage o-- IntelDetailHeader : shown on vendor tabs only
    GpuPage o-- GpuController
```

- **The page is never replaced.** The tabs come from the detail class's
  `TABS`, so the switcher doesn't jump around as the state changes.
- **Until the detail source runs,** each vendor tab shows an
  `Adw.StatusPage` for the current state, with the right button: Show
  Detailed Statistics, Try Again, or Turn On.
- **When it starts,** `create_views()` fills the tabs. A new detail backend
  (a restart) brings new views.
- **The switcher sits in the header,** as the page's title widget. In narrow
  windows it moves to a bar at the bottom, as in intel_gpu_top_gui. The
  pause button and menu appear only on the vendor tabs, and the last tab
  used is remembered (`gpu-view`).

Opening the details when administrator rights are needed:

```mermaid
sequenceDiagram
    participant U as User
    participant P as GpuPage
    participant C as GpuController
    participant B as IntelGpuTopBackend
    participant K as pkexec
    U->>P: Details tab
    P-->>U: StatusPage "Detailed statistics need administrator rights" [Show Detailed Statistics]
    U->>P: click
    P->>C: start_details(elevate=True)
    C->>B: new backend, start(elevate=True)
    C-->>P: detail-changed(STARTING) → spinner
    B->>K: pkexec proccoli-helper gpu-top 1000 card1 (→ intel_gpu_top -J -s 1000 -d drm:/dev/dri/card1)
    K-->>U: password prompt
    B-->>C: first record → updated
    C-->>P: detail-changed(RUNNING)
    P->>B: create_views(controller, settings)
    P->>P: fill Details and Processes tabs, show header buttons
```

### 7.4 Backend selection

| Backend | Role | Probe result |
|---|---|---|
| `IntelGpuTopBackend` | DETAIL | `PREFERRED` when `vendor == INTEL`, the driver is `i915` or `xe`, and `intel_gpu_top` is installed. `needs_elevation` unless running as root, `perf_event_paranoid` ≤ 0, or the binary has file capabilities. |
| `GenericDrmBackend` | SUMMARY | `FALLBACK` for any DRM card |
| `NvidiaSmiBackend` (future) | DETAIL | `PREFERRED` when `vendor == NVIDIA` and `nvidia-smi` is present |
| `AmdGpuTopBackend` (future) | DETAIL | `PREFERRED` when the driver is `amdgpu` and `amdgpu_top` is present |

The registry picks the best SUMMARY class and the best DETAIL candidate
separately. Adding a vendor means one DETAIL backend class with its `TABS`
and views, plus a registration line. Nothing else changes.

## 8. Processes and Apps

```mermaid
classDiagram
    direction TB
    class ProcessMonitor {
        <<GObject>>
        +ProcessMonitor(sysroot, settings, system, gpu_controllers)
        +processes: dict~int, ProcessInfo~
        +users: int
        +acquire()
        +release()
        +follow(ticker)
        +refresh(now)
        +cpu_count() int
        +use_elevated_io(reader)
        +stop_elevated_io()
        +signal updated()
        +signal elevated-io(on)
    }
    class RawProc {
        <<dataclass>>
        counters from /proc/pid/stat, status, io, cgroup, cmdline
    }
    class ProcessInfo {
        <<dataclass>>
        +pid, ppid, name, commandline, user, state, nice
        +cpu, memory, swap
        +read_bps, write_bps, read_total, write_total
        +gpu, vram, encode, decode
        +cpu_time_user, cpu_time_system, started
        +cgroup, containerized, app_id
    }
    class AppGrouper {
        +AppGrouper(lookup: app_id → AppInfo)
        +info_for(app_id) AppInfo|None
        +icon_for(process) Gio.Icon|None
        +group(processes) dict~str, App~
    }
    class App {
        <<dataclass>>
        +id, name, icon, description
        +pids: list
        +totals (cpu, memory, drive, gpu, ...)
    }
    class ProcessActions {
        +ProcessActions(system, helper?)
        +signal(action, targets, report)
        +set_priority(pid, nice, report)
        +set_affinity(pid, cpus, report)
    }
    class Action {
        <<enumeration>>
        END
        KILL
        HALT
        CONTINUE
    }
    ProcessMonitor ..> RawProc : reads
    ProcessMonitor ..> ProcessInfo : builds
    ProcessMonitor ..> GpuController : process_usage()
    AppGrouper ..> App : builds
    ProcessActions o-- System
    ProcessActions o-- PrivilegedHelper
    ProcessActions ..> Action
```

- **Per-process data:**
  - CPU: `/proc/PID/stat` deltas (normalised by the CPU count, if set)
  - Memory: `/proc/PID/status` (`VmRSS`, `VmSwap`)
  - Disk I/O: `/proc/PID/io` (own processes only)
  - Cgroup: `/proc/PID/cgroup`, read once per process lifetime
  - GPU columns: summed over every `GpuController.process_usage()`
- **Scanning on demand:** the scan runs only while a table page or an
  information dialog is open (`acquire`/`release`).
- **Other users' disk I/O:** the "Show Drive I/O of All Processes" toggle
  streams `proccoli-helper processes` (root) into the monitor
  (`use_elevated_io`). It fills in the processes we can't read ourselves.
- **App grouping:** by the systemd unit in the cgroup path:
  - `app-<id>.slice` (GNOME 49)
  - `app-gnome-<id>-<n>.scope`
  - `app-flatpak-<id>-<n>.scope`
  - `snap.<name>.<app>-<uuid>.scope` (desktop ID `<name>_<app>`)

  Names, icons and descriptions come from `System.desktop_app`. Everything
  else falls under "System Processes".
- **Icons:** every row of both tables starts with an icon. Apps show
  their own; each process shows the icon of the app it belongs to
  (`AppGrouper.icon_for`, injected into `ProcessesPage`), so an app's
  processes share it. Anything without an icon (System Processes, kernel
  threads, daemons, or a `.desktop` icon the theme doesn't have) shows a
  solid puzzle piece, `MISSING_APP_ICON` (our own
  `<APP_ID>-missing-app-symbolic`; Adwaita's is an outline). Being
  symbolic, it takes the text colour: white in the dark style, dark in the
  light style. The GPU's vendor *Processes* tab shows icons the same way:
  it knows only PIDs, so `AppIconLookup(sysroot, grouper).icon_for_pid`
  reads `/proc/<pid>/cgroup` (cached per PID; in `--demo` an empty root,
  since the demo's PIDs are made up). It reaches the view as
  `DetailServices.app_icon`, which the page factory builds from the
  context. `ui/widgets/app_icon.set_app_icon` does the puzzle-piece
  fallback for all three tables.
- **Context menus:** right-click (long-press on touch, Menu key or
  Shift+F10) on an Apps or Processes row selects it (unless it's already
  part of the selection) and opens: Information, Options (Processes), End,
  Kill, Halt, Continue: the same `table.*` actions as the action bar.
  - *Freeze fix (M43):* both the cell's right-click gesture and the
    ColumnView row's own click gesture see the press. The menu used to
    pop up without claiming it, so the row gesture stayed mid-click.
    On Wayland the popup took the button release, and the window then
    ignored all input. `open_cell_menu` now claims the gesture first
    (`EventSequenceState.CLAIMED`), which cancels the row's gesture.
  - *One popover per table:* it's made once and reused
    (`set_menu_model` each time). Its parent is the page's box
    (`menu_parent`), not the clicked cell. Table cells are recycled and
    rebound on every refresh, and a box positions popovers through its
    layout manager. `menu_point` translates the click into the box's
    coordinates; the keyboard menu points at the table's corner.
    `shutdown()` unparents it.
  - Re-sorting under an open menu is safe: `Gtk.MultiSelection` keeps the
    selection on the same rows, i.e. the same processes, not positions
    (checked while investigating: right-click firefox, the table re-sorts
    by processor for 6 s, the selection is still firefox).
- **Switch To** (Apps, top of the menu): GNOME on Wayland lets an app raise
  only its own window, so Proccoli asks the app to show itself
  (`System.activate_app`): D-Bus-activatable apps (most GNOME apps) get
  `org.freedesktop.Application.Activate`; apps declaring
  `SingleMainWindow=true` are relaunched, which shows their window. Others
  (e.g. Firefox, VS Code) would open a second window if relaunched, so the
  item isn't offered for them, nor for System Processes or a multi-row
  selection.
- **Actions:** `ProcessActions` acts directly first (the user's own
  processes). Only what was denied with EPERM goes to the helper, which asks
  for authentication once. Messages name the app ("Ended Firefox"), not the
  number of processes.

## 9. UI layer

```mermaid
classDiagram
    direction TB
    class ResourcePage {
        <<Adw.Bin>>
        +page_id, kind, title, icon_name, description, sort_name
        +sidebar_summary() SidebarSummary|None
        +header_widgets() list
        +title_widget() Gtk.Widget|None
        +track(source, handler_id) int
        +shutdown()
        +summary_changed()
        +report(text)
        +signal summary-changed()
    }
    class ScrollingPage {
        +add_group(title, description) Adw.PreferencesGroup
    }
    class DevicePage {
        +monitor: Monitor
        +graph_box(group, title, series, max, min_max, color_offset) GraphBox
        +add_properties(dict) Adw.PreferencesGroup
        +add_banner(title, button) Adw.Banner
        +update_labels(snapshot)*
    }
    class GpuPage {
        +controller: GpuController
        Overview + vendor tabs (§7.3)
    }
    class TablePage {
        +COLUMNS: list~Column~
        +update_rows(items)
        +items()* dict
        +targets(selected)* list
        +info_dialog(item)*
        +options_dialog(item)*
        +run_action(action)
    }
    class PageFactory {
        +register(kind, builder)
        +create(monitor) ResourcePage
    }
    class PageContainer {
        header bar (logo + burger when the sidebar isn't beside it) around a page;
        the page's title_widget() replaces the title
    }
    class MainWindow {
        +MainWindow(app, ctx)
        +add_page(page)
        +remove_page(id)
        +replace_page(page)
        +select_page(id)
    }
    ResourcePage <|-- ScrollingPage
    ResourcePage <|-- TablePage
    ResourcePage <|-- PlaceholderPage
    ScrollingPage <|-- DevicePage
    DevicePage <|-- CpuPage
    DevicePage <|-- MemoryPage
    DevicePage <|-- DrivePage
    DevicePage <|-- NetworkPage
    DevicePage <|-- BatteryPage
    DevicePage <|-- DemoPage
    DevicePage <|-- GpuPage
    TablePage <|-- AppsPage
    TablePage <|-- ProcessesPage
    MainWindow *-- StackSidebar
    MainWindow *-- "many" PageContainer
    MainWindow o-- PageFactory
    PageContainer o-- ResourcePage
    TablePage ..> ProcessActions
    ProcessesPage ..> ProcessInfoDialog
    ProcessesPage ..> ProcessOptionsDialog
    AppsPage ..> AppInfoDialog
```

**Dialogs:**
- `ProcessInfoDialog` and `AppInfoDialog` update live while open, and
  acquire the process scan for as long as they're shown.
- `ProcessOptionsDialog` sets the priority (names, or niceness with *Show
  Niceness Values*) and CPU affinity through `ProcessActions`.
- `PreferencesDialog` has General (Appearance: style and palette;
  Administrator Rights; Diagnostics), **Sidebar** (§9.5), Apps,
  Processes, Devices and **GPU** pages. Every row is bound both ways to its key and applies immediately.
  The GPU page has one detailed-statistics switch per GPU that has a detail
  source (`GpuController.set_details_enabled`), plus `gpu-elevate` and the
  intel_gpu_top update interval and history length.
- `about_dialog()` and `shortcuts_dialog()` come from the `SHORTCUTS` table,
  which tests check against the real accelerators.

**Page lifecycle (added in Milestone 1):** pages connect to longer-lived
objects (monitors, settings, GPU controllers). Every such connection is
registered with `ResourcePage.track()`. `MainWindow` calls
`page.shutdown()` when a page is removed (unplugged device), replaced or
the window closes, and `shutdown()` disconnects them all. The GPU page also
drops its detail views (and their backend connections) whenever the detail
source stops or restarts.

### 9.1 Widgets

```mermaid
classDiagram
    direction LR
    class Graph {
        <<Gtk.DrawingArea>>
        +set_series(series, colors, color_offset)
        +set_max(max)
        +set_show_grid(show)
        +set_show_axes(show)
        +set_time_span(seconds)
        +plot_rect(w, h)
        +set_aspect(ratio, min, max)
        +set_entry_color(i) / set_entry_base(i)
    }
    class GraphPane {
        graph + title + info line
    }
    class GraphBox {
        <<Adw.PreferencesRow>>
    }
    class DoubleGraphBox {
        <<Adw.PreferencesRow>>
        +start: GraphPane
        +end: GraphPane
    }
    class InfoRow {
        <<Adw.ActionRow>>
        +set_value(text|None)
    }
    class Meter {
        <<Gtk.Stack>>
        area chart (default) | progress bar
    }
    GraphPane *-- Graph
    GraphBox *-- GraphPane
    DoubleGraphBox *-- "2" GraphPane
    Meter *-- Graph
```

- **Graph:** rounded corners, a fill under the line in the first palette
  colour, an optional grid, and lines snapped to device pixels. Colours
  come from the window's theme (§9.3); with the System palette, extra
  series skip colours close to the accent (`palette_without`).
- **InfoRow** with `set_value(None)` hides itself, so pages never show
  "N/A".
- **Axes** (`ui/axes.py` holds the arithmetic): every graph of
  percentages on a 0–100 scale (page graphs, per-thread CPU graphs, sidebar
  charts) gets a left gutter of y labels (0/25/50/75/100 %, labelled as
  far as they fit, always 0 and 100) with tick marks, and a bottom row of
  time labels with ticks: round steps (`nice_step`: 10 s, 1 min, …) back
  from "now" at the right edge, one unit per axis. The span is graph data
  points × refresh interval (`history_span_s`), followed live. Small
  graphs use a smaller font, and sidebar charts grow from 36 to 52 px to
  fit the labels. `show-graph-axes` (Preferences → *Show Graph Axes*, on
  by default) turns them off. Graphs of rates and temperatures have no
  axes. The Intel Details tab keeps intel_gpu_top_gui's own axes.
- **Graphs fill the page** (`ui/layout.py` holds the arithmetic), on
  landscape and portrait screens alike (M36):
  - *Width:* the content column is clamped at `MAX_CONTENT_WIDTH` (1600
    px), so graphs use the window; text rows still don't span a 4K screen.
  - *Height:* a `DevicePage` splits the viewport's height among its graph
    rows (`fit_heights`): everything down to the last graph row fits on
    screen, and what's below (Properties) scrolls. Rows are grouped by top
    edge (`group_rows`), so side-by-side graphs share one. Each row stays
    within `height_range(width)` of its narrowest graph, from
    `GraphLimits`:
    - at least 120 px (`min_height`), so small windows scroll;
    - at most 560 px (`max_height`) and half the graph's width
      (`max_ratio`), so a tall portrait window doesn't stretch graphs into
      towers. Height a capped row can't use goes to the other rows; any
      rest stays empty below the content.
  - *Pairs* (`DoubleGraphBox`: GPU video encode/decode, demo read/write)
    sit side by side, and stack (`set_stacked`) when the window is portrait
    or a pane would be narrower than 280 px (`stack_pair`). Pages register
    them with `DevicePage.add_pair`; `_fit_graphs` arranges them first and
    fits again once the new rows are laid out.
  - *When:* `FittingPage` (`ui/page.py`, shared by `DevicePage` and the
    Overview since M50) notices size changes in its own `size_allocate` (it
    drops `AdwBin`'s layout manager, which bypasses that vfunc) and calls
    the page's `fit(width, height)` on idle, never during allocation,
    whenever `fit_key()` changes (the viewport's size, plus whatever else
    the page's layout depends on). Heights change only by 2 px or more, so
    layout can't oscillate. Stacking depends only on the viewport, so it
    can't flip back and forth either. `fit` returning True means "fit
    again once this is laid out".
  - *Overview grid* (M50): see §9.6.
  - *Per-thread CPU graphs:* height-for-width (`Graph.set_aspect`, 0.6 of
    the width, 48–240 px; also the minimum, since a scrolled page gets only
    its minimum height); cells are at least 120 px wide, so the grid picks
    fewer, larger columns.
  - *GPU Details:* intel_gpu_top_gui's `GraphGrid` shares out the spare
    height and picks its column count from the width; spare height now
    stops at `graph_cap(column width)` (same limits), passing what a
    capped graph can't take to the others.

```mermaid
flowchart TD
    A["FittingPage.size_allocate: fit_key() changed"] -->|idle| B{"DevicePage.fit: stack_pair for each pair"}
    B -->|a pair changed| C[queue_resize, fit again after layout]
    B -->|no change| D[group_rows by top edge]
    D --> E[row widths: narrowest graph per row]
    E --> F["fit_heights(viewport, fixed, widths, GraphLimits)"]
    F --> G[set_content_height per row, if changed by 2 px or more]
```

```mermaid
classDiagram
    direction LR
    class ScrollingPage {
        +box
        +scroller
    }
    class FittingPage {
        +fit_key() tuple
        +viewport_size() (int, int)
        +refit()
        +fit(width, height) bool
        +do_size_allocate()
    }
    class DevicePage {
        +fit(w, h) bool : pairs, then fit_heights
    }
    class OverviewPage {
        +plan: GridPlan
        +fit_key() : + card count, tables' height
        +fit(w, h) bool : plan_grid
    }
    ScrollingPage <|-- FittingPage
    FittingPage <|-- DevicePage
    FittingPage <|-- OverviewPage
```

- **Meter:** the sidebar's usage display. By default a 36 px area chart
  across the row (as in Resources) of `SidebarSummary.series`: one
  percentage for Processor, Memory, GPUs, drives (busy time) and
  batteries; receive and send, auto-scaled, for network interfaces. Apps
  and Processes have no summary, so no chart. *Sidebar Meter Type* can
  switch to a slim progress bar.

### 9.2 Window behaviour (mirrors Resources)

- Minimum size 360×240. The `AdwBreakpoint` at `max-width: 780sp` collapses
  the split view: the sidebar becomes an overlay.
- **Hiding the sidebar, burger top left (M46, M52):** the sidebar can be
  hidden at any width from the main menu's *Show Sidebar* check item or
  F9, both the stateful `win.toggle-sidebar` action. (Until M52 a toggle
  button beside the burger did this; it's gone.) The main menu ("burger")
  always stays at the window's top left:
  - *The corner (M47):* the app's logo (`app_logo_button`, 24 px, a flat
    button for `app.about`) sits in the top-left corner, with the burger
    right beside it: *logo, burger*, and nothing else, in both places
    below.
  - *Sidebar beside the content:* the sidebar's header starts with the
    logo and the burger (`main_menu_button`).
  - *Sidebar hidden, or folded into an overlay on a narrow window:* every
    `PageContainer` header starts with its own logo and burger
    (`start_controls`). They show exactly when
    `header_controls_visible(show_sidebar, collapsed)`, i.e. when the
    sidebar isn't beside the content. All burgers share one menu model.
  - *The menu item (M52):* `SidebarVisibility.action` is a stateful
    boolean action with no parameter, so GTK draws a check item, with F9
    shown beside it. Its state follows `show-sidebar` (any change: menu,
    F9, the overlay closing after a page is picked, the window
    narrowing); activating it toggles (GIO's default for such an action
    goes through `change-state`, which sets `show-sidebar`). It sits in
    the menu's first section, after *Go To*.
  - `SidebarVisibility(split_view, settings)` (`ui/sidebar_visibility.py`)
    applies the rules. On wide windows `show-sidebar` follows and saves
    `sidebar-shown`. On narrow ones the overlay starts closed, closes when
    a page is picked, and leaves `sidebar-shown` alone, so widening the
    window restores the user's choice. Tests use a fake split view
    without a display. `PageContainer.release()` disconnects a removed
    page's header.

```mermaid
stateDiagram-v2
    direction LR
    state "Wide, sidebar shown" as WS
    state "Wide, sidebar hidden" as WH
    state "Narrow, overlay closed" as NC
    state "Narrow, overlay open" as NO
    [*] --> WS: sidebar-shown = true
    [*] --> WH: sidebar-shown = false
    WS --> WH: ≡ → Show Sidebar (uncheck) / F9 (saves false)
    WH --> WS: ≡ → Show Sidebar (check) / F9 (saves true)
    WS --> NC: window narrows
    WH --> NC: window narrows
    NC --> NO: ≡ → Show Sidebar / F9
    NO --> NC: pick a page / F9 / click outside
    NC --> WS: widens, sidebar-shown = true
    NC --> WH: widens, sidebar-shown = false
    note right of WS: logo + burger in the sidebar header; Show Sidebar checked
    note right of WH: logo + burger in every page header
```

```mermaid
classDiagram
    direction LR
    class SidebarVisibility {
        +split: OverlaySplitView
        +settings
        +action: Gio.SimpleAction ("toggle-sidebar", state b)
        +preferred: bool
        +toggle()
        +page_selected()
        +shutdown()
        -_on_collapsed()
        -_on_shown() : saves; syncs action state
        -_on_change_state(value) : sets show-sidebar
    }
    class MainWindow {
        +menu_model: primary_menu(goto)
        +add_action(sidebar_visibility.action)
        F9 → win.toggle-sidebar
    }
    class primary_menu {
        Go To ›
        Show Sidebar ✓ (win.toggle-sidebar)
        Show All Details… / Preferences / Shortcuts / About
    }
    MainWindow --> SidebarVisibility
    MainWindow --> primary_menu
    primary_menu ..> SidebarVisibility : item targets its action
```
- **Go To (M48):** the main menu's first item is a *Go To* submenu listing
  every pane in the sidebar's display order, so panes can be switched
  without the sidebar (useful while it's hidden). `ui/navigation.py`
  (display-free) builds it: `fill_goto_menu(menu, [(id, title,
  description)])` refills one `Gio.Menu` in place, so an open menu stays
  current. `goto_labels` adds the description when two panes share a
  title (two identical drives), or the page ID if there's none. Items
  target the stateful `win.go-to` action (parameter and state: a page ID).
  Activating it calls `select_page`, and `_on_visible_page` sets its
  state, so the current pane is marked however it was reached. The window
  refills the menu on the sidebar's `entries-changed`, in
  `StackSidebar.display_order()`, which is already right while a row is
  being added. Placeholder pages say "Not available in demo mode." or "Not
  available on this system.", and a static test keeps planning-document
  references out of user-visible strings.

```mermaid
sequenceDiagram
    participant S as StackSidebar
    participant W as MainWindow
    participant M as goto_menu (Gio.Menu)
    participant A as win.go-to (state: page ID)
    S-->>W: entries-changed (add, remove, move, replace)
    W->>M: fill_goto_menu(display_order, titles, descriptions)
    Note over M: user picks "Memory" in ≡ → Go To
    M->>A: activate("memory")
    A->>W: select_page("memory")
    W->>A: set_state("memory") (from _on_visible_page)
```
- **Back and forward (M49):** `NavigationHistory` (`ui/navigation.py`, no
  display) keeps the panes visited, browser-style. `visit` starts a new
  branch and drops forward; `back` / `forward` move through the history;
  `remove` forgets an unplugged page and merges the neighbours that
  leaves equal. History holds 50 entries. `MainWindow._on_visible_page`
  records every page change (sidebar, Go To, Overview, …) except those
  made by `go_back` / `go_forward` (`_navigating`). Inputs:
  - the mouse's thumb buttons, through one `Gtk.GestureClick(button=0)`
    on the window in the capture phase. `on_mouse_button` maps GDK
    buttons 8/11 to back and 9/10 to forward (`mouse_direction`), claims
    them, and denies every other button at once, so clicks still reach
    their own widgets. Nothing happens while a dialog is open;
  - `win.back` / `win.forward`, on Alt+Left / Alt+Right, enabled only
    when there's somewhere to go; listed under Keyboard Shortcuts.

```mermaid
classDiagram
    direction LR
    class NavigationHistory {
        +current: str
        +back_stack: list~str~
        +forward_stack: list~str~
        +visit(page_id)
        +back() str
        +forward() str
        +remove(page_id)
        +can_go_back() bool
        +can_go_forward() bool
    }
    class MainWindow {
        +history: NavigationHistory
        +mouse_nav: GestureClick (capture, any button)
        +nav_actions: back, forward
        +go_back() bool
        +go_forward() bool
        +on_mouse_button(gesture) bool
    }
    MainWindow *-- NavigationHistory
    MainWindow ..> mouse_direction : 8/11 back, 9/10 forward
```
- Built-in page order in the sidebar: Overview (Proccoli-only, M39), Apps,
  Processes, Processor, Memory,
  GPUs (by PCI slot), Drives (by name), Network interfaces (Ethernet, then
  Wi-Fi, then others), Batteries.
- **The user's order** (Proccoli-only): Overview, Apps and Processes stay
  pinned at the top, with no chart and no entry colour (`UNCHARTED`). Every other entry can be moved (row menu on right-click, long-press,
  the Menu key or Shift+F10: *Move Up*, *Move Down*, *Minimize*/*Expand*,
  *Reset Order*; Alt+Up/Down; drag and drop) and minimised to its icon and
  name (the chevron on the row). `sidebar-order` holds the order below the
  pinned entries, `sidebar-minimized` the minimised ones.
  `ui/sidebar_order.py` (pure, unit-tested) arranges: pinned first, then
  the saved order; entries it doesn't know (a new drive) go right after
  their predecessor in the built-in order.
- **Parts per entry:** each movable entry can show or hide its name,
  description (model, device ID, interface name...), usage line and chart
  (row menu *Show …* check items; Preferences, §9.5). `sidebar-hidden-fields`
  (`a{sas}`: page ID → hidden parts) holds the choices;
  `ui/sidebar_fields.visible()` combines them with the global *Show Usage
  Details* / *Show Device Descriptions* switches and minimising. The icon
  always stays, so a fully hidden entry is still there to click.

```mermaid
classDiagram
    direction LR
    class StackSidebar {
        +order() list
        +default_order() list
        +move(id, delta)
        +move_before(id, target)
        +set_minimized(id, on)
        +reset_order()
        +set_field_shown(id, field, on)
        +row_menu(id) Gio.Menu
        +row_actions(id) Gio.ActionGroup
        +assign_colors()
    }
    class sidebar_order {
        <<module, pure>>
        +arrange(default, saved, pinned) list
        +move(order, id, delta, pinned) list
        +move_before(order, id, target, pinned) list
        +can_move(order, id, delta, pinned) bool
    }
    class StackSidebarItem {
        +movable: bool
        +minimized: bool
        +set_minimized(on)
        +set_hidden_fields(fields)
        +shows(field) bool
        +minimize_button
        +details: icon-aligned box
    }
    StackSidebar ..> sidebar_order
    StackSidebarItem ..> sidebar_fields : visible()
    StackSidebar *-- "many" StackSidebarItem
    StackSidebar ..> Settings : sidebar-order, sidebar-minimized
```
- **Sidebar icons:** each entry has a 16 px symbolic icon left of its name;
  its description, usage line and chart line up under the name. Apps and
  Processes use Adwaita's app grid and list icons. Processor, Memory and GPU
  (a graphics card) use our own (`PROCESSOR_ICON`, `MEMORY_ICON`,
  `GPU_ICON` in `data/icons`, 0BSD: Resources' icons are GPL). Drives use
  Adwaita's icon for their type (solid state, hard disk, removable, optical,
  memory card, virtual), network interfaces theirs (wired, wireless, VPN)
  and batteries `battery-symbolic`.
- The last viewed page and the window size and maximised state are saved.
- Keyboard: `Ctrl+F` search (table pages), `Ctrl+,` Preferences, `Ctrl+?`
  shortcuts, `Ctrl+Q` quit, `Delete` end process, `Ctrl+Delete` kill
  process, `Ctrl+I` information.

### 9.3 Appearance

```mermaid
classDiagram
    direction LR
    class Theme {
        <<GObject>>
        +settings
        +style_manager
        +dark: bool
        +palette: Palette
        +system_accent() RGB
        +series_rgb(index) RGB
        +accent_rgb() RGB
        +accent_css() str
        +entry_rgb(index, series) RGB
        +entry_css() str
        +css() str
        +shutdown()
        +signal changed()
    }
    class Palette {
        <<core.palette, frozen dataclass>>
        +id, name
        +light: hex colours
        +dark: hex colours
        +follows_accent: bool
    }
    class ThemeCss {
        <<ui.style>>
        CSS provider with accent_css()
    }
    class Graph {
        colours from theme_of(self)
    }
    Theme --> Palette
    Theme --> Style
    class Style {
        <<core.styles, frozen dataclass>>
        +id, name
        +base: system|light|dark
        +colors: surface → hex
    }
    ThemeCss o-- Theme
    Graph ..> Theme : via its window
    class StyleManager {
        <<Adw.StyleManager or a test fake>>
        +set_color_scheme(scheme)
        +get_dark() bool
        +get_accent_color_rgba()
        +notify::dark, notify::accent-color
    }
    Theme o-- StyleManager
    Theme ..> Settings : color-scheme
```

- **Styles** (`core/styles.py`, no GTK): *Follow System* (default; maps to
  `Adw.ColorScheme.DEFAULT`, which follows the desktop), *Light*, *Dark*,
  and four tinted styles named after ExpressVPN's themes, with our own
  colours: *Sand* (warm light), *Sky* (cool light), *Twilight* (dusk
  purple, dark) and *Midnight* (near-black navy, dark). A style has a base
  scheme and, if tinted, colours for libadwaita's surfaces (window, view,
  header bar, sidebar, cards, popovers, dialogs; `style_css` writes the
  `--*-color` variables and the pre-1.6 `@define-color` names, loaded by
  `ThemeCss`). Text meets WCAG AAA contrast (7:1) on every surface (tested).
  Changes apply at once; `Theme` emits `changed` once per change.
- **Palettes** (`core/palette.py`, no GTK): eight, after GNOME Terminal's
  built-in schemes plus Nord: **System** (default: the desktop's accent
  colour first, then colour-blind-friendly steps that don't clash with it),
  GNOME, Tango, Solarized, Linux Console, XTerm, Rxvt and Nord. Each has a
  light variant (the terminal's normal colours) and a dark one (its bright
  colours), in series order blue, red, green, yellow, magenta, cyan.
- **What a palette colours:** every graph series (page graphs, sidebar
  meters, the Intel Details graphs and legends) and, except for System, the
  accent colour: `ThemeCss` loads `--accent-bg-color` (and the pre-1.6
  `@define-color` names) at application priority, so switches, progress
  bars and selections match.
- **Where it lives:** `Application` builds the `Theme` into
  `AppContext.theme` (the UI half of the composition root) and a
  `ThemeCss`; `MainWindow` makes a theme if a test didn't, and exposes it
  as `window.theme`.
- **How widgets get it:** no globals. A graph asks its window
  (`theme_of(widget)` reads `widget.get_root().theme`) when it draws;
  outside a themed window it uses the System palette. When the theme
  emits `changed` the window queues a redraw of every drawing area under it
  (`redraw_tree`), because GTK caches each widget's rendering.
- **A colour per sidebar entry:** the sidebar numbers its charted entries
  (all but Apps and Processes) in the built-in order (so moving an entry
  keeps its colour) and gives each
  `Theme.entry_rgb(i)`: the palette's colours, then lighter and darker
  shades (`entry_colors`), so every entry differs however many there are.
  Its chart uses that colour (network's send series a shade of it,
  `secondary`), its progress bar the `.entry-color-<i>` rule `ThemeCss`
  loads, and its page's graphs start at the same colour
  (`ResourcePage.set_entry_color` → `Graph.set_entry_base`), so sidebar and
  page match.
- **Preferences → General → Appearance:** *Style* (Follow System, Light,
  Dark) and *Colour Palette* (each entry shows its colours for the current
  style).

#### App icon (M38)

The icon is a gauge whose needle is a broccoli. The stalk is the needle's
shaft and its cut end sits on the pivot; the lumpy crown is the needle's
head. The broccoli's awkward shape (thin stem, big top) becomes the most
natural part of the picture, instead of being squeezed into a frame.

- *Flat dial:* dark bezel and face, a 240° scale in GNOME green, yellow
  and red with ticks, and a green sparkline under the pivot (usage over
  time).
- *Broccoli on top:* drawn with depth (gradient stalk with fibres and a
  pale cut face; ten florets with radial shading, each covered in buds lit
  from the upper left), and a soft shadow on the dial. It points at about
  58 % of the scale, in the green.
- *Small sizes:* at 16 px the dial ring, the green broccoli and the red
  end of the scale still read.
- `packaging/make-logo.py` writes the SVG. Buds come from a seeded random
  generator, so every run gives the same file; tests check that the
  committed SVG is exactly its output, that it stays on the canvas, and
  that the PNGs match it. `make icons` runs it, then
  `render-icons.py` renders the PNGs (16–512 px).

### 9.4 Optional authentication at launch

```mermaid
classDiagram
    direction LR
    class ElevationOffer {
        <<dataclass>>
        +id: page ID
        +title, subtitle
        +run(done: ok → None)
    }
    class ElevationRunner {
        +start()
        +results: dict~id, bool~
        one offer at a time
    }
    class ResourcePage {
        +elevation_offer() ElevationOffer|None
    }
    class LaunchAuthDialog {
        <<Adw.AlertDialog>>
        a switch per offer
        Authenticate | Not Now
        Don't ask at start-up
    }
    ResourcePage ..> ElevationOffer : offers
    LaunchAuthDialog o-- "1..n" ElevationOffer
    LaunchAuthDialog ..> ElevationRunner : Authenticate
    MainWindow ..> LaunchAuthDialog : at launch, menu
```

- **Offers** (`ResourcePage.elevation_offer()`), only while there's
  something to unlock:
  - *Memory:* module properties through `dmidecode`, only when udev had
    none (§6).
  - *GPU:* detailed statistics when the detail source is NEEDS_AUTH (§7.2).
  - *Processes:* every process's drive I/O through the helper.
- **At launch,** if `auth-at-launch` is on and there are offers, the window
  shows `LaunchAuthDialog` once it's on screen. *Authenticate* runs the
  switched-on offers with `ElevationRunner`, strictly one after another,
  because each may show a polkit prompt (dmidecode and the I/O stream are
  separate polkit actions; intel_gpu_top never caches). A failure or
  cancelled prompt doesn't stop the rest.
- **Optional:** *Not Now* changes nothing. Every page keeps its own button
  (Memory's *Authenticate*, the GPU tabs' *Show Detailed Statistics*,
  Processes' I/O toggle), and the main menu's *Show All Details…*
  (`win.authenticate`, enabled while there are offers) brings the dialog
  back. "Don't ask at start-up" and Preferences → General → *Ask for
  Administrator Rights at Start-Up* control `auth-at-launch`.

### 9.5 Sidebar preferences

```mermaid
classDiagram
    direction LR
    class PreferencesDialog {
        +sidebar: StackSidebar|None
        +entry_rows: dict~id, Adw.ActionRow~
        +open_entry(id) EntryPage
    }
    class EntryPage {
        <<Adw.NavigationPage>>
        +switches: Field → Adw.SwitchRow
        +minimized: Adw.SwitchRow
        +up, down: Gtk.Button
        +sync()
        +shutdown()
    }
    PreferencesDialog *-- "0..n" EntryPage : push_subpage
    EntryPage ..> StackSidebar : set_field_shown, set_minimized, move
```

- Preferences → **Sidebar**: *All Entries* (the global *Show Usage
  Details*, *Show Device Descriptions* and *Meter Type*, moved from
  General) and *Entries*: one row per movable entry, in sidebar order,
  with its icon and current description (model, device ID, interface
  name...). Apps and Processes aren't listed: they stay on top.
- A row opens the entry's sub-page: *Name*, *Description*, *Usage Details*
  and *Chart* switches (each subtitled with what it shows now),
  *Minimized*, and *Position* with Move Up/Down. Everything goes through
  the window's `StackSidebar` (injected as `sidebar=`), so it uses the same
  settings and rules as the row menu, and the page follows changes made
  there (`sync()`); it disconnects when the dialog closes.

---

### 9.6 Overview page (M39, M41, M50, M51)

The first sidebar entry, pinned above Apps and Processes. It shows a card
for every entry that has a sidebar chart, in the sidebar's order and
colours: the entry's icon, name and usage on top; its detail and
description below; then a chart of the same series as its sidebar chart.
Clicking a card opens that page. Placeholder pages (no summary at all) get
no card. On a first start (no `last-viewed-page`) it's the page shown.

- **Layout: an N × M grid that tries to fill the page** (M50, M51). Before, chart
  height followed card width (0.4 ×, at most 240 px), which left most of a
  full-screen portrait monitor empty. Now the cards (a homogeneous
  `Gtk.FlowBox`) fill the height the page gives them:
  - *Area:* the viewport less the column's margins and the top tables'
    natural height (and the gap above them). If that would make charts
    shorter than 80 px (`GRID_MIN_CHART`), the cards take the whole
    viewport and the tables scroll into view below. With fewer charts the
    tables always stay on screen.
  - *Shape:* `plan_grid` (`ui/layout.py`, no display) tries 1–4 columns,
    each card at least as wide as its minimum (280 px plus the FlowBox
    child's padding); rows share the height equally. It scores each by
    how far the chart's height/width is from 0.5 (log scale) plus 2 × the
    share of empty cells, so full rows win over a slightly better shape;
    any plan needing charts under 80 px loses to one that doesn't.
  - *Never taller than wide* (M51): the grid only *tries* to fill. A
    chart's height stays strictly below its width (`GRID_MAX_RATIO` 1.0,
    `max_chart_height(w) = ceil(w × ratio) − 1`), so one or two cards on a
    portrait screen don't become towers. The score adds 2 × the share of
    the area left unfilled, so among plans within the cap the one that
    fills most wins: two cards on a landscape page stack (filling) rather
    than sit side by side capped. What the cap leaves stays empty below
    the grid; the tables move up into it.
  - *Chrome:* a card's height apart from its chart is measured from the
    FlowBox child (its padding included), at the planned width. Its width
    apart from the chart (the child's margins, the card's border and
    padding) is measured as the column slot (flow width ÷ columns) less
    the chart's allocated width, so the cap holds on screen. Before the
    first layout it's estimated, and the page fits once more after it.
  - *Applying:* `max_children_per_line` = the planned columns (the
    minimum stays 1, so the window can still be made narrower), and every
    chart's content height = the planned height. A column change refits
    once more after layout, and only once, so rounding can't flip the
    column count back and forth.
  - *When:* `OverviewPage` is a `FittingPage` whose `fit_key()` adds the
    number of cards and the tables' height (they grow from "Waiting for
    data…" to ten rows), so all three refit.

```mermaid
flowchart TD
    A["fit_key() changed: viewport, cards, tables"] -->|idle| B["area = viewport − margins − tables"]
    B --> C["plan_grid(count, width, area, chrome)"]
    C --> D{charts ≥ 80 px?}
    D -->|yes| F[apply: max columns, chart heights]
    D -->|no| E["plan_grid(count, width, viewport − margins): tables below the fold"]
    E --> F
    F --> G{columns changed?}
    G -->|"yes, or chrome width only estimated; first time"| H[fit again after layout]
    G -->|no| I[done]
```
- **Data:** a card calls `page.sidebar_summary()` and follows the page's
  `summary-changed`, exactly like a sidebar row. `SidebarSummary.text()`
  builds the usage line for both. Charts redraw only while mapped; axes
  and time span follow `show-graph-axes`, `graph-data-points` and
  `refresh-speed`.
- **Decoupled from the sidebar (DI):** `OverviewPage(settings,
  navigate)` never touches the sidebar. `StackSidebar` emits
  `entries-changed` whenever its charted entries, their order or their
  colours change (every `assign_colors()`), and `entries()` lists
  `(page, colour index)` in display order. The window connects the two
  (`overview.sync(sidebar.entries())`) and passes `select_page` as
  `navigate`. Tests drive `sync()` with fake pages.

```mermaid
classDiagram
    direction LR
    class OverviewPage {
        +settings
        +navigate(page_id)
        +plan: GridPlan
        +plan_for(width, viewport_h) GridPlan
        +grid_area(viewport_h, with_tables) int
        +cards: dict~str, OverviewCard~
        +sync(entries: list~(ResourcePage, int)~)
        +order() list~str~
        +shutdown()
    }
    class OverviewCard {
        +page: ResourcePage
        +graph: Graph
        +set_page(page, colour)
        +set_chart_height(px)
        +chrome_height(width) int
        +chrome_width(slot) int?
        +set_style()
        +update()
        +shutdown()
    }
    class StackSidebar {
        +colors: dict~str, int~
        +entries() list~(ResourcePage, int)~
        +signal entries-changed()
    }
    class ResourcePage {
        +sidebar_summary() SidebarSummary
        +signal summary-changed()
    }
    class SidebarSummary {
        +text() str
        +has_chart() bool
    }
    FittingPage <|-- OverviewPage
    OverviewPage "1" *-- "*" OverviewCard
    OverviewCard --> ResourcePage : follows
    ResourcePage --> SidebarSummary
    MainWindow --> OverviewPage : sync(sidebar.entries()), navigate = select_page
    MainWindow --> StackSidebar : entries-changed
```

```mermaid
sequenceDiagram
    participant W as MainWindow
    participant S as StackSidebar
    participant O as OverviewPage
    participant C as OverviewCard
    participant P as Device page
    W->>S: add_item(page) / move / remove_item / replace_page
    S->>S: assign_colors()
    S-->>W: entries-changed
    W->>O: sync(S.entries())
    O->>C: create, re-colour, reorder or drop cards
    P-->>C: summary-changed (each tick)
    C->>P: sidebar_summary()
    C->>C: labels, series, queue_draw if mapped
    C-->>O: child-activated (click)
    O->>W: navigate(page_id) = select_page
```

#### Busiest apps and processes (M41)

Below the cards, **Busiest** shows two tables: the top 10 apps and the
top 10 processes. Each row has rank, icon (the puzzle piece when there's
none), name, processor use and memory.

- **Ranking** (`processes/top.py`, pure): by processor use or memory,
  chosen with the *Processor / Memory* toggle (`overview-top-by`). Ties go
  to the other measure, then the name (case-insensitive), so rows don't
  swap on equal values. *System Processes* isn't ranked as an app: it
  would nearly always be first, and its processes are in the other table.
  The column used for the ranking is highlighted.
- **Data:** the same `ProcessMonitor` and `AppGrouper` as the Apps and
  Processes pages. `TopTables` acquires the monitor only while the
  Overview is mapped, so processes aren't sampled for a page no one sees.
  Memory follows the unit base preference.
- **Widgets:** `TopTable` (`ui/widgets/top_table.py`) makes its 10
  `TopRow`s once and refills them in place, hiding unused ones, so updates
  don't flicker or move keyboard focus. Activating a row opens the Apps
  or Processes page.
- **Layout:** a `FlowBox` puts the tables side by side when each can be at
  least 340 px wide, and stacks them otherwise (portrait windows). It isn't
  homogeneous, so the shorter table leaves no gap.
- **No monitor, no tables:** in demo mode and in tests without one,
  `OverviewPage(processes=None)` shows only the cards.

```mermaid
classDiagram
    direction LR
    class TopTables {
        +monitor: ProcessMonitor
        +grouper: AppGrouper
        +apps: TopTable
        +processes: TopTable
        +by_buttons: dict~TopMetric, ToggleButton~
        +metric: TopMetric
        +refresh()
        +start()  acquire
        +stop()  release
        +shutdown()
    }
    class TopTable {
        +rows: list~TopRow~
        +set_rows(rows)
        +set_sorted_by(metric)
        +shown() list~str~
    }
    class top_py {
        <<module>>
        +TopMetric: CPU, MEMORY
        +rank_key(item, metric)
        +top(items, metric, count)
        +top_apps(apps, metric, count)
        +top_processes(processes, metric, count)
    }
    OverviewPage *-- TopTables : when a monitor exists
    TopTables *-- "2" TopTable
    TopTable *-- "10" TopRow
    TopTables ..> top_py
    TopTables --> ProcessMonitor : updated
```

## 10. Runtime flow

### 10.1 Start-up

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
    GC->>GC: registry.best(SUMMARY).start(); best(DETAIL) started unless it needs a password
    A->>W: create window
    DM-->>W: device-added(monitor) × N
    W->>W: page = ctx.pages.create(monitor) (GPU: GpuPage with the detail TABS)
    W->>W: add PageContainer + StackSidebarItem
    W->>W: restore last-viewed page
    A->>T: start(refresh speed)
```

### 10.2 Each tick

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

---

## 11. Cross-cutting concerns

- **Settings schema** (`io.github.mamadingleberry.Proccoli`) mirrors
  Resources' keys: window size and maximised state, temperature unit, unit
  base, refresh speed, virtual drives and network interfaces, sidebar
  details, description and meter type, network bits, every `apps-show-*` and
  `processes-show-*` column, logical CPUs, graph grids, graph data points,
  sort column and order, last viewed page, normalize CPU usage, detailed
  priority. Proccoli adds:
  - `color-scheme`: the style: `system` (follow the desktop), `light`,
    `dark`, `sand`, `sky`, `twilight` or `midnight`
  - `palette`: one of the eight colour palettes (§9.3), `system` by default
  - `auth-at-launch`: offer to authenticate at start-up (§9.4), on by default
  - `sidebar-shown`: whether the sidebar shows on wide windows (§9.2), on
    by default
  - `overview-top-by`: what ranks the Overview's busiest apps and
    processes, `cpu` (default) or `memory` (§9.6)
  - `sidebar-order`, `sidebar-minimized` and `sidebar-hidden-fields`: the
    user's sidebar (§9.2)
  - `show-graph-axes`: axes on percentage graphs (§9.1), on by default
  - `log-level`, `log-max-size`, `log-performance-interval`: the
    diagnostics log (below)
  - `gpu-details-disabled`: PCI slots whose detailed statistics are off
  - `gpu-view`: the GPU page's last tab (overview, details, processes)
  - `gpu-elevate`: start the detail source through pkexec at launch
    instead of waiting for the user to ask
  - `intel-gpu-top-interval` and `intel-gpu-top-history`: the Details tab's
    own update interval (empty = the refresh speed) and history length
- **Diagnostics log** (`core/applog.py`): standard practice on Linux, a
  rotating file at `$XDG_STATE_HOME/proccoli/proccoli.log`
  (`~/.local/state/proccoli/`). `FileLog` attaches a `RotatingFileHandler`
  to the `proccoli` logger: `log-level` (off, error, warning, info (default),
  debug) and `log-max-size` (KiB, default 1024, 64–65536); one older file
  is kept, so it never takes more than twice the size on disk (tested).
  The terminal keeps its own level (`--debug`). `PerformanceLog` (in the
  context, connected to the ticker first, so it times whole refreshes)
  writes every `log-performance-interval` minutes (default 10, 0 off):
  Proccoli's CPU %, memory, threads, refreshes and the slowest refresh, from
  `/proc/self` through `SysRoot`. Preferences → General → *Diagnostics*
  sets all three and opens the log folder. `Application(log_file=...)`
  and `PreferencesDialog(launcher=...)` are injectable, so tests never
  write to the real home. Log files are private (0600, folder 0700).
- **Stall watchdog** (`core/watchdog.py`, M44): a frozen window logs
  nothing, because the main loop that would write is the thing that's
  stuck. `Application` starts a `StallWatchdog`: the main loop beats every
  250 ms (`GLib.timeout_add`), and a daemon thread checks the beat. After 3
  s without one, it logs an error with three samples, 0.3 s apart, of every
  thread's Python stack (`format_stacks`, main thread first), so a loop
  shows its repeating frames. When the beat returns, it logs how long the
  stall lasted. PyGObject releases the GIL while GTK runs C code, so the
  thread runs even then. Clock, sleep, stack capture and scheduling are
  injectable.

```mermaid
sequenceDiagram
    participant M as Main loop
    participant W as StallWatchdog thread
    participant L as Log
    loop every 250 ms
        M->>W: beat() (last_beat = now)
    end
    loop every 250 ms
        W->>W: check(): now - last_beat
    end
    Note over M: stuck (e.g. a GTK layout loop)
    W->>L: ERROR main loop stalled for 3.0 s + 3 stack samples
    M->>W: beat() again
    W->>L: WARNING responsive again after N s
```
- **Errors:** a monitor that fails to read keeps its page, but shows empty
  graphs and an `AdwBanner` with the reason. Backend failures follow the
  state diagram in §7.2. Nothing ever raises into GTK callbacks; exceptions
  are logged with the device ID.
- **Accessibility:** every graph has an accessible label with its current
  value; table columns have headers; the sidebar is keyboard-navigable.
- **Internationalisation:** strings are wrapped in `_()` from the start
  (gettext); translations come later.
- **Licensing (decided): 0BSD (Zero-Clause BSD).** Anyone may use, copy,
  modify and redistribute the code, with or without a fee, without even
  keeping the copyright notice. It is OSI-approved and written for software.
  The Unlicense and CC0 are less suitable: the Unlicense's public-domain
  wording isn't recognised everywhere, and CC0 explicitly withholds a
  patent grant.
  - **Consequence:** Resources is **GPL-3.0-or-later**, so **no code, UI
    files, CSS or assets are copied from it**. Its UX is re-implemented from
    scratch, using only the observable behaviour documented in §2.1.
  - intel_gpu_top_gui code is ours, so it can be reused under 0BSD.
  - Third-party code with attribution or copyleft terms can't be vendored in.
    Depend on it as a system package instead.
- **Naming:** "Proccoli" is a prototype name. The display name, app ID and
  version live only in `src/proccoli/__init__.py`. Everything else reads
  those constants, so a rename means editing that file, renaming the
  `src/proccoli/` package directory, and renaming the `data/` files.

### 11.1 Security: what runs as administrator (M40)

**What runs as root,** always through `pkexec` after the user types an
administrator password:

| Program | Started by | Polkit action | Prompt |
|---|---|---|---|
| `proccoli-helper signal/renice/affinity` | End/Kill/Halt/Continue, Process Options on another user's process | `….signal`, `….renice`, `….affinity` | `auth_admin_keep` |
| `proccoli-helper dmidecode` | Memory → Authenticate (only when udev lacks the modules) | `….dmidecode` | `auth_admin_keep` |
| `proccoli-helper processes` | Processes → drive activity of other users' processes | `….processes` | `auth_admin_keep` |
| `proccoli-helper gpu-top MS cardN` → `intel_gpu_top -J -s MS -d drm:/dev/dri/cardN` | GPU → Show Detailed Statistics, or `gpu-elevate` | `….gpu-top` | `auth_admin_keep` |
| `intel_gpu_top …` directly (fallback: helper older than protocol 3) | as above | `….intel-gpu-top` | `auth_admin` every time |

**Threat model.** The user is an administrator and trusts Proccoli. The
attacker is other code running as the same user, such as a malicious
extension, a compromised npm or pip package, or a script. That code can't
become root on its own. It can, however, try to turn the user's *next
password prompt* into root for itself, or make a root action hit something
the user didn't choose.

**Review findings and what changed:**

| # | Finding | Severity | Fix |
|---|---|---|---|
| 1 | In a source checkout the helper was the checkout's own script, `pkexec python3 ~/…/proccoli_helper.py`. Code running as the user could edit it, or plant a `json.py` next to it (Python puts the script's folder first on `sys.path`). The next prompt, polkit's generic "run python3 as root" one, then ran that code as root. | High | `helper_argv` uses only an installed helper that only root can change (`core.trust.is_trusted_path`: the file and every folder up to `/` owned by root, not group- or world-writable, symlinks resolved). A source checkout's helper runs only with `PROCCOLI_DEV_HELPER=1`, through `python3 -I`. Otherwise those actions are off, with a log line saying why. |
| 2 | `intel_gpu_top` for pkexec came from `PATH`. On Ubuntu `PATH` includes `~/.local/bin`, so a planted `~/.local/bin/intel_gpu_top` would run as root at the next Show Detailed Statistics. | High | Elevated starts use `find_trusted("intel_gpu_top")`: only `/usr/bin`, `/usr/sbin`, `/bin`, `/sbin`, `/usr/local/bin`, `/usr/local/sbin`, and only a root-only copy. Otherwise the start fails with an explanation (`UNTRUSTED_REASON`). Unelevated starts still use `PATH`: they run as the user, so nothing is gained. |
| 3 | The helper acted on bare PIDs. Between the click and the end of the password prompt (seconds), the target can exit and the kernel can reuse its PID for another process, possibly a root one, which the root helper would then kill. | Medium | `ProcessActions` reads each process's start time (`read_start_time`, field 22 of `/proc/PID/stat`) when the user acts and sends `PID@STARTTIME`. The helper acts only if the start time still matches. It signals through a pidfd (`os.pidfd_open` → check → `signal.pidfd_send_signal`), so the check and the signal hit the same process. Without pidfds it checks, then signals. renice and affinity check just before acting (a sub-millisecond race remains; the syscalls have no pidfd form). A process already gone counts as done and isn't sent at all. |
| 4 | The helper's interpreter wasn't isolated. | Low | Shebang `#!/usr/bin/python3 -I`: no script folder on `sys.path`, no `PYTHON*` variables, no user site-packages. pkexec already clears the environment; this is defence in depth. |
| 5 | `str.isdigit()` accepted non-ASCII digits (`"²"` crashed the helper with a traceback; Arabic-Indic digits parsed). | Low | ASCII digits only (`_digits`). |
| 6 | A hung `dmidecode` crashed the helper with a traceback. | Low | Timeout → JSON error, exit 1. |
| 7 | The diagnostics log could be read by other local users when the home folder allows it. It can name processes and devices. | Low | `PrivateRotatingFileHandler`: files 0600 (every rollover too), folder 0700. |
| 8 | An installed helper from before these changes would refuse `PID@STARTTIME`. | Compatibility | The helper declares its `PROTOCOL` (2: identities; 3: `gpu-top`). The app reads it from the file (no root needed, `helper_protocol`) and sends an older helper only what it understands, logging a reinstall hint. |
| 9 | *Found in M41, fixed in M42:* the root `intel_gpu_top` outlived Proccoli. M40 had judged that it dies of SIGPIPE when Proccoli stops reading. It doesn't: it ignores SIGPIPE (`SigIgn` bit 13 in `/proc/PID/status`), and Proccoli can't signal a root process. Four orphans were found on the development machine, the oldest over 12 hours old, each polling the GPU. Each stop, restart (interval change) or quit after Show Detailed Statistics left one behind. | Medium | `proccoli-helper gpu-top MS cardN` runs `intel_gpu_top` with fixed arguments (interval 100–10000 ms, `card\d+`, no `-o`) and relays its output (`relay`). When a write fails (Proccoli stopped reading or exited), it terminates the child, kills it after 2 s if needed, and exits. The helper is root, so it may. `IntelGpuTopBackend` uses it whenever `GpuDeps.helper` speaks protocol 3, falling back (with a warning) to running `intel_gpu_top` directly. Since the arguments are fixed and no files can be written, the action may keep its authorization (`auth_admin_keep`). |

**Reviewed and acceptable as they are:**

- *Retained authorization:* `auth_admin_keep` on the helper actions.
  polkit keeps the authorization for "the same action identifier and
  subject", and pkexec's subject is the process that ran it, i.e.
  Proccoli. pkexec's manual asks that programs whose authorization is kept
  validate their arguments, and the helper validates every argument: fixed
  subcommands, four signals, PID > 1 and not itself, nice −20..19, existing
  CPUs, no free-form paths, no shell. `intel_gpu_top` can write files
  (`-o`), so its action keeps `auth_admin` and asks every time.
- *Root output, unprivileged parser:* the helper and `intel_gpu_top` send
  JSON to Proccoli, which runs as the user. Nothing flows from the user
  into root except validated helper arguments and `intel_gpu_top`'s fixed
  argv. The card name comes from `/sys` and must match `card\d+`.
- *Root processes outliving Proccoli:* Proccoli can't signal a root child,
  so `StreamReader.stop()` closes the pipe instead. The helper's own
  streams (`processes`, `gpu-top`) are Python, which turns the closed pipe
  into `BrokenPipeError`: `processes` exits, and `gpu-top` stops
  `intel_gpu_top` first (finding 9). Both happen within one interval, also
  if Proccoli crashes. Only the fallback for an old helper (`intel_gpu_top`
  run directly) can still outlive Proccoli. A warning in the log says so.
- *What admin views reveal:* elevated drive activity and GPU clients show
  other users' processes to this user. That's the purpose of those views,
  and it's behind the administrator password.
- *`gpu-elevate`:* off by default. When on, a password prompt appears at
  start-up without a click. That's the user's choice, and polkit's dialog
  names the action.

```mermaid
flowchart TD
    U[User clicks Kill on PID 4242] --> A[ProcessActions: os.kill]
    A -->|EPERM| T["read_start_time(4242) at click time"]
    T -->|gone| D[report done, no prompt]
    T -->|start 98765| H{helper_argv}
    H -->|installed, root-only| P["pkexec /usr/libexec/proccoli/proccoli-helper signal KILL 4242@98765"]
    H -->|source checkout| X[off unless PROCCOLI_DEV_HELPER=1, then python3 -I]
    P --> F["pidfd_open(4242)"]
    F --> C{"start time still 98765?"}
    C -->|no: PID reused| N[leave it alone, report gone]
    C -->|yes| S[pidfd_send_signal]
```

## 12. Open decisions

| # | Question | Default if not decided |
|---|---|---|
| 1 | ~~Licence~~ | **Decided:** 0BSD (§11) |
| 2 | Final app name and ID (Proccoli is a prototype name) | `io.github.mamadingleberry.Proccoli` until renamed |
| 3 | Should intel_gpu_top_gui keep living as its own app, or become a thin wrapper around Proccoli's `gpu.intel_gpu_top` package? | Copy the modules in first (Milestone 9); decide about sharing later |
| 4 | Battery page: Resources has one, but it isn't in the requested sidebar list | Build it last (Milestone 14), skip it on desktops |
| 5 | Switch from periodic rescans to GUdev for hotplug? | Rescans; revisit if the CPU cost shows up in profiling |
