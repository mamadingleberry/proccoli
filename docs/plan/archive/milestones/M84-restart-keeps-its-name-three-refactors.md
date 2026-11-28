# Milestone 84: Restart keeps its name; three refactors

*✅ Done.* *Restart Now* runs the launcher itself, so the window isn't listed as `python3` (Bug 14); `Connections` in 17 modules, a `DeviceSource` base for both device managers, monitors that describe themselves (Feature 21: R1, R2, R3)

Asked for after M83: "let's do python3 process fix, then refactor signal,
device managers, and device descriptions. keep the Big Classes in the
Feature for now".

| Step | Create / change | Test |
|---|---|---|
| 84.1 | Bug 14: `core/system.restart_command(argv0, interpreter, runnable)` → `(program, argv)`; `System.restart_self` runs the launcher itself when it's executable | Unit: the cases; a real launcher restarted the same way keeps its process name (`python3` without the fix) |
| 84.2 | R1: `core/connections.Connections` (`connect`, `watch`, `add`, `adopt`, `disconnect_all`) in place of the handler lists in `metrics_service`, `window`, `sidebar_visibility`, `graph_toolbar`, `gpu/controller`, the AMD, Intel and NVIDIA backends, `chart_settings`, `devices/remote`, `page`, `preferences` (both dialogs), `overview`, `history_store` (one per followed device), `applog` (both), `theme`, `pages/gpu` | Unit `test_connections`; the existing shutdown and leak tests |
| 84.3 | R2: `devices/source.DeviceSource`: signals, `monitors`, `monitor`, `connected`, `status`, `readings`, `remote`, `reconnect`, and `start`/`stop`/`refresh`/`rescan`/`retry` for each kind; `DeviceManager` and `RemoteDeviceManager` subclass it. `app.py`, `window.py` and `metrics_service` use `devices.remote` and `devices.retry` instead of `hasattr`/`getattr` | Unit `test_device_source`: both are sources; local always connected; status announced once; no `hasattr(…devices…)` anywhere |
| 84.4 | R3: `Monitor.describe(encode)` and `Monitor.reading(encode)`, extended by `FailedMonitor`, `CpuMonitor`, `MemoryMonitor` and `GpuController`; `metrics_service.device_info`/`reading` only ask. The wire format is unchanged | Unit: common fields; each kind's fields round-trip through `monitor_for`; no reading before the first sample; no `hasattr`/`getattr` in the service |
| 84.5 | Light refactoring: three docstrings broken by the earlier reference cleanup (a line holding only "." or ":") mended | `make test` |

**Kept for later (by request):** the big classes (R4–R7, R9, R10). R11
is covered by `Connections.watch`; R8 and R12 remain.
