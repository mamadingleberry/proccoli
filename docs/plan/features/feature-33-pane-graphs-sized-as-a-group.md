# Feature 33: A page's graphs sized as a group

Design note: [design/features/feature-33-pane-graphs-sized-as-a-group.md](../../design/features/feature-33-pane-graphs-sized-as-a-group.md)

*Open; settled with the user.* Graphs on one page (for example the
Processor's usage, frequency and temperature) end up different sizes.
They form a group that shares one width and height and resizes together
as the window changes.

| Step | Create / change | Test |
|---|---|---|
| F33.1 | Pure `group_size(available, count, orientation) -> (w, h)` in `ui/layout.py`, keeping the "never taller than wide" rule | Unit, table-driven (portrait, landscape, 1–6 graphs) |
| F33.2 | A `GraphGroup` that lays its graphs out at that size (one `Gtk.SizeGroup` per group) | UI: three graphs, equal allocations at two window sizes |
| F33.3 | Device pages use `GraphGroup` | `shoot.py` scenes for each page |
| F33.4 | DESIGN §9.1 | — |
