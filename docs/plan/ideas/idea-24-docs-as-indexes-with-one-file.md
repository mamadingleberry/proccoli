# Idea 24: The docs as short indexes, with one file per topic

*Done as Milestone 85.*

**Seen:** "condense PLAN.md to major milestones to reduce token usage
(can/should we do similar for DESIGN.md, maybe … put separate
sections/milestones/etc in other markdown files in a subdir … that can be
linked if needed as an LLM reference)".

**Why:** `docs/PLAN.md` had grown to 343 KB (about 85 000 tokens) and
`docs/DESIGN.md` to 195 KB (about 50 000). Every change reads them, or
large parts of them, though it needs one milestone, one bug or one design
section. Both mix what's current with years of history.

**Decision:** both become short indexes; everything else moves to one
file per topic, named so it can be opened without the index:

| Kind | File |
|---|---|
| Milestone 53 | `docs/plan/milestones/M53-<slug>.md` |
| Idea 19 | `docs/plan/ideas/idea-19-<slug>.md` |
| Bug 22 | `docs/plan/bugs/bug-22-<slug>.md` |
| DESIGN section 7.2 | `docs/design/07.2-<slug>.md` (a short section keeps its subsections in one file, `docs/design/05-<slug>.md`) |
| An idea's or bug's design note | `docs/design/ideas/idea-19-<slug>.md`, `docs/design/bugs/bug-22-<slug>.md` |

- **PLAN.md** keeps the working rules, the current state (test counts,
  platform floor), the open bugs, the ideas, and the milestones grouped
  into five major phases, one line each, linked.
- **DESIGN.md** keeps what the design is for and a linked contents list.
- Design notes for ideas and bugs carry the plan's number (DESIGN's §13
  had its own numbering, one off from the ideas after Idea 5); section
  references in the moved text became links, and §13/§14 references now
  read "Idea 13's design", "Bug 18's design".
- Each idea and bug file links to its design note, and back.
- A milestone file starts with its status and the one-line summary that
  was its Progress table row.
- The rules go in `CLAUDE.md` and the `proccoli-change` skill: read the
  index, open only the files the change needs; new work gets a new file
  and one index line.
- `tests/test_docs.py` keeps it so: every relative link resolves, every
  file under `docs/plan/` and `docs/design/` is linked from its index,
  and the two indexes stay under 32 KB each.
