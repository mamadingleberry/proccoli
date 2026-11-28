# Milestone 46: Collapsible sidebar, burger top left

*✅ Done.* Hide at any width (toggle or F9, remembered); the main menu stays at the top left in every state

| Step | Create / change | Test |
|---|---|---|
| 46.1 | `ui/sidebar_visibility.py`: `header_controls_visible(show_sidebar, collapsed)`; `SidebarVisibility(split_view, settings)`: wide windows follow and save `sidebar-shown`, narrow overlay starts closed and closes on page pick without touching the choice, `toggle()`, `shutdown()` | Unit with a fake split view (no display): every rule above |
| 46.2 | Schema `sidebar-shown` (b, true) | Static test: every key used |
| 46.3 | `page.main_menu_button(model)`, `page.sidebar_toggle(split, hide)`; sidebar header starts with burger + *Hide Sidebar*; `PageContainer(page, split, menu_model)`: `start_controls` (burger + *Show Sidebar*) shown when the sidebar isn't beside the content; `release()` | UI tests: burger at the window's top left (by coordinates), left of the toggle, in both states |
| 46.4 | `win.toggle-sidebar` with F9; *Show or Hide the Sidebar* in Keyboard Shortcuts; `MainWindow` uses `SidebarVisibility` (replacing its own collapse handling) | UI tests: F9, starting hidden, removed pages stop following |
| 46.5 | Screenshot scene `wide-sidebar-hidden` | Screenshots |
| 46.6 | *Found while smoke-testing 46:* run from the checkout, `Settings.load` took the installed (older) schema, which lacked `sidebar-shown`, and GSettings aborted. Now the checkout's own schema comes first, and `choose_schema` skips any schema missing a key (`schema_covers`) | Unit with a real compiled schema missing a key: skipped, in either order |

**Done when:** the sidebar hides and shows at any width, the burger never
leaves the top left, and the choice survives a restart.
