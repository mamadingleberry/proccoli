# 1. Goals and non-goals

**Goals**

1. Mirror the Resources user experience: sidebar of resources on the left,
   detail page on the right, Apps and Processes tables, a Preferences dialog,
   and the same page structure (Usage, Sensors and Properties groups).
2. **GPU carve-out:** the GPU page is chosen per GPU, at runtime, by a
   pluggable *GPU backend*. It can be switched while the app is running (for
   example after authenticating, or by choice in Preferences).
3. The first detailed backend is `intel_gpu_top`, reusing what
   intel_gpu_top_gui already does well.
4. Incremental: every milestone in PLAN.md ends with a runnable, tested app.
5. Testable without real hardware. Every data source reads from an injectable
   filesystem root or command runner, so tests use fixture files.

**Non-goals (for now)**

- An AMD detailed backend. The interfaces are designed for it, but it isn't
  built yet. (NVIDIA's arrived in M55, [§7.4](07.4-backend-selection.md).)
- NPU pages. Resources has them, but they are out of scope.
- Copying Resources' code, icons or name. Proccoli re-implements the UX from
  scratch, because Resources is GPL and Proccoli is 0BSD (see [§11](11-cross-cutting-concerns.md), Licensing).
