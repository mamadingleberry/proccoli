# Feature 1: Lightweight mode (minimal memory)

Design note: [design/features/feature-01-lightweight-mode.md](../../design/features/feature-01-lightweight-mode.md)

*Done as v0.3.0 (what changed from this plan is listed there).*

*Was v0.2.0. Steps are numbered L.1–L.11 so they don't clash with
milestones; when it's picked up, it becomes the next milestone.*

**Goal:** a mode that keeps Proccoli's memory as low as it can while still
showing the basic figures: processor, memory, GPU, drive, network and
battery usage, and the process list. It uses the system style and palette,
minimal graphs, no app or process icons, and leaves out anything else not
needed for those figures.

**Where the memory goes now** (measured on this machine, Ubuntu 24.04,
headless display; private memory, `RssAnon`):

| Stage | RssAnon | Python heap |
|---|---|---|
| GTK + libadwaita initialised, empty window | 15–17 MB | – |
| Proccoli's modules imported | 23 MB | 4 MB |
| Context built (pci.ids parsed: 3.6 MB of Python objects) | 40 MB | 8 MB |
| Window built (every page, all built at start) | 53 MB | 10 MB |
| Shown and running for 8 s | ~100 MB | 12 MB |

Total resident memory is about 153 MB, against 61 MB for an empty
libadwaita window. Most of the difference is **GTK's own memory**, not
Python's: the widget trees of every page (built at start, even unseen),
and what drawing them leaves behind (render nodes, glyph and icon caches,
textures). So the mode saves most by **not building, and not drawing,
what isn't on screen**, and by drawing less.

**Design ([Feature 1's design](../../design/features/feature-01-lightweight-mode.md) has the details):**

- One setting, `lightweight` (boolean, off by default). Preferences →
  General → *Lightweight Mode*, and `--lightweight` on the command line.
  The choice changes what the composition root builds, so it applies at
  the next start; Preferences offers *Restart Now*.
- `build_context` reads it and passes a `Profile` (frozen dataclass:
  `full()` and `lightweight()`) to everything it builds; pages and
  widgets read the profile, never the setting. Tests build either profile.
- What lightweight turns off or down:

| Area | Full | Lightweight | Why it saves memory |
|---|---|---|---|
| Pages | Built at start | Built on first visit (`LazyPage` placeholder) and dropped 60 s after leaving (except the Overview) | Widget trees and their render caches exist only for the page on screen |
| Sidebar | Chart per entry | Usage text only (no meters) | No drawing area or render nodes per entry |
| Overview | Chart cards + busiest tables | Compact list: name and usage text per device; no busiest tables | No charts, and no process scan for the Overview |
| Page graphs | Graphs with axes, grid option, the chosen *Graph Time Range* | One graph per page (the main usage); at most 1 minute (since v0.2.0 the range sets the points); no axes; other figures as text rows. With Feature 2, longer ranges come from disk instead of memory | Fewer drawing areas, shorter histories |
| Per-CPU chart | One line per CPU + legend | Off (*Show Usages of Logical CPUs* hidden) | 24 series and a legend gone |
| Style, palette | User's choice, tinted styles, palette CSS | Follow System and the System palette; no `ThemeCss` provider | No extra CSS providers or recoloring |
| App and process icons | Icon per row (themed lookups, textures) | None (no icon column) | No icon textures |
| GPU detail sources | Started if allowed (intel_gpu_top stream, NVIDIA polling) | Not started; Details tabs say how to turn them on | No extra process, stream parsing or history |
| pci.ids | Parsed whole at start | Looked up on demand (scan for the IDs needed, keep only those) | About 3.6 MB of Python objects |
| Diagnostics | Debug level, performance lines, watchdog | Warning level, no performance lines; watchdog kept (cheap) | Fewer log records and formatting |
| Process scan | While Apps/Processes/Overview tables show | Only while Apps or Processes shows | – (CPU, not memory) |

- **Kept:** the sidebar with every device; each device page's main usage
  graph and its figures as text; Apps and Processes tables (no icons) with
  their actions; the error pages; detection of every GPU (summary source).
- **Measured, not assumed:** a new `tests/ui/mem.py` reports RssAnon after
  start, after visiting every page, and after 10 minutes, in both
  profiles, on the headless display and on a real desktop session (where
  the GL renderer adds its own memory). Target: lightweight at least 40 %
  less private memory than full on the same machine, and no growth over
  10 minutes. The renderer (`GSK_RENDERER=cairo` instead of GL) is
  measured too, but changed only if the desktop measurement shows it
  pays: it would need setting before GTK starts.

| Step | Create / change | Test |
|---|---|---|
| L.1 | `tests/ui/mem.py`: the measurement above, both profiles, recorded in this plan | Run on the headless display and on the desktop |
| L.2 | Schema `lightweight` (b, false); `--lightweight`; `core/profile.py`: `Profile` (`full()`, `lightweight()`: `lazy_pages`, `page_drop_s`, `sidebar_charts`, `overview_charts`, `overview_tables`, `extra_graphs`, `max_time_range`, `axes`, `themes`, `app_icons`, `gpu_details`, `pci_on_demand`, `log_level`); `AppContext.profile`; `build_context(profile=...)` | Unit: both profiles; the setting and the flag choose it |
| L.3 | `core/pciids.py`: `PciIds.on_demand(path)`: scans the file for a vendor/device when first asked and caches only the answers | Unit: same answers as the full parse on the test pci.ids; memory of the on-demand object stays small |
| L.4 | `ui/page.py`: `LazyPage` (a sidebar entry and summary from the monitor alone; builds the real page on first map, drops it `page_drop_s` after unmap). `SidebarSummary` from the monitor, not the page (`Monitor.sidebar_summary()`), so the sidebar works without a built page | UI: page built only on visit, dropped after the timeout (fake clock), sidebar follows the monitor meanwhile |
| L.5 | Sidebar and Overview without charts; Overview without busiest tables (`OverviewPage(profile=...)`) | UI: no `Graph` in the sidebar or Overview in lightweight |
| L.6 | Device pages: only the main usage graph, other figures as `InfoRow`s, no axes, `max_time_range`; *Show Usages of Logical CPUs* hidden | UI per page kind |
| L.7 | Tables without the icon column; `AppIconLookup` not built (`ctx.app_icons = None`) | UI |
| L.8 | `Theme` fixed to Follow System and the System palette; no `ThemeCss`; Appearance rows insensitive with a note | Unit/UI |
| L.9 | GPU detail sources not started (`GpuController(start_details=False)`); the Details tab explains and links to Preferences | Unit/UI |
| L.10 | Preferences → General → *Lightweight Mode* (switch + *Restart Now*), log level default warning while on | Dialog test |
| L.11 | Measure again (L.1); record the numbers; README section *Lightweight mode*; [Feature 1's design](../../design/features/feature-01-lightweight-mode.md) updated from plan to as-built | – |

**Done when:** with *Lightweight Mode* on, Proccoli shows every device's
usage and the process list, uses at least 40 % less private memory than
the full mode on the same machine (measured by `tests/ui/mem.py`), and
doesn't grow over 10 minutes.

**Open questions for the user:**
1. Should lightweight apply live (rebuilding the window) instead of at
   the next start? Live is possible but complicates every page's teardown;
   the plan restarts.
2. Is the Overview still the start page in lightweight mode? The plan
   keeps it, as a compact list.
3. Keep Apps and Processes at all? They're the largest pages; the plan
   keeps them (built on visit, icon-free).
