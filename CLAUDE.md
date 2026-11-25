# Proccoli

A GTK 4 / libadwaita system monitor for the Linux desktop, in Python
(PyGObject, system packages only, no build step).

- `README.md`: the user guide (users only, no design details).
- `docs/DESIGN.md`: how it's built (layers, classes, diagrams).
- `docs/PLAN.md`: the milestone plan and progress log.

## Every change

**Before making any code change, load the `proccoli-change` skill**
(`.claude/skills/proccoli-change/SKILL.md`) and follow it. In short, with
each change:

1. **Design for testing:** dependency injection through
   `context.build_context()`; OS access only through `SysRoot` and
   `System`; logic in display-free modules.
2. **Add tests:** unit tests without a display, smoke tests for UI;
   `make test` and `make ui-test` must pass.
3. **Update `docs/PLAN.md`, `docs/DESIGN.md` and `README.md`** as needed. Create/Modify mermaid diagrams and UML as needed.
4. **Do light refactoring** where the change touches code that needs it.
5. **Repeat the documented Ideas and Bugs** that the user wants to revisit at the end of each response and ask if they'd like to tackle any of them.
6. **No planning references in code:** never put milestone, idea, bug or
   step numbers, `DESIGN.md` / `PLAN.md` section references, or other
   planning metadata in code, comments, docstrings, tests, scripts or
   data files ("(M72)", "Idea 19", "Bug 8", "DESIGN.md §9.2"). Say what
   the code does and why in plain words; the history belongs in
   `docs/PLAN.md` and `docs/DESIGN.md`. `tests/test_static.py` checks it.

## Commands

```sh
make run        # from the checkout (PYTHONPATH=src python3 -m proccoli)
make demo       # made-up devices
make test       # tests that need no display
make ui-test    # all tests on a private headless Broadway display + screenshots
```

## Platform floor

Ubuntu 24.04 / Debian 13: Python 3.10+, GTK 4.10+, libadwaita 1.5+ (Ubuntu
24.04 ships GTK 4.14, libadwaita 1.5, GLib 2.80, PyGObject 3.48). Any newer
GTK, libadwaita or GLib API must be feature-checked with a fallback.
