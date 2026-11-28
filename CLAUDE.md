# Proccoli

A GTK 4 / libadwaita system monitor for the Linux desktop, in Python
(PyGObject, system packages only, no build step).

@VOICE.md
@AUDIENCE.md

## Every response ends the same way: no exceptions

Code change, docs-only change, a question answered, or a turn cut short
by a new message: **every** response ends with the three parts in the
`software-design` skill's *The end of every response* (its template is
the only copy): **Summary**, **Test report**, **Next**. A Stop hook
(`.claude/hooks/response_ending.py`) sends a response back once when a
part is missing.

- `README.md`: the short page for someone deciding to try Proccoli;
  `docs/USER-GUIDE.md`: the full user guide (both for users only, no
  design details).
- `docs/DESIGN.md`: how it's built: an index of `docs/design/` (one file
  per section; features' and bugs' design notes in `features/` and
  `bugs/`), starting with `design/DESIGN_UML.md` and `design/DESIGN_DB.md`.
- `docs/PLAN.md`: the plan: current state, open bugs, features and the
  releases, an index of `docs/plan/` (one file per feature, bug and
  release; the old milestones in `plan/archive/`).

## Every change

**Before making any change, load the `proccoli-engineer` skill**
(`.claude/skills/proccoli-engineer/SKILL.md`), which loads
`software-project` and through it `software-design`, `software-testing`
and `application-design`. Follow them.

**The `engineering-skills` plugin is required** (alirezarezvani/claude-skills,
marketplace `claude-code-skills`): it supplies the generic engineering
standards. Use its `engineering-skills` router and the one skill a task
needs (`senior-architect`, `tdd-guide`, `red-green-proof`,
`code-reviewer`, `senior-security`...). Our skills replace only what it
doesn't cover, and win where they differ. If it isn't installed, ask the
user to run `/plugin marketplace add alirezarezvani/claude-skills` and
`/plugin install engineering-skills@claude-code-skills`.

In short, with each change:

1. **Design for testing:** dependency injection through
   `context.build_context()`; OS access only through `SysRoot` and
   `System`; logic in display-free modules.
2. **Add tests:** unit tests without a display, smoke tests for UI;
   `make test` and `make ui-test` must pass.
3. **Update `docs/PLAN.md`, `docs/DESIGN.md`, `docs/USER-GUIDE.md` and `README.md`** as needed,
   with `DESIGN_UML.md` and `DESIGN_DB.md` and other Mermaid diagrams.
   **With every request, check the standing design sections** (goals and
   non-goals, technology decisions, architecture, runtime flow, open
   decisions) against what the request changes, and say in the summary
   which were updated (`software-design`, *Documentation layout*).
4. **Do light refactoring** where the change touches code that needs it.
5. **End each response** as the section above says.
6. **No planning references in code:** never put feature, bug, release,
   milestone or step numbers, `DESIGN.md` / `PLAN.md` section references,
   or other planning metadata in code, comments, docstrings, tests,
   scripts or data files ("(M72)", "Feature 19", "Bug 8",
   "DESIGN.md §9.2"). Say what the code does and why in plain words; the
   history belongs in `docs/`. `tests/test_static.py` checks it.
7. **Read and write the docs as indexes:** read `docs/PLAN.md` and
   `docs/DESIGN.md` (both short), then open only the files the change
   needs; never read the whole `docs/` tree. Features, bugs and releases
   are documented and indexed as `software-design`'s *Tracking work*
   section says, and nowhere else. `tests/test_docs.py` checks that links
   resolve, every file is reachable from its index, and each index stays
   under 32 KB.
8. **Releases** (only when asked): as `software-project` says; publish on
   GitHub only when the user says so.

## Commands

```sh
make run        # from the checkout (PYTHONPATH=src python3 -m proccoli)
make demo       # made-up devices
make test       # tests that need no display; quiet: one line, or the failures
make ui-test    # all tests on a private headless Broadway display; quiet
make check      # everything, quietly: run before saying a change is done
make test-verbose / make ui-test-verbose   # every test by name (people, not the agent)
make screenshots  # the UI scenes into tests/ui/out (visual changes, releases)
```

Run tests quietly (`make test`, `make check`) and read their output as
it is; never run the `-verbose` targets or pipe through `grep`/`tail`
just to shorten them: a full run's output is ~36 000 tokens.

## Platform floor

Ubuntu 24.04 / Debian 13: Python 3.10+, GTK 4.10+, libadwaita 1.5+ (Ubuntu
24.04 ships GTK 4.14, libadwaita 1.5, GLib 2.80, PyGObject 3.48). Any newer
GTK, libadwaita or GLib API must be feature-checked with a fallback.
