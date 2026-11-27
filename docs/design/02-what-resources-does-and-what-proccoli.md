# 2. What Resources does, and what Proccoli changes

## 2.1 Resources' structure (from the Ubuntu 26.04 package, v1.10.2)

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
            │                 Proccoli: the logo (its main menu) instead, M52, M61;
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

- *General:* unit prefix, network bits, temperature unit, update interval,
  graph grids, graph data points, sidebar details, descriptions and meter
  type, normalize CPU usage
- *Apps:* column toggles
- *Processes:* niceness option and column toggles
- *Devices:* virtual drives, virtual network interfaces

It also stores the window size, sort columns and last viewed page.
(Proccoli doesn't keep the last page: it always opens on the Overview.)

**Privileged work** goes through helper executables in
`/usr/libexec/resources/`:

- `resources-processes` streams process data, run via `pkexec` to see all
  users' processes
- `resources-kill` and `resources-adjust` signal or renice other users'
  processes

All three are authorised by a polkit policy.

## 2.2 The GPU gap

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
