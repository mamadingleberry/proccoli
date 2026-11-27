---
name: proccoli-change
description: Checklist for every code change in Proccoli (feature, bug fix, refactor, new milestone or step). Use before and while editing anything under src/, tests/, data/ or packaging/. Covers designing for testability (dependency injection through context.py, System, SysRoot), adding tests, updating docs/PLAN.md, docs/DESIGN.md and README.md, and light refactoring.
---

# Making a change to Proccoli

Every change, however small, follows these four rules. Work through them
in order. A change isn't finished until all four are done and the tests
pass.

## 1. Design for testing

Write code that a test can drive without the real machine or a display.

- **Inject, don't reach.** Services are created only in the composition
  root, `context.build_context()` → `AppContext` (DESIGN §4.2). New
  services take what they need as constructor arguments and go into
  `AppContext`. No module-level state, singletons or globals.
- **OS access goes through the seams:**
  - every `/proc` and `/sys` read goes through `SysRoot`, so tests use a
    fixture tree under `tests/fixtures/` (capture with
    `tests/fixtures/capture.sh`);
  - everything else that touches the OS (`os.kill`, `subprocess`,
    `shutil.which`, `pwd`, D-Bus, app launching...) goes through `System`,
    faked by `FakeSystem` in `tests/helpers.py`;
  - time, timers, clocks, sleeps and scheduling are injectable (`Ticker`,
    `clock=`, `sleep=`, `schedule=` like `StallWatchdog`);
  - settings come from `Settings`; tests use `Settings.for_tests()`;
  - the style manager, launchers and log files are injected
    (`Theme(settings, style_manager)`, `PreferencesDialog(launcher=...)`,
    `Application(log_file=...)`).
- **Keep logic out of widgets.** Put arithmetic and decisions in pure,
  display-free modules (like `ui/layout.py`, `ui/navigation.py`,
  `ui/sidebar_order.py`, `processes/top.py`) and keep the widget a thin
  shell over them.
- **Respect the layering:** UI → Domain → Core, never the other way.
  Domain modules don't import Gtk at module level; they tell the UI about
  changes through GObject signals.
- **No planning references in code:** comments, docstrings, tests,
  scripts and data files never mention milestone, idea, bug or step
  numbers or `DESIGN.md` / `PLAN.md` sections; explain in plain words.
  Milestone notes such as "(M52)" go in docs/DESIGN.md and docs/PLAN.md
  only (`tests/test_static.py` checks the code).
- **New GPU backends** live in their own `gpu/<vendor>/` package and need
  only a registration line outside it (the checklist in `docs/plan/milestones/M16-*.md`).
- `tests/test_static.py` enforces much of this (OS calls, Gtk imports,
  docstrings, settings keys, icons, duplicate test class names, no
  planning references in user-visible strings). Don't weaken it to make a
  change pass; fix the change instead.

## 2. Always add tests

- Write the test with, or before, the code. A behaviour change with no
  test change is incomplete.
- **Domain and core code:** unit tests that run without a display, using
  `tests/helpers.py` (`FakeRoot`, `FakeSystem`, `FakeStreamReader`,
  `FakeStyleManager`, `make_context`) and fixtures. Table-driven tests are
  welcome.
- **UI code:** at least a smoke test (build the widget, feed it a
  snapshot) on the headless Broadway display. These are skipped by plain
  `make test` and run by `make ui-test`.
- **Bug fixes:** add a test that fails without the fix.
- **Settings:** a new schema key in
  `data/io.github.mamadingleberry.Proccoli.gschema.xml` needs a settings
  test and must actually be used (the static test checks both ways).
- **Visual changes:** add or update a scene in `tests/ui/shoot.py` and look
  at the screenshots.
- Run both before finishing, and report real results (including
  failures):
  ```sh
  make test       # no display needed
  make ui-test    # everything, on a private headless display, plus screenshots
  ```
- Keep test class names unique within a file.

## 3. Update docs/PLAN.md, docs/DESIGN.md and README.md

Check all three every time, and change whichever no longer matches.

**The two docs are indexes.** Read `docs/PLAN.md` and `docs/DESIGN.md`,
then open only the files the change needs; don't read all of `docs/`.
Files are named after their numbers, so a reference opens directly:

| Reference | File |
|---|---|
| Milestone 53, M53 | `docs/plan/milestones/M53-*.md` |
| Idea 19 | `docs/plan/ideas/idea-19-*.md` (design note: `docs/design/ideas/idea-19-*.md`) |
| Bug 22 | `docs/plan/bugs/bug-22-*.md` (design note: `docs/design/bugs/bug-22-*.md`) |
| DESIGN §7.2 | `docs/design/07.2-*.md`, or the section's file `docs/design/07-*.md` when it isn't split |

- **docs/PLAN.md** (the index: current state, open bugs, ideas,
  milestones by phase) and **docs/plan/**:
  - new work gets its own file, `docs/plan/milestones/M<n>-<slug>.md`:
    a `# Milestone <n>: <title>` heading, then its status and a
    one-sentence summary (`*✅ Done.* …`), a short why, a
    `Step | Create / change | Test` table, and a *Done when* line where
    useful; add one line for it under its phase in PLAN.md;
  - a new idea or bug is `docs/plan/ideas/idea-<nn>-<slug>.md` or
    `docs/plan/bugs/bug-<nn>-<slug>.md` (status line first: `*Open.*`,
    `*Fixed in Milestone <n>.*`, `*Done as Milestone <n>.*`), with a
    line in PLAN.md's *Open bugs* or *Ideas*; when fixed or built, move
    it to the *Fixed* / *Built* line;
  - update the test counts in PLAN.md's *Current state* (`make ui-test`
    total, and how many plain `make test` runs);
  - record anything found along the way, or any deviation from the plan,
    with the reason (*Found while doing N:* ...) in the milestone's file;
  - mark superseded steps as *(Superseded by ...)* rather than deleting
    them.
- **docs/DESIGN.md** (the index) and **docs/design/** (how it's built):
  update the class diagrams, package layout (§4.1), `AppContext`/seams
  (§4.2), settings keys (§11), and any section whose behaviour changed,
  in that section's file. A new section or design note gets its own file
  and a line in DESIGN.md. Keep Mermaid diagrams in line with the code;
  note the milestone that introduced a behaviour (e.g. "(M52)") there,
  never in the code.
- Link between files with relative links. `tests/test_docs.py` checks
  that they resolve, that every file is in its index, and that each index
  stays under 32 KB; when an index nears that, move detail out of it.
- **README.md** is a **user guide only**: what users see and do, keyboard
  shortcuts, preferences, files Proccoli keeps, troubleshooting. Update it
  when anything user-visible changes. Never put milestones, class names or
  design references in it.
- Follow the documents' style: plain, short sentences. Spell it
  "color" (American), in code, UI text and docs alike; other words keep
  the spelling the docs already use (minimise).

## 4. Light refactoring

While in the code, leave it a little better:

- remove duplication you touch, extract a pure helper when logic hides in
  a widget, rename for clarity, delete dead code and stale comments;
- keep refactors small and in service of the change. Anything bigger
  (moving modules, changing interfaces across layers) is its own PLAN.md
  entry, like the existing *Refactor:* rows;
- refactors keep `make test` green and update the docs like any other
  change.

## Finishing checklist

- [ ] New code is injectable and reaches the OS only through `SysRoot` /
      `System` / other injected seams
- [ ] Tests added or updated; `make test` and `make ui-test` pass
- [ ] PLAN.md: the milestone's file and its index line, test counts,
      findings
- [ ] DESIGN.md: the sections' files (diagrams) match the code; new
      files are in the index
- [ ] README.md: user-visible changes described (no design details)
- [ ] Light refactoring done where the change touched messy code
- [ ] Commit at the end of each numbered step (when asked to commit)
