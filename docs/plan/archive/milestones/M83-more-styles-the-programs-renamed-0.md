# Milestone 83: More styles; the programs renamed; 0.5.0

*✅ Done.* 18 more styles (High Contrast Light and Dark among them); the recorder is now `proccoli` (program, unit, package) and the window `proccoli-gui`; the meta package is gone; version 0.5.0

Asked for after M82: "add a lot more style options. and then i want the
proccoli back process to be renamed from 'proccoli-metric' to 'proccoli'
and 'proccoli' to be renamed to 'proccoli-gui'", and "i need this version
bumped to 0.5.0".

| Step | Create / change | Test |
|---|---|---|
| 83.1 | `core/styles.py`: light tints Mint, Rose, Lavender, Paper, Solarized Light, Gruvbox Light, Catppuccin Latte, High Contrast Light; dark tints Nord, Dracula, Gruvbox Dark, Solarized Dark, Catppuccin Mocha, Tokyo Night, Forest, Ember, Black, High Contrast Dark. Light tints listed before dark ones; the schema's `ColorScheme` enum in the same order (existing values kept); `shoot.py` scenes `style-*` | Unit: ids and names unique; light before dark; high contrast is pure black and white; existing rules (7:1 text on every surface, light styles light) cover them all |
| 83.2 | The recorder's program, unit and package become `proccoli` (`data/proccoli.service`, `data/proccoli.preset`, log `proccoli.log`); the window's program becomes `proccoli-gui` (desktop `Exec`, log `proccoli-gui.log`); the names live once, as `COLLECTOR` and `WINDOW` in `proccoli/__init__.py` | Unit: desktop file runs `proccoli-gui`; the debs hold `/usr/bin/proccoli` and `/usr/bin/proccoli-gui`; log paths |
| 83.3 | Packages: `proccoli` (the recorder) and `proccoli-gui` (depends on it); the meta package is gone. `proccoli` *Conflicts* and *Replaces* `proccoli-metrics` and *Replaces*/*Breaks* `proccoli-gui (<< 0.5.0)` (which owned `/usr/bin/proccoli`); its `postinst` disables the old unit; `install.sh` removes the old program and unit | Unit: two debs; the relationships; `postinst` disables `proccoli-metrics.service`; installing over the old names removes them |
| 83.4 | Version 0.5.0: `__version__`, metainfo release notes, README | `test_meta` (README installs this version) |

**Decision:** the recorder takes the plain name because it's the part
every install has (alone on a server); the window is the add-on. The
D-Bus name (`<app ID>.Metrics`) and the Python modules (`proccoli.metrics`,
`metrics_service`) keep their names: they're interfaces and code, not
what people run.

**Upgrade path:** from 0.4.0, `apt install` of both new debs upgrades the
old meta package `proccoli` to the recorder, removes `proccoli-metrics`
(its `prerm` stops the old unit for every user), and the new `postinst`
enables and starts `proccoli.service`. The history and settings are the
same files.
