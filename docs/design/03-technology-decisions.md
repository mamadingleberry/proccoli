# 3. Technology decisions

| Decision | Choice | Why |
|---|---|---|
| Language | Python 3 (system interpreter) + PyGObject | Same stack as intel_gpu_top_gui, so code can be reused directly. No build step and nothing from pip. |
| Toolkit | GTK ≥ 4.10, libadwaita ≥ 1.5 | `AdwOverlaySplitView`, `AdwBreakpoint`, `AdwToolbarView` (1.4) and `AdwDialog`, `AdwPreferencesDialog`, `AdwAboutDialog` (1.5). Ubuntu 24.04 ships 1.5 (with GTK 4.14 and GLib 2.80). `AdwShortcutsDialog` (1.8) is used when present. |
| Newer APIs | Only through `ui/compat.py` or a `hasattr` check | Ubuntu 24.04 is the floor, tested on a real machine since v0.2.0. `compat` has `spinner` (`Adw.Spinner`, 1.6, else `Gtk.Spinner`), `ensure_font_dpi` (libadwaita 1.5's `sp` breakpoints need a font DPI) and `without_css_variables` (GTK < 4.16 can't read `:root` variables). `app.signal_adder` picks GLib's Unix signal function. `test_static.PlatformFloorTest` rejects unguarded newer libadwaita classes. |
| UI definitions | Built in Python (not `.ui` files) | Simple to review and test, and avoids a GResource compile step. `.ui` files can be added later. |
| Graph drawing | Cairo `Gtk.DrawingArea`, one chart family in `ui/` | Pixel snapping and the hover crosshair come from intel_gpu_top_gui's `GraphView`; since Feature 3 every graph, the Intel Details tab's included, is the shared `Graph` ([§9.1](09.1-widgets.md)). |
| Settings | GSettings with an installed schema, plus an in-memory fallback | Mirrors Resources. The fallback makes running from a source checkout and testing easy. |
| Dependency injection | By hand, in one composition root (`context.py`, [§4.2](04-architecture-overview.md)) | No framework needed. Every OS service sits behind `System` and every file read behind `SysRoot`, so tests swap in fakes. |
| Two programs | A recorder (`proccoli`, a systemd user service, no Gtk) and a window (`proccoli-gui`), separate packages | The history keeps growing while no window is open, one process reads the hardware however many windows there are, and the recorder runs on a machine without a screen. `packaging/split.py` assigns each file to one package; a static test keeps the recorder free of the GUI. |
| Recorder ↔ window | D-Bus on the session bus (`APP_ID.Metrics`): `Devices`, `Subscribe`, `Flush`, the `Readings` signal; JSON payloads | Already on every desktop, activatable (the bus starts the recorder), and per user. JSON carries `None` and nested snapshots, which `a{sv}` can't. A Web UI would be another client of the same service. |
| History | SQLite (stdlib `sqlite3`), WAL, one writer by file lock; rolled up to minutes and hours, capped in size ([DESIGN_DB.md](DESIGN_DB.md)) | No server and no extra package; small appends and range reads are what SQLite does well. |
| Data collection | In the recorder: `/proc` and `/sys` reads on its main loop, plus subprocess readers for streaming tools. The window reads only processes | `/proc` reads are cheap. `intel_gpu_top` and the privileged helper stream JSON on a worker thread and hand results to the main loop with `GLib.idle_add`. |
| D-Bus | `Gio.DBusProxy` to NetworkManager (Wi-Fi name, connection type) and UPower (battery) | No extra packages; `gir1.2-nm` is not installed by default. |
| Hotplug | Periodic rescans (every few seconds) for drives and network interfaces | GUdev's introspection data isn't installed by default; it can replace the rescans later. |
| Privilege | `pkexec` + polkit policy + one helper script (`proccoli-helper`) | Same model as Resources. |
