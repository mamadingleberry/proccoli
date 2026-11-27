# 9. UI layer

```mermaid
classDiagram
    direction TB
    class ResourcePage {
        <<Adw.Bin>>
        +page_id, kind, title, icon_name, description, sort_name
        +sidebar_summary() SidebarSummary|None
        +header_widgets() list
        +title_widget() Gtk.Widget|None
        +track(source, handler_id) int
        +shutdown()
        +summary_changed()
        +report(text)
        +signal summary-changed()
    }
    class ScrollingPage {
        +add_group(title, description) Adw.PreferencesGroup
    }
    class DevicePage {
        +monitor: Monitor
        +graph_box(group, title, series, max, min_max, color_offset) GraphBox
        +add_properties(dict) Adw.PreferencesGroup
        +add_banner(title, button) Adw.Banner
        +update_labels(snapshot)*
    }
    class GpuPage {
        +controller: GpuController
        Overview + vendor tabs (§7.3)
    }
    class TablePage {
        +COLUMNS: list~Column~
        +update_rows(items)
        +items()* dict
        +targets(selected)* list
        +info_dialog(item)*
        +options_dialog(item)*
        +run_action(action)
    }
    class PageFactory {
        +register(kind, builder)
        +create(monitor) ResourcePage
    }
    class PageContainer {
        header bar (the logo, i.e. the main menu, when the sidebar isn't beside it) around a page,
        the page's title_widget() replaces the title
    }
    class MainWindow {
        +MainWindow(app, ctx)
        +add_page(page)
        +remove_page(id)
        +replace_page(page)
        +select_page(id)
    }
    ResourcePage <|-- ScrollingPage
    ResourcePage <|-- TablePage
    ResourcePage <|-- PlaceholderPage
    ScrollingPage <|-- DevicePage
    DevicePage <|-- CpuPage
    DevicePage <|-- MemoryPage
    DevicePage <|-- DrivePage
    DevicePage <|-- NetworkPage
    DevicePage <|-- BatteryPage
    DevicePage <|-- DemoPage
    DevicePage <|-- GpuPage
    TablePage <|-- AppsPage
    TablePage <|-- ProcessesPage
    MainWindow *-- StackSidebar
    MainWindow *-- "many" PageContainer
    MainWindow o-- PageFactory
    PageContainer o-- ResourcePage
    TablePage ..> ProcessActions
    ProcessesPage ..> ProcessInfoDialog
    ProcessesPage ..> ProcessOptionsDialog
    AppsPage ..> AppInfoDialog
```

**Dialogs:**
- `ProcessInfoDialog` and `AppInfoDialog` update live while open, and
  acquire the process scan for as long as they're shown.
- `ProcessOptionsDialog` sets the priority (names, or niceness with *Show
  Niceness Values*) and CPU affinity through `ProcessActions`.
- `PreferencesDialog` is built from `ui/preferences_layout.py` (M88):
  six pages (Appearance, **Sidebar** ([§9.5](09.5-sidebar-preferences.md)), Tables, Recording,
  Devices, System), each a tuple of groups, each group's rows in order.
  A row is a settings key or a `SPECIAL` item (rows built from a service,
  or several keys at once: the column lists, the sidebar's entries, the
  GPUs' switches, the history's status and actions). `_builders()` maps
  every item to the function that adds its row; a group whose rows all
  need a service the dialog wasn't given (history store, background
  unit, export, window switcher, log file) is hidden. The column lists
  are `Adw.ExpanderRow`s in place, not subpages, so search still finds
  each column. Every row is bound both ways to its key and applies
  immediately. Devices has one detailed-statistics switch per GPU that
  has a detail source (`GpuController.set_details_enabled`), plus
  `gpu-elevate` and the intel_gpu_top update interval.

```mermaid
flowchart LR
    L["preferences_layout<br/>PAGES → Group → items<br/>SPECIAL, ELSEWHERE"] --> B["PreferencesDialog._builders()<br/>item → add its row"]
    B --> P["six Adw.PreferencesPages"]
    S["settings schema"] -. "test: every key placed once<br/>or in ELSEWHERE" .- L
```
- `about_dialog()` and `shortcuts_dialog()` come from the `SHORTCUTS` table,
  which tests check against the real accelerators.

**Page lifecycle (added in Milestone 1):** pages connect to longer-lived
objects (monitors, settings, GPU controllers). Every such connection is
registered with `ResourcePage.track()`. `MainWindow` calls
`page.shutdown()` when a page is removed (unplugged device), replaced or
the window closes, and `shutdown()` disconnects them all. The GPU page also
drops its detail views (and their backend connections) whenever the detail
source stops or restarts.
