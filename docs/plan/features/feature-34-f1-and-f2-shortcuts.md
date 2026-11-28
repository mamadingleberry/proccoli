# Feature 34: F2 for Preferences, F1 for Keyboard Shortcuts

Design note: [design/features/feature-34-f1-and-f2-shortcuts.md](../../design/features/feature-34-f1-and-f2-shortcuts.md)

*✅ Built; in v0.6.0.* F2 opens Preferences and F1 the Keyboard
Shortcuts; Ctrl+, and Ctrl+? keep working, as GNOME users expect them.
F9 (sidebar) and F10 (the main menu, GTK's own) are untouched.

| Step | Create / change | Test |
|---|---|---|
| F34.1 | `ui/shortcuts.py`: one table for the app's and window's accelerators and the dialog; `app.py` and `window.py` set them from it | Unit (`test_shortcuts`): F2/F1 first, Ctrl kept, no key used twice, F10 free; UI: the app sets them |
| F34.2 | The menu shows F2 and F1 | UI smoke |
| F34.3 | README (*Keyboard shortcuts*) | — |
