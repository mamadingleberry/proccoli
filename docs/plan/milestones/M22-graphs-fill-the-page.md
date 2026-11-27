# Milestone 22: Graphs fill the page

*✅ Done.*

| Step | Create / change | Test |
|---|---|---|
| 22.1 | *(Superseded by M36: `fit_heights`.)* Pure helper `fit_graph_height(viewport, fixed, graphs, minimum, maximum)` in `ui/layout.py` | Unit |
| 22.2 | Device pages: the content column is as wide as the page allows (no 800 px cap below 1400 px), and page graphs share the spare height (120 px minimum, so small windows still scroll) | UI test: graphs grow with the window |
| 22.3 | Processor page: per-thread graphs grow to fill each row | UI test |
| 22.4 | GPU Details tab: graph sections fill the height (intel_gpu_top_gui's grid already fills the width) | UI test |

**Done when:** resizing the window resizes every graph on the visible page,
in both directions.

Milestones 23–28 are the second round of requested changes, done in order
with the same rules (docs, dependency injection, tests at every step).
