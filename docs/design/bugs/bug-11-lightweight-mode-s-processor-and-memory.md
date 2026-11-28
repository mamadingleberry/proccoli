# Bug 11: Lightweight Mode's Processor and Memory pages were blank

Plan: [plan/bugs/bug-11-lightweight-mode-s-processor-and-memory.md](../../plan/bugs/bug-11-lightweight-mode-s-processor-and-memory.md)


*[PLAN.md, Bug 11](../../plan/bugs/bug-11-lightweight-mode-s-processor-and-memory.md). Fixed in v0.5.0.* With a collector the window opens before
its devices arrive, so the Processor and Memory start as placeholders.
`MainWindow._on_device_added` registered the lazy page, then removed the
placeholder, whose removal dropped that lazy entry; it now removes the
old page first.
