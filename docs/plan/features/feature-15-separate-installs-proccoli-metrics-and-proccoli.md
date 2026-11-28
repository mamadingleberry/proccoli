# Feature 15: Separate installs: `proccoli-metrics` and `proccoli-gui`

Design note: [design/features/feature-15-separate-installs-proccoli-and-proccoli-gui.md](../../design/features/feature-15-separate-installs-proccoli-and-proccoli-gui.md)

*Done as v0.5.0* (its decisions and deviations are listed there).

**Goal:** the background collector (Feature 13) and the window install
separately, from the same source and version:

- **`proccoli-metrics`**: the display-free part. The collector
  (`proccoli-metrics`, a systemd user unit), and the library both parts
  use: `core/`, `devices/`, `processes/`, the GPU summary and detail
  backends without their views, the settings schema. Depends only on
  `python3` and `python3-gi` (GLib, Gio, GObject): **no GTK, no
  libadwaita**, so it fits a server or a headless box.
- **`proccoli-gui`**: the window. `ui/`, the GPU tabs' views, the
  privileged helper and its polkit policy, the desktop file, metainfo,
  icons and the GNOME Shell extension. Depends on `proccoli-metrics` (=
  the same version), GTK 4 and libadwaita.
- **`proccoli`**: a small package that depends on both, so `apt install
  proccoli` and upgrades from 0.4.0 (one package called `proccoli`) get
  everything, as now.

**Why:** a server, a NAS or a headless lab machine should record its
history without pulling in GTK, and someone who only wants the window
shouldn't have a service they don't use. Separate installs also make the
collector's contract explicit: the database and the settings are the
interface between the two, never Python imports from `ui/`.

**Depends on Feature 13** (the collector must exist). Can be done in the
same milestone or right after.

**Design ([Feature 15's design](../../design/features/feature-15-separate-installs-proccoli-and-proccoli-gui.md)):**

- **The split follows the layers that already exist** (UI → Domain →
  Core, `tests/test_static.py`). Everything under `ui/`, plus the
  domain packages' `views.py` (`UI_IN_DOMAIN`), the helper and `app.py`,
  is the GUI; the rest is the library. A new static test turns the rule
  into a list: no module in the library may import from `ui/`, `app`,
  Gtk, Gdk or Adw, at any level (today only module level is checked),
  and the GPU backends reach their views only through `create_views`'s
  lazy import, which `proccoli-gui` provides.
- **One Python package, two installs:** both install into the same
  `share/proccoli/proccoli/` tree, each its own files (no file in both),
  so `import proccoli.ui` works only with the GUI installed. A file list
  per package, `packaging/files-metrics.txt` and `files-gui.txt`,
  generated from the rule above, and a test that the two lists cover
  every source file exactly once.
- **The settings schema** ships in `proccoli-metrics`: the collector
  reads it (*Keep History*, the limits, the update interval), and the
  GUI depends on the library anyway. Its window-only keys are harmless
  there.
- **Commands:** `proccoli-metrics` (collector; `--once` for a single
  reading, `--status` to print what it's recording and the database
  size), and `proccoli` (the window) from `proccoli-gui`.
- **The GUI without the service running** works as today: it records
  the history itself (Feature 13's lock decides who writes). With
  `proccoli-metrics` installed but its unit disabled, nothing changes
  from today either; Preferences' *Record in the Background* turns the
  unit on.
- **Packaging:**
  - `packaging/build-deb.sh` builds three `.deb`s (`proccoli-metrics`,
    `proccoli-gui`, `proccoli`), the GUI's `Depends:` pinned to the same
    metrics version, and `Breaks/Replaces: proccoli (<< 0.5)` so the
    files that move from the old single package hand over cleanly.
  - `packaging/install.sh --metrics` or `--gui` (default: both), with
    `--uninstall` taking the same choice; uninstalling the library while
    the GUI is installed refuses and says why.
  - The systemd user unit and its `proccoli-metrics.log` belong to
    `proccoli-metrics`; removing it stops and disables the unit for
    every user (`deb-systemd-helper --user`), and leaves each user's
    history, as removing the package does today.
- **Versions in lockstep:** both read and write the same database
  (schema version in `meta`) and settings. A collector that finds a
  newer schema than it knows stops writing and logs why, rather than
  guessing.

| Step | Create / change | Test |
|---|---|---|
| F15.1 | `tests/test_static.py`: the library never imports `ui/`, `app`, Gtk, Gdk or Adw at any level | Static: today `gpu/intel_gpu_top/clients.py` (the Intel *Processes* tab) imports `ui.widgets.app_icon`; it's view code, so it moves with the views (renamed `clients_view.py`, in `UI_IN_DOMAIN`) |
| F15.2 | `packaging/split.py`: the two file lists from the rule; `files-metrics.txt`, `files-gui.txt` | Unit: every source file in exactly one list; the metrics list imports with Gtk blocked (`sys.modules['gi.repository.Gtk'] = None`) |
| F15.3 | `packaging/install.sh --metrics/--gui`; uninstall checks | `test_packaging`: a staged install of each alone has only its files; the metrics install runs `proccoli-metrics --once` with no display |
| F15.4 | `packaging/build-deb.sh`: three packages, `Depends`, `Breaks/Replaces`, the user unit | `test_packaging`: control fields; `dpkg-deb -c` contents per package; upgrade from a 0.4.0 `.deb` in a scratch root (`dpkg --root`) |
| F15.5 | `HistoryDb`: a newer schema than known stops writing | Unit: schema 3 in `meta` → read-only, logged |
| F15.6 | README *Installing* (the three packages, server installs), *Uninstalling*; [DESIGN §4.1](../../design/04-architecture-overview.md), [Feature 15's design](../../design/features/feature-15-separate-installs-proccoli-and-proccoli-gui.md) as built | Run |

**Done when:** `proccoli-metrics` installs and records on a machine
without GTK, `proccoli-gui` installs on top and shows that history,
`apt install proccoli` gives both as today, upgrading from 0.4.0 keeps
the history and settings, and each package removes only its own files.

**Open questions for the user:**
1. Package names: `proccoli-metrics`, `proccoli-gui` and `proccoli` (the
   one that installs both), or should `proccoli` itself be the GUI with
   `proccoli-metrics` as its dependency (two packages, no
   meta-package)?
2. Should `proccoli-gui` *depend* on `proccoli-metrics` (shared library,
   as designed) or only *recommend* it, with the library in a third
   `proccoli-common` package? The second lets someone install the GUI
   without the collector's unit file, at the cost of a third package.
3. Does `proccoli-metrics` alone need a way to read the history without
   the GUI (`proccoli-metrics --export FOLDER`, the Feature 7/14 export
   from the command line)? Useful on a server.
