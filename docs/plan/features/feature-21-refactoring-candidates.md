# Feature 21: Refactoring candidates

Design note: [design/features/feature-21-refactoring-candidates.md](../../design/features/feature-21-refactoring-candidates.md)

*✅ Built; in v0.6.0.* R1–R3 in v0.5.0; R4–R10 and R12 now. None changes what users see, except that the recorder now logs its own stalls and crashes (R8).

**Goal:** places where the code would be clearer as classes, base
classes or small helpers, found by size (files over 500 lines, classes
with 35+ methods, functions over 60 lines) and by repeated patterns.
Each is its own step when taken on; none changes what users see.

| # | Where | Now | Proposed |
|---|---|---|---|
| R1 | 17 modules (`window.py`, `theme.py`, `chart_settings.py`, `sidebar_visibility.py`, `graph_toolbar.py`, `page.py`, `metrics_service.py`, …) | Each keeps its own list of `(source, handler id)` pairs and a loop that disconnects them | A `Connections` helper: `connect(source, signal, fn)`, `disconnect_all()`; one tested place for clean shutdown |
| R2 | `devices/manager.py`, `devices/remote.py` | `DeviceManager` and `RemoteDeviceManager` share an interface only by duck typing; `app.py` and `window.py` ask `hasattr(devices, "connected")` | An abstract `DeviceSource` base (monitors, monitor, start, stop, refresh, rescan, retry, `connected`, `status`, the signals); the local one is always connected |
| R3 | `metrics_service.device_info` | Probes each monitor with `hasattr` (`plan`, `thread_names`, `modules`, `detail_state`) to build what it sends | `Monitor.describe()` overridden by the processor, memory and GPU monitors, and `RemoteMonitor.from_description()` the matching reader: each class encodes and decodes its own fields |
| R4 | `core/system.py` (`System`, 35 methods) | One seam for processes, locks, D-Bus, GNOME Shell windows and extensions, wmctrl, app launching | `System` as a facade over `ProcessControl`, `Locks`, `ShellIntegration` and `AppLauncher`; `FakeSystem` splits the same way |
| R5 | `ui/widgets/graph.py` (`Graph`, 36 methods, 712 lines) | Data, axes, hover and drawing in one widget; `SidebarGraph` overrides `has_axes` and `y_tick_labels` | `GraphAxes` (ticks, `plot_rect`, drawing the axes) and `GraphHover` (pointer, readout) as helper objects; `PaneGraph` and `SidebarGraph` pick an axes policy instead of overriding |
| R6 | `MainWindow.__init__` (157 lines) | Builds the sidebar, pages, banner, toolbar, Go To menu, back/forward, mouse buttons, Overview and authentication inline | `_build_*` methods, and a `NavigationController` class for back/forward, the mouse side buttons and Go To |
| R7 | `PreferencesDialog` (35 methods, `__init__` 134 lines) | One class builds every page | A class per page (`AppearancePage`, …) from a layout table; with Feature 20 |
| R8 | `app.py`, `metrics.py` | Each starts its own logging; only the window has the stall watchdog and crash hook | A shared `Runtime.start(settings, log name)` (file log, watchdog, exception hook), so the recorder gets the same diagnostics |
| R9 | `ui/pages/table.py` (`TablePage`, 37 methods) | Columns, their settings keys, order and widths are worked out inside the widget | A display-free `ColumnSet` (which columns, order, widths, settings keys); the page renders it |
| R10 | `ui/sidebar.py` (`StackSidebar`, 39 methods) | Rows, drag and drop, meters and selection in one class | `SidebarDragAndDrop` and `SidebarMeters` helpers; ordering already lives in `sidebar_order.py` |
| R11 | 40 `settings.connect("changed::…")` calls | Each widget connects and later disconnects keys one by one | `settings.watch(keys, fn)` returning a handle that R1's `Connections` closes |
| R12 | `tests/test_packaging.py` | Reads a deb's control scripts three times inline | A `control_script(deb, name)` helper |

**Done now (all of R4–R10, R12):**

| # | What was done | Test |
|---|---|---|
| R4 | `core/system.py`: `System` is `Programs`, `Locks`, `ProcessControl`, `ChildProcesses`, `AppLauncher` and `ShellIntegration` (the last two on a shared `SessionBus`); one flat interface for callers. `FakeSystem` stays one class | `SystemPartsTest`: `System` is exactly its parts, no method written twice, a part works alone, `FakeSystem` has every method |
| R5 | `ui/axes.py`: `PaneAxes`, `SidebarAxes` (whether axes show, the ticks, the grid); `SidebarGraph` picks one instead of overriding three methods. `ui/widgets/graph_hover.py`: `GraphHover` (pointer, texts, drawing the readout); `Graph` keeps thin `set_hover`, `hover_lines`, `format_for` | `AxesPolicyTest` (no display); the graph UI tests unchanged but for `readout._on_motion` |
| R6 | `MainWindow.__init__` 153 → 39 lines: `_build_shell`, `_build_graph_toolbar`, `_build_pages`, `_build_authentication`; `ui/navigation_controller.py`: back and forward, the mouse side buttons and Go To | `test_navigation` through `win.navigation` |
| R7 | `PreferencesDialog`'s rows in four parts: `preferences_rows.py` (pages, groups, bound rows, the padlock), `preferences_appearance.py`, `preferences_history.py`, `preferences_system.py`; the dialog keeps the layout table and the Sidebar page | The Preferences UI tests, unchanged |
| R8 | `core/runtime.py`: `Runtime` (log file, stall watchdog, uncaught-exception hook) and `console_logging`, used by `app.py` and `metrics.py`: the recorder gains the watchdog and the hook | `test_runtime` |
| R9 | `ui/columns.py`: `Column`, `ColumnSet` (setting keys, visibility, the saved sort and what to save), `compare`; `TablePage` renders it | `test_columns` (no display) |
| R10 | `ui/sidebar_arrangement.py` (`SidebarArrangement`: order, minimised, hidden details) and `ui/sidebar_row_menu.py` (`SidebarRowMenu`: menu, keys, drag and drop), parts of `StackSidebar` | The sidebar UI tests, unchanged |
| R12 | `test_packaging`: `control_script(deb, name)` | The three deb tests |

**Found while doing it:** three planning references had slipped into
code across a line break; `test_static` now catches those (with
Feature 26). The parts are mixins, each in its own module, rather than
helper objects for R4, R7 and R10: every caller and test keeps working
against one object, while each concern can be read on its own.

**Done before:** the program names (`COLLECTOR`, `WINDOW`) moved into
`proccoli/__init__.py` with v0.5.0, instead of being spelled out in four
modules. R1, R2 and R3 in v0.5.0; R11 with R1 (`Connections.watch`). The
big classes (R4–R7, R9, R10) wait, by request.

**Suggested order:** R1 and R11 (small, touch many files, make the rest
safer), R2 and R3 (remove the duck typing between the window and the
recorder), then R5, R6, R9, R10 one at a time; R7 with Feature 20.
