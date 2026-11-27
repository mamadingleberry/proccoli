# Bug 11: Lightweight Mode's Processor and Memory pages are blank

Design note: [design/bugs/bug-11-lightweight-mode-s-processor-and-memory.md](../../design/bugs/bug-11-lightweight-mode-s-processor-and-memory.md)

*Fixed in Milestone 81.*

**Seen:** "why are the Processor and Memory tabs blank in lightweight
mode?"

**Cause:** since Idea 19 the window opens before the collector's devices
arrive, so the Processor and Memory start as placeholder pages. When a
device arrived, the window registered its lazy page and then removed the
placeholder, and removing a page forgets its lazy entry: a visit never
built the real page, and the empty stand-in stayed. Only devices with
placeholders were affected; before Idea 19 they existed when the window
opened.

**Fix:** remove the placeholder (or error page) first, then register the
new page.

| Step | Create / change | Test |
|---|---|---|
| B11.1 | `ui/window.py` (`_on_device_added`) | `test_ui_remote`: a Lightweight window on a collector builds the real Memory page when visited (fails without the fix) |
