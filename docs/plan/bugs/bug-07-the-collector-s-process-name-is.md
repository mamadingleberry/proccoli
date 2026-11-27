# Bug 7: The collector's process name is cut short

Design note: [design/bugs/bug-07-the-collector-s-process-name-was.md](../../design/bugs/bug-07-the-collector-s-process-name-was.md)

*Fixed in Milestone 77.*

**Seen:** with `proccoli-metrics` running, the Processes page listed it
as `proccoli-metric`.

**Cause:** the kernel keeps only 15 characters of a process's name
(`comm`), and `display_name` restores a cut name from the command line's
first word, the program. For a script that's the interpreter
(`/usr/bin/python3`), which doesn't match, so the cut name stayed.

**Fix:** it also tries the second word, the script.

| Step | Create / change | Test |
|---|---|---|
| B7.1 | `processes/model.py` | `test_processes`: `test_display_name_of_a_script_is_the_script` |
