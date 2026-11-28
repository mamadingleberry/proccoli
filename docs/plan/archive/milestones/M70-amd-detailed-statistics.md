# Milestone 70: AMD detailed statistics

*✅ Done.* A *Details* tab from amdgpu's own files (`gpu_metrics`, clock tables, hwmon, fdinfo): no tool, no password. The NVIDIA tab's chart code shared as `DetailChartsView`. A second demo GPU (AMD). Checked on the same Vega 6

Milestone 16's AMD backend, built from amdgpu's own sysfs files instead
of `amdgpu_top`: they're readable by every user, need nothing installed,
and `amdgpu_top` isn't in the Ubuntu or Debian archives. Reuses the chart
classes (`ChartCard`, `ChartGridView`, `ChartSettings`) through the NVIDIA
tab's code, moved to a shared `DetailChartsView`.

| Step | Create / change | Test |
|---|---|---|
| 70.1 | `gpu/amdgpu/metrics.py`: `parse_gpu_metrics` (APU layout v2.x), `socket_power_w`, `throttle_reasons` | Unit on the idle and load samples: temperatures, the 4 cores in use, 15 W / 32 W, cores and SoC power, clocks, "Fast power limit" under load; v2.0's whole degrees; revision 1, truncated and empty tables give None |
| 70.2 | `gpu/amdgpu/sensors.py`: `AmdgpuSample`, `read_sample`, `engine_classes`, `HISTORY_UNITS`, `to_summary` | Unit: the APU fixture; a discrete GPU from hwmon (junction, memory temperature, board power and cap, fan, voltage); engine folding |
| 70.3 | `gpu/amdgpu/backend.py`: `AmdgpuBackend` (probe, refresh, history, processes, history database), `DemoAmdgpuBackend`; `registry.standard_registry` registers it before the generic source | Unit: probe matrix (APU, NVIDIA, `radeon`, no usage file); readings, history, per-engine use and GTT per process; the time range followed until stopped; this APU's plan; the controller runs it without a password |
| 70.4 | `ui/widgets/detail_charts.py`: `DetailChartsView` (from `NvidiaDetailsView`); `gpu/nvidia/views.py` and `gpu/amdgpu/views.py` subclass it | UI: the NVIDIA tests unchanged; the AMD cards and lines on the fixture (no fan, no junction), "Package 15.0 W", "limited by fast power limit", memory "of 8.9 GB" |
| 70.5 | `devices/demo.py`: a second demo GPU, *Demo AMD Radeon Graphics* (`gpu-demo-amd`); `tests/ui/shoot.py`: `demo-amd-details`, `demo-amd-overview` | Demo GPUs never read the system; sidebar order; Preferences lists both |
| 70.6 | README *GPU*, *Graphics details*; [DESIGN §4.1](../../../design/04-architecture-overview.md), [§7](../../../design/07-the-gpu-carve-out.md), [§7.5](../../../design/07.5-amd.md) | – |

**Done:** on this laptop the GPU page has *Overview* and *Details* tabs;
Details shows utilization, engines, memory, clocks, temperatures (GPU,
SoC, processor), power (package, cores, SoC) and voltages, with no
password.

**Found while doing 70:**

- Renoir's firmware breaks two of the kernel's documented units in
  `gpu_metrics`: the package power is in watts (not milliwatts) and the
  memory clock is a level number (6). Both are handled and tested.
- Its `average_gfx_activity` is in hundredths of a percent (611 = 6.11 %,
  beside `gpu_busy_percent` 6). The tab uses `gpu_busy_percent`, which
  every amdgpu device has, rather than guess the unit per chip.
- `ChartGridView` already has a `caption` label, so the subclass hook is
  `caption_line()`.
- The first screenshot of the real Details tab showed the right column
  clipped: the *Engines* card appears with the second reading, and that
  frame was mid-layout. A second shot was fine; not seen in the app.

**Deviations:** no *Processes* tab yet (Intel has one); the process
columns already show each app's graphics use and memory from fdinfo. The
summary and detail sources each read fdinfo while the Details tab runs.
