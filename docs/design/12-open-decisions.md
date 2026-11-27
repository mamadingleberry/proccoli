# 12. Open decisions

| # | Question | Default if not decided |
|---|---|---|
| 1 | ~~Licence~~ | **Decided:** 0BSD ([§11](11-cross-cutting-concerns.md)) |
| 2 | Final app name and ID (Proccoli is a prototype name) | `io.github.mamadingleberry.Proccoli` until renamed |
| 3 | Should intel_gpu_top_gui keep living as its own app, or become a thin wrapper around Proccoli's `gpu.intel_gpu_top` package? | Copy the modules in first (Milestone 9); decide about sharing later |
| 4 | Battery page: Resources has one, but it isn't in the requested sidebar list | Build it last (Milestone 14), skip it on desktops |
| 5 | Switch from periodic rescans to GUdev for hotplug? | Rescans; revisit if the CPU cost shows up in profiling |
