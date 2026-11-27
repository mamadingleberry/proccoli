# Bug 7: The collector's process name was cut short

Plan: [plan/bugs/bug-07-the-collector-s-process-name-is.md](../../plan/bugs/bug-07-the-collector-s-process-name-is.md)


*[PLAN.md, Bug 7](../../plan/bugs/bug-07-the-collector-s-process-name-is.md). Fixed in M77.* The kernel keeps 15 characters of a
process name; `display_name` restored a cut name from the program's name,
which for a script is the interpreter. It now also tries the script (the
command line's second word): `proccoli-metric` →
`proccoli-metrics` (the collector's name then).
