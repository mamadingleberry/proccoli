# Feature 29: General engineering skills under a Proccoli skill

Design note: [design/features/feature-29-engineering-skills.md](../../design/features/feature-29-engineering-skills.md)

*✅ Built; in v0.6.0.* `proccoli-change` is renamed
`proccoli-engineer` and keeps only what is specific to Proccoli; it
references four new, project-neutral skills in `.claude/skills/`:

- **`software-project`**: basic standards, and a reminder to consider the
  three below on every code change. Committing, cutting a release and
  tagging on GitHub, with where versions live (`src/proccoli/__init__.py`,
  `data/*.metainfo.xml`, `README.md`, `packaging/`). The README layout:
  what the app is, a note on Claude's part in writing it, SECURITY.md,
  LICENSE, minimum requirements (OS, CPU, memory), install, basic use;
  nothing about the project's structure. CLAUDE.md and `.claude/skills/`
  set up; CLAUDE.md imports VOICE.md and AUDIENCE.md
  ([Feature 28](feature-28-voice-and-audience.md)).
- **`software-design`**: short and direct. The `docs/` layout (indexes,
  one file per topic), UML standards, database standards (OLTP vs OLAP;
  CSV, Avro, Parquet; SQLite, DuckDB; schemas; permissions; where files
  live), cohesion and decoupling, light vs heavy refactors, tracking
  Features, Releases and Bugs ([Feature 26](feature-26-releases-and-features.md)),
  logging, UTC for every stored time, other data standards, memory and
  CPU. The end of every response: (1) a summary of the changes with the
  paths of the docs written, (2) a short test report, (3) an offer to
  fix a bug or build a feature (listed to choose from) and/or to update
  docs or skills.
- **`software-testing`**: unit and integration test standards.
- **`application-design`**: the high-level split (a background recorder
  vs. a window that only shows), color blindness and other usability,
  i18n and other optional standards considered but applied only when
  asked, the user's flow through the app kept efficient.

| Step | Create / change | Test |
|---|---|---|
| F29.1 | The four skills, each a short `SKILL.md` | Read through |
| F29.2 | Rename `proccoli-change` to `proccoli-engineer`; cut what moved, link the four | `test_docs` / `test_static` paths that name the skill |
| F29.3 | CLAUDE.md names `proccoli-engineer`; README follows the `software-project` layout (with [Feature 11](feature-11-a-shorter-friendlier-readme.md)) | `test_meta` |

**Changed while doing it:** the user asked that the generic standards
come from the `engineering-skills` plugin (alirezarezvani/claude-skills,
marketplace `claude-code-skills`), required by CLAUDE.md and referenced
from `software-project`. Our four skills keep only what the plugin
doesn't cover. Where they differ, the user chose ours:

| Topic | Plugin | Ours (chosen) |
|---|---|---|
| Decisions | Separate ADRs (`senior-architect`) | In the Feature's design note, under ADR headings (Context, Options, Decision, Trade-offs) |
| Diagrams | Mermaid, PlantUML or ASCII | Mermaid only |
| Database | SQL vs NoSQL, PostgreSQL by default | OLTP vs OLAP; SQLite for a desktop app |
| Specs | `specs/<feature>.md`, "AC-n" tags in tests | The feature's plan file; no planning numbers in tests |

Adopted from the plugin: `tdd-guide`'s red-green-refactor and
`red-green-proof`'s "revert the fix and see the test fail" for bugs.

**Left for the user:** enabling the plugin for the project in
`.claude/settings.json` (`extraKnownMarketplaces` and `enabledPlugins`)
was not written by Claude; the user adds it or installs the plugin with
`/plugin`.
