# Bug 23: Preferences, Shortcuts and About open again on every press

Design note: [design/bugs/bug-23-preferences-and-other-dialogs-stack.md](../../design/bugs/bug-23-preferences-and-other-dialogs-stack.md)

*Fixed; in Unreleased.*

**Seen:** "you can also use the keyboard shortcuts to open an unlimited
amount of preferences dialog windows... no bueno".

**Cause:** `Application.show_preferences` (and `show_shortcuts`,
`show_about`) built and presented a new dialog every time, stacked on
the last. Each Preferences dialog connects about 62 settings handlers and
builds every page, swatch and row: measured on the headless display, ten
presses held ten dialogs, 620 more handlers and 90 MiB more memory.

**Fix:** `Application._present_once(name, build)`: one dialog per name;
asking again presents the open one; its `closed` (or a window's
`close-request`) forgets it, so the next press builds a fresh one.

| Step | Create / change | Test |
|---|---|---|
| B23.1 | `app.py`: `_present_once` for Preferences, Keyboard Shortcuts and About | `OneDialogEachTest`: five more presses keep the same dialog and no new handlers; a closed dialog is forgotten and its handlers let go; Shortcuts and About one each (all fail on the old code) |

**Measured after:** ten presses: one dialog, 62 handlers, 13 MiB.
