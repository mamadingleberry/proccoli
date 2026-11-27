# Milestone 85: The docs as indexes, one file per topic

*✅ Done.* Was Idea 24. PLAN.md (343 KB) and DESIGN.md (195 KB) became
short indexes; each milestone, idea, bug and design section is its own
file under `docs/plan/` and `docs/design/`, linked from them; a test keeps
the links and the index sizes honest

See [Idea 24](../ideas/idea-24-docs-as-indexes-with-one-file.md) for the
decision and the file names.

| Step | Create / change | Test |
|---|---|---|
| 85.1 | A one-off script (not kept) splits both documents by heading: `## Milestone`, `### Idea`, `### Bug` in PLAN; DESIGN's top sections, the long ones (UI, GPU) by subsection, §13 and §14 by idea and bug. Section references become relative links; links aren't added inside code blocks | Every original non-heading line is in the new files, except the intros the indexes replace |
| 85.2 | `docs/PLAN.md` and `docs/DESIGN.md` written as indexes; the Progress table's notes became each milestone's first line; the early *Deviations* list is `docs/plan/early-deviations.md` | — |
| 85.3 | `CLAUDE.md` rule 7 and the `proccoli-change` skill: how to read and add to the docs | — |
| 85.4 | `tests/test_docs.py` | Unit: links resolve, every split file is in its index, each index under 32 KB; fails on a broken link or an unlisted file |

**Done when:** a change reads PLAN.md and DESIGN.md (under 32 KB each)
plus the few files it touches, not 540 KB.

*Measured:* PLAN.md 343 231 → 16 161 bytes; DESIGN.md
194 972 → 7 582 bytes (about 85 000 and 50 000 tokens → 4 000 and
2 000). 200 topic files, the largest
17 053 bytes. Tests: 1160 (873 without a display).
