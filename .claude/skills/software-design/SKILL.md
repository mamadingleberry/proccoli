---
name: software-design
description: Design standards on top of the engineering-skills plugin's senior-architect, straight to the point - docs layout, decisions, Mermaid-only UML, database and data-file standards, light vs heavy refactors, tracking Features, Releases and Bugs, logging, UTC times, memory and CPU, and the end-of-response report. Use with every code change (via software-project) and whenever designing, documenting or refactoring.
---

# Software design standards

**The general practice comes from the `engineering-skills` plugin:**
`senior-architect` (architecture patterns, monolith vs services,
dependency analysis), `code-reviewer` (reviews), and the domain skills
(`senior-backend`, `senior-data-engineer`...) when a project has that
part. This skill adds what they don't say, and **wins where they
differ**: decisions live in design notes (not separate ADRs), diagrams
are Mermaid only, and the database choice follows *Data and databases*
below.

## Documentation layout

- `docs/DESIGN.md` (how it's built) and `docs/PLAN.md` (what's planned,
  built and released) are **short indexes**: one line per topic, no
  detail. Each topic is its own file in `docs/design/` or `docs/plan/`,
  named after its number so it opens without the index.
- `docs/design/DESIGN_UML.md` and `docs/design/DESIGN_DB.md` are the
  standing overviews; keep them current with every change that touches
  what they show.
- **The standing design sections drift unless checked.** With every
  request, ask whether it changes:
  - the **direction** (a new goal, a non-goal dropped or added, a
    future direction): update *Goals and non-goals*;
  - a **technology choice** (a library, a store, a protocol, a platform
    floor): update *Technology decisions*;
  - the **shape** (a program, layer, package or how they talk): update
    the architecture overview, the runtime flow and `DESIGN_UML.md`;
  - an **open question** (asked, answered or newly raised): update *Open
    decisions*.
  Say in the response's summary which of them were updated, or that none
  needed to be. A request that only touches a feature still counts: a
  feature can settle an open decision or retire a non-goal.
- Provenance in the design cites the **Feature or Bug** that brought a
  behaviour (stable numbers), or the **release** for work from before
  features were tracked; never archived planning units such as
  milestones. Describe the design as it is now; history of how it got
  there belongs in the plan files.
- Read the index, then only the files the change needs.
- Relative links between files; a test checks they resolve and that every
  file is reachable from its index.
- No planning references (feature, bug, release or step numbers, doc
  sections) in code, comments or tests: those belong in `docs/`.

## Decisions

- A decision is recorded in the design note of the Feature that needed
  it, under the ADR headings: **Context**, **Options** (a table: how, for,
  against), **Decision**, **Trade-offs**. No separate ADR folder.
- Decisions not yet made wait in the design's *Open decisions* section, or
  in *Requires Human Input* when the user must choose.

## UML

- **Mermaid only**, in the markdown, so it renders on GitHub and diffs as
  text. No PlantUML or ASCII art. `senior-architect`'s diagram generator
  may be a starting point with `--format mermaid`; trim what it draws to
  what matters.
- Use the diagram that answers the question: `flowchart` for deployment,
  packages and flows; `classDiagram` for structure; `sequenceDiagram` for
  interactions over time; `stateDiagram-v2` for lifecycles; `erDiagram`
  for data.
- Show the important 10–20 boxes, not every class. Name boxes as the code
  does.
- Change the diagram in the same change as the code.

## Data and databases

These replace `senior-architect`'s *Database Selection Workflow* (which
defaults to PostgreSQL for server applications).

- **OLTP** (many small writes, reads by key or recent time range: app
  state, a metrics recorder): SQLite (embedded, one file) or PostgreSQL
  (shared, many writers). Normalised tables, a primary key per table,
  indexes for the queries that run.
- **OLAP** (scans and aggregates over much history: reports, analysis):
  DuckDB or a columnar file; wide or star schemas; partition by time.
- **Files:** CSV for people and spreadsheets (always a header row, UTF-8,
  units in column names); JSON / JSON Lines for nested records and logs;
  Parquet for columnar analysis (typed, compressed); Avro for row-wise
  streams with an evolving schema.
- **Schemas:** a version in the store; migrations that only add (new
  tables, new nullable columns) where possible; refuse to write a newer
  schema than the code knows.
- **Retention:** say how long each level is kept and the size cap, and
  enforce both without needing a restart; summarise (minute, hour) as data
  ages.
- **Security and permissions:** user data private by default (files
  `0600`, folders `0700`); least privilege for anything shared (a group, a
  dedicated user); no secrets in the database or logs.
- **Storage:** follow the platform's places: on Linux,
  `$XDG_STATE_HOME` for history and logs, `$XDG_CONFIG_HOME` for config,
  `$XDG_CACHE_HOME` for what can be rebuilt, `/var/lib/<app>` for system
  services.

## Time and other data standards

- Store and send every timestamp in **UTC** (epoch milliseconds, or ISO
  8601 with `Z`). Convert to local time only to show it, using the
  system's time zone; never store local time.
- Durations and intervals use monotonic clocks, not wall-clock time.
- Store numbers with their unit (in the column name or a units table);
  fixed-point integers where exactness matters.
- Text is UTF-8.

## Logging

- One log per program, in its state folder, rotated or capped in size.
- Levels: `ERROR` (something failed for the user), `WARNING` (degraded,
  carrying on), `INFO` (lifecycle: start, stop, settings that matter),
  `DEBUG` (detail, off by default).
- Timestamps in UTC; name the component; one event per line.
- Never log secrets, passwords or other users' data.

## Cohesion and decoupling

Patterns and their trade-offs are in `senior-architect`. In addition:

- Inject dependencies through one composition root; reach the OS only
  through small seams that tests fake.
- Pure, display-free functions for decisions and arithmetic; widgets and
  handlers stay thin.

## Refactoring

- **Light** (every change, if useful and small): remove duplication you
  touch, extract a helper from a long function, rename for clarity, delete
  dead code and stale comments. Keeps the tests green; no interface changes
  across layers.
- **Heavy** (its own planned feature): when the same thing is built
  several ways (many graphs with no shared base or library), when a
  responsibility belongs in another process or layer (a background monitor
  split from the GUI), or when an interface across layers changes. Plan it
  with steps and tests; do it in steps that each keep the tests green.

## Tracking work: Features, Bugs and Releases

**What each is**

- **Feature**: something the software should do.
- **Bug**: something it does wrong.
- **Release**: a set of built Features and fixed Bugs with a version tag.
  Work done since the last tag collects in *Unreleased*.

**Where each is documented** (`NN` is the number, two digits; `<slug>`
a few words of the title):

| What | Plan side (steps, status) | Design side (how) |
|---|---|---|
| Feature | `docs/plan/features/feature-NN-<slug>.md` | `docs/design/features/feature-NN-<slug>.md` |
| Bug | `docs/plan/bugs/bug-NN-<slug>.md` | `docs/design/bugs/bug-NN-<slug>.md` |
| Release | `docs/plan/releases/vX.Y.Z.md` | — |
| Unreleased work | `docs/plan/releases/unreleased.md` | — |
| Older planning units (history) | `docs/plan/archive/<kind>/` | — |

The two sides link to each other on their first lines.

**What each file holds**

- Feature plan: the status line first; the goal; the decisions settled
  with the user; a `Step | Create / change | Test` table (this is the
  spec); *Found while doing it* notes; superseded steps marked
  *(Superseded by ...)*, never deleted.
- Feature design: the status; the design, its decisions under the ADR
  headings (see *Decisions*) and its Mermaid diagrams.
- Bug plan: the status; *Seen* (the user's words); the cause; the steps;
  the regression test.
- Bug design: the cause in the code, and the fix's design.
- Release: the status (*Not released yet* or *Released <date> as tag …*);
  a one-paragraph description in users' words; *Features* and *Bugs
  fixed* as links; links to any archived units it shipped.

**Statuses**, the first line of each file:

| Feature | Bug |
|---|---|
| `*Open.*` → `*🚧 In progress.*` → `*✅ Built; in Unreleased.*` → `*✅ Built; in vX.Y.Z.*` | `*Open.*` → `*Fixed; in Unreleased.*` → `*Fixed in vX.Y.Z.*` |

**How the indexes change** (`docs/PLAN.md` and `docs/DESIGN.md` hold one
line per file and no detail):

| Event | `docs/PLAN.md` | `docs/DESIGN.md` | Release files |
|---|---|---|---|
| New feature | a line under *Features* | a line under *Features' design notes* | — |
| New bug | a line under *Open bugs* | a line under *Bugs' design notes*, marked *(open)* | — |
| Needs the user's input | — | a bullet under *Features* (or *Bugs*) *that Require Human Input*; once settled it becomes a file and an index line, and the bullet goes | — |
| Feature built | its line moves to the *Built* line | unchanged | added to `unreleased.md` |
| Bug fixed | its line moves to the *Fixed* line | *(open)* → *(fixed)* | added to `unreleased.md` |
| Release cut | a line under *Releases* | — | `unreleased.md` becomes `vX.Y.Z.md`; statuses say *in vX.Y.Z* |

Numbers are never reused; the next one is one more than the highest of
its kind, open or done. Keep both *Requires Human Input* subsections in
`docs/DESIGN.md` even when empty. Archived units are history: new work is
always a Feature or a Bug.

Every link to a numbered file is relative; the file opens from its number
without the index (`docs/plan/features/feature-19-*.md`).

## Memory and CPU

- Measure before optimising; keep a script that measures the app's own
  CPU and memory.
- Do no work nobody sees: pause what's off screen, stop sending when
  nobody subscribes, read lazily.
- Bound every buffer and history; cap files on disk.
- Keep idle cost near zero; batch writes (one transaction per few
  seconds, not per reading).

## The end of every response

**Every** response ends with these three parts, whatever it was: a code
change, a docs-only change, an answer to a question, or a turn
interrupted by a new message. Use these headings (a Stop hook looks for
them):

```markdown
**1. Summary**
What changed or was fixed, or what was answered; the paths of the docs
written or updated (or "no docs changed"); and which standing design
sections (goals, technology, architecture, runtime, open decisions) were
updated, or "none needed".

**2. Test report**
The commands run and their results (ran, passed, failed, skipped); say
which suites weren't run and why. "No code changed; tests not run" is a
valid report.

**3. Next**
a. Fix a bug or build a feature? The open bugs, the bugs and features
   that need the user's input, and the open features, one line each,
   from `docs/PLAN.md` and `docs/DESIGN.md`.
b. Create or update any documentation or Claude skills? (no list)
Plus anything waiting on the user (installs, approvals, commits).
```
