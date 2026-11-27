# Bug 13: The Overview's tables changed width with their contents

Plan: [plan/bugs/bug-13-the-overview-s-tables-change-width.md](../../plan/bugs/bug-13-the-overview-s-tables-change-width.md)


*[PLAN.md, Bug 13](../../plan/bugs/bug-13-the-overview-s-tables-change-width.md). Fixed in M82.* A GTK label's natural width is its whole
text even when it ellipsizes; the name column now has `max_width_chars`
(natural width fixed) and the value columns `width_chars` =
`max_width_chars` at their widest value.
