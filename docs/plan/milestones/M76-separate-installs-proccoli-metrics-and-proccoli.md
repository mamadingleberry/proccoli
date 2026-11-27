# Milestone 76: Separate installs: `proccoli-metrics` and `proccoli-gui`

*✅ Done.* Was Idea 15. `packaging/split.py` puts every source file in one part; `install.sh --metrics / --gui`; three debs: `proccoli-metrics` (no GTK), `proccoli-gui` (needs the same metrics), `proccoli` (both), taking over the old single package's files. A static test keeps the library free of the GUI at any level

Was Idea 15 (kept below with its design). Steps I15.1–I15.6, with the
deviations listed after the table.

| Step | Create / change | Test |
|---|---|---|
| 76.1 | `packaging/split.py`: `part(path)` ("metrics" or "gui": `ui/`, `helper/`, `app.py`, `__main__.py` and `GUI_IN_DOMAIN`, the GPU tabs' views); `tests/test_static.py` takes `UI_IN_DOMAIN` from it | Static: nothing in the metrics part imports the GUI part, Gtk, Gdk or Adw at any level, except inside `create_views`; every source file is in exactly one part (and synthetic crossings are caught) |
| 76.2 | `install.sh --metrics / --gui` (both by default), from `split.py`'s lists; the schema and the unit with the metrics part; uninstalling the metrics part refuses while the window is installed, and installing the window refuses without it | `test_packaging`: the two parts together are the whole install, with no file in both; the refusals; the metrics part installed alone builds the collector and reads a fixture machine with Gtk, Gdk and Adw blocked |
| 76.3 | `build-deb.sh`: three packages; `Replaces: proccoli (<= version)`, `Breaks: proccoli (<< version)`; `proccoli-gui` depends on `proccoli-metrics (= version)`; `proccoli-metrics`' `prerm` stops each logged-in user's collector on removal | `test_packaging.DebTest`: the metrics package needs no GTK, the GUI the same metrics, no file in two packages, the meta package installs both, the takeover fields, the `prerm`. By hand: upgrade from the single 0.4.0 package in a scratch dpkg root (below) |
| 76.4 | A newer schema stops a writer (I15.5) | Done in M75 (`NewerSchema`) |
| 76.5 | README *Installing* (the three packages, a server install), *Uninstalling*; [DESIGN §4.1](../../design/04-architecture-overview.md), [Idea 15's design](../../design/ideas/idea-15-separate-installs-proccoli-and-proccoli-gui.md) as built | `test_meta`: the README's package versions |

**Decisions on Idea 15's open questions** (the design's leanings):
(1) three packages, `proccoli` installing both; (2) the window *depends*
on `proccoli-metrics`, no third common package; (3) no command-line
export yet (`--status` and `--once` came with M75).

**Deviations from Idea 15, and why:**
- **No committed `files-metrics.txt` / `files-gui.txt`:** `install.sh`
  asks `split.py` at install time, so a new file can't be left out of a
  stale list.
- **`clients.py` keeps its name:** it's listed in `GUI_IN_DOMAIN`
  beside the views, which is the one list both the split and the static
  tests read.
- **`Replaces` covers the same version (`<=`):** no release has been made
  since 0.4.0, so the version is still 0.4.0; with `<<` the new packages
  couldn't take files over from a 0.4.0 single package (yours is one).
  `Breaks` stays `<<`, or it would break the new `proccoli` itself.
- **No `deb-systemd-helper --user`:** `prerm` stops running collectors
  with `systemctl --user -M user@`; an enabled user's
  `default.target.wants` link is left pointing at nothing, which systemd
  skips.

**Checked by hand** (dpkg `--root` in a scratch folder, dependencies
forced since the folder has no system packages): the previous single
`proccoli` 0.4.0 package installed, then the three new ones together:
"Replacing files in old package proccoli (0.4.0)", all three installed,
`proccoli-metrics` owning 62 Python files, `proccoli-gui` 69, `proccoli`
only its copyright. Removing `proccoli` and `proccoli-gui` left the
metrics part complete; removing it too left no files.
