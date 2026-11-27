# Milestone 72: Graph toolbar

*✅ Done.* Was Idea 12. A toolbar under each page with charts: a *Time Range* menu, *Graph Axes* and *Graph Grid* switches (and *Logical CPUs* on the Processor page), each titled, each the same setting as Preferences; *Graph Grid* now reaches the Overview cards and sidebar charts too; drag (or Ctrl+Shift+Left/Right) to reorder, ⋮ to show, hide or reset; *Show Toolbar* in the main menu. The sidebar's ordering is now the shared `reorder.py` and `make_reorderable`. Not in Lightweight Mode

Was Idea 12 (kept below with its design). Steps I12.1–I12.5 as planned,
with the deviations listed after the table.

| Step | Create / change | Test |
|---|---|---|
| 72.1 | `ui/sidebar_order.py` → `ui/reorder.py` (the tests moved to `test_reorder.py`); `ui/widgets/reorderable.py`: `make_reorderable` (drag, drop, modifier+arrow keys); the sidebar switched to it | Unit: the order functions as before; the keys (Alt+Up/Down for the sidebar, Ctrl+Shift+Left/Right for the toolbar, Caps Lock ignored); UI: the sidebar's drop and move tests unchanged |
| 72.2 | `ui/toolbar_items.py`: the items, `shown`, `set_shown`, `applies`; Preferences' time-range and interval choices moved there | Unit: every item's key and type match the schema; every nick has a label; Preferences uses the same tuples; showing an item puts it at its default place |
| 72.3 | `toolbar-items`, `show-toolbar` keys; `ui/widgets/graph_toolbar.py`; `ResourcePage.has_graphs`; `PageContainer.attach_toolbar` / `detach_toolbar`; `MainWindow._place_toolbar`, `win.show-toolbar` and *Show Toolbar* in the main menu; `Profile.graph_toolbar` (off in Lightweight Mode) | UI: toggles and menus set their settings and follow them; *Grid* reaches the page's graphs; one toolbar moves with the page and survives removing the shown page; items per page; pinned keys greyed out; *Show Toolbar* hides it both ways; no toolbar in Lightweight Mode |
| 72.4 | Reordering, ⋮ *Show in Toolbar* and *Reset Toolbar*, right-click on the bar | UI: a drop and Ctrl+Shift+arrow store the order; hiding, showing and reset |
| 72.5 | README (*Toolbar*, shortcuts), [DESIGN §4.1](../../design/04-architecture-overview.md), [§9.2](../../design/09.2-window-behaviour.md), [§11](../../design/11-cross-cutting-concerns.md), [Idea 12's design](../../design/ideas/idea-12-a-graph-toolbar.md); `shoot.py` `toolbar-all-items`, `narrow-toolbar` | `make ui-test` |
| 72.6 | Every item has a title above it (`ToolbarItem.title`, asked for after 72.5: menus showed only their value, and a tooltip isn't enough): a cell with a dim caption over the control; toggles show *On* / *Off*; *Axes* and *Grid* are titled *Graph Axes* and *Graph Grid*; the cell is what's dragged | Unit: every item has a distinct title; UI: each cell is the title over its control; a toggle says *On* or *Off* |
| 72.7 | Toggles are `Gtk.Switch`es (no text: slide right, accent color when on); *Logical CPUs* is `fixed`: always on the Processor page's toolbar, nowhere else, not listed or stored; the page's own row shows only without the toolbar (`toolbar_shown`) | Unit: fixed items never stored; `toolbar_shown`; UI: toggles are switches; *Logical CPUs* last on the Processor page; an old saved `logical-cpus` ignored; the page row hides and shows with *Show Toolbar* |
| 72.8 | *Update Interval* out of the toolbar (the user's choice: it sets every reading everywhere, not a page's view; Preferences keeps it); every item is about graphs, so the bar hides on Apps and Processes. `ChartSettings` gives *Graph Grid* to every kind of chart: Overview cards and sidebar meters had ignored it (the graph could always draw it), so the toolbar's switch didn't change charts in plain sight | Unit: every kind gets the grid, live; no item applies without graphs; an old saved `update-interval` ignored; UI: the toolbar's *Graph Grid* reaches the Overview cards and sidebar meters; `shoot.py` `overview-grids` |

**Decisions on Idea 12's open questions** (taken with the design's own
leanings, since the request was to build it): (1) "button-drag" is
dragging toolbar buttons to reorder them; dragging across a graph to
zoom would be its own change; (2) on by default, and *Show Toolbar* in
the main menu turns it off (see the finding below); (3) *Time Range*,
*Axes* and *Grid* shown, *Update Interval* and *Logical CPUs* available
(changed in 72.7 and 72.8: *Logical CPUs* is fixed to the Processor
page, and *Update Interval* left the toolbar).

**Deviations from Idea 12, and why:**
- **Under the page header, not one header for the content:** every page
  already has its own header bar (`PageContainer`), so the toolbar is a
  second top bar there, and the window moves its one instance to the
  page shown.
- **Customize is a menu, not a dialog:** ⋮ lists every item as a check
  item plus *Reset Toolbar*; a dialog added nothing a menu can't do.
- **Scrolls instead of an overflow menu** in a narrow window: simpler,
  and the 360 px minimum still shows the first items.
- **Ctrl+Shift+Left/Right, not Alt+Left/Right:** Alt+Left/Right are Back
  and Forward (M49).
- **No toolbar in Lightweight Mode:** every graph setting on it is
  pinned there anyway.

*Found while doing 72:* the bar takes about 46 px (65 px since 72.6), and at 1024×768 that
was the difference between the Overview's tables fitting below the
charts and moving below the fold (two `test_overview` geometry tests
failed). The planner was right; the room was gone. Hence *Show Toolbar*;
those geometry tests now run with it off, and `WindowToolbarTest` checks
that turning it off gives the page the room back.
