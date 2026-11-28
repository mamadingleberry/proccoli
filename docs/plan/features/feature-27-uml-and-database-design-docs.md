# Feature 27: Always-current UML and database design docs

Design note: [design/features/feature-27-uml-and-database-design-docs.md](../../design/features/feature-27-uml-and-database-design-docs.md)

*✅ Built; in v0.6.0.* Two standing documents,
`design/DESIGN_UML.md` (the high-level classes, packages and processes)
and `design/DESIGN_DB.md` (the history database: tables, keys, retention,
who writes and who reads). DESIGN.md links both at the top and says
every change that alters a class, a process or a table updates them.

| Step | Create / change | Test |
|---|---|---|
| F27.1 | `design/DESIGN_UML.md`: package diagram, the recorder/window process diagram, the main class diagram, gathered from §4–§10 | `test_docs` |
| F27.2 | `design/DESIGN_DB.md`: the SQLite schema as a Mermaid ER diagram, read from `history/` | A test that every table in the schema is named in `DESIGN_DB.md` |
| F27.3 | DESIGN.md and the change skill: "update DESIGN_UML / DESIGN_DB with the change" | Read through |
