# Milestone 45: User-guide README; previous name removed

*✅ Done.* README is for users only; the one-time settings import from the previous name is gone

| Step | Create / change | Test |
|---|---|---|
| 45.1 | README rewritten as a user guide: what it shows, requirements, install, use, administrator rights, preferences, files it writes, uninstall, troubleshooting, license; an AI-assistance disclaimer as in intel_gpu_top_gui. No milestones or design references | — |
| 45.2 | The previous project name removed everywhere. The one-time settings import from its dconf path is removed with it (`core/legacy.py`, `System.dconf_dump`, `Application(legacy_dump=)`, schema key `legacy-settings-imported`, their tests) | Whole suite; `grep` finds no references |
