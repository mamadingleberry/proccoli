---
name: proccoli-engineer
description: How to make any change in Proccoli (feature, bug fix, refactor, docs, release). Use before and while editing anything under src/, tests/, data/, packaging/ or docs/. Says where Proccoli's seams, tests, docs and version strings live, on top of the general software-project, software-design, software-testing and application-design skills.
---

# Engineering on Proccoli

**Load `software-project` first**; it brings in `software-design`,
`software-testing` and `application-design`. Those say *what* good
practice is. This skill says *where* it lives in Proccoli, and where
Proccoli is stricter. A change isn't finished until every section below
is done and the tests pass.

## 1. Design for testing: Proccoli's seams

- **The composition roots:** `context.build_context()` → `AppContext`
  (the window) and `build_metrics_context()` → `MetricsContext` (the
  recorder, `proccoli`). Services are created only there and take what
  they need as constructor arguments. No module-level state, singletons
  or globals.
- **OS access goes through the seams:**
  - every `/proc` and `/sys` read goes through `SysRoot`; tests use a
    fixture tree under `tests/fixtures/` (capture with
    `tests/fixtures/capture.sh`);
  - everything else (`os.kill`, `subprocess`, `shutil.which`, `pwd`,
    D-Bus, app launching...) goes through `System`, faked by `FakeSystem`
    in `tests/helpers.py`;
  - time and scheduling are injectable (`Ticker`, `clock=`, `sleep=`,
    `schedule=` like `StallWatchdog`);
  - settings come from `Settings`; tests use `Settings.for_tests()`;
  - the style manager, launchers and log files are injected
    (`Theme(settings, style_manager)`, `PreferencesDialog(launcher=...)`,
    `Application(log_file=...)`).
- **Logic out of widgets:** pure, display-free modules such as
  `ui/layout.py`, `ui/navigation.py`, `ui/sidebar_order.py`,
  `ui/sidebar_style.py`, `processes/top.py`.
- **Layers:** UI → Domain → Core, never back. Domain modules don't import
  Gtk at module level and report changes through GObject signals. The
  `proccoli` package (the recorder) never imports the GUI
  (`packaging/split.py` lists which files go where).
- **New GPU backends** live in their own `gpu/<vendor>/` package and need
  only a registration line outside it (the checklist in
  `docs/plan/archive/milestones/M16-*.md`).
- **Platform floor:** Ubuntu 24.04 (GTK 4.14, libadwaita 1.5, GLib 2.80).
  Newer APIs go through `ui/compat.py` or a `hasattr` check.
- `tests/test_static.py` enforces much of this (OS calls, Gtk imports,
  docstrings, settings keys, icons, the install split, libadwaita
  versions, no planning references, even across a line break). Don't
  weaken it to make a change pass: fix the change.

## 2. Tests

- Unit tests use `tests/helpers.py` (`FakeRoot`, `FakeSystem`,
  `FakeStreamReader`, `FakeStyleManager`, `make_context`) and fixtures.
- UI code gets at least a smoke test on the headless Broadway display;
  plain `make test` skips those, `make ui-test` runs them.
- A new key in `data/io.github.mamadingleberry.Proccoli.gschema.xml`
  needs a settings test and must actually be used (the static test checks
  both ways).
- Visual changes: add or update a scene in `tests/ui/shoot.py`, run
  `make screenshots` and look at the scenes that changed (a scene that
  reports FAIL may be the headless display's blank-frame race: run it
  again before suspecting the change).
- While working, `make test` (no display, seconds); before finishing,
  `make check` (everything, on the headless display), and report the
  real results. Both print one line when all pass, and only the failures
  otherwise (`tests/run_quiet.py`); `make test-verbose` is for people.

## 3. Docs: PLAN.md, DESIGN.md, the user guide and README.md

Check all three every time. The two docs are indexes: read them, then
open only the files the change needs.

- **Features, bugs and releases:** documented and indexed only as
  `software-design` *Tracking work* says.
- Update the test counts in PLAN.md's *Current state*.
- **docs/DESIGN.md** and **docs/design/**: update
  `design/DESIGN_UML.md` and `design/DESIGN_DB.md` when what they show
  changes; the package layout (§4.1), `AppContext` and seams (§4.2),
  settings keys (§11), and any section whose behaviour changed. Mermaid
  diagrams stay in line with the code; note the Feature or Bug that
  introduced a behaviour there (never a milestone), never in the code.
- **Every request, the standing sections** (`software-design`'s rule;
  here): `design/01-goals-and-non-goals.md` (direction: the recorder and
  window split, pluggable GPU details, customisation, the Web UI and
  network monitoring to come), `design/03-technology-decisions.md`,
  `design/04-architecture-overview.md`, `design/10-runtime-flow.md`,
  `design/12-open-decisions.md`, and `design/02-*.md` when Proccoli's
  differences from Resources change.
- `tests/test_docs.py` checks that links resolve, every file is reachable
  from its index, each index stays under 32 KB, and `DESIGN_DB.md` names
  every table the code creates.
- **README.md** is the short page (the layout in `software-project`):
  what Proccoli is, requirements, install, common tasks with screenshots,
  help. **docs/USER-GUIDE.md** is the full user guide: what users see and
  do, keyboard shortcuts, preferences, files Proccoli keeps,
  troubleshooting. A user-visible change goes in the guide, and in the
  README only if it changes one of its tasks. Neither has milestones,
  class names or design references. `make screenshots` refreshes the
  README's images from the demo devices.
- Write as `VOICE.md` says, for the readers in `AUDIENCE.md`. Spell it
  "color" (American) in code, UI text and docs alike.

## 4. Light refactoring

As `software-design` says. Anything bigger (moving modules, changing
interfaces across layers) gets its own feature file, like
`docs/plan/features/feature-21-*.md`.

## 5. Releases: where the version lives

Follow `software-project`'s release steps. The version is written in:

- `src/proccoli/__init__.py` (`__version__`; `packaging/build-deb.sh`
  reads it);
- `data/io.github.mamadingleberry.Proccoli.metainfo.xml` (a new
  `<release>` with the description);
- `README.md` and `docs/USER-GUIDE.md` (the `.deb` names;
  `tests/test_meta.py` checks them).

Before tagging: `make check`, then `make screenshots` (it also refreshes
the README's images). Build with `packaging/build-deb.sh`; it writes `dist/proccoli_X.Y.Z_all.deb`
and `dist/proccoli-gui_X.Y.Z_all.deb`, which the GitHub release attaches.

## Finishing checklist

- [ ] New code is injectable and reaches the OS only through `SysRoot` /
      `System` / other injected seams
- [ ] Tests added or updated; `make check` passes (and `make screenshots`
      for visual changes)
- [ ] PLAN.md: the feature's or bug's file, its index line, *Unreleased*,
      test counts
- [ ] DESIGN.md: the section files, `DESIGN_UML.md` and `DESIGN_DB.md`
      match the code
- [ ] docs/USER-GUIDE.md (and README.md if a task changed): user-visible changes described
- [ ] Light refactoring done where the change touched messy code
- [ ] The response ends with `software-design`'s summary, test report and
      next steps
