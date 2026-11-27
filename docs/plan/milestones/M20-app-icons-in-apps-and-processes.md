# Milestone 20: App icons in Apps and Processes

*✅ Done.*

| Step | Create / change | Test |
|---|---|---|
| 20.1 | `processes/apps.py`: `AppGrouper.app_for(process)` (the app a process belongs to, using the same cgroup rules as grouping) | Unit on cgroup fixtures |
| 20.2 | `MISSING_APP_ICON = "application-x-addon-symbolic"` (a puzzle piece) in `proccoli/__init__.py` | Static icon test |
| 20.3 | Apps: each row's icon is the app's icon, or the puzzle piece | UI test with a fake desktop lookup |
| 20.4 | Processes: each row's icon is its app's icon, or the puzzle piece (kernel threads and background processes included) | UI test |

**Done when:** every row in both tables starts with an icon, and processes
of the same app share its icon.
