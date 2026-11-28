# Milestone 67: Switch To any running app

*✅ Done.* Was Feature 5. Proccoli's own GNOME Shell extension (installed off; *Install* / *Turn On* in Preferences); activation tokens for the M32 ways; `wmctrl` on X11. Not yet tried with the extension loaded: that needs a log-out

Was Feature 5 (kept below with what was checked on this desktop). Its open
questions were settled with its own recommendations: Proccoli ships its
own small extension (an outside one's D-Bus interface could change under
it), and an app with several windows gets its most recently used one
raised.

| Step | Create / change | Test |
|---|---|---|
| 67.1 | Activation token: `System.activate_app(app_id, launch_context)` puts it in `platform-data` (`activation-token`, `desktop-startup-id`) and relaunches with the context; `system.activation_token`. The Apps page passes its display's launch context | Unit: the token, none, a context that can't give one; the context reaches the launch |
| 67.2 | Running GApplications: `app_switch_method` answers "dbus" when the app owns its ID on the bus (`bus_name_owned`), except apps that open a new window on *Activate* (`NEW_WINDOW_ON_ACTIVATE`: terminals, Files) | Unit |
| 67.3 | The extension, `data/gnome-shell/extensions/proccoli-windows@mamadingleberry.github.io/` (`metadata.json` for Shell 45–50, `extension.js`); `packaging/install.sh` installs and removes it | Unit: metadata, the interface agrees with `core.windows`, `gjs` parses it; a staged install has it |
| 67.4 | `core/windows.py`: `Window`, `windows_for`, `parse_wmctrl`, `WindowSwitcher` (extension → ask the app → X11; extension states; install; enable); the `System` methods behind it; `AppContext.windows` | Unit with `FakeSystem`: matching, the most recent window, the order of ways, every extension state, install marks it enabled at log-in |
| 67.5 | Apps: *Switch To* for every single real app; nothing reaches it → a toast with *Set Up…* (`app.preferences`). Preferences → General → *Window Switching* (state, *Install* from a checkout, *Turn On*) | UI: the extension raises an app's window; an unreachable app gets the toast; the Preferences row through every state |
| 67.6 | [DESIGN §8](../../../design/08-processes-and-apps.md), [Feature 5's design](../../../design/features/feature-05-switch-to-any-running-app.md); README (*Switch To*, *Window Switching*) | – |

**Checked on this desktop** (GNOME Shell 50.1, Wayland): Proccoli reads
the Shell's extension states over D-Bus (ours: not installed; others:
their real states), and `NameHasOwner` sees GNOME Terminal and Files.
**Not checked yet:** switching with the extension running. Installing it
here would change the user's desktop and takes a log-out to load on
Wayland, so that's left for the user to do from Preferences.
