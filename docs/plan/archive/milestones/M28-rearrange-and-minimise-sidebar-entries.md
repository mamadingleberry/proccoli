# Milestone 28: Rearrange and minimise sidebar entries

*✅ Done.* Also Alt+Up/Down; entry colors stay with the entry when moved

Apps and Processes stay pinned at the top; every other entry can be moved
and minimised (only its icon and name).

| Step | Create / change | Test |
|---|---|---|
| 28.1 | Schema: `sidebar-order` (`as`, page IDs) and `sidebar-minimized` (`as`) | Settings tests |
| 28.2 | `ui/sidebar_order.py` (pure): `arrange(default_order, saved, pinned)`: pinned first, then saved order, new entries at their default place; `move(order, id, delta, pinned)` | Unit: unknown/removed IDs, pinned can't move, nothing can move above them |
| 28.3 | Row menu (right-click, long-press, or the row's ⋮ button): *Move Up*, *Move Down*, *Minimize*/*Expand*, *Reset Order*; drag and drop of rows | UI test: move, persist, restore on restart; pinned rows have no menu |
| 28.4 | Minimised rows hide description, usage and chart | UI test |

Milestones 29–35 are the third round of requested changes, in order, with
the same rules.
