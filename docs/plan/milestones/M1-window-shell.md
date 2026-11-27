# Milestone 1: Window shell (sidebar + stack, no data)

*✅ Done.* Including 1.8 (last viewed page) and 1.9 (demo device in the real sidebar), deferred from M2/M3

*Goal: Resources' window layout with placeholder pages. Nothing is measured
yet.*

| # | Create | Test |
|---|---|---|
| 1.1 | `ui/page.py`: `ResourcePage` (abstract), `ScrollingPage` (ScrolledWindow → Clamp → Box, `add_group()`), `SidebarSummary` dataclass | Smoke: a dummy subclass builds and `add_group()` returns an `Adw.PreferencesGroup` |
| 1.2 | `ui/page.py`: `PageContainer` (ToolbarView + flat HeaderBar + `AdwWindowTitle` + sidebar toggle) | Smoke: `set_page()` updates the title |
| 1.3 | `ui/sidebar.py`: `StackSidebarItem` (icon, name, detail, usage label, progress bar) and `StackSidebar` (ListBox, `bind_stack`, `add_item`, `remove_item`, keeps the documented order) | Unit: ordering helper (`sidebar_rank(kind, info)`) sorts Apps, Processes, CPU, Memory, GPU, Drive, Network, Battery. Smoke: selecting a row changes the stack's visible child. |
| 1.4 | `ui/window.py`: `AdwOverlaySplitView` with sidebar `ToolbarView` (header + primary menu: Preferences, Keyboard Shortcuts, About) and content `Gtk.Stack`. `add_page`, `remove_page`, `replace_page` keyed by page ID. | Smoke: `replace_page` keeps the same stack name and the selection |
| 1.5 | `AdwBreakpoint max-width: 780sp` → `collapsed`; sidebar toggle bound to `show-sidebar` | UI test: at 700 px wide the split view is collapsed and the toggle is visible |
| 1.6 | Placeholder pages: Apps, Processes, Processor, Memory (each a `ScrollingPage` with a "Coming soon" `AdwStatusPage`) | Manual: click through all four |
| 1.7 | `tests/ui/shoot.py`: the headless screenshot harness from intel_gpu_top_gui (non-unique app, per-size windows), run through the existing `tests/run-headless.sh` | `make ui-test` writes PNGs for 1280×800 and 700×600 |
| 1.8 | *(from 2.8)* Save and restore the last viewed page (`last-viewed-page`) | UI test: close and reopen → same page |
| 1.9 | *(from 3.7)* Move the demo device into the real sidebar: a `StackSidebarItem` with the `Meter` following *Sidebar Meter Type*; remove the preview group from `DemoPage` | UI screenshot: the sidebar meter moves in both meter types |

**Done:** the window looks like Resources with four empty pages. It
collapses when narrow, and the sidebar toggle works.
