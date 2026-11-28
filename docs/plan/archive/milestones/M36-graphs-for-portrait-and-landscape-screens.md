# Milestone 36: Graphs for portrait and landscape screens

*✅ Done.* Height capped at half the width and 560 px; pairs stack on portrait or narrow pages

On a portrait monitor the window is tall and narrow, and graphs that share
out the whole height grow into towers. Sizing now weighs both directions.

| Step | Create / change | Test |
|---|---|---|
| 36.1 | `ui/layout.py`: `GraphLimits` (min height 120, max height 560, max height/width 0.5, min pane width 280), `height_range(width)`, `fit_heights(viewport, fixed, row_widths)`: each row within its own range, and height a capped row can't use goes to the others; `group_rows`; `MAX_CONTENT_WIDTH` (1600) used by the page clamp. `fit_graph_height` is replaced | Unit: landscape share, portrait cap, redistribution, minimum |
| 36.2 | `is_portrait`, `stack_pair(pair_width, viewport)`: a pair stacks when a pane would be under 280 px or the window is portrait. `DoubleGraphBox.set_stacked`; `DevicePage.add_pair` registers pairs (GPU video encode/decode, demo read/write), and `_fit_graphs` arranges them before fitting | Unit; UI test: stacks at 800×1600, side by side again at 1024×768 |
| 36.3 | `DevicePage._fit_graphs` fits row by row (`group_rows`; each row's narrowest graph sets its cap) | UI test: 700×1800 window, every graph ≤ half its width |
| 36.4 | GPU Details `GraphGrid`: `graph_cap(col_w)` and `extra_heights(..., cap)`, so a single tall column leaves spare height empty rather than stretching graphs | Unit; UI test at 700×1800 |
| 36.5 | Screenshot scenes `portrait-demo`, `portrait-gpu-details`; `shoot.py` takes scene names to render a few | Screenshots |

**Done when:** on a portrait window the graphs stay at most half as tall
as they are wide, the Read/Write and Encoder/Decoder pairs stack, and
landscape windows look as before.
