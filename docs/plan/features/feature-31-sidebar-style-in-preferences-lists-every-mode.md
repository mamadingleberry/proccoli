# Feature 31: Preferences' Sidebar Style lists every mode

Design note: [design/features/feature-31-sidebar-style-in-preferences-lists-every-mode.md](../../design/features/feature-31-sidebar-style-in-preferences-lists-every-mode.md)

*Open; settled with the user.* Preferences' *Sidebar Style* offers only
*Full* and *Icons Only*; the main menu offers *Full*, *Icons Only* and
*Hidden*. Both show the same list, from `sidebar_style.menu_modes()`,
and both set the mode through `sidebar_style.choose()`.

| Step | Create / change | Test |
|---|---|---|
| F31.1 | Preferences' row built from `menu_modes(full_allowed)`; picking one calls `choose()` and writes both settings | Unit: the row's options equal the menu's, in and out of Lightweight Mode |
| F31.2 | The row follows changes made from the menu or F9 | UI: toggle F9, the row shows *Hidden* |
| F31.3 | README (*Preferences*) | — |
