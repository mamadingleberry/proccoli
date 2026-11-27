# Idea 20: Preferences in named sections

Plan: [plan/ideas/idea-20-preferences-in-named-sections.md](../../plan/ideas/idea-20-preferences-in-named-sections.md)


*[PLAN.md, Idea 20](../../plan/ideas/idea-20-preferences-in-named-sections.md). Built in M88; [§9](../09-ui-layer.md) describes it as built.* Preferences built from a display-free layout table:
pages, groups and order per settings key, with long lists as subpages.

```mermaid
flowchart LR
    L["ui/preferences_layout.py<br/>key → page, group, order<br/>subpages for long lists"] --> D["PreferencesDialog<br/>(Adw.PreferencesDialog)"]
    D --> P1["Appearance"]
    D --> P2["Sidebar → entry subpages"]
    D --> P3["Tables → Apps / Processes columns<br/>(expander rows)"]
    D --> P4["Recording"]
    D --> P5["Devices → a switch per GPU"]
    D --> P6["System"]
```

- Actions and status rows sit in their own group at a page's end.
- A unit test checks every user-facing key appears exactly once.
