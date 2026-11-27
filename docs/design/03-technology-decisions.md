# 3. Technology decisions

| Decision | Choice | Why |
|---|---|---|
| Language | Python 3 (system interpreter) + PyGObject | Same stack as intel_gpu_top_gui, so code can be reused directly. No build step and nothing from pip. |
| Toolkit | GTK ≥ 4.10, libadwaita ≥ 1.5 | `AdwOverlaySplitView`, `AdwBreakpoint`, `AdwToolbarView` (1.4) and `AdwDialog`, `AdwPreferencesDialog`, `AdwAboutDialog` (1.5). Ubuntu 24.04 ships 1.5 (with GTK 4.14 and GLib 2.80). `AdwShortcutsDialog` (1.8) is used when present. |
| Newer APIs | Only through `ui/compat.py` or a `hasattr` check | Ubuntu 24.04 is the floor and is tested on (M53). `compat` has `spinner` (`Adw.Spinner`, 1.6, else `Gtk.Spinner`), `ensure_font_dpi` (libadwaita 1.5's `sp` breakpoints need a font DPI) and `without_css_variables` (GTK < 4.16 can't read `:root` variables). `app.signal_adder` picks GLib's Unix signal function. `test_static.PlatformFloorTest` rejects unguarded newer libadwaita classes. |
| UI definitions | Built in Python (not `.ui` files) | Simple to review and test, and avoids a GResource compile step. `.ui` files can be added later. |
| Graph drawing | Cairo `Gtk.DrawingArea`, one chart family in `ui/` | Pixel snapping and the hover crosshair come from intel_gpu_top_gui's `GraphView`; since M60 every graph, the Intel Details tab's included, is the shared `Graph` ([§9.1](09.1-widgets.md)). |
| Settings | GSettings with an installed schema, plus an in-memory fallback | Mirrors Resources. The fallback makes running from a source checkout and testing easy. |
| Dependency injection | By hand, in one composition root (`context.py`, [§4.2](04-architecture-overview.md)) | No framework needed. Every OS service sits behind `System` and every file read behind `SysRoot`, so tests swap in fakes. |
| Data collection | `/proc` and `/sys` reads on the main loop, plus subprocess readers for streaming tools | `/proc` reads are cheap. `intel_gpu_top` and the privileged helper stream JSON on a worker thread and hand results to the main loop with `GLib.idle_add`. |
| D-Bus | `Gio.DBusProxy` to NetworkManager (Wi-Fi name, connection type) and UPower (battery) | No extra packages; `gir1.2-nm` is not installed by default. |
| Hotplug | Periodic rescans (every few seconds) for drives and network interfaces | GUdev's introspection data isn't installed by default; it can replace the rescans later. |
| Privilege | `pkexec` + polkit policy + one helper script (`proccoli-helper`) | Same model as Resources. |
