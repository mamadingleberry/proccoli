# Milestone 9: intel_gpu_top backend + detailed page

*✅ Done.*

*Goal: the reason this project exists.*

| # | Create | Test |
|---|---|---|
| 9.1 | `core/jsonstream.py` + `core/runner.py` + `StreamReader`: port `JsonStreamParser` and `Sampler` from intel_gpu_top_gui and generalise them (argv, optional pkexec, `record` and `exited` signals) | Port `test_sampler.py` (chunked JSON, a broken stream, exit codes) |
| 9.2 | `gpu/intel_gpu_top/backend.py`: `IntelGpuTopBackend.probe()` (vendor, driver, binary present, perf access → `needs_elevation`) | Unit: probe matrix (no binary / non-Intel / paranoid=2 / cap_perfmon set) |
| 9.3 | Backend run loop: start `intel_gpu_top -J -s <interval> -d <device filter for this card>`; keep its own `History` (ported `flatten_sample`); `summary()` = max engine busy as usage, Video as encode/decode, actual frequency, GPU power | Unit: feed recorded JSON → summary values |
| 9.4 | `process_usage()` from the `clients` records (pid → per-engine-class busy; Render/3D+Compute → `usage`, Video → `encode`/`decode`) | Unit with a recorded clients sample |
| 9.5 | *(Superseded by the GPU tabs refactor; see Progress.)* `gpu/intel_gpu_top/page.py`: `IntelGpuTopPage(GpuPage)`. Port `GraphSection`, `GraphGrid`, `AxisGroup` and `LegendItem` from intel_gpu_top_gui; add a Properties group (shared helper with the generic page) and an "Engines by Process" expander with the ported `ClientsView` | Port `test_grid.py` and `test_graph_helpers.py`. UI screenshots at 1280×800 and 700×600. |
| 9.6 | Header widgets: pause, *Export as CSV…*, and the backend menu ("Detailed (intel_gpu_top)" / "Summary") | Smoke: the menu lists every candidate from the registry |
| 9.7 | *(Superseded by the GPU tabs refactor; see Progress.)* Fallback flow ([DESIGN §7.1](../../design/07.1-roles-summary-and-detail-sources.md) state diagram): permission failure → generic page + banner "Show Detailed Statistics" → `swap_backend(elevate=True)` via pkexec; cancelled → toast; unexpected exit → generic + banner | Unit on `GpuController` with a fake runner covering every state transition |
| 9.8 | *(Superseded by the GPU tabs refactor; see Progress.)* Settings: `gpu-backend` per PCI slot, `gpu-elevate`, optional `intel-gpu-top-interval` | Settings tests; restart restores the chosen backend |
| 9.9 | `--demo` gains a synthetic intel_gpu_top stream (port `_run_demo`) | UI screenshot test in demo mode |

**Done:** on this laptop the GPU entry opens the detailed intel_gpu_top
page, or the summary page with an authenticate banner if perf access is
blocked. The menu switches between them without restarting, and the sidebar
entry never changes.
