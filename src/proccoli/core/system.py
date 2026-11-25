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
- file locks (who writes the history)

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


# Apps whose org.freedesktop.Application.Activate opens a new window rather
# than showing the one they have.
NEW_WINDOW_ON_ACTIVATE = frozenset({
    "org.gnome.Terminal", "org.gnome.Console", "org.gnome.Ptyxis",
    "com.raggesilver.BlackBox", "org.gnome.Nautilus",
})


def activation_token(launch_context, info=None) -> str:
    """The token that lets GNOME raise another app's window (from the
    window's ``Gdk.AppLaunchContext``), or "" without one."""
    if launch_context is None:
        return ""
    try:
        return launch_context.get_startup_notify_id(info, []) or ""
    except (TypeError, AttributeError):
        return ""


def restart_command(argv0: str, interpreter: str,
                    runnable: bool) -> tuple[str, list[str]]:
    """How to start Proccoli again, as ``(program, argv)`` for ``execv``.

    - Started as a module (argv[0] is the package's ``__main__.py``):
      ``python3 -m proccoli``.
    - Started from its launcher (``runnable``: an executable file): run the
      launcher itself, not the interpreter with the launcher as argument.
      The kernel names a process after the program it runs, so going
      through the interpreter would list the window as "python3".
    - Otherwise (a script that isn't executable): the interpreter with it.
    """
    if os.path.basename(argv0) == "__main__.py":
        return interpreter, [interpreter, "-m", "proccoli"]
    if runnable:
        return argv0, [argv0]
    return interpreter, [interpreter, argv0]


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

    def restart_self(self, args) -> None:
        """Replace this process with a fresh Proccoli (*Restart Now*),
        started the way this one was: the installed launcher, or
        ``python3 -m proccoli`` from a checkout."""
        import sys
        argv0 = sys.argv[0]
        runnable = os.path.isfile(argv0) and os.access(argv0, os.X_OK)
        program, argv = restart_command(argv0, sys.executable, runnable)
        os.execv(program, [*argv, *args])

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

    # -- file locks ---------------------------------------------------------------------

    def try_lock(self, path) -> Optional[int]:
        """An exclusive lock on ``path`` (created 0600), or None when
        another process (or another open of it) holds it. The kernel frees
        it when the holder exits, so it can't go stale."""
        import fcntl
        os.makedirs(os.path.dirname(os.fspath(path)), mode=0o700, exist_ok=True)
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return None
        return fd

    def release_lock(self, handle: int) -> None:
        import fcntl
        try:
            fcntl.flock(handle, fcntl.LOCK_UN)
        finally:
            os.close(handle)

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
        # A running GApplication owns its app ID on the bus even when its
        # .desktop file doesn't say so; terminals open a new
        # window on Activate, so they're left out.
        if app_id not in NEW_WINDOW_ON_ACTIVATE and self.bus_name_owned(app_id):
            return "dbus"
        return None

    def activate_app(self, app_id: str, launch_context=None) -> bool:
        """Ask the app to show its window (see ``app_switch_method``).
        ``launch_context`` (``Gdk.AppLaunchContext``) gives the activation
        token that lets GNOME bring it to the front."""
        method = self.app_switch_method(app_id)
        if method == "dbus":
            from gi.repository import Gio, GLib
            data = {}
            token = activation_token(launch_context, self._desktop_info(app_id))
            if token:
                data = {"activation-token": GLib.Variant("s", token),
                        "desktop-startup-id": GLib.Variant("s", token)}
            path = "/" + app_id.replace(".", "/").replace("-", "_")
            Gio.bus_get_sync(Gio.BusType.SESSION, None).call(
                app_id, path, "org.freedesktop.Application", "Activate",
                GLib.Variant("(a{sv})", (data,)), None, Gio.DBusCallFlags.NONE, 5000,
                None, None, None)
            return True
        if method == "launch":
            return bool(self._desktop_info(app_id).launch([], launch_context))
        return False

    # -- windows (core.windows decides) ------------------------------------

    def _session_call(self, dest: str, path: str, iface: str, method: str, args=None,
                      reply: Optional[str] = None, timeout_ms: int = 1000):
        """A session-bus call; its unpacked reply, or None on any error."""
        from gi.repository import Gio, GLib
        try:
            result = Gio.bus_get_sync(Gio.BusType.SESSION, None).call_sync(
                dest, path, iface, method, args,
                GLib.VariantType(reply) if reply else None,
                Gio.DBusCallFlags.NO_AUTO_START, timeout_ms, None)
        except GLib.Error:
            return None
        return result.unpack() if result is not None else ()

    def bus_name_owned(self, name: str) -> bool:
        from gi.repository import GLib
        reply = self._session_call("org.freedesktop.DBus", "/org/freedesktop/DBus",
                                   "org.freedesktop.DBus", "NameHasOwner",
                                   GLib.Variant("(s)", (name,)), "(b)")
        return bool(reply and reply[0])

    def shell_windows(self) -> Optional[list[tuple]]:
        """Every window, from Proccoli's Shell extension, or None when it
        isn't running: ``(id, pid, app id, title, last used)``."""
        from .windows import EXTENSION_INTERFACE, EXTENSION_PATH, LIST_SIGNATURE
        reply = self._session_call("org.gnome.Shell", EXTENSION_PATH, EXTENSION_INTERFACE,
                                   "List", None, LIST_SIGNATURE)
        return None if reply is None else [tuple(row) for row in reply[0]]

    def shell_activate_window(self, window_id: int) -> bool:
        from gi.repository import GLib
        from .windows import EXTENSION_INTERFACE, EXTENSION_PATH
        reply = self._session_call("org.gnome.Shell", EXTENSION_PATH, EXTENSION_INTERFACE,
                                   "Activate", GLib.Variant("(t)", (window_id,)), "(b)")
        return bool(reply and reply[0])

    def shell_extension_info(self, uuid: str) -> Optional[dict]:
        """GNOME Shell's view of an extension: ``{}`` if it doesn't know
        it, None if this isn't GNOME Shell."""
        from gi.repository import GLib
        reply = self._session_call("org.gnome.Shell", "/org/gnome/Shell",
                                   "org.gnome.Shell.Extensions", "GetExtensionInfo",
                                   GLib.Variant("(s)", (uuid,)), "(a{sv})")
        return None if reply is None else dict(reply[0])

    def enable_shell_extension(self, uuid: str) -> bool:
        from gi.repository import GLib
        reply = self._session_call("org.gnome.Shell", "/org/gnome/Shell",
                                   "org.gnome.Shell.Extensions", "EnableExtension",
                                   GLib.Variant("(s)", (uuid,)), "(b)", timeout_ms=5000)
        return bool(reply and reply[0])

    @staticmethod
    def _user_extensions_dir():
        from pathlib import Path
        data = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        return Path(data) / "gnome-shell" / "extensions"

    def user_extension_installed(self, uuid: str) -> bool:
        return (self._user_extensions_dir() / uuid / "metadata.json").is_file()

    def install_user_extension(self, uuid: str, source) -> bool:
        """Copy an extension folder into the user's extensions."""
        target = self._user_extensions_dir() / uuid
        try:
            shutil.copytree(source, target, dirs_exist_ok=True)
        except OSError:
            return False
        return True

    def enable_extension_at_login(self, uuid: str) -> bool:
        """Add ``uuid`` to GNOME Shell's enabled extensions, so a newly
        copied extension starts on at the next log-in (what
        ``gnome-extensions enable`` does for one the Shell hasn't loaded)."""
        from gi.repository import Gio
        source = Gio.SettingsSchemaSource.get_default()
        if source is None or source.lookup("org.gnome.shell", True) is None:
            return False
        shell = Gio.Settings.new("org.gnome.shell")
        enabled = list(shell.get_strv("enabled-extensions"))
        if uuid not in enabled:
            shell.set_strv("enabled-extensions", enabled + [uuid])
        return True

    def session_type(self) -> str:
        return os.environ.get("XDG_SESSION_TYPE", "")

    def wmctrl_list(self) -> str:
        """``wmctrl -l -p`` (X11), or "" without wmctrl."""
        exe = self.which("wmctrl")
        if exe is None:
            return ""
        import subprocess
        try:
            return subprocess.run([exe, "-l", "-p"], capture_output=True, text=True,
                                  timeout=2).stdout
        except (OSError, subprocess.SubprocessError):
            return ""

    def wmctrl_activate(self, window_id: int) -> bool:
        exe = self.which("wmctrl")
        if exe is None:
            return False
        import subprocess
        try:
            return subprocess.run([exe, "-i", "-a", hex(window_id)], timeout=2).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def desktop_app(self, app_id: str) -> Optional[AppInfo]:
        """Name, icon and description from ``<app_id>.desktop``, or None."""
        info = self._desktop_info(app_id)
        if info is None:
            return None
        return AppInfo(info.get_display_name() or info.get_name() or app_id,
                       info.get_icon(), info.get_description() or "")
