# Feature 12: A graph toolbar

Design note: [design/features/feature-12-a-graph-toolbar.md](../../design/features/feature-12-a-graph-toolbar.md)

*Done as v0.5.0* (its decisions and deviations are listed there).

**Goal:** the settings people change while looking at graphs are one
click away, in a toolbar across the top of the pages, instead of in
Preferences:

- **Menus:** *Time Range* (the presets, and *Custom…* once Feature 9 is
  built), to start with; *Update Interval* next.
- **Toggles:** *Axes* and *Grids*, then *Logical CPUs*.
- **Customizable:** drag a button to move it; right-click the toolbar
  (or its overflow menu) for *Customize Toolbar…*, a list of every
  button with a switch to show or hide it and *Reset*.

**Why:** changing the range to look back an hour, or turning the grid on
to read a value, takes four clicks into Preferences and a click back.
They're view controls, so they belong next to the view.

**Design ([Feature 12's design](../../design/features/feature-12-a-graph-toolbar.md)):**

- **One place for the buttons' meaning:** `ui/toolbar_items.py`
  (display-free) lists each item: id, label, icon, kind (`menu` or
  `toggle`), the settings key it changes and, for menus, the choices
  (the schema's enum nicks with their labels, shared with Preferences so
  the two never disagree). A toggle *is* the setting: the button binds
  to it through `settings.bind`, so Preferences, the toolbar and the
  graphs stay in step, and a Lightweight pin (`ProfileSettings.bind`)
  shows the pinned value with the button greyed out, as Preferences
  does.
- **Where it goes:** an `Adw.HeaderBar` on the content side of the
  split view (today only the sidebar has one), built by
  `ui/widgets/graph_toolbar.py`. Pages without graphs (Apps, Processes)
  hide the graph items, so the bar never offers a control that does
  nothing there. In a narrow window, items that don't fit go into an
  overflow menu, in order.
- **Abstract the sidebar's ordering (the light refactoring):** the
  sidebar's drag-to-reorder (`sidebar_order.arrange` / `move`, and the
  `DragSource` / `DropTarget` wiring in `StackSidebar._wire_row`) moves
  into a shared `ui/reorder.py`: the pure order functions (with pinned
  heads) and a `Reorderable` helper that wires drag, drop and
  Alt+arrow keys onto any widget given its id and a `move_before`
  callback. The sidebar and the toolbar both use it; the sidebar's tests
  keep passing unchanged.
- **Settings:** `toolbar-items` (`as`, the shown items in order;
  default `['time-range', 'axes', 'grids']`). `sidebar_order.arrange`'s
  rule handles items a newer version adds: they appear where the default
  puts them.
- **Keyboard:** each item is a window action (`win.time-range`,
  `win.graph-axes`...), so they get shortcuts and work from the menus
  too, and the toolbar is reachable with F10 / Tab like any header bar.

| Step | Create / change | Test |
|---|---|---|
| F12.1 | `ui/reorder.py` from `sidebar_order.py` and the sidebar's drag wiring; the sidebar switched to it | Unit: the order functions as before (the sidebar_order tests moved); UI: sidebar drag and Alt+Up still reorder |
| F12.2 | `ui/toolbar_items.py`: the items table; Preferences' time-range and interval choices read from it | Unit: every item's key exists in the schema; every enum nick has a label; Preferences and toolbar list the same choices |
| F12.3 | `data/…gschema.xml`: `toolbar-items`; `ui/widgets/graph_toolbar.py`: the content header bar with menus and toggles bound to settings | Unit: settings test for the key; UI: toggling *Grids* sets `show-graph-grids` and a graph redraws with a grid; picking *1 Hour* sets the range; a pinned key's button is insensitive in Lightweight Mode |
| F12.4 | Dragging items; *Customize Toolbar…*; graph items hidden on Apps and Processes; overflow in a narrow window | UI: a drag stores the new order; hiding an item removes it; overflow holds what doesn't fit at 400 px |
| F12.5 | README *Graphs* and keyboard shortcuts; [Feature 12's design](../../design/features/feature-12-a-graph-toolbar.md) as built; screenshot scenes | `make ui-test` |

**Done when:** the time range and the axes and grids can be changed from
the toolbar on every graph page, the change shows in Preferences and on
every graph at once, the buttons can be reordered by dragging and
hidden, and the sidebar still reorders by drag through the same helper.

**Open questions for the user:**
1. By "button-drag" did you mean dragging toolbar buttons to reorder
   them (as designed here), or dragging across a graph to choose a time
   range (zoom into a stretch)? The second is a bigger change of its own
   (graphs would need a "from–to" range, not just "the last N").
2. Should the toolbar be on by default, or shown from the main menu
   (*Show Toolbar*, like the sidebar's F9)?
3. Apart from the time range, axes and grids, which controls do you
   want first: update interval, logical CPUs, temperature unit, bits or
   bytes?
