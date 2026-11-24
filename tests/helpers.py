"""Shared test helpers."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from typing import Mapping, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.sysroot import SysRoot  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
LAPTOP = os.path.join(FIXTURES, "alderlake-laptop")


class FakeRoot:
    """A writable fake filesystem root for SysRoot-based code.

        root = FakeRoot(self, {"/proc/stat": "cpu 1 2 3 4\\n"},
                        links={"/sys/class/net/eth0/device/driver": "../e1000e"},
                        dirs=["/sys/class/net/wlan0/wireless"])
        monitor = Thing(root.sysroot)
        root.write("/proc/stat", "cpu 2 3 4 5\\n")   # next sample
    """

    def __init__(self, test: unittest.TestCase, files: Mapping[str, str] = (),
                 links: Optional[Mapping[str, str]] = None, dirs=()) -> None:
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.sysroot = SysRoot(self.dir)
        for path, text in dict(files).items():
            self.write(path, text)
        for path, target in (links or {}).items():
            self.link(path, target)
        for d in dirs:
            os.makedirs(self.sysroot.path(d), exist_ok=True)

    def write(self, path: str, text: str) -> None:
        p = self.sysroot.path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def link(self, path: str, target: str) -> None:
        p = self.sysroot.path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(p):
            os.remove(p)
        os.symlink(target, p)

    def remove(self, path: str) -> None:
        import shutil
        p = self.sysroot.path(path)
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
        elif os.path.lexists(p):
            os.remove(p)


class FakeSystem:
    """Stands in for proccoli.core.system.System. Records every call that would
    change something (signals, priorities, child processes) and answers
    queries from attributes tests can set."""

    def __init__(self, programs: Optional[dict] = None, euid: int = 1000,
                 capabilities: bool = False, users: Optional[dict] = None,
                 apps: Optional[dict] = None, machine: str = "x86_64") -> None:
        self.programs = programs if programs is not None else {}
        self.euid = euid
        self.capabilities = capabilities
        self.users = users if users is not None else {0: "root", 1000: "user"}
        self.apps = apps if apps is not None else {}
        self.switchable: dict = {}       # app_id -> "dbus" / "launch" (Switch To)
        self.activated: list = []
        self._machine = machine
        self.killed: list[tuple[int, int]] = []
        self.denied_pids: set[int] = set()
        self.priorities: dict[int, int] = {}
        self.affinities: dict[int, set] = {}
        self.runs: list[list[str]] = []
        self.run_results: list[tuple[int, str, str]] = []   # queued (rc, out, err)
        self.readers: list = []
        # Paths only root can change (core.trust): anything under /usr by
        # default, so the usual fixtures look like a system install.
        self.trusted: Optional[set] = None

    def which(self, name):
        return self.programs.get(name)

    def trusted_executable(self, path):
        if self.trusted is not None:
            return path in self.trusted
        return path.startswith(("/usr/", "/bin/", "/sbin/"))

    def geteuid(self):
        return self.euid

    def has_file_capabilities(self, path):
        return self.capabilities

    def user_name(self, uid):
        return "" if uid is None else self.users.get(uid, str(uid))

    def clk_tck(self):
        return 100

    def machine(self):
        return self._machine

    def _check(self, pid):
        import errno
        if pid in self.denied_pids:
            raise PermissionError(errno.EPERM, "Operation not permitted")

    def kill(self, pid, sig):
        self._check(pid)
        self.killed.append((pid, sig))

    def get_priority(self, pid):
        return self.priorities.get(pid, 0)

    def set_priority(self, pid, nice):
        self._check(pid)
        self.priorities[pid] = nice

    def get_affinity(self, pid):
        return self.affinities.get(pid, set(range(4)))

    def set_affinity(self, pid, cpus):
        self._check(pid)
        self.affinities[pid] = set(cpus)

    def stream_reader(self):
        reader = FakeStreamReader()
        self.readers.append(reader)
        return reader

    def run_async(self, argv, callback):
        self.runs.append(list(argv))
        rc, out, err = self.run_results.pop(0) if self.run_results else (0, "", "")
        callback(rc, out, err)

    def desktop_app(self, app_id):
        return self.apps.get(app_id)

    def app_switch_method(self, app_id):
        return self.switchable.get(app_id)

    def activate_app(self, app_id):
        self.activated.append(app_id)
        return app_id in self.switchable


class FakeStreamReader:
    """A StreamReader whose records tests push with ``feed()``."""

    def __init__(self) -> None:
        from gi.repository import GObject  # noqa: F401
        self.started: Optional[tuple] = None
        self.stopped = False
        self._handlers: dict[int, tuple[str, object]] = {}
        self._next_id = 0

    def connect(self, signal, callback):
        assert signal in ("record", "exited"), signal
        self._next_id += 1
        self._handlers[self._next_id] = (signal, callback)
        return self._next_id

    def disconnect(self, handler):
        del self._handlers[handler]

    def _callbacks(self, signal):
        return [cb for sig, cb in list(self._handlers.values()) if sig == signal]

    def start(self, argv, elevate=False):
        self.started = (list(argv), elevate)

    def start_generator(self, make, interval_s):
        self.started = ("generator", interval_s)

    def stop(self):
        self.stopped = True

    def feed(self, record):
        for cb in self._callbacks("record"):
            cb(self, record)

    def exit(self, rc, stderr="", count=0):
        for cb in self._callbacks("exited"):
            cb(self, rc, stderr, count)


def make_context(test: unittest.TestCase, *, demo: bool = False, sysroot=None,
                 system=None, settings=None, pci=None, helper_command=None,
                 gpu_registry=None):
    """An AppContext built by the real composition root, with fakes: test
    settings, a FakeSystem, a fixture SysRoot and no NetworkManager."""
    from proccoli.context import build_context
    from proccoli.core import pciids
    from proccoli.core.settings import Settings

    ctx = build_context(
        settings or Settings.for_tests(), demo=demo,
        system=system or FakeSystem(),
        sysroot=sysroot or SysRoot(LAPTOP),
        pci=pci or pciids.load(os.path.join(FIXTURES, "pci", "pci.ids")),
        helper_command=helper_command, connection_name=None, gpu_registry=gpu_registry)
    test.addCleanup(ctx.stop)
    return ctx


def read_file(path) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class FakeStyleManager:
    """Stands in for ``Adw.StyleManager`` (``ui.theme.Theme`` tests): a
    desktop whose light/dark preference is ``system_dark``."""

    def __init__(self, system_dark: bool = False, accent=(0.2, 0.5, 0.9)) -> None:
        from gi.repository import GObject

        class _Notifier(GObject.Object):
            dark = GObject.Property(type=bool, default=False)
            accent_color = GObject.Property(type=int, default=0)   # a change counter
        self._obj = _Notifier()
        self.system_dark = system_dark
        self.scheme = None
        self.accent = accent
        self.active: set[int] = set()    # connected handler ids (leak checks)
        self._obj.dark = system_dark

    def connect(self, signal, callback):
        handler = self._obj.connect(signal, lambda *_: callback(self))
        self.active.add(handler)
        return handler

    def disconnect(self, handler):
        self._obj.disconnect(handler)
        self.active.discard(handler)

    def set_color_scheme(self, scheme) -> None:
        from gi.repository import Adw
        self.scheme = scheme
        dark = {Adw.ColorScheme.FORCE_DARK: True,
                Adw.ColorScheme.FORCE_LIGHT: False}.get(scheme, self.system_dark)
        if dark != self._obj.dark:
            self._obj.dark = dark

    def set_system_dark(self, dark: bool) -> None:
        """The desktop switches style."""
        from gi.repository import Adw
        self.system_dark = dark
        if self.scheme in (None, Adw.ColorScheme.DEFAULT):
            self._obj.dark = dark

    def get_dark(self) -> bool:
        return self._obj.dark

    def get_accent_color_rgba(self):
        from types import SimpleNamespace
        r, g, b = self.accent
        return SimpleNamespace(red=r, green=g, blue=b, alpha=1.0)

    def set_accent(self, rgb) -> None:
        """The desktop's accent colour changes."""
        self.accent = rgb
        self._obj.accent_color += 1

