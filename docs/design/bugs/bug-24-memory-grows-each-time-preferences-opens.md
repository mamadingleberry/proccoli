# Bug 24: Memory grows each time Preferences opens

Plan: [plan/bugs/bug-24-memory-grows-each-time-preferences-opens.md](../../plan/bugs/bug-24-memory-grows-each-time-preferences-opens.md)

*Open.* The dialog's settings handlers are all let go on `closed`; what
happens to its widgets after a real close is still to be measured on a
real display (the headless one can't close an `Adw.Dialog`).
