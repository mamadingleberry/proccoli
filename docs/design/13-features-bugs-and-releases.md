# 13. Features, Bugs and Releases

How work on Proccoli is tracked (Feature 26). The rules (which files,
what they hold, their statuses, which index line changes when) are in the
`software-design` skill's *Tracking work* section
(`.claude/skills/software-design/SKILL.md`) and only there; releases are
cut as the `software-project` skill says. This section is the picture.

```mermaid
erDiagram
    RELEASE ||--o{ FEATURE : ships
    RELEASE ||--o{ BUG : fixes
    RELEASE ||--o{ ARCHIVED_MILESTONE : "shipped (history)"
    FEATURE ||--o| FEATURE_DESIGN : "design note"
    BUG ||--o| BUG_DESIGN : "design note"
```
