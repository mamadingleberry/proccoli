# Idea 18: Overview pages for groups of devices

Design note: [design/ideas/idea-18-overview-pages-for-groups-of-devices.md](../../design/ideas/idea-18-overview-pages-for-groups-of-devices.md)

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

**Design ([Idea 18's design](../../design/ideas/idea-18-overview-pages-for-groups-of-devices.md)):**

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
  cards, fitting and planner, M50–M51) filtered to the group's devices,
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
  question 4* says otherwise; the toolbar (M72) applies to group pages
  (they have charts).
- **Lightweight Mode:** group pages are built on visit and dropped like
  any page; the group row's chart is the small one.
- **Display-free logic:** `ui/sidebar_groups.py`: which kinds group, the
  group of each page ID, the order (groups and children), collapsed
  state, all pure and unit-tested; the sidebar and Go To read it.

| Step | Create / change | Test |
|---|---|---|
| I18.1 | `ui/sidebar_groups.py`: grouping rules, order with groups, collapsed groups; `sidebar-collapsed-groups` key | Unit: one GPU → no group; two → a group with both; network types; order and moves within and across; a device added or removed |
| I18.2 | Sidebar group rows with expanders and indented children; *Go To* nested | UI: two demo GPUs make a *GPUs* group; collapse hides children and is remembered; drag within a group |
| I18.3 | `GroupPage`: the Overview's cards for the group's devices; combined network and drive charts | UI: the *GPUs* page has a card per GPU; *Network* totals equal the sum of its children |
| I18.4 | Network: Ethernet, Wi-Fi and Other sub-headings | Unit: interface kinds to sections; UI: the demo's connections land in the right sections |
| I18.5 | README (*Sidebar*), [DESIGN §9.2](../../design/09.2-window-behaviour.md), [§9.6](../../design/09.6-overview-page.md), [Idea 18's design](../../design/ideas/idea-18-overview-pages-for-groups-of-devices.md); screenshots | `make ui-test` |

**Done when:** a machine with two GPUs or drives shows one group entry
with its devices beneath, a group page comparing them, Network groups
its connections by type with total traffic, and a machine with one of
each looks as it does today.

**Open questions for the user:**
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
