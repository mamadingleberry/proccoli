# Milestone 4: Processor page

*✅ Done.*

*Goal: the first real device, from end to end.*

| # | Create | Test |
|---|---|---|
| 4.1 | `devices/cpu.py`: `CpuDiscoverer` (one CPU device, properties: model, logical/physical cores, sockets, max frequency, virtualization, architecture) | Fixture: properties for `alderlake-laptop` and a second fixture (AMD desktop, sockets=1) |
| 4.2 | `CpuMonitor.sample()`: totals and per-thread usage from `/proc/stat` deltas; frequency; uptime | Fixture pair (`stat.t0`, `stat.t1`) → known percentages; the first sample returns `None` usage |
| 4.3 | CPU temperature: hwmon lookup (`coretemp` Package id 0, `k10temp` Tctl, `zenpower`) | Fixtures for both vendors, and none present → `None` |
| 4.4 | `devices/manager.py`: `DeviceManager` with `Discoverer` registration and `device-added`; `Application` owns it and `Ticker` drives it | Unit: fake discoverer → signal emitted once per device |
| 4.5 | `ui/pages/cpu.py`: `CpuPage`. Usage group with total `GraphBox`, or a FlowBox of small per-thread graphs (*Show Usages of Logical CPUs* switch, saved in settings); Sensors; Properties | Smoke with a canned `CpuSnapshot`; UI screenshot at both switch states |
| 4.6 | Sidebar item: "Processor", the CPU model as description, usage % | Manual: matches `top` within a few % |
| 4.7 | *Normalize Processor Usage* setting (used by Processes later; stored now) | Settings unit test |

**Done:** the Processor page and sidebar item show live, correct CPU data.
