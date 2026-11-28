# Feature 26: Releases and Features instead of Milestones and Ideas

Design note: [design/features/feature-26-releases-and-features.md](../../design/features/feature-26-releases-and-features.md)

*✅ Built; in v0.6.0* (F26.5, publishing on GitHub, waits for the user's approval of the notes). Work is tracked as **Features** (formerly
"Ideas") and **Bugs**; a **Release** is a set of Features and Bug fixes
with a version tag. Milestones go away.

**Settled:**
- "Ideas" become "Features" everywhere in the repo (files, indexes,
  headings, links, the skill). "Fixtures" in the request was a slip:
  `tests/fixtures/` keeps its meaning.
- The 89 milestone files are grouped into releases, one file each:
  v0.1.0 = M0–M52, v0.2.0 = M53–M59, v0.3.0 = M60–M67, v0.4.0 = M68,
  v0.5.0 = M69–M84, *Unreleased* = M85–M89. Milestone files move to
  `plan/archive/milestones/` and are linked from their release.
- When the user asks for a release, Claude collects the Features and
  Bugs done since the last tag into the release file, and uses that
  file's description and list as the tag message and the GitHub release
  notes.
- Release notes for v0.1.0, v0.2.0 and v0.3.0 are drafted in the repo
  first; the user approves them before any GitHub release is created or
  edited.

**Found while settling it:** the `v0.5.0` tag points at `a2eab5a` (the
0.4.0 commit), not `02a83f0` ("Proccoli 0.5.0"), and v0.1.0 and v0.2.0
have no GitHub release. Moving the tag is part of the approved GitHub
step.

| Step | Create / change | Test |
|---|---|---|
| F26.1 | `plan/releases/v0.1.0.md` … `v0.5.0.md`, `unreleased.md`: summary, Features, Bugs fixed, milestones archived | `test_docs`: every release in the index; links resolve |
| F26.2 | Move `plan/archive/milestones/` to `plan/archive/milestones/`; PLAN.md lists releases instead of phases | `test_docs` |
| F26.3 | Rename ideas to features: `plan/features/feature-NN-*.md`, `design/features/…`, the index headings, CLAUDE.md, the skill | `test_docs`; `test_static`'s planning-reference check also matches "Feature N" and "Release N" |
| F26.4 | DESIGN.md: how Releases, Features and Bugs relate, and Claude's release steps | Read through |
| F26.5 | Draft v0.1.0–v0.3.0 notes; after the user approves: GitHub releases for v0.1.0 and v0.2.0, edit v0.3.0, move `v0.5.0` to `02a83f0` | `gh release list` shows five releases |

**Found while doing it:**
- v0.5.0's commit (`02a83f0`) already held v0.5.0 (its PLAN.md lists it), so
  v0.5.0 is M69–M84 and *Unreleased* starts at M85.
- The index test now asks that every file be *reachable* from its index
  (PLAN.md links the releases, and each release links its archived
  milestones), so PLAN.md stays small.
- Three planning references had slipped into code across a line break
  ("(Milestone\n51)"); `test_static` now catches those, and "Feature N"
  and "Release vN".
- The release notes for v0.1.0–v0.3.0 are drafted as their release files;
  nothing on GitHub has changed yet.
