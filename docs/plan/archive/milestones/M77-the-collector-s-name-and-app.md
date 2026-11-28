# Milestone 77: The collector's name and app

*✅ Done.* Fixes Bug 7 (Processes showed `proccoli-metric`: a script's name now comes from the script); the unit runs in the desktop's app slice for Proccoli (`Slice=app-<app ID>.slice`), so the Apps page groups it with the window instead of *System Processes*

Asked for after M76: the collector showed as `proccoli-metric` on the
Processes page and under *System Processes* on the Apps page.

| Step | Create / change | Test |
|---|---|---|
| 77.1 | `processes/model.display_name`: when the kernel's 15-character name is cut, also try the second word of the command line (the script an interpreter runs) | Unit: `proccoli-metric` + `/usr/bin/python3 /usr/bin/proccoli-metrics` → `proccoli-metrics` (fails without the fix); a later argument never counts; an uncut name stays |
| 77.2 | `data/proccoli-metrics.service`: `Slice=app-@APP_ID@.slice`, filled in by `install.sh`. The unit keeps its short name; systemd puts it under `app.slice/app-<app ID>.slice/`, the form GNOME uses for app slices, which `app_id_for_cgroup` already maps to the app | Unit: that cgroup → the app ID; `test_packaging`: the installed unit's `Slice=`. By hand: a transient unit in that slice (`systemd-run --user --slice=…`) got that cgroup, and the app ID back |
| 77.3 | README (*Recording in the background*); [Feature 13's design](../../../design/features/feature-13-record-the-history-in-the-background.md), [Bug 7's design](../../../design/bugs/bug-07-the-collector-s-process-name-was.md) | – |

**Decision:** a slice rather than renaming the unit to the app's name
(`app-<app ID>@metrics.service`): the same grouping, and `systemctl
--user … proccoli-metrics` stays short to type.
