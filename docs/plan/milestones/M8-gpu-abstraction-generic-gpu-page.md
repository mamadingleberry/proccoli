# Milestone 8: GPU abstraction + generic GPU page

*✅ Done.*

*Goal: the carve-out's framework, with the Resources-level page as the first
backend. After this milestone every GPU has a page.*

| # | Create | Test |
|---|---|---|
| 8.1 | `gpu/info.py`: `GpuVendor` and `GpuInfo.discover(sysroot)` from `/sys/class/drm/card*/device/{vendor,device,uevent}` (driver, PCI slot), render node, integrated heuristic (Intel without `lmem`, or boot_vga + no VRAM) | Fixtures: Intel Alder Lake (this laptop), and hand-made AMD and NVIDIA trees |
| 8.2 | `gpu/backend.py`: `GpuBackend` ABC, `Probe`, `SupportLevel`, `Capability`, `GpuSummary`, `GpuProcessUsage` | Unit: a `FakeBackend` satisfies the ABC |
| 8.3 | *(Superseded by the GPU tabs refactor; see Progress.)* `gpu/registry.py`: `GpuBackendRegistry` (`register`, `candidates`, `create`, priority and tie order) | Unit: preference order, `UNSUPPORTED` filtered out, the user override wins only when supported |
| 8.4 | `gpu/fdinfo.py`: `FdinfoReader`. Scans `/proc/*/fdinfo/*` for `drm-engine-*`, `drm-memory-*` and `drm-client-id` (deduplicated per client), and turns deltas into per-PID usage. | Fixtures with i915 and amdgpu fdinfo samples; two clients in one PID; duplicate fds |
| 8.5 | `gpu/generic_drm.py`: `GenericDrmBackend`. Summary from sysfs (frequency: `gt_cur_freq_mhz` / `pp_dpm_sclk`; busy: `gpu_busy_percent` or the fdinfo total; VRAM: `mem_info_vram_*`; hwmon power and temperature), and `process_usage()` from fdinfo | Fixture-driven; the Intel iGPU yields usage and frequency, with VRAM and temperature `None` |
| 8.6 | *(Superseded by the GPU tabs refactor; see Progress.)* `gpu/controller.py`: `GpuController` (a `Monitor`): chooses a backend, `refresh()`, `swap_backend()`, `backend-changed`, history for the sidebar | Unit with fake backends: choose, swap, a failing backend falls back |
| 8.7 | *(Superseded by the GPU tabs refactor; see Progress.)* `ui/pages/gpu_generic.py`: `GpuPage` base (header backend menu, `set_banner`) and `GenericGpuPage` (Usage: usage, encode/decode `DoubleGraphBox`, VRAM, frequency, VRAM frequency, power rows; Sensors: temperature; Properties: manufacturer, PCI slot, driver, max power cap, link). Rows the backend can't fill are hidden. | Smoke with a canned summary |
| 8.8 | *(Superseded by the GPU tabs refactor; see Progress.)* Window: GPU devices create their page through `controller.backend.create_page()` and handle `backend-changed` with `replace_page` | UI test: swap between two fake backends and check the stack child is replaced while the sidebar row stays selected |

**Done:** this laptop shows a "GPU" sidebar entry ("Intel UHD Graphics")
with a Resources-style page. A test backend can be swapped in while the app
runs.
