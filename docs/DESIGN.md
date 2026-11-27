# Proccoli: Design

How Proccoli is put together: what it copies from Resources, where it
deliberately differs (the swappable GPU page), the layers of the
application, and the classes in each layer. [PLAN.md](PLAN.md) gives the
order in which to build it.

**How these docs are kept:** this page is an index. Each section is its
own file under `design/` (a long section is split by subsection:
`design/09.2-*.md`), and each idea's and bug's design note is
`design/ideas/idea-19-*.md` or `design/bugs/bug-22-*.md`, numbered like
the plan. Read this page, then only the sections a change touches.

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
  - [7.5 AMD (M70)](design/07.5-amd.md)
- [8. Processes and Apps](design/08-processes-and-apps.md)
- [9. UI layer](design/09-ui-layer.md)
  - [9.1 Widgets](design/09.1-widgets.md)
  - [9.2 Window behaviour (mirrors Resources)](design/09.2-window-behaviour.md)
  - [9.3 Appearance](design/09.3-appearance.md)
  - [9.4 Optional authentication at launch](design/09.4-optional-authentication-at-launch.md)
  - [9.5 Sidebar preferences](design/09.5-sidebar-preferences.md)
  - [9.6 Overview page (M39, M41, M50, M51; Lightweight Mode M71)](design/09.6-overview-page.md)
  - [9.7 Error pages (M55)](design/09.7-error-pages.md)
- [10. Runtime flow](design/10-runtime-flow.md)
- [11. Cross-cutting concerns](design/11-cross-cutting-concerns.md)
- [12. Open decisions](design/12-open-decisions.md)

## Ideas' design notes

Designed but not built, or the design record of an idea that was; the plan side (steps, status) is linked from each.

- [Idea 1: Lightweight mode (minimal memory)](design/ideas/idea-01-lightweight-mode.md)
- [Idea 2: Metrics history in a SQLite database](design/ideas/idea-02-metrics-history-in-a-sqlite-database.md)
- [Idea 3: Intel Details graphs on the shared chart code](design/ideas/idea-03-intel-details-graphs-on-the-shared.md)
- [Idea 4: One chart family everywhere](design/ideas/idea-04-one-chart-family-everywhere.md)
- [Idea 5: Switch To any running app](design/ideas/idea-05-switch-to-any-running-app.md)
- [Idea 7: Export any part of the history](design/ideas/idea-07-export-any-part-of-the-history.md)
- [Idea 8: Lightweight Mode: small charts on the Overview, a minimal sidebar](design/ideas/idea-08-lightweight-mode-small-charts-on-the.md)
- [Idea 9: Custom graph time range](design/ideas/idea-09-custom-graph-time-range.md)
- [Idea 10: Shade the time Proccoli wasn't running](design/ideas/idea-10-shade-the-time-proccoli-wasn-t.md)
- [Idea 11: A shorter, friendlier README](design/ideas/idea-11-a-shorter-friendlier-readme.md)
- [Idea 12: A graph toolbar](design/ideas/idea-12-a-graph-toolbar.md)
- [Idea 13: Record the history in the background](design/ideas/idea-13-record-the-history-in-the-background.md)
- [Idea 14: Exported statistics describe their devices](design/ideas/idea-14-exported-statistics-describe-their-devices.md)
- [Idea 15: Separate installs: `proccoli` and `proccoli-gui`](design/ideas/idea-15-separate-installs-proccoli-and-proccoli-gui.md)
- [Idea 16: A Web GUI, hosted locally (brainstorm)](design/ideas/idea-16-a-web-gui-hosted-locally.md)
- [Idea 17: The Web GUI for machines on the local network (brainstorm)](design/ideas/idea-17-the-web-gui-for-machines-on.md)
- [Idea 18: Overview pages for groups of devices](design/ideas/idea-18-overview-pages-for-groups-of-devices.md)
- [Idea 19: The window reads nothing: `proccoli` serves every reading](design/ideas/idea-19-the-window-reads-nothing-proccoli-serves.md)
- [Idea 20: Preferences in named sections](design/ideas/idea-20-preferences-in-named-sections.md)
- [Idea 21: Refactoring candidates](design/ideas/idea-21-refactoring-candidates.md)
- [Idea 22: Recording from boot (lingering)](design/ideas/idea-22-recording-from-boot.md)
- [Idea 23: Icons Only on narrow windows](design/ideas/idea-23-icons-only-on-narrow-windows.md)
- [Idea 25: A recorder for the whole machine](design/ideas/idea-25-a-recorder-for-the-whole-machine.md)

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
- [Bug 18: A Time Range change shows the last seconds as "not running"](design/bugs/bug-18-a-time-range-change-shows-the.md) (open)
- [Bug 19: An idle Intel GPU's Overview card is a blank chart](design/bugs/bug-19-an-idle-intel-gpu-s-overview.md) (fixed)
- [Bug 20: A chart with no readings is drawn blank](design/bugs/bug-20-a-chart-with-no-readings-is.md) (fixed)
- [Bug 21: An NVIDIA GPU too new for pci.ids is named "NVIDIA GPU"](design/bugs/bug-21-an-nvidia-gpu-too-new-for.md) (open)
- [Bug 22: The window freezes after unlocking or waking from suspend](design/bugs/bug-22-the-window-freezes-after-unlocking-or.md) (open)
