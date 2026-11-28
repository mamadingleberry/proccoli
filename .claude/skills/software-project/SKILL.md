---
name: software-project
description: Basic software engineering standards for any project, the entry point to the engineering-skills plugin and to software-design, software-testing and application-design. Use with every code change, and when committing, cutting a release or tag, setting up a repo (README, SECURITY.md, LICENSE, CLAUDE.md, .claude/skills/), or writing the end-of-response summary.
---

# Software project standards

The basics every change keeps.

## The engineering-skills plugin

The generic engineering practice comes from the **`engineering-skills`**
plugin (alirezarezvani/claude-skills, marketplace `claude-code-skills`).
Start from its router skill, `engineering-skills`, and load only the one
skill a task needs:

| Task | Plugin skill |
|---|---|
| Architecture, patterns, splitting a component | `senior-architect` |
| Writing tests, test-first, coverage | `tdd-guide` |
| Fixing a bug | `red-green-proof` |
| Reviewing a change | `code-reviewer` |
| Security-sensitive code (privileged helpers, D-Bus, files) | `senior-security` |
| CI pipelines | `senior-devops` |

The skills below and the project's own skill add what the plugin doesn't
cover and **win where they differ** (decisions in design notes, Mermaid
only, the database standard, specs in the plan files, no planning
references in code). If it isn't installed:
`/plugin marketplace add alirezarezvani/claude-skills`, then
`/plugin install engineering-skills@claude-code-skills`.

## Our skills

On **every code change**, also consider:

- **software-design**: docs layout, UML, data, refactoring, tracking,
  logging, time, resources, and the end-of-response report;
- **software-testing**: what to test and how;
- **application-design**: the shape of the application and its users.

A project's own skill (for example `proccoli-engineer`) says where these
standards live in that repo; follow it over this one where they differ.

## Every change

1. Read the project's CLAUDE.md and its own skill first.
2. Design so it can be tested; write the test with the code.
3. Keep the build green: run the whole test suite before saying it's done,
   and report real results, failures included.
4. Update the docs the change touches (design, plan, user guide) in the
   same change.
5. Leave touched code a little better (see software-design).
6. Never commit secrets (`.env`, keys, tokens, `settings.local.json`).

## Committing

- Commit only when the user asks. Never commit to the default branch
  without being asked: branch first.
- One logical change per commit; the subject says what changed in the
  imperative ("Add F2 for Preferences"), at most about 70 characters; the
  body says why.
- Tests pass at every commit.

## Releases and tags

A release is a set of built features and fixed bugs (see software-design,
*Tracking work*). When the user asks for one:

1. **Collect** the features and bugs done since the last tag
   (`git describe --tags --abbrev=0`, `git log <tag>..HEAD`, the tracking
   files).
2. **Write the release notes**: a one-paragraph description in users'
   words, then *Features* and *Bugs fixed*. The repo's release file is the
   single source; the tag message and the GitHub notes copy it.
3. **Bump the version** in every place it's written: the code's version
   constant, the package metadata (AppStream metainfo, `pyproject.toml`,
   `package.json`...), install instructions in the README, and any
   changelog. The project skill lists the exact paths; a test should check
   they agree.
4. **Test and build** the packages.
5. **Commit** "<Name> X.Y.Z", then an **annotated tag** on that commit:
   `git tag -a vX.Y.Z -m "<description>"`. Check that the tag points at
   the release commit (`git rev-list -n1 vX.Y.Z`).
6. **Publish only when the user says so** (it's public and hard to undo):
   `git push origin <branch> vX.Y.Z`, then
   `gh release create vX.Y.Z --title "<Name> X.Y.Z" --notes-file <notes>`
   with the packages attached. Editing an existing release:
   `gh release edit`. Moving a published tag needs the user's explicit
   go-ahead.

Versions follow [Semantic Versioning](https://semver.org): MAJOR for
breaking changes, MINOR for features, PATCH for fixes; `0.y.z` while the
project is young.

## The repository

Every repo has:

- **README.md**: for users only, in this order:
  1. what the application is and does (a screenshot helps);
  2. a short disclaimer that it was written with Claude (an AI assistant)
     and reviewed by its maintainer;
  3. minimum requirements: OS and versions, CPU, memory, disk, and any
     required packages;
  4. installing (and upgrading, and removing);
  5. basic use;
  6. links to SECURITY.md and LICENSE.
  Nothing about how the project is structured or built inside: that's
  `docs/`.
- **SECURITY.md**: supported versions and how to report a vulnerability.
- **LICENSE** (or `LICENSE.md`).
- **CLAUDE.md**: what the project is, the commands, the platform floor,
  which skill to load before a change; it imports `VOICE.md` and
  `AUDIENCE.md` (`@VOICE.md`, `@AUDIENCE.md`).
- **VOICE.md** (how text sounds) and **AUDIENCE.md** (who reads what).
- **`.claude/skills/`**: the project's own skill, which references these
  general skills.
- **`docs/`**: design and plan (see software-design).
