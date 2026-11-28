# Milestone 51: Overview charts never taller than wide

*✅ Done.* The grid tries to fill the page, but each chart's height stays under its width; among plans within that, the one filling most wins

M50 let the Overview's charts grow without limit, so one or two cards on
a portrait monitor became towers. The grid now *tries* to fill the page,
but a chart's height always stays below its width; what that leaves
unused stays empty below the grid (the tables move up into it).

| Step | Create / change | Test |
|---|---|---|
| 51.1 | `plan_grid(…, max_ratio=GRID_MAX_RATIO)`: chart height capped below `max_ratio` × chart width (1.0: height < width). The score gains the share of the area left unfilled, so among plans that respect the cap, the one that fills most wins (with shape and empty cells as before) | Unit: every plan's chart is shorter than wide; one card on a portrait area is capped and doesn't fill; a capped plan loses to one that fills; M50's cases unchanged |
| 51.2 | `OverviewPage`: the cards' horizontal chrome (padding, FlowBox child, border) measured from the layout (`cell width − chart width`), so the cap uses the chart's real width | UI tests: every chart shorter than wide at portrait, landscape and one-card sizes; filling tests still pass where the cap doesn't bite |

*Found while doing 51:* the FlowBox puts 3 px of margin outside each card,
so "cell width − chart width" undercounted the chrome and a chart came
out 6 px taller than wide; the chrome is now measured against the column
slot, and a fit made before the first layout (an estimate) runs again
once laid out.
