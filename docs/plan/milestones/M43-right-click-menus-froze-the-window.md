# Milestone 43: Right-click menus froze the window (bug)

*✅ Done.* Gesture now claimed before the popup; one reused popover on a stable parent. Not reproducible headless (Wayland-only); confirm on the desktop

Reported: the app froze on right-click menus in Apps and Processes. It
didn't reproduce on the headless Broadway display, with default or the
user's CPU sorting: the main loop stayed responsive (worst iteration
under 50 ms) and the selection followed the right process across
re-sorts. The cause is Wayland-specific. See [DESIGN.md §8](../../design/08-processes-and-apps.md), *Context menus*.

| Step | Create / change | Test |
|---|---|---|
| 43.1 | `TablePage.open_cell_menu(gesture, item, cell, x, y)`: claims the gesture, selects the row, opens the menu | UI test: the gesture is claimed before the menu opens; the clicked row is selected |
| 43.2 | One `Gtk.PopoverMenu` per table, parented to `menu_parent` (the page's box), reused; `menu_point` translates the click; `shutdown()` unparents it | UI tests: same popover each time, kept across refreshes, points at the click, keyboard menu, shutdown |
| 43.3 | `test_static`: no test file defines a module-level class name twice (a duplicate `ContextMenuTest` had silently hidden six tests while writing 43.1) | Static test (checked against the duplicate) |

**Done when:** right-clicking rows in Apps and Processes opens the menu
and the window keeps responding (to be confirmed on the Wayland desktop).
