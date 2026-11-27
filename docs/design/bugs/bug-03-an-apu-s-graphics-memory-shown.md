# Bug 3: An APU's graphics memory shown as the carve-out alone

Plan: [plan/bugs/bug-03-an-amd-apu-s-graphics-memory.md](../../plan/bugs/bug-03-an-amd-apu-s-graphics-memory.md)


*[PLAN.md, Bug 3](../../plan/bugs/bug-03-an-amd-apu-s-graphics-memory.md). Fixed in Milestone 69.* An APU's `mem_info_vram_*` is
the small carve-out the firmware reserves (1 GiB here, 85 % used at
idle); the GPU uses GTT (system memory it maps, 7.3 GiB here) as much.
The Overview tab, the sidebar's facts and each process's *Video Memory*
counted only the carve-out. `GpuInfo.integrated` also guessed an APU from
the carve-out's size (under 2 GiB), so a BIOS with a larger UMA setting
made an APU look discrete. **Fix:** `GpuSummary.gtt_*`,
`shared_memory` and `memory_used/total/usage`; the APU is recognised by
`gpu_metrics`' format revision; fdinfo counts GTT for an APU's clients.
