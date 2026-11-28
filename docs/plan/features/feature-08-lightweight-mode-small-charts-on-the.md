# Feature 8: Lightweight Mode: small charts on the Overview, a minimal sidebar

Design note: [design/features/feature-08-lightweight-mode-small-charts-on-the.md](../../design/features/feature-08-lightweight-mode-small-charts-on-the.md)

*Done as v0.5.0* (its decisions and measurements are there).

**Goal:** in Lightweight Mode the Overview shows each device's trend
again, as the small line chart the sidebar uses, and it keeps the
busiest apps and processes. The sidebar can only be *Icons Only* or
*Hidden*, never *Full*.

**Why:** v0.3.0 made the lightweight Overview a plain list of
readings, with no charts and without the busiest apps and processes, and
kept the full sidebar (with progress bars).
So at a glance there's no trend anywhere, while the sidebar's full
entries still repeat the Overview's figures. Moving the small charts to
the Overview and keeping the sidebar to icons puts the trend where people
look, and the window draws about the same number of charts as before:
one small chart per device, in one place instead of two. With the sidebar
down to icons (or hidden), the Overview is the one page that shows what's
going on, so what's using the machine belongs there too.

**Design ([Feature 8's design](../../design/features/feature-08-lightweight-mode-small-charts-on-the.md)):**

- **Overview cards in Lightweight Mode:** name, readings, and under them
  the sidebar's small chart (`Graph(GraphStyle.SMALL)`, 36 px high, in
  the entry's color, network's receive and send on one automatic
  scale). It's the same as `Meter`'s graph, so it has no hover and no
  axes; axes stay pinned off. Its time range is the pinned one (at most
  1 minute), so it costs what a sidebar meter did. `OverviewCard(chart=
  "small")` (`"full"` / `"small"` / none instead of `True`/`False`); the
  page keeps its 3-column list layout (no grid fitting) and binds the
  graphs as `ChartKind.METER`.
- **The busiest apps and processes stay on the Overview** in Lightweight
  Mode: the two `TopTable`s below the cards (5 each, ranked by
  `overview-top-by`), as in the full mode, but **without icons**
  (`profile.app_icons` is off, so `TopTable.fill` leaves the icon out and
  the image isn't built). `Profile.overview_tables` becomes true for
  Lightweight Mode. The process scan still runs only while the Overview,
  Apps or Processes is on screen (`ProcessMonitor.acquire`/`release`), and
  with nobody showing it the process list is still dropped
  (`keep_process_data`, v0.3.0). So the tables cost only while they're
  visible. A click on a row opens Apps or Processes (built on visit) as
  now.
- **The sidebar:** `sidebar-style` is pinned to *Icons Only*
  (`ProfileSettings`), so it stays *Icons Only* or *Hidden*
  (`sidebar-shown`). The main menu's *Sidebar* section lists only *Icons
  Only* and *Hidden* (`primary_menu(modes=…)`), and `SidebarVisibility`
  turns a request for *Full* (a stale action target, F9 toggling back)
  into *Icons Only*. The pin on `sidebar-meter-type` (progress bars) is
  no longer needed: an icons-only sidebar shows no meters at all, so
  their widgets aren't built (`StackSidebarItem` builds its meter on
  first use).
- **Memory, measured not assumed** (`tests/ui/mem.py`): the sidebar's
  meters go; the Overview's small charts and its two tables (and the
  process scan while it's shown) come in. Charts alone should be no worse
  than v0.3.0 (37.8 MiB at start). The tables add the process list
  while the Overview is open, a few MiB; the plan records both numbers
  rather than assuming either, and the README's "about half the memory"
  is corrected if they don't support it.

| Step | Create / change | Test |
|---|---|---|
| F8.1 | `core/profile.py`: pin `sidebar-style` to `icons`; drop the `sidebar-meter-type` pin; `Profile.overview_charts` becomes `overview_chart` (`"full"`, `"small"`); `overview_tables` true in Lightweight Mode | Unit: the pins and flags; a user's *Full* comes back when the mode is off |
| F8.2 | `ui/window.py` / `ui/sidebar_visibility.py`: the *Sidebar* menu without *Full* in Lightweight Mode; *Full* requests become *Icons Only* | UI: the menu's items; F9 and the action's targets |
| F8.3 | `ui/pages/overview.py`: `OverviewCard(chart="small")` with the small chart, bound as `METER`, in the entry's color; the busiest apps and processes below the cards; `ui/widgets/top_table.py`: rows without icons when the profile has none; `ui/sidebar.py`: meters built only when an item first needs one | UI: every Overview card has a `SMALL` graph and no axes; the two tables show, with no icon images, and their rows open Apps or Processes; the process scan stops when the Overview is left; an icons-only sidebar has no meter widgets |
| F8.4 | Measure (`tests/ui/mem.py`), README *Lightweight mode*, [Feature 1's design](../../design/features/feature-01-lightweight-mode.md) and [Feature 8's design](../../design/features/feature-08-lightweight-mode-small-charts-on-the.md) as built | Run |

**Done when:** in Lightweight Mode every Overview card shows its small
chart, the Overview shows the busiest apps and processes (without
icons), the sidebar offers only *Icons Only* and *Hidden*, and memory is
measured and recorded against v0.3.0's.

**Open questions for the user:**
1. On a narrow window the sidebar opens over the page instead of beside
   it. Should it be icons only there too, or full there, since it's only
   shown while you pick a page?
2. The sidebar's chart is a filled area under the line. Keep the fill on
   the Overview, or draw a plain line?
3. When Lightweight Mode is turned on, should the sidebar start *Hidden*
   (the Overview then has every device) or *Icons Only*?
4. The busiest tables show 5 apps and 5 processes in the full mode.
   Keep 5 in Lightweight Mode, or show fewer (say 3) to keep the page
   short?
