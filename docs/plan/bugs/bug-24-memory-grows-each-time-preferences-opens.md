# Bug 24: Memory grows each time Preferences opens

Design note: [design/bugs/bug-24-memory-grows-each-time-preferences-opens.md](../../design/bugs/bug-24-memory-grows-each-time-preferences-opens.md)

*Open; partly explained.*

**Seen:** "There still appears to be a memory leak with some of the
Preferences menus" (Requires Human Input), then "it appears to leak
memory whenever the dialog window pops up".

**Found so far (2026-11-28):**
- Opening one Preferences dialog costs about 62 settings handlers and
  ~9–13 MiB (every page, row and swatch is built at once).
- Stacked dialogs ([Bug 23](bug-23-preferences-and-other-dialogs-stack.md))
  multiplied that with every press; fixed.
- When a dialog's `closed` signal fires, every settings handler is let
  go (`OneDialogEachTest`). Whether the dialog's widgets and memory are
  then freed couldn't be measured: on the headless display (Broadway with
  no browser attached) no `Adw.Dialog` ever finishes closing, not even an
  empty one, so `closed` never fires there; no virtual X or Wayland
  server is installed.

**Next:** run the probe (open and close Preferences 30 times, then count
live dialogs, settings handlers and memory) once on a real desktop. If
memory still climbs after real closes: find what keeps a closed dialog
(its swatch factories, the sidebar's entry pages, GPU rows) and drop it
on `closed`; consider building pages on first visit instead of all at
once.

| Step | Create / change | Test |
|---|---|---|
| B24.1 | Measure on a real display (a probe, not shipped) | Counts after 30 real opens and closes |
| B24.2 | Depending on B24.1: release what a closed dialog keeps; pages built on first visit | A test that a closed dialog is collected (where the display allows) |
