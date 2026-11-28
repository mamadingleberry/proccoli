# Proccoli: Build Plan

The index of the plan. Work is tracked as **Features** (what Proccoli
should do) and **Bugs** (what it does wrong). A **Release** is a set of
built Features and fixed Bugs, shipped as a version tag. Each Feature
lists **what to create, in order**, with the test that proves each
piece.

**How these docs are kept:** this page and [DESIGN.md](DESIGN.md) are
indexes. Each feature, bug and release is its own file, linked below and
named after its number, so it can be opened directly:
`plan/features/feature-19-*.md`, `plan/bugs/bug-22-*.md`,
`plan/releases/v0.5.0.md`. Before features, work was planned as
milestones; those files are kept in `plan/archive/milestones/`
and linked from the release they shipped in. Read this page, then only
the files a change needs.

**Working rules for every feature and bug fix**

1. Write the test with (or before) the class. Domain and core code must be
   testable without a display.
2. Every `/proc` and `/sys` read goes through `SysRoot`, so its test uses a
   fixture tree under `tests/fixtures/`. Capture fixtures from real machines
   with `tests/fixtures/capture.sh`.
3. UI code gets a **smoke test**: build the widget and feed it a snapshot, on
   the headless Broadway backend (`GDK_BACKEND=broadway`, `make ui-test`).
   Visual checks use the screenshot script, `tests/ui/shoot.py`.
4. `make test` stays green at the end of every step; `make check` before
   saying it's done.
5. Commit at the end of every numbered step (when asked to commit).
6. Documenting and indexing features, bugs and releases: the
   `software-design` skill, *Tracking work*.

## Current state

Tests: 1312, all passing on the headless display (`make ui-test`; on
GTK 4.14, 3 skip because they need a window taller than the 1024×768
headless screen; [why](plan/archive/milestones/M53-runs-on-ubuntu-24-04.md)). A plain `make test` runs the 999 that need no
display and skips the rest, so it never opens windows on your desktop.

**Platform floor:** Ubuntu 24.04 (Python 3.12, GTK 4.14, libadwaita 1.5,
GLib 2.80, PyGObject 3.48) is tested on a real 24.04 machine since v0.2.0.
Newer APIs go through `ui/compat.py` or a `hasattr` check, and
`tests/test_static.py` enforces this for libadwaita.

**Tools:**
- `tests/ui/shoot.py --real`: screenshots, including this machine's own
  devices and processes.
- `tests/ui/perf.py`: Proccoli's own CPU use.

## Open bugs

Found but not fixed. Each is fixed as its own change, with a regression test; each file has the cause and the steps, and links to its design note.

- 🐞 [Bug 24: Memory grows each time Preferences opens](plan/bugs/bug-24-memory-grows-each-time-preferences-opens.md)

Fixed: [1](plan/bugs/bug-01-graphs-stretch-old-points-after-a.md) (v0.4.0), [2](plan/bugs/bug-02-an-amd-apu-s-package-power.md) (v0.5.0), [3](plan/bugs/bug-03-an-amd-apu-s-graphics-memory.md) (v0.5.0), [4](plan/bugs/bug-04-amd-processes-video-memory-is-counted.md) (v0.5.0), [5](plan/bugs/bug-05-the-readme-installs-an-old-version.md) (v0.5.0), [6](plan/bugs/bug-06-an-amd-gpu-s-fdinfo-is.md) (v0.5.0), [7](plan/bugs/bug-07-the-collector-s-process-name-is.md) (v0.5.0), [8](plan/bugs/bug-08-lightweight-mode-froze-the-window-at.md) (v0.5.0), [9](plan/bugs/bug-09-a-window-s-graphs-miss-the.md) (v0.5.0), [10](plan/bugs/bug-10-the-lightweight-switch-shows-the-setting.md) (v0.5.0), [11](plan/bugs/bug-11-lightweight-mode-s-processor-and-memory.md) (v0.5.0), [12](plan/bugs/bug-12-a-test-started-the-installed-collector.md) (v0.5.0), [13](plan/bugs/bug-13-the-overview-s-tables-change-width.md) (v0.5.0), [14](plan/bugs/bug-14-after-restart-now-the-window-is.md) (v0.5.0), [15](plan/bugs/bug-15-a-second-recorder-waits-around-instead.md) (Bugs 15–16), [16](plan/bugs/bug-16-a-recorder-stopped-by-a-signal.md) (Bugs 15–16), [17](plan/bugs/bug-17-one-point-gaps-every-few-minutes.md) (Bugs 17, 19, 20), [19](plan/bugs/bug-19-an-idle-intel-gpu-s-overview.md) (Bugs 17, 19, 20), [20](plan/bugs/bug-20-a-chart-with-no-readings-is.md) (Bugs 17, 19, 20), [18](plan/bugs/bug-18-changing-the-time-range-shows-the.md) (v0.6.0), [21](plan/bugs/bug-21-an-nvidia-gpu-too-new-for.md) (v0.6.0), [22](plan/bugs/bug-22-the-window-freezes-after-unlocking-or.md) (v0.6.0), [23](plan/bugs/bug-23-preferences-and-other-dialogs-stack.md) (Unreleased).

## Features

Designed but not built. Each ships in the next release once it's built.

- 💡 [Feature 7: Export Statistics for the session or the whole saved history](plan/features/feature-07-export-statistics-for-the-session-or.md): *Export Statistics…* for this session, the last hour/day/week, or all saved history
- 💡 [Feature 16: A Web GUI, hosted locally (brainstorm)](plan/features/feature-16-a-web-gui-hosted-locally.md): a browser view served by the recorder on this machine (brainstorm)
- 💡 [Feature 17: The Web GUI for machines on the local network (brainstorm)](plan/features/feature-17-the-web-gui-for-machines-on.md): one Web GUI for several machines on the local network (brainstorm)
- 🚧 [Feature 19: The window reads nothing: `proccoli-metrics` serves every reading](plan/features/feature-19-the-window-reads-nothing-proccoli-metrics.md): the window reads nothing itself: 19a and 19b done (v0.5.0), 19c left
- 💡 [Feature 23: Icons Only on narrow windows](plan/features/feature-23-icons-only-on-narrow-windows.md): a narrow window keeps a narrow sidebar before hiding it
- 💡 [Feature 25: A recorder for the whole machine](plan/features/feature-25-a-recorder-for-the-whole-machine.md): one system recorder and history from boot, for everyone (Feature 22's option C)
- 💡 [Feature 30: Network sidebar graphs scaled to the link speed](plan/features/feature-30-network-graphs-scaled-to-link-speed.md): Ethernet and Wi-Fi graphs topped at the link speed
- 💡 [Feature 31: Preferences' Sidebar Style lists every mode](plan/features/feature-31-sidebar-style-in-preferences-lists-every-mode.md): Full, Icons Only and Hidden, as in the main menu
- 💡 [Feature 33: A page's graphs sized as a group](plan/features/feature-33-pane-graphs-sized-as-a-group.md): graphs on one page share a size and resize together
- 💡 [Feature 35: Sidebar groups you can turn off, per kind](plan/features/feature-35-optional-sidebar-groups.md): group (or not) GPUs, Drives, Network and Batteries
- 💡 [Feature 36: Each device's meter on a collapsed group](plan/features/feature-36-meters-on-collapsed-groups.md): a slim bar per device on a collapsed group's row, toggleable
- 💡 [Feature 37: A `software-prototype` skill for quick ideas](plan/features/feature-37-software-prototype-skill.md): a lighter `software-project` for idea-to-creation

Built: [1](plan/features/feature-01-lightweight-mode.md) (v0.3.0), [2](plan/features/feature-02-metrics-history-in-a-sqlite-database.md) (v0.3.0), [3](plan/features/feature-03-intel-details-graphs-on-the-shared.md) (v0.3.0), [4](plan/features/feature-04-one-chart-family-everywhere.md) (v0.3.0), [5](plan/features/feature-05-switch-to-any-running-app.md) (v0.3.0), [6](plan/features/feature-06-update-interval-instead-of-refresh-speed.md) (v0.3.0), [8](plan/features/feature-08-lightweight-mode-small-charts-on-the.md) (v0.5.0), [9](plan/features/feature-09-custom-graph-time-range.md) (v0.5.0), [10](plan/features/feature-10-shade-the-time-proccoli-wasn-t.md) (v0.4.0), [12](plan/features/feature-12-a-graph-toolbar.md) (v0.5.0), [13](plan/features/feature-13-record-the-history-in-the-background.md) (v0.5.0), [14](plan/features/feature-14-exported-statistics-describe-their-devices.md) (v0.5.0), [15](plan/features/feature-15-separate-installs-proccoli-metrics-and-proccoli.md) (v0.5.0), [24](plan/features/feature-24-docs-as-indexes-with-one-file.md) (the next release), [20](plan/features/feature-20-preferences-in-named-sections.md) (the next release), [22](plan/features/feature-22-recording-from-boot.md) (the next release), [26](plan/features/feature-26-releases-and-features.md) (v0.6.0), [27](plan/features/feature-27-uml-and-database-design-docs.md) (v0.6.0), [28](plan/features/feature-28-voice-and-audience.md) (v0.6.0), [29](plan/features/feature-29-engineering-skills.md) (v0.6.0), [34](plan/features/feature-34-f1-and-f2-shortcuts.md) (v0.6.0), [21](plan/features/feature-21-refactoring-candidates.md) (v0.6.0), [11](plan/features/feature-11-a-shorter-friendlier-readme.md) (v0.6.0), [18](plan/features/feature-18-overview-pages-for-groups-of-devices.md) (v0.6.0), [32](plan/features/feature-32-graph-type-per-sidebar-entry.md) (v0.6.0), [38](plan/features/feature-38-cheaper-test-runs.md) (Unreleased).

## Releases

Each release file has its description (also the tag message and the
GitHub release notes), its Features and Bugs, and the archived milestones
it shipped. Newest first.

- 🚧 [Unreleased](plan/releases/unreleased.md): quieter test runs (Feature 38); one dialog of each kind (Bug 23)
- ✅ [v0.6.0](plan/releases/v0.6.0.md) (2026-11-28): sidebar groups, a Graph Type per entry, Preferences in six pages, recording from boot, a steadier window
- ✅ [v0.5.0](plan/releases/v0.5.0.md) (2026-11-25): the background recorder `proccoli` and the window `proccoli-gui`; AMD statistics; the graph toolbar
- ✅ [v0.4.0](plan/releases/v0.4.0.md) (2026-11-24): honest graph time; the time Proccoli wasn't running is shaded
- ✅ [v0.3.0](plan/releases/v0.3.0.md) (2026-11-24): the SQLite history, one chart family, Update Interval, Lightweight Mode
- ✅ [v0.2.0](plan/releases/v0.2.0.md) (2026-11-23): Ubuntu 24.04, NVIDIA, GPU detection, the icons-only sidebar
- ✅ [v0.1.0](plan/releases/v0.1.0.md) (2026-11-23): the window, a page per device, the Overview

Other history: [early deviations from the first plan](plan/early-deviations.md).
