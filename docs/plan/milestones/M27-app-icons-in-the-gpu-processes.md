# Milestone 27: App icons in the GPU Processes tab

*✅ Done.*

| Step | Create / change | Test |
|---|---|---|
| 27.1 | `processes/apps.py`: `AppIconLookup(sysroot, grouper)`: `icon_for_pid(pid)` from `/proc/<pid>/cgroup` (cached per PID) | Unit on fixtures |
| 27.2 | `DetailBackend.create_views(controller, services)` with `DetailServices(settings, app_icon)`, built by the page factory from the context (DI instead of more parameters) | Unit/UI |
| 27.3 | Intel `ClientsView`: an icon column like Apps and Processes (app icon or the puzzle piece) | UI test |
