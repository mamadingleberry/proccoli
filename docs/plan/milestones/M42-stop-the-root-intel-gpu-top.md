# Milestone 42: Stop the root intel_gpu_top with Proccoli

*✅ Done.* Found during M41: it ignores SIGPIPE. Now run by the helper's `gpu-top`, which stops it; needs the reinstalled helper (protocol 3)

Found while checking M41's screenshots: four root `intel_gpu_top`
processes with no Proccoli, up to 12 hours old. It ignores SIGPIPE, so
closing its pipe (M40's assumption) doesn't stop it, and Proccoli can't
signal root processes. Details: [DESIGN.md §11.1](../../design/11-cross-cutting-concerns.md), finding 9.

| Step | Create / change | Test |
|---|---|---|
| 42.1 | Helper `gpu-top MS cardN`: validated (100–10000 ms, `card` + ASCII digits, nothing else), fixed `intel_gpu_top -J -s MS -d drm:/dev/dri/cardN`, `relay()` copies output and terminates (then kills) the child when the reader goes away; `PROTOCOL = 3` | Unit: bad arguments refused before anything runs; a fake `intel_gpu_top` that ignores SIGPIPE is gone after the reader leaves, one that also ignores SIGTERM is killed; fixed argv; missing binary |
| 42.2 | Polkit action `….gpu-top` (`auth_admin_keep`); `….intel-gpu-top` kept for the fallback | Packaging test: every helper subcommand has an action |
| 42.3 | `PrivilegedHelper.gpu_top_argv` (None below protocol 3); `GpuDeps.helper`; `GpuDiscoverer(…, helper)`; `standard_discoverers(…, helper)` | Unit |
| 42.4 | `IntelGpuTopBackend.start(elevate=True)` goes through the helper; with an older helper it runs `intel_gpu_top` directly and logs a warning | Unit |
| 42.5 | [DESIGN §11.1](../../design/11-cross-cutting-concerns.md) corrected (finding 9, the root-processes note, the sequence diagram) | — |

**Done when:** stopping detailed statistics, changing their interval or
quitting Proccoli leaves no root `intel_gpu_top` behind (with the
helper reinstalled).
