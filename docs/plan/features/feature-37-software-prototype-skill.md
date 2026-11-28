# Feature 37: A `software-prototype` skill for quick ideas

Design note: [design/features/feature-37-software-prototype-skill.md](../../design/features/feature-37-software-prototype-skill.md)

*Open.* Asked: "a watered down version of `software-project` for quicker
idea-to-creation turnaround time".

**Goal:** a general skill for trying an idea fast, in this repo or a new
one, that keeps what makes later work cheap and drops what slows a first
version down.

**Sketch: what it keeps and what it drops from `software-project`:**

| | `software-project` | `software-prototype` |
|---|---|---|
| Tests | With the code, both suites before "done" | A smoke test of the main path; unit tests only for tricky logic |
| Docs | Plan, design, user guide, UML/DB overviews, standing sections | One `PROTOTYPE.md`: the idea, how to run it, what's faked, what's next |
| Tracking | A Feature file, index lines, release notes | None until it's kept; then it becomes a Feature |
| Design | Seams, layers, composition root | Seams only where the OS is touched (so it can graduate); no layering rules |
| Ending | Summary, test report, next list | Summary and how to try it |
| Kept always | No secrets committed; nothing published without asking; UTC times; runs from a clean checkout | same |

- **Graduating:** a checklist for turning a prototype into a Feature
  (add the Feature file, tests, docs; move code behind the seams).
- **Where it applies:** a prototype lives on its own branch or folder
  (`prototypes/<name>/` or a new repo), never mixed into `main` unasked,
  so the stricter rules and `tests/test_static.py` don't block it.

| Step | Create / change | Test |
|---|---|---|
| F37.1 | `.claude/skills/software-prototype/SKILL.md` | Read through |
| F37.2 | `software-project` and `proccoli-engineer` say when to use it, and the graduation checklist | Read through |

**Open questions for the user:**
1. In this repo, where do prototypes live: a `prototypes/` folder, a
   branch, or always a new repository?
2. Should the Stop hook's three-part ending apply to prototype work too,
   or only *Summary* and *How to try it*?
