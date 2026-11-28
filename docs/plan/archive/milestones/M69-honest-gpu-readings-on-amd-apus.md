# Milestone 69: Honest GPU readings on AMD APUs; README version

*✅ Done.* Fixes Bugs 2–5: an APU's package power was shown as the GPU's, its graphics memory as the carve-out alone, AMD process memory counted twice, and the README still installed 0.3.0. Checked on a Ryzen 3 4300U (Radeon Vega 6)

Fixes Bugs 2, 3, 4 and 5 (kept below as the record). Found by comparing
the generic GPU page with amdgpu's own files on a Ryzen 3 4300U (Radeon
Vega 6, Renoir APU), the first AMD GPU Proccoli ran on.

| Step | Create / change | Test |
|---|---|---|
| 69.1 | `core/sysroot.py`: `read_bytes` (binary attributes); `tests/helpers.FakeRoot.write_bytes`; fixture `tests/fixtures/renoir-apu` (this APU's amdgpu files and two `gpu_metrics` samples) | – |
| 69.2 | `gpu/info.py`: `amd_is_apu`: `gpu_metrics` format revision 2, the carve-out size only without it | Unit: a 4 GiB UMA APU is integrated; a revision-1 table isn't; both fallbacks |
| 69.3 | `gpu/backend.py`: `GpuSummary.gtt_used/gtt_total`, `shared_memory`, `power_is_package`, `memory_used/total/usage` (replaces `vram_usage`); `gpu/generic_drm.py` sets them for an AMD APU; `controller.py` records `gtt-used/-total` | Unit (Bugs 2, 3) on the fixture: memory includes GTT (under 20 % against 85 % for the carve-out), power is the package's; a discrete GPU unchanged |
| 69.4 | `gpu/fdinfo.py`: each memory region once, `drm-total-*` first (Bug 4); `FdinfoReader(shared_memory=)` counts GTT | Unit with this machine's amdgpu fdinfo: 415 160 KiB, not twice; GTT added on an APU; an old kernel's `drm-memory-*` alone still counts. Fails on the old code |
| 69.5 | `ui/pages/gpu.py`: *Graphics Memory* and *Processor Package Power* titles (`memory_title`, `power_title`); `ui/summaries.py` facts from `memory_used/total` | UI on the fixture: the titles, "of 8.9 GB", "12.0 W"; a discrete GPU keeps *Video Memory* and *Power Usage* |
| 69.6 | README: `proccoli_0.4.0_all.deb` (Bug 5) | `test_meta`: every package name in the README is `__version__` |
| 69.7 | [DESIGN §7.1](../../../design/07.1-roles-summary-and-detail-sources.md), [Bug 2's design](../../../design/bugs/bug-02-an-apu-s-package-power-shown.md)–14.5 | – |

**Found while doing 69:** Renoir's hwmon `power1` reads whole watts (12,
15, 34), so the earlier guess that 15.000 W "looks like a limit" was
wrong: it's the package's power, rounded by the firmware.
