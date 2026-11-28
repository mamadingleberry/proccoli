# Milestone 31: Per-entry sidebar details

*✅ Done.* The icon always stays, so a hidden entry can still be clicked

Every entry except Apps and Processes can show or hide each of its parts.

| Step | Create / change | Test |
|---|---|---|
| 31.1 | `ui/sidebar_fields.py` (pure): `Field` = NAME, DESCRIPTION, USAGE, CHART; `visible_fields(entry, global settings, hidden map)` | Unit |
| 31.2 | Schema `sidebar-hidden-fields` (`a{sas}`: page ID → hidden fields); the global *Show Usage Details* / *Descriptions* switches still apply to all | Settings tests |
| 31.3 | Row menu: *Show Name*, *Show Description*, *Show Usage*, *Show Chart* (check items); *Minimize* (M28) hides all but the name | UI test |
