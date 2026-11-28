# Feature 20: Preferences in named sections

Design note: [design/features/feature-20-preferences-in-named-sections.md](../../design/features/feature-20-preferences-in-named-sections.md)

*✅ Built; in v0.6.0.* Answers: the six pages as proposed, graph
options on *Appearance*, the bottom switcher.

**Goal:** Preferences stops being one long *General* page. Settings are
grouped into a few named pages, and long lists open as subpages, so each
page is short and its name says what's on it.

**Why:** *General* holds eight groups today (Memory Use, Appearance,
Administrator Rights, Units, User Interface, Diagnostics, Window
Switching, History), mixing how Proccoli looks, what it records, what
it may do, and how it runs. Some items aren't settings at all but
actions or status (*Export…*, *Delete History…*, *Recording*, *Size on
Disk*).

**Proposed pages** (`Adw.PreferencesDialog` pages, chosen from the
bottom switcher; long lists as subpages with `push_subpage`):

| Page | Holds |
|---|---|
| **Appearance** | Style, Color Palette, Graph Axes, Graph Grid, Graph Time Range (and *Custom…*), Units |
| **Sidebar** | as today (style, meters, entries), each entry's options as a subpage |
| **Tables** | Apps columns and Processes columns (each a subpage), sorting, Normalize Processor Usage |
| **Recording** | Keep History, its limits, *Start at Boot*, *Recording* status, *Export…*, Include Hardware Addresses, *Delete History…* |
| **Devices** | virtual drives and connections, GPUs' detailed statistics (each GPU a subpage) |
| **System** | Update Interval, Lightweight Mode, Administrator Rights, Window Switching, Diagnostics |

- **Actions apart from settings:** within a page, actions (*Export…*,
  *Delete History…*, *Install*) and status rows (*Recording*, *Size on
  Disk*) sit in their own group at the end, so a page reads as settings
  first.
- **Search** keeps finding every row (`search_enabled` covers subpages).
- **Lightweight Mode's notice and padlocks** move with their rows: each
  page that has a fixed setting shows the notice.
- **Display-free layout:** a `ui/preferences_layout.py` table maps each
  settings key to its page, group and order, so a test can check every
  key is somewhere, exactly once, and the dialog builds from it.

| Step | Create / change | Test |
|---|---|---|
| F20.1 | `ui/preferences_layout.py`: pages, groups, order, subpages | Unit: every user-facing settings key placed once; no page over N rows |
| F20.2 | `PreferencesDialog` built from the layout; subpages for columns, sidebar entries, GPUs | UI: each page's rows; subpages open and go back; search finds a subpage row |
| F20.3 | README *Preferences*; DESIGN; screenshots of each page | `make ui-test` |

**Open questions for the user:**
1. Are these pages right, or would you name or split them differently?
2. Should *Graph Time Range* and the units live on *Appearance*, or on
   a *Graphs* page of their own?
3. Six pages fit the bottom switcher on a narrow window; more would need
   a sidebar-style list of sections instead. Six, or a list?
