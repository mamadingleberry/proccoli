"""*Switch To* for any running app.

GNOME on Wayland lets an app focus only its own windows, so Proccoli
can't raise another app's window by itself. ``WindowSwitcher`` tries, in
order:

1. **Proccoli's GNOME Shell extension** (``EXTENSION_UUID``, shipped in
   ``data/gnome-shell/extensions/``): it lists every window with its process ID and
   activates one. An app's windows are the ones whose process is one of
   the app's (``windows_for``); the most recently used is raised. Works
   for every app with a window, on Wayland and X11.
2. **Asking the app**: D-Bus activation, or relaunching a
   single-window app, now with an activation token from the window's
   launch context so GNOME lets it come to the front; also for running
   GApplications that own their app ID on the bus.
3. **X11** (``wmctrl``, in an X11 session): ``_NET_ACTIVE_WINDOW`` on the
   app's window, matched by process ID.

Everything that touches the desktop goes through ``System`` (faked in
tests); this module only decides.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional, Sequence

from .. import APP_ID

EXTENSION_UUID = "proccoli-windows@mamadingleberry.github.io"
# The extension's D-Bus object (data/gnome-shell/extensions/…/extension.js spells
# the same; tests/test_windows.py checks).
EXTENSION_PATH = "/" + APP_ID.replace(".", "/") + "/Windows"
EXTENSION_INTERFACE = APP_ID + ".Windows"
LIST_SIGNATURE = "(a(tussu))"


@dataclass(frozen=True)
class Window:
    id: int
    pid: int
    app_id: str = ""
    title: str = ""
    user_time: int = 0         # when it was last used (larger: more recent)


def windows_for(pids: Iterable[int], windows: Sequence[Window],
                app_id: str = "") -> list[Window]:
    """``windows`` that belong to an app: by process, or (for apps whose
    windows come from a helper process) by app ID; most recent first."""
    wanted = set(pids)
    mine = [w for w in windows if w.pid in wanted or (app_id and w.app_id == app_id)]
    return sorted(mine, key=lambda w: w.user_time, reverse=True)


def parse_wmctrl(text: str) -> list[Window]:
    """``wmctrl -l -p`` lines: id, desktop, pid, host, title. X11 gives no
    last-used time, so the list order stands in (later: more recent)."""
    out = []
    for n, line in enumerate(text.splitlines()):
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        try:
            win_id, pid = int(parts[0], 16), int(parts[2])
        except ValueError:
            continue
        out.append(Window(win_id, pid, "", parts[4] if len(parts) > 4 else "", n))
    return out


def extension_source():
    """The extension's folder in a source checkout (to install for the
    user), or None (an installed Proccoli ships it in the system's
    extensions folder, where the Shell finds it)."""
    from pathlib import Path
    folder = (Path(__file__).resolve().parents[3] / "data" / "gnome-shell" / "extensions"
              / EXTENSION_UUID)
    return folder if (folder / "metadata.json").is_file() else None


class Way(str, Enum):
    EXTENSION = "extension"
    ASK_APP = "ask-app"          # D-Bus activation or relaunch
    X11 = "x11"


class ExtensionState(str, Enum):
    """What Preferences says about the extension."""
    ENABLED = "enabled"
    DISABLED = "disabled"            # installed, turned off
    NEEDS_LOGIN = "needs-login"      # copied in; the Shell loads it at the next log-in
    NOT_INSTALLED = "not-installed"
    UNAVAILABLE = "unavailable"      # not GNOME Shell


class WindowSwitcher:
    def __init__(self, system) -> None:
        self.system = system

    # -- which way --------------------------------------------------------------

    def _extension_windows(self) -> Optional[list[Window]]:
        rows = self.system.shell_windows()
        return None if rows is None else [Window(*row) for row in rows]

    def way(self, app) -> Optional[Way]:
        """How ``app`` (``processes.apps.App``) can be brought to the front
        now, or None."""
        windows = self._extension_windows()
        if windows is not None:
            if windows_for(app.pids, windows, app.id):
                return Way.EXTENSION
        if self.system.app_switch_method(app.id) is not None:
            return Way.ASK_APP
        if self.system.session_type() == "x11" and self._x11_windows(app):
            return Way.X11
        return None

    def _x11_windows(self, app) -> list[Window]:
        text = self.system.wmctrl_list()
        return windows_for(app.pids, parse_wmctrl(text)) if text else []

    # -- switching -------------------------------------------------------------------

    def switch(self, app, launch_context=None) -> bool:
        """Bring ``app``'s most recently used window to the front."""
        way = self.way(app)
        if way == Way.EXTENSION:
            windows = windows_for(app.pids, self._extension_windows() or [], app.id)
            return bool(windows) and self.system.shell_activate_window(windows[0].id)
        if way == Way.ASK_APP:
            return self.system.activate_app(app.id, launch_context)
        if way == Way.X11:
            windows = self._x11_windows(app)
            return bool(windows) and self.system.wmctrl_activate(windows[0].id)
        return False

    # -- the extension ----------------------------------------------------------------

    def extension_state(self) -> ExtensionState:
        info = self.system.shell_extension_info(EXTENSION_UUID)
        if info is None:
            return ExtensionState.UNAVAILABLE
        if not info:
            return (ExtensionState.NEEDS_LOGIN if self.system.user_extension_installed(
                EXTENSION_UUID) else ExtensionState.NOT_INSTALLED)
        if info.get("state") == 1 and info.get("enabled", True):     # ACTIVE
            return ExtensionState.ENABLED
        return ExtensionState.DISABLED

    def install(self, source) -> bool:
        """Copy the extension to ~/.local/share/gnome-shell/extensions (for a
        source checkout; packages install it for everyone) and mark it
        enabled, so the Shell starts it at the next log-in."""
        return (self.system.install_user_extension(EXTENSION_UUID, source)
                and self.system.enable_extension_at_login(EXTENSION_UUID))

    def enable(self) -> bool:
        return self.system.enable_shell_extension(EXTENSION_UUID)
