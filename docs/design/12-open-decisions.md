# 12. Open decisions

Questions about the whole design that aren't settled. A settled one keeps
its row with the answer; questions about one feature live in that
feature's file (and in DESIGN.md's *Requires Human Input* lists until
asked).

| # | Question | Now |
|---|---|---|
| 1 | Licence | **Decided:** 0BSD ([§11](11-cross-cutting-concerns.md)) |
| 2 | Final app name and ID | **Decided:** Proccoli, `io.github.mamadingleberry.Proccoli` (renamed in v0.1.0) |
| 3 | Should intel_gpu_top_gui stay its own app, or wrap Proccoli's `gpu.intel_gpu_top`? | **Decided for Proccoli:** its modules were copied in, then moved onto Proccoli's shared charts (v0.3.0); intel_gpu_top_gui itself is left as it is |
| 4 | A battery page? | **Decided:** built (v0.1.0); desktops without a battery don't show one |
| 5 | Periodic rescans or GUdev for hotplug? | Open: rescans every few seconds in the recorder; revisit if their cost shows in profiling |
| 6 | How do several machines' recorders reach one window or Web UI (discovery, authentication, encryption)? | Open: brainstormed in [Feature 17](features/feature-17-the-web-gui-for-machines-on.md) |
| 7 | A recorder per user, or one for the whole machine? | Per user today (with recording from boot offered); a machine-wide one is [Feature 25](features/feature-25-a-recorder-for-the-whole-machine.md), with its questions there |
