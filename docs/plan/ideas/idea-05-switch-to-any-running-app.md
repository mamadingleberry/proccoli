# Idea 5: Switch To any running app

Design note: [design/ideas/idea-05-switch-to-any-running-app.md](../../design/ideas/idea-05-switch-to-any-running-app.md)

*Done as Milestone 67.*

**Goal:** the Apps page's right-click menu offers *Switch To* for every
running app with a window, not only the ones M32 can reach, and it brings
that app's window to the front.

**What's possible** (checked on this machine, Ubuntu with GNOME Shell
50.1 on Wayland, during M61):

| Way | Works for | Status here |
|---|---|---|
| Ask the app over D-Bus, `org.freedesktop.Application.Activate` (M32) | D-Bus-activatable apps; also any running GApplication that owns its app ID on the session bus, even if its `.desktop` file doesn't say `DBusActivatable` | Works, but the call sends no **activation token**, so GNOME's focus-stealing prevention may show "… is ready" instead of raising the window. Of the apps running now only GNOME Terminal owns its name; a terminal's *activate* may open a new window rather than raise one (not tried, to leave the desktop alone) |
| Relaunch the `.desktop` entry (M32) | Apps with `SingleMainWindow=true` | Works; also needs the activation token (`GAppLaunchContext`), which M32 doesn't pass (it launches with `None`) |
| GNOME Shell's own D-Bus `org.gnome.Shell.FocusApp(app_id)` | Every app | **Refused:** "FocusApp is not allowed". GNOME 41+ allows it only to a short list of GNOME's own programs; `Eval` is refused too |
| `wmctrl` / `_NET_ACTIVE_WINDOW` (X11), matched by `_NET_WM_PID` | Every window in an X11 session; under Wayland only X11 apps running through XWayland | `wmctrl` isn't installed; Ubuntu's default session is Wayland |
| A **GNOME Shell extension** that exposes windows over D-Bus (list windows with their PIDs and app IDs, activate one) | Every window on GNOME, X11 or Wayland: the extension runs inside the Shell, which may focus any window | Not installed. Existing ones ("Window Calls" and similar) do this; Proccoli could also ship a small one of its own |
| KDE: KWin scripting over D-Bus | Every window on KDE Plasma | Not this desktop; possible later behind the same interface |

So **there's no way for an ordinary app to focus another app's window on
GNOME Wayland**; that's deliberate on GNOME's side. The only way to do it
for every app is code running inside the Shell, i.e. an extension the
user installs and enables once (and, on Wayland, logs out and in again
the first time).

**Design ([Idea 5's design](../../design/ideas/idea-05-switch-to-any-running-app.md)):**

- **`WindowSwitcher`** (`core/windows.py`, through `System`, faked in
  tests): `can_switch(app)` and `switch(app)`, trying in order:
  1. **Proccoli's Shell extension** if it's enabled
     (`proccoli-windows@mamadingleberry.github.io`, about 60 lines of
     GJS, shipped in the `.deb` under
     `/usr/share/gnome-shell/extensions/`): a D-Bus object
     `io.github.mamadingleberry.Proccoli.Windows` with `List() →
     [(window id, pid, app id, title)]` and `Activate(window id)`.
     Proccoli matches an app's PIDs (`App.pids`) to window PIDs, so it
     works for Firefox, VS Code, terminals and anything else with a
     window. Its only powers are listing and activating windows, and
     only on the user's own session bus.
  2. **D-Bus activation with an activation token** (M32, fixed): the
     token from `Gdk.Display.get_app_launch_context()` goes in
     `platform-data` (`activation-token`, `desktop-startup-id`), and
     relaunches pass the same launch context. Also for running
     GApplications that own their app ID on the bus.
  3. **X11:** `_NET_ACTIVE_WINDOW` for the app's windows when the session
     is X11 (or the app runs through XWayland), if `wmctrl` is
     installed. (An optional dependency, like `dmidecode`.)
- **The menu:** *Switch To* shows for every app with a window when the
  extension is on. Without it, for apps the other ways reach. Apps it
  can't reach get a greyed *Switch To* whose hover text says how to turn
  on the extension (once per session, a toast offers *Enable…*, which
  runs `gnome-extensions enable` and explains the log-out on Wayland).
- **Preferences → General:** *Window Switching*: whether the extension
  is installed and enabled, with a button to enable it.

| Step | Create / change | Test |
|---|---|---|
| I5.1 | Activation token for the existing ways (`System.activate_app` takes the launch context's token; `launch` passes the context) | Unit (fake System): the token reaches `platform-data` and the launch |
| I5.2 | Running GApplications: `NameHasOwner(app_id)` makes an app switchable by D-Bus even without `DBusActivatable` (skipped for apps known to open a new window on *activate*, such as terminals) | Unit: name owned / not owned |
| I5.3 | The extension (`data/gnome-shell/proccoli-windows@…/`: `metadata.json` for Shell 46–50, `extension.js`) and its packaging | Lint the JS in `make test` (`gjs -c` if present); manual check on the desktop |
| I5.4 | `WindowSwitcher` with the three ways in order; `AppsPage` uses it; PID → window matching (`processes/` helper, pure) | Unit: matching an app's PIDs to windows (several windows: the most recently used); the order of ways |
| I5.5 | Menu states, the toast, Preferences row | UI: enabled / greyed with hover text; the toast once |
| I5.6 | [DESIGN §8](../../design/08-processes-and-apps.md) and [§11.1](../../design/11-cross-cutting-concerns.md) (what the extension can do), README (*Switch To*, installing the extension), packaging | – |

**Done when:** with the extension enabled, *Switch To* brings any
running app with a window to the front on GNOME (Wayland and X11);
without it, the M32 ways work reliably (with a token), and the menu says
what to do for the rest.

**Open questions for the user:**
1. Ship Proccoli's own small extension, or use an existing one from
   extensions.gnome.org if it's installed (less to maintain, but the
   user installs it themselves and its D-Bus interface can change)?
2. If an app has several windows, raise the most recently used one, or
   offer a submenu of window titles?
