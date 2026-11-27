# Milestone 12: Dialogs + privileged helper

*✅ Done.* Real pkexec prompts untested (they need a password)

| # | Create | Test |
|---|---|---|
| 12.1 | `ui/dialogs/process_info.py`: `ProcessInfoDialog` (`Adw.Dialog`; Usage and Properties groups as in [DESIGN §2.1](../../design/02-what-resources-does-and-what-proccoli.md); live while open) | Smoke |
| 12.2 | `ui/dialogs/app_info.py`: `AppInfoDialog` | Smoke |
| 12.3 | `helper/proccoli_helper.py`: subcommands `processes` (streams JSON per interval), `kill`, `stop`, `cont`, `renice`, `affinity`, `dmidecode`. Strict argument validation; no shell. | Unit: argument validation rejects bad pids and signals; the `processes` output parses |
| 12.4 | `data/…policy`: polkit actions, one per helper subcommand, `auth_admin_keep` | `xmllint` in `make test` |
| 12.5 | `HelperSource` + "Show all processes' I/O" (elevated) toggle; actions on other users' processes go through the helper | Unit with a fake runner |
| 12.6 | `ui/dialogs/process_options.py`: niceness spin, priority combo (*Show Niceness Values* setting), CPU affinity expander | Unit: niceness ↔ priority mapping |
| 12.7 | Memory page banner (Milestone 5.5) now uses `helper dmidecode` | Manual |

**Done:** every action in Resources' Processes page works, including on
other users' processes after authenticating.
