# Milestone 55: GPU detection, error pages, NVIDIA, per-CPU chart, Overview at launch, UTC log

*✅ Done.* NVIDIA checked on a real RTX 5060 Laptop GPU (Wayland: nvidia-smi); nvidia-settings' X11 path only against its documented format

Six requests in one round. The NVIDIA work was checked on a hybrid laptop
(Intel Graphics + RTX 5060 Laptop GPU, driver 580, GNOME on Wayland).

| Step | Create / change | Test |
|---|---|---|
| 55.1 | `gpu/detect.py` (pure): `plan_gpu(gpu, registry, deps)` → `GpuPlan`: every backend's probe (`GpuBackendRegistry.probe_all`, unsupported ones too), the chosen summary and detail sources, `panel()` ("overview only", "overview + NVIDIA tabs", "error page"), `detail_text()`, `explain()`. `GpuController` uses it (logged at INFO), raises with the explanation when nothing can serve the GPU; the GPU page's *Detailed Statistics* property shows `detail_text()` | Unit: this machine's two GPUs, explanation lines, nothing usable → error with the plan; UI: the property |
| 55.2 | `devices.base.FailedMonitor`; `DeviceManager._build`: a monitor that can't be built **or started** becomes a `FailedMonitor` (message + traceback), so the device keeps its sidebar entry; `DeviceManager.retry(id)` | Unit: both failure points, half-started monitor stopped, retry |
| 55.3 | `ui/pages/error.py`: `ErrorPage` (error status page, message, *Technical Details* expander with *Copy Details*, *Try Again* → `retry` signal). `PageFactory.create` returns it for a `FailedMonitor` and when a page builder raises. `MainWindow._on_retry`: `devices.retry` (stays on the page) or rebuild the page. The GPU tabs' FAILED state uses the error icon | UI: factory both ways, retry fails then succeeds, page stays selected |
| 55.4 | `gpu/nvidia/` (DETAIL backend, registered between Intel and generic): `query.py` (pure argv builders and parsers for nvidia-settings' normal and terse output and nvidia-smi's CSV; `NvidiaSample`, `NvidiaError(unreachable)`), `backend.py` (`NvidiaBackend`: polls once per refresh with `System.run_async`, never two at once; nvidia-settings first: find `[gpu:N]` by PCI slot, then read it; falls back to nvidia-smi when nvidia-settings is missing or can't reach the GPU; fails with the reason when neither can, or after 3 bad readings in a row once running; answers after a stop are dropped), `views.py` (Details tab: caption with GPU, driver, tool and why; graphs for utilisation, video engines, VRAM, clocks, temperature, power, fan; legends; unreported measures hidden) | Unit on real fixtures (nvidia-smi CSV, nvidia-settings' Wayland output and error) and documented X11 output; probe matrix; fallback; failures; UI: both views |
| 55.5 | `GpuController.process_usage`: the detail source's figures only when it has some (NVIDIA's tools give none cheaply), otherwise the summary source's | Unit |
| 55.6 | Per-CPU usage is one chart with a line per logical CPU (`Graph.set_fill(False)`, `set_distinct_colors`, `set_series_shown`) and `ui/widgets/legend.py` (`Legend`, `LegendItem`: swatch, name, value; a toggle that hides its line). `devices.cpu.busiest_thread` for the info line. Replaces the grid of small graphs (`ThreadCell`, removed) | Unit: `busiest_thread`; UI: series, distinct colors, legend, toggles, fills the page |
| 55.7 | Always open on the Overview: `MainWindow.show_overview()` at start, and from `Application.do_activate` when launched again; schema key `last-viewed-page` removed | UI: reopens on Overview after another page, second launch, no Overview → first entry |
| 55.8 | Log: `UtcFormatter` (ISO 8601 UTC, milliseconds, `Z`); `log-level` default `debug` (*Everything (Debug)*) | Unit: fixed instant, independent of `TZ`; default writes debug lines |
| 55.9 | Screenshot scenes `real-gpu-last-details`, `real-gpu-last-overview` (`_pick: last`) | Screenshots on this machine |

**Done when:** an NVIDIA GPU shows live figures and a Details tab, a device
that can't be read shows an error page with *Try Again*, the Processor page
draws every core in one chart, Proccoli always opens on the Overview, and
the log is in UTC at debug level.

*Found while doing 55:*
- In a Wayland session nvidia-settings answers the PCI attributes (it
  lists `[gpu:0]`) and even temperature and memory, but not utilisation
  or clocks: those need NV-CONTROL, an X11 extension. A query mixing them
  fails as a whole (exit 1), so the backend falls back to nvidia-smi.
  On Ubuntu's default session, then, the figures come from nvidia-smi.
- Before 55, the NVIDIA GPU's sidebar entry showed nothing: the generic
  sysfs source has no usage for NVIDIA's driver.
- pci.ids has no name for the RTX 5060 Laptop GPU yet, so the sidebar
  calls it "NVIDIA GPU"; the Details caption has nvidia-smi's name.
- Debug logging is light: about 1 KB in 20 s, mostly at start-up, so the
  1 MiB default cap still holds days of history.
- Per-process NVIDIA use isn't shown: `nvidia-smi pmon` takes about a
  second per sample. A later step could read NVIDIA's DRM fdinfo, if the
  driver fills it.
