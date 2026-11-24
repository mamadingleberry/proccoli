"""The operating-system services Proccoli uses, behind one injectable object.

File reads of /proc and /sys go through ``SysRoot``. Everything else that
touches the OS goes through ``System``:

- finding programs
- sending signals
- user names, credentials and file capabilities
- clock ticks
- priorities and CPU affinity
- child processes, both one-shot and streaming
- desktop-file lookups

Production code receives a ``System`` from the composition root
(``proccoli.context``); tests pass a fake with the same methods.
"""

from __future__ import annotations

import os
import pwd
import shutil
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

# (return code, stdout, stderr)
RunCallback = Callable[[int, str, str], None]


@dataclass
class AppInfo:
    """What the Apps page shows for an app, from its .desktop file."""
    name: str
    icon: object = None          # Gio.Icon
    description: str = ""


class System:
    def __init__(self) -> None:
        self._user_names: dict[int, str] = {}

    # -- programs and credentials -------------------------------------------------

    def which(self, name: str) -> Optional[str]:
        return shutil.which(name)

    def trusted_executable(self, path: str) -> bool:
        """Whether only root can change ``path`` and its directories, so it
        may be run through pkexec (``core.trust``)."""
        from .trust import is_trusted_path
        return is_trusted_path(path)

    def geteuid(self) -> int:
        return os.geteuid()

    def has_file_capabilities(self, path: str) -> bool:
        """Whether ``path`` carries file capabilities (``setcap``)."""
        try:
            return bool(os.getxattr(path, "security.capability"))
        except OSError:
            return False

    def user_name(self, uid: Optional[int]) -> str:
        if uid is None:
            return ""
        if uid not in self._user_names:
            try:
                self._user_names[uid] = pwd.getpwuid(uid).pw_name
            except KeyError:
                self._user_names[uid] = str(uid)
        return self._user_names[uid]

    def clk_tck(self) -> int:
        return os.sysconf("SC_CLK_TCK")

    def machine(self) -> str:
        return os.uname().machine

    # -- processes ----------------------------------------------------------------------

    def kill(self, pid: int, sig: int) -> None:
        os.kill(pid, sig)

    def get_priority(self, pid: int) -> int:
        return os.getpriority(os.PRIO_PROCESS, pid)

    def set_priority(self, pid: int, nice: int) -> None:
        os.setpriority(os.PRIO_PROCESS, pid, nice)

    def get_affinity(self, pid: int) -> set[int]:
        return set(os.sched_getaffinity(pid))

    def set_affinity(self, pid: int, cpus: set[int]) -> None:
        os.sched_setaffinity(pid, cpus)

    # -- child processes ------------------------------------------------------------------

    def stream_reader(self):
        """A new ``StreamReader`` (JSON records from a long-running child)."""
        from .runner import StreamReader
        return StreamReader()

    def run_async(self, argv: Sequence[str], callback: RunCallback) -> None:
        """Run ``argv`` without blocking the main loop (pkexec prompts can
        take a while); ``callback(rc, stdout, stderr)`` runs on the main loop."""
        from gi.repository import Gio, GLib

        try:
            proc = Gio.Subprocess.new(list(argv), Gio.SubprocessFlags.STDOUT_PIPE
                                      | Gio.SubprocessFlags.STDERR_PIPE)
        except GLib.Error as exc:
            # (exc is unbound after this block: capture the message now.)
            message = exc.message
            GLib.idle_add(lambda: callback(127, "", message) and False)
            return

        def done(p, result):
            try:
                _ok, out, err = p.communicate_utf8_finish(result)
            except GLib.Error as exc:
                callback(127, "", exc.message)
                return
            callback(p.get_exit_status() if p.get_if_exited() else -1,
                     out or "", err or "")

        proc.communicate_utf8_async(None, None, done)

    # -- desktop integration ------------------------------------------------------------------

    @staticmethod
    def _desktop_info(app_id: str):
        import gi
        try:   # GLib >= 2.80 moved DesktopAppInfo to GioUnix
            gi.require_version("GioUnix", "2.0")
            from gi.repository import GioUnix
            cls = GioUnix.DesktopAppInfo
        except (ImportError, ValueError, AttributeError):
            from gi.repository import Gio
            cls = Gio.DesktopAppInfo
        try:
            return cls.new(f"{app_id}.desktop")
        except TypeError:
            return None

    def app_switch_method(self, app_id: str) -> Optional[str]:
        """How Proccoli can bring an app's window to the front, if at all
        (GNOME on Wayland lets an app raise only itself, so the app is asked
        to): "dbus" for D-Bus-activatable apps (org.freedesktop.Application
        .Activate), "launch" for apps with a single main window (relaunching
        shows it), None otherwise (relaunching would open another window)."""
        info = self._desktop_info(app_id)
        if info is None:
            return None
        if info.get_boolean("DBusActivatable"):
            return "dbus"
        if info.get_boolean("SingleMainWindow"):
            return "launch"
        return None

    def activate_app(self, app_id: str) -> bool:
        """Ask the app to show its window (see ``app_switch_method``)."""
        method = self.app_switch_method(app_id)
        if method == "dbus":
            from gi.repository import Gio, GLib
            path = "/" + app_id.replace(".", "/").replace("-", "_")
            Gio.bus_get_sync(Gio.BusType.SESSION, None).call(
                app_id, path, "org.freedesktop.Application", "Activate",
                GLib.Variant("(a{sv})", ({},)), None, Gio.DBusCallFlags.NONE, 5000,
                None, None, None)
            return True
        if method == "launch":
            return bool(self._desktop_info(app_id).launch([], None))
        return False

    def desktop_app(self, app_id: str) -> Optional[AppInfo]:
        """Name, icon and description from ``<app_id>.desktop``, or None."""
        info = self._desktop_info(app_id)
        if info is None:
            return None
        return AppInfo(info.get_display_name() or info.get_name() or app_id,
                       info.get_icon(), info.get_description() or "")
