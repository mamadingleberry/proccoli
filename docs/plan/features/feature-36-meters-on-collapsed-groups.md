# Feature 36: Each device's meter on a collapsed group

Design note: [design/features/feature-36-meters-on-collapsed-groups.md](../../design/features/feature-36-meters-on-collapsed-groups.md)

*Open.* Asked: "make top-level progress bars visible/toggleable for
collapsed groupings".

**Goal:** a collapsed group ([Feature 18](feature-18-overview-pages-for-groups-of-devices.md))
still shows how busy each of its devices is: a slim progress bar per
device, in the device's entry color, on the group's row, so collapsing
saves room without hiding the readings. It can be turned off.

**Sketch:**
- The group row's details gain a column of slim bars (one per device,
  its usage, its color; hover gives the device's name and usage), shown
  only while the group is collapsed and the option is on.
- A device without a percentage (network speeds) gets a bar scaled to its
  link speed when [Feature 30](feature-30-network-graphs-scaled-to-link-speed.md)
  is built; until then, the group's total text only.
- The option: `sidebar-collapsed-meters` (on by default), Preferences →
  Sidebar → *All Entries*.

| Step | Create / change | Test |
|---|---|---|
| F36.1 | `GroupPage.member_meters()`: (name, usage, color) per device, pure | Unit: two GPUs give two bars in their colors; a device without a usage is left out |
| F36.2 | The group row's bars, shown while collapsed and the option is on; the setting | UI: collapsing *GPUs* shows two bars; the switch hides them; expanding hides them |
| F36.3 | User guide (*Sidebar*), DESIGN §9.2, §11; a screenshot scene | `make ui-test` |

**Open questions for the user:**
1. Progress bars only, or the devices' small charts stacked?
2. One option for every group, or per group (in each group's entry
   settings)?
3. Show them in the icons-only sidebar too (as a tiny bar under the
   icon), or only in the full sidebar?
