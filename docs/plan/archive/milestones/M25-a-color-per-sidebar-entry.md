# Milestone 25: A color per sidebar entry

*✅ Done.* Each page's graphs also start at its entry's color

| Step | Create / change | Test |
|---|---|---|
| 25.1 | `core/palette.py`: `entry_colors(colors, n)`: n distinct colors from a palette; past its length, lighter and darker variants of its colors | Unit: distinct for n up to 24, deterministic |
| 25.2 | `Theme.entry_rgb(index)`; `ThemeCss` adds `.entry-color-<i>` rules so progress bars match | Unit |
| 25.3 | The sidebar numbers its device entries in the built-in order (moving keeps colors, M28) (Apps and Processes have no chart) and gives each its color: chart line and fill, progress bar. Network's second series (send) is a lighter shade of the same color. | UI test: all entry colors differ; a palette change recolors |
