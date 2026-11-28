# Feature 18: Overview pages for groups of devices

Design note: [design/features/feature-18-overview-pages-for-groups-of-devices.md](../../design/features/feature-18-overview-pages-for-groups-of-devices.md)

*✅ Built; in v0.6.0*, with one step changed (F18.4, below).

**Goal:** where a machine can have more than one of something (GPUs,
drives, network connections, batteries), the sidebar groups them under
one entry with its own **overview page**, and the devices become its
children:

- **GPUs** → a *GPUs* page: a card per GPU (usage, video memory,
  temperature, power), side by side, then each GPU below it in the
  sidebar.
- **Drives** → a *Drives* page: a card per drive (activity, read and
  write speeds, space used), and combined read/write throughput.
- **Network** → a *Network* page with **Ethernet**, **Wi-Fi** and
  **other connections** (VPN, mobile broadband, bridges, virtual ones
  when shown) as children: a card per connection and the machine's total
  download and upload.
- **Batteries** → a *Batteries* page (laptops with two batteries, or a
  connected UPS): charge and rate per battery.

**Why:** today each device is its own top-level entry, so a machine
with two GPUs shows "GPU" twice (this laptop's demo does), three drives
take three rows, and there's no place to compare them or see the total
(all network traffic, all drive activity). The Overview shows every
device, but mixed with everything else.

**Design ([Feature 18's design](../../design/features/feature-18-overview-pages-for-groups-of-devices.md)):**

- **When a group appears:** for a kind with two or more devices by
  default; a single GPU or drive stays a plain entry as now (no extra
  click). Network always groups once there's more than one connection.
  *Open question 1* covers "always group".
- **Sidebar:** a group row (icon, name, a summary line and a chart of
  the total or the busiest child) with an expander; its children are
  indented beneath it. Collapsing a group hides its children; the
  choice is remembered (`sidebar-collapsed-groups`). Children reorder
  within their group (the shared `reorder.py`, with the group as its
  own list); groups move as a whole among the other entries. Colors:
  children keep their own entry colors; the group row uses the first
  child's.
- **The group page** reuses the Overview's machinery (`OverviewPage`'s
  cards, fitting and planner, v0.1.0) filtered to the group's devices,
  plus a combined chart where adding up makes sense (network download
  and upload; drive read and write), never where it doesn't (GPU usage
  percentages aren't summed; the cards sit side by side instead).
- **Network:** children are grouped by connection type from the
  interface's kind (`devices/network.py` already tells Ethernet from
  Wi-Fi from virtual). Within Network, *Ethernet*, *Wi-Fi* and *Other*
  are sub-headings, not extra pages, unless *open question 3* says
  otherwise.
- **Everything else follows the sidebar:** *Go To* lists groups with
  their children indented; Back and Forward and the window's restored
  page treat a group page like any page; the Overview page shows a card
  per **device**, not per group (it's the whole machine), unless *open
  question 4* says otherwise; the toolbar (v0.5.0) applies to group pages
  (they have charts).
- **Lightweight Mode:** group pages are built on visit and dropped like
  any page; the group row's chart is the small one.
- **Display-free logic:** `ui/sidebar_groups.py`: which kinds group, the
  group of each page ID, the order (groups and children), collapsed
  state, all pure and unit-tested; the sidebar and Go To read it.

| Step | Create / change | Test |
|---|---|---|
| F18.1 | `ui/sidebar_groups.py`: grouping rules, order with groups, collapsed groups; `sidebar-collapsed-groups` key | Unit: one GPU → no group; two → a group with both; network types; order and moves within and across; a device added or removed |
| F18.2 | Sidebar group rows with expanders and indented children; *Go To* nested | UI: two demo GPUs make a *GPUs* group; collapse hides children and is remembered; drag within a group |
| F18.3 | `GroupPage`: the Overview's cards for the group's devices; combined network and drive charts | UI: the *GPUs* page has a card per GPU; *Network* totals equal the sum of its children |
| F18.4 | Network: Ethernet, Wi-Fi and Other sub-headings | Unit: interface kinds to sections; UI: the demo's connections land in the right sections |
| F18.5 | README (*Sidebar*), [DESIGN §9.2](../../design/09.2-window-behaviour.md), [§9.6](../../design/09.6-overview-page.md), [Feature 18's design](../../design/features/feature-18-overview-pages-for-groups-of-devices.md); screenshots | `make ui-test` |

**Done when:** a machine with two GPUs or drives shows one group entry
with its devices beneath, a group page comparing them, Network groups
its connections by type with total traffic, and a machine with one of
each looks as it does today.

**Answered by the user:**
1. **Always group** (asked "is Always simpler to implement?": it is: a
   kind's group never appears or vanishes as a second device comes or
   goes). A group exists while its kind has a device.
2. Processor and Memory stay top-level.
3. One Network page, with its connections as sub-headings (see F18.4).
4. The Overview keeps a card per device.

**Done:**

| Step | Done | Test |
|---|---|---|
| F18.1 | `ui/sidebar_groups.py` (pure): `GROUPS`, `group_for`, `nest`, `move`, `move_before`, `hidden_children`, `count_text`; `sidebar-collapsed-groups` (set by the group's arrow, so in `preferences_layout.ELSEWHERE`) | `test_sidebar_groups` |
| F18.2 | Sidebar: a group row's arrow (in place of the minimise arrow), devices indented 16 px, hidden while collapsed; a group takes its first device's color; Go To indents devices (an em space) | `test_ui_groups`: two demo GPUs make *GPUs*, collapse is remembered, moves within a group and of a whole group, Go To |
| F18.3 | `pages/group.py`: `GroupPage(OverviewPage)` (the Overview takes an identity now), the devices' cards and their count; `total_text` adds up network and drive speeds (never percentages) for the group's entry; the window adds and removes it with its devices | `TotalTextTest` (no display); the group page has a card per GPU; it goes with its last device |
| F18.4 | *(Changed)* Network's cards are ordered by connection type (Ethernet, Wi-Fi, VPN, bridge, other: the order network pages already sort by), without sub-headings | – |
| F18.5 | User guide (*What it shows*, *Sidebar*), DESIGN §9.2, §11, [DESIGN_UML.md](../../design/DESIGN_UML.md); README screenshots refreshed | `make ui-test` |

**Changed while doing it:** sub-headings on the Network page (F18.4)
would need the Overview's single card grid split into sections and its
fitting arithmetic redone; the cards are in type order instead. Section
headings remain possible as their own change. The combined charts
(total download and upload as a chart) are a text total on the group's
entry for now; the group's entry charts its first device.

**Asked before building (now answered):**
1. Group only when there are two or more of a kind (as designed), or
   always (a *GPUs* page even with one GPU, so the sidebar looks the
   same on every machine)?
2. Should the Processor and Memory be grouped too (a *System* group),
   or stay top-level?
3. Network: are Ethernet, Wi-Fi and Other sub-headings on one Network
   page (as designed), or each its own overview page with children (a
   three-level sidebar)?
4. Should the main Overview show a card per group (fewer, summarised)
   or keep a card per device?
