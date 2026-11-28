# Proccoli: Design

How Proccoli is put together: what it copies from Resources, where it
deliberately differs (the swappable GPU page), the layers of the
application, and the classes in each layer. [PLAN.md](PLAN.md) gives the
order in which to build it.

**How these docs are kept:** this page is an index. Each section is its
own file under `design/` (a long section is split by subsection:
`design/09.2-*.md`), and each feature's and bug's design note is
`design/features/feature-19-*.md` or `design/bugs/bug-22-*.md`, numbered like
the plan. Read this page, then only the sections a change touches.

**Start here:** [DESIGN_UML.md](design/DESIGN_UML.md) (the programs,
packages and main classes) and [DESIGN_DB.md](design/DESIGN_DB.md) (the
history database). Both are always kept current: a change that alters a
program, package, main class, table or retention rule updates them in the
same change.

Diagrams use [Mermaid](https://mermaid.js.org/), which GitHub renders.

**The name.** Proccoli is a portmanteau of *process* and *broccoli*.

## Contents

- [1. Goals and non-goals](design/01-goals-and-non-goals.md)
- [2. What Resources does, and what Proccoli changes](design/02-what-resources-does-and-what-proccoli.md)
- [3. Technology decisions](design/03-technology-decisions.md)
- [4. Architecture overview](design/04-architecture-overview.md)
- [5. Core layer](design/05-core-layer.md)
- [6. Devices layer: monitors and snapshots](design/06-devices-layer-monitors-and-snapshots.md)
- [7. The GPU carve-out](design/07-the-gpu-carve-out.md)
  - [7.1 Roles: summary and detail sources](design/07.1-roles-summary-and-detail-sources.md)
  - [7.2 The controller](design/07.2-the-controller.md)
  - [7.3 The page](design/07.3-the-page.md)
  - [7.4 Backend selection](design/07.4-backend-selection.md)
  - [7.5 AMD (v0.5.0)](design/07.5-amd.md)
- [8. Processes and Apps](design/08-processes-and-apps.md)
- [9. UI layer](design/09-ui-layer.md)
  - [9.1 Widgets](design/09.1-widgets.md)
  - [9.2 Window behaviour (mirrors Resources)](design/09.2-window-behaviour.md)
  - [9.3 Appearance](design/09.3-appearance.md)
  - [9.4 Optional authentication at launch](design/09.4-optional-authentication-at-launch.md)
  - [9.5 Sidebar preferences](design/09.5-sidebar-preferences.md)
  - [9.6 Overview page (v0.1.0; Lightweight Mode Feature 8)](design/09.6-overview-page.md)
  - [9.7 Error pages (v0.2.0)](design/09.7-error-pages.md)
- [10. Runtime flow](design/10-runtime-flow.md)
- [11. Cross-cutting concerns](design/11-cross-cutting-concerns.md)
- [12. Open decisions](design/12-open-decisions.md)
- [13. Features, Bugs and Releases](design/13-features-bugs-and-releases.md)

## Features' design notes

Designed but not built, or the design record of a feature that was; the plan side (steps, status) is linked from each.

- [Feature 1: Lightweight mode (minimal memory)](design/features/feature-01-lightweight-mode.md)
- [Feature 2: Metrics history in a SQLite database](design/features/feature-02-metrics-history-in-a-sqlite-database.md)
- [Feature 3: Intel Details graphs on the shared chart code](design/features/feature-03-intel-details-graphs-on-the-shared.md)
- [Feature 4: One chart family everywhere](design/features/feature-04-one-chart-family-everywhere.md)
- [Feature 5: Switch To any running app](design/features/feature-05-switch-to-any-running-app.md)
- [Feature 7: Export any part of the history](design/features/feature-07-export-any-part-of-the-history.md)
- [Feature 8: Lightweight Mode: small charts on the Overview, a minimal sidebar](design/features/feature-08-lightweight-mode-small-charts-on-the.md)
- [Feature 9: Custom graph time range](design/features/feature-09-custom-graph-time-range.md)
- [Feature 10: Shade the time Proccoli wasn't running](design/features/feature-10-shade-the-time-proccoli-wasn-t.md)
- [Feature 11: A shorter, friendlier README](design/features/feature-11-a-shorter-friendlier-readme.md)
- [Feature 12: A graph toolbar](design/features/feature-12-a-graph-toolbar.md)
- [Feature 13: Record the history in the background](design/features/feature-13-record-the-history-in-the-background.md)
- [Feature 14: Exported statistics describe their devices](design/features/feature-14-exported-statistics-describe-their-devices.md)
- [Feature 15: Separate installs: `proccoli` and `proccoli-gui`](design/features/feature-15-separate-installs-proccoli-and-proccoli-gui.md)
- [Feature 16: A Web GUI, hosted locally (brainstorm)](design/features/feature-16-a-web-gui-hosted-locally.md)
- [Feature 17: The Web GUI for machines on the local network (brainstorm)](design/features/feature-17-the-web-gui-for-machines-on.md)
- [Feature 18: Overview pages for groups of devices](design/features/feature-18-overview-pages-for-groups-of-devices.md)
- [Feature 19: The window reads nothing: `proccoli` serves every reading](design/features/feature-19-the-window-reads-nothing-proccoli-serves.md)
- [Feature 20: Preferences in named sections](design/features/feature-20-preferences-in-named-sections.md)
- [Feature 21: Refactoring candidates](design/features/feature-21-refactoring-candidates.md)
- [Feature 22: Recording from boot (lingering)](design/features/feature-22-recording-from-boot.md)
- [Feature 23: Icons Only on narrow windows](design/features/feature-23-icons-only-on-narrow-windows.md)
- [Feature 25: A recorder for the whole machine](design/features/feature-25-a-recorder-for-the-whole-machine.md)
- [Feature 26: Releases and Features instead of Milestones and Ideas](design/features/feature-26-releases-and-features.md)
- [Feature 27: Always-current UML and database design docs](design/features/feature-27-uml-and-database-design-docs.md)
- [Feature 28: VOICE.md and AUDIENCE.md](design/features/feature-28-voice-and-audience.md)
- [Feature 29: General engineering skills under a Proccoli skill](design/features/feature-29-engineering-skills.md)
- [Feature 30: Network sidebar graphs scaled to the link speed](design/features/feature-30-network-graphs-scaled-to-link-speed.md)
- [Feature 31: Preferences' Sidebar Style lists every mode](design/features/feature-31-sidebar-style-in-preferences-lists-every-mode.md)
- [Feature 32: Graph Type, per sidebar entry](design/features/feature-32-graph-type-per-sidebar-entry.md)
- [Feature 33: A page's graphs sized as a group](design/features/feature-33-pane-graphs-sized-as-a-group.md)
- [Feature 34: F2 for Preferences, F1 for Keyboard Shortcuts](design/features/feature-34-f1-and-f2-shortcuts.md)
- [Feature 35: Optional sidebar groups](design/features/feature-35-optional-sidebar-groups.md)
- [Feature 36: Meters on collapsed groups](design/features/feature-36-meters-on-collapsed-groups.md)
- [Feature 37: The `software-prototype` skill](design/features/feature-37-software-prototype-skill.md)
- [Feature 38: Cheaper test runs](design/features/feature-38-cheaper-test-runs.md)

### Features that Require Human Input

NOTE: Keep this subsection but move Features to a proper index after human input has been given to clarify the feature.

*None waiting.* The last ones were settled as Features 26–34.

## Bugs' design notes

The cause and the fix design of each bug; the plan side is linked from each.

- [Bug 1: Graphs stretch old points after a time range change](design/bugs/bug-01-graphs-stretch-old-points-after-a.md) (fixed)
- [Bug 2: An APU's package power shown as the GPU's](design/bugs/bug-02-an-apu-s-package-power-shown.md) (fixed)
- [Bug 3: An APU's graphics memory shown as the carve-out alone](design/bugs/bug-03-an-apu-s-graphics-memory-shown.md) (fixed)
- [Bug 4: AMD processes' video memory counted twice](design/bugs/bug-04-amd-processes-video-memory-counted-twice.md) (fixed)
- [Bug 5: The README installed an old version](design/bugs/bug-05-the-readme-installed-an-old-version.md) (fixed)
- [Bug 6: An AMD GPU's fdinfo was read twice per update](design/bugs/bug-06-an-amd-gpu-s-fdinfo-was.md) (fixed)
- [Bug 7: The collector's process name was cut short](design/bugs/bug-07-the-collector-s-process-name-was.md) (fixed)
- [Bug 8: Lightweight Mode froze the window at start](design/bugs/bug-08-lightweight-mode-froze-the-window-at.md) (fixed)
- [Bug 9: A window's graphs missed the collector's last seconds](design/bugs/bug-09-a-window-s-graphs-missed-the.md) (fixed)
- [Bug 10: The Lightweight switch showed the setting, not the mode](design/bugs/bug-10-the-lightweight-switch-showed-the-setting.md) (fixed)
- [Bug 11: Lightweight Mode's Processor and Memory pages were blank](design/bugs/bug-11-lightweight-mode-s-processor-and-memory.md) (fixed)
- [Bug 12: A test started the installed collector](design/bugs/bug-12-a-test-started-the-installed-collector.md) (fixed)
- [Bug 13: The Overview's tables changed width with their contents](design/bugs/bug-13-the-overview-s-tables-changed-width.md) (fixed)
- [Bug 14: *Restart Now* renamed the window "python3"](design/bugs/bug-14-restart-now-renamed-the-window-python3.md) (fixed)
- [Bug 15: A second recorder waits instead of leaving](design/bugs/bug-15-a-second-recorder-waits-instead-of.md) (fixed)
- [Bug 16: A recorder stopped by a signal isn't started again](design/bugs/bug-16-a-recorder-stopped-by-a-signal.md) (fixed)
- [Bug 17: Graphs from the history miss a point every few minutes](design/bugs/bug-17-graphs-from-the-history-miss-a.md) (fixed)
- [Bug 18: A Time Range change shows the last seconds as "not running"](design/bugs/bug-18-a-time-range-change-shows-the.md) (fixed)
- [Bug 19: An idle Intel GPU's Overview card is a blank chart](design/bugs/bug-19-an-idle-intel-gpu-s-overview.md) (fixed)
- [Bug 20: A chart with no readings is drawn blank](design/bugs/bug-20-a-chart-with-no-readings-is.md) (fixed)
- [Bug 21: An NVIDIA GPU too new for pci.ids is named "NVIDIA GPU"](design/bugs/bug-21-an-nvidia-gpu-too-new-for.md) (fixed)
- [Bug 22: The window freezes after unlocking or waking from suspend](design/bugs/bug-22-the-window-freezes-after-unlocking-or.md) (fixed)
- [Bug 23: Dialogs stack on every press](design/bugs/bug-23-preferences-and-other-dialogs-stack.md) (fixed)
- [Bug 24: Memory grows each time Preferences opens](design/bugs/bug-24-memory-grows-each-time-preferences-opens.md) (open)


### Bugs that Require Human Input

NOTE: Keep this subsection but move Bugs to a proper index after human input has been given to clarify the bug.

*None waiting.* The memory leak became Bugs 23 and 24.

