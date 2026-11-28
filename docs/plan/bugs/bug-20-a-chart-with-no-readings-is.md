# Bug 20: A chart with no readings is drawn blank instead of "No data"

Design note: [design/bugs/bug-20-a-chart-with-no-readings-is.md](../../design/bugs/bug-20-a-chart-with-no-readings-is.md)

*Fixed in v0.6.0.* Not with a running count as proposed:
`Series.values` is a deque its `History` replaces and changes in place in
six places, so a count would have to follow all of them. `has_values()`
looks from the newest point and stops at the first reading: at once for
a series that's reading, at most `MAX_GRAPH_POINTS` (1200) for one with
only gaps, the case that needs it.

**Seen:** while diagnosing Bug 19: the idle Intel GPU's Overview card
showed an empty chart frame instead of its "No data" label.

**Cause:** `SidebarSummary.has_chart()` is `bool(self.series)`: true as
soon as the device has a series, even when every point in it is `None`.
`OverviewCard.update` then shows the graph and hides `empty_label`, and
the graph has nothing to draw.

**Fix (proposed):** `has_chart()` is true only when some series holds a
reading. `Series` keeps a count of the non-`None` values it holds
(updated on append and when old points drop off), so the check stays
O(1) per update rather than a scan of up to a day of points. A card
whose device starts reading switches from "No data" to the chart on the
next `summary-changed`.

| Step | Create / change | Test |
|---|---|---|
| B20.1 | `core/history.py`: `Series.has_values()` from a running count | Unit: empty, all-`None`, one value then aged out, mixed |
| B20.2 | `ui/page.py`: `SidebarSummary.has_chart()` uses it | Unit: a summary over an all-`None` series has no chart; UI smoke: such a card shows "No data", then the chart after its first reading |
| B20.3 | [Bug 20's design](../../design/bugs/bug-20-a-chart-with-no-readings-is.md) | — |

**Done when:** no Overview card draws an empty chart; a device without
readings says "No data".
