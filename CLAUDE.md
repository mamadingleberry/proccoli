# Proccoli

A GTK 4 / libadwaita system monitor for the Linux desktop, in Python
(PyGObject, system packages only, no build step).

- `README.md`: the user guide (users only, no design details).
- `docs/DESIGN.md`: how it's built: an index of `docs/design/` (one file
  per section; ideas' and bugs' design notes in `ideas/` and `bugs/`).
- `docs/PLAN.md`: the plan: current state, open bugs, ideas and the
  milestones by phase, an index of `docs/plan/` (one file per milestone,
  idea and bug).

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
7. **Read and write the docs as indexes:** read `docs/PLAN.md` and
   `docs/DESIGN.md` (both short), then open only the files the change
   needs; never read the whole `docs/` tree. File names follow the
   numbers, so a reference can be opened without the index:
   `docs/plan/milestones/M53-*.md`, `docs/plan/ideas/idea-19-*.md`,
   `docs/plan/bugs/bug-22-*.md`, `docs/design/07.2-*.md`,
   `docs/design/ideas/idea-19-*.md`, `docs/design/bugs/bug-22-*.md`.
   New work gets its own file and one line in its index (a milestone's
   first line is its status and a one-sentence summary); the indexes hold
   no detail. Link between files with relative links. `tests/test_docs.py`
   checks that links resolve, every file is in its index, and each index
   stays under 32 KB.

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
