# Feature 32: Graph Type, per sidebar entry

Design note: [design/features/feature-32-graph-type-per-sidebar-entry.md](../../design/features/feature-32-graph-type-per-sidebar-entry.md)

*✅ Built; in v0.6.0.* *Sidebar Meter Type* is renamed
*Graph Type*. *All Entries* keeps it as the default, and each entry's
own settings offer *Default*, *Graph* or *Progress Bar*.

| Step | Create / change | Test |
|---|---|---|
| F32.1 | Rename the label to *Graph Type* (the key `sidebar-meter-type` stays, so settings carry over) | `test_static` labels |
| F32.2 | New key `sidebar-graph-types` (`a{ss}`, entry id → type); pure `graph_type_for(entry, overrides, default)` | Settings test; unit |
| F32.3 | Each entry's preferences row; `SidebarRow` applies its own type | UI: one entry as progress bar, the rest graphs |
| F32.4 | README (*Sidebar*), DESIGN §9.5, §11 settings | — |

**Done:**

| Step | Done | Test |
|---|---|---|
| F32.1 | *Graph Type*, subtitled "Each entry can have its own"; the key stays `sidebar-meter-type` | `test_the_default_is_named_graph_type` |
| F32.2 | `sidebar-graph-types` (`a{ss}`); `sidebar_fields.graph_type_for`, `set_graph_type` (pure; *Default* removes the entry's own) | `GraphTypeTest` |
| F32.3 | `EntryPage`: *Graph Type* row (*Default (Graph)* names the default, *Graph*, *Progress Bar*), bound both ways; `StackSidebar.graph_type_choice`, `set_graph_type`; each row styled with its own type | `test_one_entry_can_have_its_own_graph_type`: one drive as a progress bar, the other follows the default and its change |
| F32.4 | User guide (*Preferences → Sidebar*), DESIGN §9.1, §9.5, §11 | – |

**Found while doing it:** the entry page's Move Up and Move Down checked
the flat order; with groups (Feature 18) they use
`sidebar_groups.can_move`, so a device's buttons follow its group.
