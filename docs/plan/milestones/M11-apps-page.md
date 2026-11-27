# Milestone 11: Apps page

*✅ Done.*

| # | Create | Test |
|---|---|---|
| 11.1 | `processes/apps.py`: `AppGrouper.app_id_for(proc)` from the cgroup (gnome app scope, flatpak, snap) | Table test over real cgroup strings |
| 11.2 | Match to `Gio.DesktopAppInfo` (name, icon, description); everything else goes under "System Processes" | Unit with a fake lookup |
| 11.3 | `App` totals (sum over pids) | Unit |
| 11.4 | `ui/pages/apps.py`: `AppsPage` (icon + name cell, `apps-show-*` columns, search, end/kill/halt/continue the whole app) | Smoke |

**Done:** the Apps page matches Resources' grouping for Firefox, Terminal
and Files.
