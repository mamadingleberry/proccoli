# Milestone 88: Preferences in six named pages

*✅ Done.* Was Idea 20. The long *General* page is gone: Appearance,
Sidebar, Tables, Recording, Devices and System, built from a display-free
layout that a test holds to every setting

See [Idea 20](../ideas/idea-20-preferences-in-named-sections.md) for the
proposal. Answers to its questions: the six pages as proposed; graph
options (axes, grids, time range) and units on *Appearance*; the bottom
switcher.

| Step | Create / change | Test |
|---|---|---|
| 88.1 | `ui/preferences_layout.py`: `PAGES` (pages → groups → items), `SPECIAL` (rows that set several keys or need a service), `ELSEWHERE` (settings set outside Preferences, and where); the column lists moved here | Unit: every schema key placed once or in `ELSEWHERE`, never both; items are keys or special; six pages in order; no page over 12 rows; graph options on Appearance; actions and status last on Recording |
| 88.2 | `ui/dialogs/preferences.py`: built from the layout through `_builders()`; groups without their service hidden (rows counted as added, since `PreferencesGroup.get_row` needs libadwaita 1.6); Lightweight Mode's notice points at System → Memory Use | UI: every switch works both ways (the set from the layout); every row on its page; a builder for every item; the column lists open in place; hidden and shown groups |
| 88.3 | `tests/ui/shoot.py`: a scene per page (`preferences-<page>`) | Screenshots |
| 88.4 | README *Preferences* and every "Preferences → General" path; DESIGN §9 and §4.1 | — |
| 88.5 | *Found while doing 88:* Bug 20's `has_chart()` failed on a summary whose series list holds `None` (pages pass a missing series that way); it now skips them | Unit: `[None]` has no chart, `[None, series]` has one |

**Deviations:**

- **Column lists as expander rows, not subpages.** `Adw.PreferencesDialog`
  search doesn't look into pushed subpages, so the proposal's "search
  finds a subpage row" doesn't hold; today's column switches are
  searchable. Expander rows keep the page short and every column
  findable.
- **No subpage per GPU.** A GPU has one switch; a subpage would add a click
  for it. They stay rows on *Devices*.

**Done when:** each page fits on screen without its column lists open,
and a new setting can't be added without a place in Preferences or a
reason in `ELSEWHERE`.
