# Feature 27: UML and database design docs

Plan: [plan/features/feature-27-uml-and-database-design-docs.md](../../plan/features/feature-27-uml-and-database-design-docs.md)

*Built:* [DESIGN_UML.md](../DESIGN_UML.md), [DESIGN_DB.md](../DESIGN_DB.md). The section files keep their detailed diagrams; the two new
files are the overview a reader opens first. A unit test keeps
`DESIGN_DB.md` honest by comparing it with the schema the code creates,
so it can't drift silently.
