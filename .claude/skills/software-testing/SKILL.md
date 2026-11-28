---
name: software-testing
description: Testing rules on top of the engineering-skills plugin's tdd-guide and red-green-proof - isolation from the real machine, injected clocks, static tests, headless UI smoke tests, skips, and honest reporting. Use with every code change (via software-project) and when adding or fixing tests.
---

# Software testing standards

**The general practice comes from the `engineering-skills` plugin:**
`tdd-guide` (red-green-refactor, fixtures and mocks, table-driven,
property-based and mutation testing, coverage gaps) and `red-green-proof`
(for every bug: prove the cause, write a test that fails, fix it, then
revert the fix and see the test fail again). This skill adds only what
they don't say, and wins where they differ.

## Where specs live (instead of `tdd-guide`'s `specs/`)

- A feature's spec is its plan file (`docs/plan/features/feature-NN-*.md`
  in Proccoli): each `Step | Create / change | Test` row names the test
  that proves it. There's no separate `specs/` folder.
- Tests carry **no** acceptance-criterion or planning numbers ("AC-3",
  "Feature 19"). The test's name says the behaviour; the plan file links
  to it. A static test enforces this.

## Isolation

- Never touch the user's real files, services, settings or session bus
  from a test: a temporary folder, a fake file tree, in-memory settings,
  a private D-Bus daemon.
- No sleeps: drive time with an injected clock and timer.
- Fixtures are captured from real machines, kept small and checked in.
- Unique test names within a file; tests run in any order.

## Kinds of tests (beyond unit and integration)

- **UI smoke:** build the widget or window on a private headless display,
  feed it data, check it shows and doesn't crash; screenshots for visual
  changes.
- **Static:** tests that read the source to enforce the project's rules
  (layering, no direct OS calls, no planning references, docs links,
  platform-floor APIs).
- **Upgrade:** a new setting, file, schema or protocol change also gets a
  test that reads what the previous version wrote.

## Skips and reporting

- A test that needs something unavailable (a display, a tool) skips with
  a reason rather than failing.
- Run the fast suite while working and the whole suite before saying
  it's done. Report the real numbers (ran, passed, failed, skipped) and
  any failure's output.
- **Critical: only ever run quiet tests.** A project's test command must
  print one summary line when everything passes, and for each failure
  only its name and the end of its traceback; a verbose target is for
  people, never for the agent. A verbose run can cost tens of thousands
  of tokens to read; a quiet one, tens. Don't trim a verbose run with
  `grep`/`tail` instead: use the quiet command.
- **Verify every run was quiet.** After each test run, check the output
  before reading on: a passing run is exactly the summary line; a failing
  run is the failures and the summary line, nothing else. If anything
  more comes out (warnings, prints, per-test lines, a crash dump), stop:
  don't read on, and fix the quiet runner or the noisy test first (or
  report it), then run again. Say in the test report that the runs were
  quiet.
- Slow, rarely-needed checks (screenshots, benchmarks) are their own
  targets, run when a change calls for them and before a release.
- Never weaken a test or a static check to make a change pass: fix the
  change.
