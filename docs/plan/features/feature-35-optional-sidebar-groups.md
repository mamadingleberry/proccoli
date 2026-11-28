# Feature 35: Sidebar groups you can turn off, per kind

Design note: [design/features/feature-35-optional-sidebar-groups.md](../../design/features/feature-35-optional-sidebar-groups.md)

*Open.* Asked: "make the drop-down grouping optional (for example,
grouping vs. not grouping drives)".

**Goal:** each kind that groups ([Feature 18](feature-18-overview-pages-for-groups-of-devices.md):
GPUs, Drives, Network, Batteries) can be grouped or not. Ungrouped, its
devices are top-level entries as before Feature 18, with no group page.

**Sketch:**
- A setting `sidebar-grouped-kinds` (`as`), default every kind that
  groups; Preferences → Sidebar → *Groups*: a switch per kind.
- `sidebar_groups.group_for(kind, enabled)` returns None for a kind
  turned off; the window's `_sync_groups` adds or removes the group page
  as the switch changes, and the sidebar re-nests.
- Turning a group off keeps its devices where they were (the group's
  place in the order); turning it on again gathers them under it.

| Step | Create / change | Test |
|---|---|---|
| F35.1 | `sidebar-grouped-kinds`; `group_for` takes the enabled kinds | Unit: a kind turned off has no group; the order flattens in place |
| F35.2 | Preferences → Sidebar → *Groups* switches; the window follows the setting | UI: turning *Drives* off removes the group page and un-indents the drives; on again restores it |
| F35.3 | User guide (*Sidebar*), DESIGN §9.2, §11 | – |

**Open questions for the user:**
1. Per kind (four switches), or one switch for all groups?
2. When a group is turned off, keep its collapsed state for when it
   comes back, or forget it?
