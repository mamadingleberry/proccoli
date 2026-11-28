# Milestone 79: The window reads from the collector (Feature 19b)

*✅ Done.* The window's devices are `RemoteDeviceManager`'s, fed by `proccoli-metrics` over D-Bus; its history read-only; the collector on for every user and started on demand (D-Bus activation); a banner with *Try Again* when readings stop. Apps and Processes stay in the window. Intel GPU *Details* wait for 19c

The second of Feature 19's parts. Open question 1 answered: Apps,
Processes and the Overview's busiest apps and processes stay in the
window.

| Step | Create / change | Test |
|---|---|---|
| 79.1 | Collector side: the codec carries `GpuInfo`, `GpuVendor` and `MemoryModule`; `Devices()` adds the sort name, the processor's thread names and sensor, a GPU's info, plan and Details source, memory modules, a failed device's message and details; `Retry(id)`; readings carry the source note; the collector's GPU controllers follow `gpu-details-disabled`; `Monitor.sort_name()` replaces `ui/summaries`' per-kind code | Unit: a GPU's info and plan over the bus; turning details off and on reaches the collector's controller |
| 79.2 | `devices/remote.py`: `RemoteDeviceManager`, `RemoteMonitor`, `RemoteGpuController`, `RemoteDetailBackend`, `FailedMonitor` for failed devices; name watching with `AUTO_START`; connected once subscribed | Unit on a private bus: the same devices, info, sort names and properties; readings into history on the window's clock; a GPU with its Details sample and history; details off through the collector; a device removed; a failed device and *Try Again*; the collector going away and coming back; the time range reaching remote histories |
| 79.3 | `build_context(remote=True)` for the application (local devices for `--demo` and tests; `pci.ids` not parsed); the window's `HistoryStore(read_only=True)`; the collector imports Milestone 58's files instead; the window's banner and *Try Again* | UI: the window's pages from a collector, the GPU's AMD Details tab built from its readings, the banner when it goes and gone when it's back; unit: the window's store never writes, even with the lock free |
| 79.4 | Packaging: the D-Bus service file, the `user-preset`, the metrics package's `postinst` (enable for every user, restart for those logged in) and `prerm` (disable), `install.sh` the same | `test_packaging`: the files and scripts |

**Deviations from the design, and why:**
- **One banner for the window, not one per page:** it's the same message
  everywhere; a banner above the pages says it once.
- **Intel GPU *Details* aren't shown yet:** their views need
  `intel_gpu_top`'s own process (clients, labels), and the collector
  can't ask for the password it needs: open question 2, in 19c.
- **The existing UI tests keep local devices:** `make_context` builds
  them as before (the window's code paths are the same); new tests build
  the window on a collector over a private bus (`test_ui_remote`).
- ***Record in the Background*** stays until 19c: turning it off now
  stops the window's readings too (the banner says so).

*Found after 79 (Bug 8, fixed in it):* Lightweight Mode's Overview
charted remote devices before their first reading, whose lines didn't
exist yet: every draw raised, and Ubuntu's crash reporter froze the
window for ~20 s. Lines now come with `Devices()`.

*Found while doing 79:*
- **A window counted as connected before the collector had it down for
  readings,** so the first updates went nowhere; it's connected once
  `Subscribe` returns.
- **Sort names lived in the UI** (`sort_name_for` read each monitor's
  interface or block name); they're `Monitor.sort_name()` now, so the
  collector can send them.
- **The window's GPU switch acted on its own controller;** with the
  collector reading, the collector's controller follows the setting.
