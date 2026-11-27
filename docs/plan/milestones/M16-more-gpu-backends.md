# Milestone 16+: More GPU backends (future)

*🟡 Started.* AMD built as Milestone 70 (amdgpu's own sysfs files, not `amdgpu_top`)

The framework from Milestone 8 means each of these is a self-contained
addition: **one new package under `gpu/` + one `register()` line + tests**.

| Backend | Data source | Detail tabs |
|---|---|---|
| `NvidiaSmiBackend` (DETAIL) | `nvidia-smi --query-gpu=… --format=csv -lms`, `nvidia-smi pmon` / `--query-compute-apps` for processes (or NVML via ctypes) | SM, memory controller, encoder, decoder, VRAM, clocks (graphics, SM, memory, video), power vs limit, temperature, fan, PCIe throughput, P-state |
| `AmdGpuTopBackend` (DETAIL) | `amdgpu_top --json` stream (or sysfs + `gpu_metrics` binary blob) | GFX, compute, VCN, SDMA rings; GTT vs VRAM; sclk, mclk, fclk; per-sensor temperatures (edge, junction, mem); power vs cap. *Built as Milestone 70 from sysfs + `gpu_metrics` (`AmdgpuBackend`), without `amdgpu_top`* |

**Checklist for adding a backend:** fixtures for its tool output → `probe()`
matrix tests → `summary()` / `process_usage()` tests → `TABS` and
`create_views()` smoke test and screenshots → no changes outside
`gpu/<vendor>/` except the registration line.

Milestones 17–22 are appearance work requested after Milestone 15. They're
done in order, before any of 16. Each one updates DESIGN.md, keeps every
new service injectable (constructor arguments, no module-level state) and
adds unit tests for its pure logic plus headless UI tests.
