# Bug 13: The Overview's tables change width as the busiest apps change

Design note: [design/bugs/bug-13-the-overview-s-tables-changed-width.md](../../design/bugs/bug-13-the-overview-s-tables-changed-width.md)

*Fixed in Milestone 82.*

**Seen:** "why do the table widths shift back and forth in size on the
Overview page? Those should be static … likely something to do with
longer process names".

**Cause:** names were cut with "…", but a GTK label's *natural* width is
its whole text, so a long name made the table ask for more room and the
page re-laid out; "100.0 %" was also one character wider than its column.

**Fix:** the name column's natural width is capped (it still fills the
space the page gives it, and ends in "…", the full name as tooltip); the
value columns are fixed at their widest values.

| Step | Create / change | Test |
|---|---|---|
| B13.1 | `ui/widgets/top_table.py` | `test_top.StableTableSizeTest` |
