# Proccoli: Build Plan

The index of an incremental plan. Each milestone adds **one** capability
on top of a working app, lists **what to create, in order** with the test
that proves each piece, and ends with a **definition of done** a user can
check with `make run` (or `make demo`).

**How these docs are kept:** this page and [DESIGN.md](DESIGN.md) are
indexes. Each milestone, idea and bug is its own file, linked below and
named after its number, so it can be opened directly:
`plan/milestones/M53-*.md`, `plan/ideas/idea-19-*.md`,
`plan/bugs/bug-22-*.md`. Read this page, then only the files a change
needs.

**Working rules for every milestone**

1. Write the test with (or before) the class. Domain and core code must be
   testable without a display.
2. Every `/proc` and `/sys` read goes through `SysRoot`, so its test uses a
   fixture tree under `tests/fixtures/`. Capture fixtures from real machines
   with `tests/fixtures/capture.sh` (Milestone 2).
3. UI code gets a **smoke test**: build the widget and feed it a snapshot, on
   the headless Broadway backend (`GDK_BACKEND=broadway`, `make ui-test`).
   Visual checks use the screenshot script from Milestone 1.
4. `make test` stays green at the end of every step, not only at the end of
   each milestone.
5. Commit at the end of every numbered step.

## Current state

Tests: 1199, all passing on the headless display (`make ui-test`; on
GTK 4.14, 3 skip because they need a window taller than the 1024×768
headless screen, see M53). A plain `make test` runs the 903 that need no
display and skips the rest, so it never opens windows on your desktop.

**Platform floor:** Ubuntu 24.04 (Python 3.12, GTK 4.14, libadwaita 1.5,
GLib 2.80, PyGObject 3.48) is tested on a real 24.04 machine since M53.
Newer APIs go through `ui/compat.py` or a `hasattr` check, and
`tests/test_static.py` enforces this for libadwaita.

**Tools:**
- `tests/ui/shoot.py --real`: screenshots, including this machine's own
  devices and processes.
- `tests/ui/perf.py`: Proccoli's own CPU use.

## Open bugs

Found but not fixed. Each is fixed as its own change, with a regression test; each file has the cause and the steps, and links to its design note.

- 🐞 [Bug 18: Changing the Time Range shows the last seconds as "not running"](plan/bugs/bug-18-changing-the-time-range-shows-the.md)
- 🐞 [Bug 21: An NVIDIA GPU too new for pci.ids is named "NVIDIA GPU"](plan/bugs/bug-21-an-nvidia-gpu-too-new-for.md)
- 🐞 [Bug 22: The window freezes after unlocking or waking from suspend](plan/bugs/bug-22-the-window-freezes-after-unlocking-or.md)

Fixed: [1](plan/bugs/bug-01-graphs-stretch-old-points-after-a.md) (M68), [2](plan/bugs/bug-02-an-amd-apu-s-package-power.md) (M69), [3](plan/bugs/bug-03-an-amd-apu-s-graphics-memory.md) (M69), [4](plan/bugs/bug-04-amd-processes-video-memory-is-counted.md) (M69), [5](plan/bugs/bug-05-the-readme-installs-an-old-version.md) (M69), [6](plan/bugs/bug-06-an-amd-gpu-s-fdinfo-is.md) (M75), [7](plan/bugs/bug-07-the-collector-s-process-name-is.md) (M77), [8](plan/bugs/bug-08-lightweight-mode-froze-the-window-at.md) (M79), [9](plan/bugs/bug-09-a-window-s-graphs-miss-the.md) (M81), [10](plan/bugs/bug-10-the-lightweight-switch-shows-the-setting.md) (M81), [11](plan/bugs/bug-11-lightweight-mode-s-processor-and-memory.md) (M81), [12](plan/bugs/bug-12-a-test-started-the-installed-collector.md) (M82), [13](plan/bugs/bug-13-the-overview-s-tables-change-width.md) (M82), [14](plan/bugs/bug-14-after-restart-now-the-window-is.md) (M84), [15](plan/bugs/bug-15-a-second-recorder-waits-around-instead.md) (M86), [16](plan/bugs/bug-16-a-recorder-stopped-by-a-signal.md) (M86), [17](plan/bugs/bug-17-one-point-gaps-every-few-minutes.md) (M87), [19](plan/bugs/bug-19-an-idle-intel-gpu-s-overview.md) (M87), [20](plan/bugs/bug-20-a-chart-with-no-readings-is.md) (M87).

## Ideas

Designed but not scheduled. Each becomes the next milestone when picked up.

- 💡 [Idea 7: Export Statistics for the session or the whole saved history](plan/ideas/idea-07-export-statistics-for-the-session-or.md): *Export Statistics…* for this session, the last hour/day/week, or all saved history
- 💡 [Idea 11: A shorter, friendlier README](plan/ideas/idea-11-a-shorter-friendlier-readme.md): a short README around what people want to do, with screenshots
- 💡 [Idea 16: A Web GUI, hosted locally (brainstorm)](plan/ideas/idea-16-a-web-gui-hosted-locally.md): a browser view served by the recorder on this machine (brainstorm)
- 💡 [Idea 17: The Web GUI for machines on the local network (brainstorm)](plan/ideas/idea-17-the-web-gui-for-machines-on.md): one Web GUI for several machines on the local network (brainstorm)
- 💡 [Idea 18: Overview pages for groups of devices](plan/ideas/idea-18-overview-pages-for-groups-of-devices.md): a group entry and overview page per kind (GPUs, Drives, Network, Batteries)
- 🚧 [Idea 19: The window reads nothing: `proccoli-metrics` serves every reading](plan/ideas/idea-19-the-window-reads-nothing-proccoli-metrics.md): the window reads nothing itself: 19a and 19b done (M78, M79), 19c left
- 💡 [Idea 21: Refactoring candidates](plan/ideas/idea-21-refactoring-candidates.md): places to restructure; R1–R3 done in M84
- 💡 [Idea 23: Icons Only on narrow windows](plan/ideas/idea-23-icons-only-on-narrow-windows.md): a narrow window keeps a narrow sidebar before hiding it
- 💡 [Idea 25: A recorder for the whole machine](plan/ideas/idea-25-a-recorder-for-the-whole-machine.md): one system recorder and history from boot, for everyone (Idea 22's option C)

Built: [1](plan/ideas/idea-01-lightweight-mode.md) (M66), [2](plan/ideas/idea-02-metrics-history-in-a-sqlite-database.md) (M62), [3](plan/ideas/idea-03-intel-details-graphs-on-the-shared.md) (M60), [4](plan/ideas/idea-04-one-chart-family-everywhere.md) (M63), [5](plan/ideas/idea-05-switch-to-any-running-app.md) (M67), [6](plan/ideas/idea-06-update-interval-instead-of-refresh-speed.md) (M65), [8](plan/ideas/idea-08-lightweight-mode-small-charts-on-the.md) (M71), [9](plan/ideas/idea-09-custom-graph-time-range.md) (M74), [10](plan/ideas/idea-10-shade-the-time-proccoli-wasn-t.md) (M68), [12](plan/ideas/idea-12-a-graph-toolbar.md) (M72), [13](plan/ideas/idea-13-record-the-history-in-the-background.md) (M75), [14](plan/ideas/idea-14-exported-statistics-describe-their-devices.md) (M73), [15](plan/ideas/idea-15-separate-installs-proccoli-metrics-and-proccoli.md) (M76), [24](plan/ideas/idea-24-docs-as-indexes-with-one-file.md) (M85), [20](plan/ideas/idea-20-preferences-in-named-sections.md) (M88), [22](plan/ideas/idea-22-recording-from-boot.md) (M89).

## Milestones

### Foundations (M0–M16)

The window and a page per device (processor, memory, drives, network, GPU, battery), processes and apps, the administrator helper, Preferences, packaging; dependency injection and the GPU's summary and detail sources ([early deviations](plan/early-deviations.md)).

- ✅ [M0 Project skeleton](plan/milestones/M0-project-skeleton.md)
- ✅ [M1 Window shell (sidebar + stack, no data)](plan/milestones/M1-window-shell.md)
- ✅ [M2 Core services](plan/milestones/M2-core-services.md)
- ✅ [M3 Graph widgets](plan/milestones/M3-graph-widgets.md)
- ✅ [M4 Processor page](plan/milestones/M4-processor-page.md)
- ✅ [M5 Memory page](plan/milestones/M5-memory-page.md)
- ✅ [M6 Drives](plan/milestones/M6-drives.md)
- ✅ [M7 Network interfaces](plan/milestones/M7-network-interfaces.md)
- ✅ [M8 GPU abstraction + generic GPU page](plan/milestones/M8-gpu-abstraction-generic-gpu-page.md)
- ✅ [M9 intel_gpu_top backend + detailed page](plan/milestones/M9-intel-gpu-top-backend-detailed-page.md)
- ✅ [M10 Processes page](plan/milestones/M10-processes-page.md)
- ✅ [M11 Apps page](plan/milestones/M11-apps-page.md)
- ✅ [M12 Dialogs + privileged helper](plan/milestones/M12-dialogs-privileged-helper.md)
- ✅ [M13 Preferences](plan/milestones/M13-preferences.md)
- ✅ [M14 Battery](plan/milestones/M14-battery.md)
- ✅ [M15 Packaging and polish](plan/milestones/M15-packaging-and-polish.md)
- 🟡 [M16+ More GPU backends](plan/milestones/M16-more-gpu-backends.md)

### Look and feel (M17–M38)

Styles, palettes, icons, sidebar charts, colors and preferences per entry, graphs that fill the page, the rename to Proccoli and its logo.

- ✅ [M17 Light/dark style follows the system](plan/milestones/M17-light-dark-style-follows-the-system.md)
- ✅ [M18 Color palettes](plan/milestones/M18-color-palettes.md)
- ✅ [M19 Sidebar area charts](plan/milestones/M19-sidebar-area-charts.md)
- ✅ [M20 App icons in Apps and Processes](plan/milestones/M20-app-icons-in-apps-and-processes.md)
- ✅ [M21 Sidebar icons](plan/milestones/M21-sidebar-icons.md)
- ✅ [M22 Graphs fill the page](plan/milestones/M22-graphs-fill-the-page.md)
- ✅ [M23 Memory type (DDR) without a password](plan/milestones/M23-memory-type-without-a-password.md)
- ✅ [M24 Solid puzzle-piece icon](plan/milestones/M24-solid-puzzle-piece-icon.md)
- ✅ [M25 A color per sidebar entry](plan/milestones/M25-a-color-per-sidebar-entry.md)
- ✅ [M26 Optional authentication at launch](plan/milestones/M26-optional-authentication-at-launch.md)
- ✅ [M27 App icons in the GPU Processes tab](plan/milestones/M27-app-icons-in-the-gpu-processes.md)
- ✅ [M28 Rearrange and minimise sidebar entries](plan/milestones/M28-rearrange-and-minimise-sidebar-entries.md)
- ✅ [M29 Axes on percentage graphs](plan/milestones/M29-axes-on-percentage-graphs.md)
- ✅ [M30 Memory speed in the sidebar](plan/milestones/M30-memory-speed-in-the-sidebar.md)
- ✅ [M31 Per-entry sidebar details](plan/milestones/M31-per-entry-sidebar-details.md)
- ✅ [M32 App context menu and Switch To](plan/milestones/M32-app-context-menu-and-switch-to.md)
- ✅ [M33 More styles (ExpressVPN-like)](plan/milestones/M33-more-styles.md)
- ✅ [M34 Diagnostics log file](plan/milestones/M34-diagnostics-log-file.md)
- ✅ [M35 Sidebar preferences per entry](plan/milestones/M35-sidebar-preferences-per-entry.md)
- ✅ [M36 Graphs for portrait and landscape screens](plan/milestones/M36-graphs-for-portrait-and-landscape-screens.md)
- ✅ [M37 Rename to Proccoli](plan/milestones/M37-rename-to-proccoli.md)
- ✅ [M38 Proccoli logo](plan/milestones/M38-proccoli-logo.md)

### The Overview and a sturdier window (M39–M55)

The Overview page, the security review, the stall watchdog, navigation (Go To, back and forward, collapsible and icons-only sidebar), Ubuntu 24.04 support, GPU detection and error pages.

- ✅ [M39 Overview page](plan/milestones/M39-overview-page.md)
- ✅ [M40 Security review of what runs as administrator](plan/milestones/M40-security-review-of-what-runs-as.md)
- ✅ [M41 Busiest apps and processes on the Overview](plan/milestones/M41-busiest-apps-and-processes-on-the.md)
- ✅ [M42 Stop the root intel_gpu_top with Proccoli](plan/milestones/M42-stop-the-root-intel-gpu-top.md)
- ✅ [M43 Right-click menus froze the window](plan/milestones/M43-right-click-menus-froze-the-window.md)
- ✅ [M44 Stall watchdog](plan/milestones/M44-stall-watchdog.md)
- ✅ [M45 User-guide README; previous name removed](plan/milestones/M45-user-guide-readme-previous-name-removed.md)
- ✅ [M46 Collapsible sidebar, burger top left](plan/milestones/M46-collapsible-sidebar-burger-top-left.md)
- ✅ [M47 Logo in the top-left corner](plan/milestones/M47-logo-in-the-top-left-corner.md)
- ✅ [M48 Go To submenu](plan/milestones/M48-go-to-submenu.md)
- ✅ [M49 Back and forward](plan/milestones/M49-back-and-forward.md)
- ✅ [M50 Overview charts fill the page](plan/milestones/M50-overview-charts-fill-the-page.md)
- ✅ [M51 Overview charts never taller than wide](plan/milestones/M51-overview-charts-never-taller-than-wide.md)
- ✅ [M52 Sidebar toggle in the main menu](plan/milestones/M52-sidebar-toggle-in-the-main-menu.md)
- ✅ [M53 Runs on Ubuntu 24.04](plan/milestones/M53-runs-on-ubuntu-24-04.md)
- ✅ [M54 Icons-only sidebar](plan/milestones/M54-icons-only-sidebar.md)
- ✅ [M55 GPU detection, error pages, NVIDIA, per-CPU chart, Overview at launch, UTC log](plan/milestones/M55-gpu-detection-error-pages-nvidia-per.md)

### Charts and the history (M57–M74)

One chart family, the SQLite history, Update Interval, Lightweight Mode, honest graph time, AMD statistics, the graph toolbar, exports and custom ranges.

- ✅ [M57 Per-CPU chart keeps the area; readings on the Overview cards](plan/milestones/M57-per-cpu-chart-keeps-the-area.md)
- ✅ [M58 Legend clicks, graph time range, statistics files](plan/milestones/M58-legend-clicks-graph-time-range-statistics.md)
- ✅ [M59 Reusable many-line chart; a chart never shows nothing](plan/milestones/M59-reusable-many-line-chart-a-chart.md)
- ✅ [M60 Intel Details graphs on the shared chart code](plan/milestones/M60-intel-details-graphs-on-the-shared.md)
- ✅ [M61 The logo is the main menu; hover in the user's units](plan/milestones/M61-the-logo-is-the-main-menu.md)
- ✅ [M62 The history database](plan/milestones/M62-the-history-database.md)
- ✅ [M63 One chart family everywhere](plan/milestones/M63-one-chart-family-everywhere.md)
- ✅ [M64 History follow-ups](plan/milestones/M64-history-follow-ups.md)
- ✅ [M65 Update Interval instead of Refresh Speed](plan/milestones/M65-update-interval-instead-of-refresh-speed.md)
- ✅ [M66 Lightweight mode](plan/milestones/M66-lightweight-mode.md)
- ✅ [M67 Switch To any running app](plan/milestones/M67-switch-to-any-running-app.md)
- ✅ [M68 Honest graph time](plan/milestones/M68-honest-graph-time.md)
- ✅ [M69 Honest GPU readings on AMD APUs; README version](plan/milestones/M69-honest-gpu-readings-on-amd-apus.md)
- ✅ [M70 AMD detailed statistics](plan/milestones/M70-amd-detailed-statistics.md)
- ✅ [M71 Lightweight Mode: small charts on the Overview, a minimal sidebar](plan/milestones/M71-lightweight-mode-small-charts-on-the.md)
- ✅ [M72 Graph toolbar](plan/milestones/M72-graph-toolbar.md)
- ✅ [M73 Exports describe their devices](plan/milestones/M73-exports-describe-their-devices.md)
- ✅ [M74 Custom graph time range](plan/milestones/M74-custom-graph-time-range.md)

### The background recorder, and upkeep (M75–M89)

`proccoli` records the history as a user service and serves every reading over D-Bus; separate installs; Lightweight Mode on Cairo; styles; 0.5.0; refactors; the docs split into indexes; one recorder per user, restarted after any exit; Preferences in six pages; recording from boot offered.

- ✅ [M75 Record the history in the background](plan/milestones/M75-record-the-history-in-the-background.md)
- ✅ [M76 Separate installs: `proccoli-metrics` and `proccoli-gui`](plan/milestones/M76-separate-installs-proccoli-metrics-and-proccoli.md)
- ✅ [M77 The collector's name and app](plan/milestones/M77-the-collector-s-name-and-app.md)
- ✅ [M78 The collector serves every reading (Idea 19a)](plan/milestones/M78-the-collector-serves-every-reading.md)
- ✅ [M79 The window reads from the collector (Idea 19b)](plan/milestones/M79-the-window-reads-from-the-collector.md)
- ✅ [M80 Pane graphs and sidebar graphs](plan/milestones/M80-pane-graphs-and-sidebar-graphs.md)
- ✅ [M81 Lightweight Mode draws with Cairo; gaps, the switch, references](plan/milestones/M81-lightweight-mode-draws-with-cairo-gaps.md)
- ✅ [M82 Palettes, padlocks, steady tables, no stray collectors](plan/milestones/M82-palettes-padlocks-steady-tables-no-stray.md)
- ✅ [M83 More styles; the programs renamed; 0.5.0](plan/milestones/M83-more-styles-the-programs-renamed-0.md)
- ✅ [M84 Restart keeps its name; three refactors](plan/milestones/M84-restart-keeps-its-name-three-refactors.md)
- ✅ [M85 The docs as indexes, one file per topic](plan/milestones/M85-docs-as-indexes.md)
- ✅ [M86 One recorder per user, restarted after any exit](plan/milestones/M86-one-recorder-restarted-after-any-exit.md)
- ✅ [M87 Steady ticks, idle Intel GPUs, "No data"](plan/milestones/M87-steady-ticks-idle-intel-gpus-no-data.md)
- ✅ [M88 Preferences in six named pages](plan/milestones/M88-preferences-in-six-named-pages.md)
- ✅ [M89 Recording from boot, offered once](plan/milestones/M89-record-from-boot-offered-once.md)
