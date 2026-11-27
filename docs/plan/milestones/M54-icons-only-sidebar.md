# Milestone 54: Icons-only sidebar

*✅ Done.* Main menu → *Sidebar*: Full, Icons Only, Hidden; hover text names each entry

The sidebar gets a third state between full and hidden: a narrow strip of
icons, with each entry's name, description and usage on hover.

| Step | Create / change | Test |
|---|---|---|
| 54.1 | Schema `sidebar-style` (enum `full`, `icons`; default `full`). Together with `sidebar-shown` it gives three modes; hiding keeps the style, so F9 brings back the same one | Settings test; static key check |
| 54.2 | `ui/sidebar_style.py` (no display): `SidebarStyle`, `Mode` (full, icons, hidden), `mode_of(shown, style)`, `choose(mode, style)`, `rail_width(header)`, `compact_tooltip(title, description, usage)` | Unit: every mode round-trips, hidden keeps the style, tooltip lines |
| 54.3 | `SidebarVisibility(split, settings, on_style=...)`: stateful `win.sidebar-mode` action (string state); follows show-sidebar and `sidebar-style` both ways; `on_style` injected | Unit with the fake split view: pick each mode, F9 after Hidden, changes from Preferences, the narrow overlay |
| 54.4 | `StackSidebarItem.set_compact` / `StackSidebar.set_compact`: only the icon, centred; no minimise button; tooltip from `compact_tooltip`. The entry's own choices (minimised, hidden parts) are kept for when it's full again | UI: rows, tooltip with usage, rows added later, back to full |
| 54.5 | `primary_menu`: a *Sidebar* section after *Go To* with radio items *Full*, *Icons Only*, *Hidden* (replaces M52's *Show Sidebar* check item; F9 stays). `MainWindow._apply_sidebar_style`: compact rows, and the split view's min and max sidebar width = `rail_width` of the sidebar header's minimum (logo, burger) | UI: menu items and state, the sidebar narrows and the corner still holds logo and burger, full widths restored |
| 54.6 | Preferences → Sidebar → *Style* (Full, Icons Only) | Dialog test, both ways |
| 54.7 | Screenshot scenes `wide-sidebar-icons`, `narrow-sidebar-icons` | Screenshots |

**Done when:** ≡ → *Sidebar* → *Icons Only* leaves a strip of icons whose
hover text names each entry, and the choice survives a restart.
