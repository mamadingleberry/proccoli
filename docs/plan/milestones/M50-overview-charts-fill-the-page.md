# Milestone 50: Overview charts fill the page

*✅ Done.* Cards form an N × M grid that fills the window (best chart shape, full rows); tables move below when there's no room. `FittingPage` shared with device pages

On a full-screen portrait monitor the Overview's cards used a small part
of the page: chart height followed card width (0.4 ×, at most 240 px), so
a tall window was mostly empty. Now the cards form an N × M grid that
fills the height the page gives them.

| Step | Create / change | Test |
|---|---|---|
| 50.1 | `ui/layout.py` (no display): `GridPlan`, `plan_grid(count, width, height, …)` picks the column count (1–4, each card ≥ 280 px wide) whose cells best fill the area: chart shape nearest 0.5 height/width, few empty cells; chart heights never below 80 px (then the page scrolls) | Unit: portrait, landscape, one card, narrow, too short, empty cells, every plan fills the area |
| 50.2 | `FittingPage` (in `ui/page.py`): the size-watching, fit-on-idle plumbing taken out of `DevicePage`, so both pages share it | Device page tests unchanged |
| 50.3 | `OverviewPage`: fits on every size change, card count change or tables' height change; the FlowBox gets exactly the planned columns, each chart the planned height. The top tables keep their natural height below; when the cards would be too short with them on screen, the cards take the whole page and the tables scroll into view below | UI tests: portrait and landscape sizes fill the viewport, column counts, tables kept or pushed below |


*Found while doing 50:* setting the FlowBox's *minimum* columns too made
its minimum width grow, so a window couldn't be made narrower again once
the Overview had several columns; only the maximum is set. Headless
frames are slow, so the new UI tests wait for the layout to settle
instead of a fixed time.
