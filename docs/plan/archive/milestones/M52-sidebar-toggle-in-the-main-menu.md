# Milestone 52: Sidebar toggle in the main menu

*✅ Done.* The sidebar button is now a *Show Sidebar* check item (F9) in the main menu; the corner is just the logo and the burger. *Show Sidebar* replaced by M54's modes

The sidebar button beside the burger (M46) is replaced by a *Show
Sidebar* item in the main menu, checked while the sidebar is open. The
top-left corner is now just the logo and the burger, wherever they sit.

| Step | Create / change | Test |
|---|---|---|
| 52.1 | `SidebarVisibility.action`: a stateful boolean `toggle-sidebar` action whose state follows `show-sidebar` (both ways); activating it toggles | Unit with the fake split view: state follows, activation toggles and saves, change-state sets |
| 52.2 | `primary_menu`: *Show Sidebar* (`win.toggle-sidebar`, F9) in the first section after *Go To*; `MainWindow` adds `sidebar_visibility.action` | Menu test: item present, checked state follows the sidebar |
| 52.3 | Remove `sidebar_toggle` and both buttons (`hide_sidebar_button`, `PageContainer.sidebar_toggle`); `PageContainer.start_controls` = logo + burger | UI tests: corner is logo then burger, nothing after; no toggle buttons anywhere; hiding and showing from the menu moves the burger |
