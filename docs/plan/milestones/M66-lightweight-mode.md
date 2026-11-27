# Milestone 66: Lightweight mode

*✅ Done.* Was Idea 1. Pages built on visit and dropped after, the Overview a list, one graph per page, no icons or GPU details; about 55 % less private memory at start, about 35 % after visiting every page

Was Idea 1 (kept below with the measurements that shaped it). Its open
questions were settled with its own recommendations: the mode applies at
the next start (Preferences offers *Restart Now*), the Overview stays the
start page as a compact list, and Apps and Processes stay (built on
visit, without icons).

| Step | Create / change | Test |
|---|---|---|
| 66.1 | `core/profile.py`: `Profile` (`full()`, `lightweight()`: `lazy_pages`, `page_drop_s`, `overview_charts`, `overview_tables`, `extra_graphs`, `app_icons`, `gpu_details`, `pci_on_demand`, `theme_css`, `keep_process_data`, `pins`), `choose_profile`, `ProfileSettings` (the same store; pinned keys answered by the profile, also in change notifications; `bind` on a pinned key only shows it), `profile_settings`, `is_pinned`, `profile_of`. Schema `lightweight`; `--lightweight`; `Application` picks the profile once and hands out the profile's settings; `AppContext.profile` | Unit: both profiles, the setting and the flag, every pin, the user's choice kept, notifications, full profile untouched |
| 66.2 | Pins: *Graph Time Range* at most 1 minute, no axes or grids, no per-CPU chart, progress-bar sidebar meters, Follow System and the System palette, log at most *Warnings* and no performance lines, table columns cut to name, ID, processor and memory | Unit: pins and kept columns; Preferences greys pinned rows out |
| 66.3 | `pciids.on_demand()` / `OnDemandPciIds`: scans one vendor's block per new question, keeps only answers | Unit: the same answers as the full parse on the fixture |
| 66.4 | `ui/summaries.py` (`summary_for`, `sort_name_for`): an entry's summary from its monitor alone, which device pages now use too (the network, processor and GPU overrides went). `ui/lazy.py`: `StubPage`, `LazyPages` (build on first visit, drop `page_drop_s` = 60 s after leaving; `schedule` injected); the window swaps them with `replace_page`, for devices and for Apps and Processes | Unit: build, keep when coming back in time, drop, removal; UI: a stub until visited, the real page after, the stub again after the timer, entry and color kept |
| 66.5 | `OverviewPage(profile)`: cards without charts in a 3-column list, no busiest tables; `OverviewCard(chart=False)` | UI: no `Graph` on the Overview, no tables |
| 66.6 | `DevicePage.add_graph`: only the first graph is drawn; the others are hidden and keep their title and figures as text (`text_only`). The CPU page's *Show Usages of Logical CPUs* switch is insensitive | UI: one graph, no axes |
| 66.7 | `ctx.app_icons = None`; `table.shown_column` drops the icon from the name column | Unit |
| 66.8 | No `ThemeCss`; GPU detail sources not started (`GpuController` says why) | UI (the app); unit (the controller) |
| 66.9 | `ProcessMonitor.release`: with nobody showing the list, its data is dropped (`keep_process_data`) | Unit |
| 66.10 | Preferences → General → *Memory Use*: *Lightweight Mode* and *Restart Now* (`app.restart`: quits as usual, then `main` runs `System.restart_self`) | Dialog tests; app test |
| 66.11 | `tests/ui/mem.py`: both profiles in fresh processes, RssAnon after start, after visiting every page, after the drop timer; README *Lightweight mode*, [Idea 1's design](../../design/ideas/idea-01-lightweight-mode.md) as built | Run (below) |

**Measured with 66.11** on this machine (headless display; RssAnon, MiB;
the full profile varies by about 10 MiB between runs):

| | Full | Lightweight | Saved |
|---|---|---|---|
| Started, on the Overview | 78–90 | 37.8 | about 55 % |
| After visiting every page | 91–95 | 61–62 | about 35 % |
| After the pages were dropped again | 84–104 | 61–62 | about 30–40 % |

Most of what remains after a visit is the Processes page (about 14 MiB
with the cut columns; 20 MiB before them): dropped pages are freed, but
glibc and GTK keep the freed memory for reuse rather than giving it back
(a `gc.collect()` plus `malloc_trim(0)` gives back about 3 MiB). So the
40 % target is met while Proccoli stays on its Overview, which is how
it's typically left running, not after a tour of every page.

**Deviations from Idea 1, and why:**

- **Pinned settings instead of a profile passed to every page.** What the
  mode changes is mostly what preferences already control (time range,
  axes, grids, style, palette, logical CPUs, log level, meters, columns);
  `ProfileSettings` pins those, and only what has no preference
  (lazy pages, the Overview, icons, GPU details, pci.ids, the theme CSS,
  process data) reads `Profile` flags. Pages need no new parameters.
- **Sidebar meters are progress bars**, not text only: a progress bar
  costs almost nothing and keeps the entries readable.
- **Extra graphs are hidden, not replaced** by `InfoRow`s: their card
  keeps its title and figures, so each page needed no change.
- **Table columns are cut too** (not in the plan): the Processes page was
  the largest single cost.
- **Not changed:** the renderer (`GSK_RENDERER`), which would need
  setting before GTK starts; it wasn't measured on a desktop session.
  *Show All Details…* only offers what built pages can unlock.
