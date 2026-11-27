# Bug 3: An AMD APU's graphics memory is the carve-out alone

Design note: [design/bugs/bug-03-an-apu-s-graphics-memory-shown.md](../../design/bugs/bug-03-an-apu-s-graphics-memory-shown.md)

*Fixed in Milestone 69.*

**Seen:** the Vega 6's *Video Memory* read 85 % used at idle: 0.9 of
1 GiB. The GPU had 7.3 GiB of GTT besides, 2 % used.

**Cause:** an APU's `mem_info_vram_*` is the carve-out the firmware
reserves; the GPU maps system memory (GTT, `mem_info_gtt_*`) as much.
Only VRAM was read, on the Overview tab, the sidebar's facts and each
process's *Video Memory*. And an APU was recognised only by a carve-out
under 2 GiB, so a BIOS with a larger UMA setting made it look discrete.

**Fix:** `GpuSummary` gains GTT, `shared_memory` and
`memory_used/total/usage`; an APU's graphics memory is both together,
named *Graphics Memory*. fdinfo counts an APU's clients' GTT. The APU
is recognised by `gpu_metrics`' format revision (2).

| Step | Create / change | Test |
|---|---|---|
| B3.1 | `GpuSummary` fields; `generic_drm`; `controller` records GTT | Unit on the fixture |
| B3.2 | `info.amd_is_apu` | Unit: UMA 4 GiB APU, discrete revision 1, both fallbacks |
| B3.3 | `FdinfoReader(shared_memory=True)` | Unit: GTT added only on an APU |
| B3.4 | `GpuPage`: `memory_title`; `summaries`: facts | UI on the fixture |
