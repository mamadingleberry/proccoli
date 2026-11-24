"""Grouping processes into apps by their systemd cgroup, like Resources.

Desktops start every app in its own systemd unit, whose name carries the
app ID. The forms seen in practice (all under app.slice):

  app-org.gnome.Terminal.slice/...           GNOME 49 (app ID + ".slice")
  app-gnome-org.gnome.Nautilus-12345.scope   launcher "gnome", random suffix
  app-flatpak-org.mozilla.firefox-12345.scope
  snap.firefox.firefox-<uuid>.scope          desktop ID "firefox_firefox"
  app-org.example.Tool@abc123.service        app started as a service
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from ..core.system import AppInfo
from .model import ProcessInfo

LAUNCHERS = ("gnome", "kde", "xfce", "flatpak", "snap", "dbus", "systemd")
SYSTEM_ID = "system"

_SNAP = re.compile(r"^snap\.([^.]+)\.([^.]+?)(?:-[0-9a-f-]{8,})?\.(?:scope|service)$")
_APP = re.compile(r"^app-(.+?)(?:\.slice|\.scope|\.service)$")


def _unescape(s: str) -> str:
    return re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), s)


def app_id_for_cgroup(cgroup: str) -> Optional[str]:
    for unit in cgroup.split("/"):
        m = _SNAP.match(unit)
        if m:
            return f"{m.group(1)}_{m.group(2)}"
        m = _APP.match(unit)
        if not m:
            continue
        name = m.group(1).split("@", 1)[0]
        if unit.endswith(".scope"):
            name = re.sub(r"-(\d+|[0-9a-f]{32})$", "", name)     # random suffix
        parts = name.split("-", 1)
        if len(parts) == 2 and parts[0] in LAUNCHERS:
            name = parts[1]
        if name:
            return _unescape(name)
    return None


@dataclass
class App:
    id: str
    name: str
    icon: object = None
    description: str = ""
    pids: list[int] = field(default_factory=list)
    cpu: float = 0.0
    memory: int = 0
    swap: int = 0
    read_bps: float = 0.0
    write_bps: float = 0.0
    read_total: int = 0
    write_total: int = 0
    gpu: float = 0.0
    vram: int = 0
    encode: float = 0.0
    decode: float = 0.0
    started: Optional[float] = None
    containerized: Optional[str] = None

    @property
    def combined_memory(self) -> int:
        return self.memory + self.swap


class AppIconLookup:
    """The app icon of a PID (for views that know only PIDs, like the Intel
    GPU's Processes tab): its cgroup from ``/proc/<pid>/cgroup``, the app
    from that, the icon from the grouper. Cached per PID."""

    MAX_CACHE = 1024

    def __init__(self, sysroot, grouper: "AppGrouper") -> None:
        self.sysroot = sysroot
        self.grouper = grouper
        self._cache: dict[int, object] = {}

    def icon_for_pid(self, pid: int) -> object:
        """A Gio.Icon, or None (no app, no icon, or the process is gone)."""
        if pid in self._cache:
            return self._cache[pid]
        text = self.sysroot.read_text(f"/proc/{pid}/cgroup") if pid > 0 else None
        if text is None:
            return None                  # gone (or never was): don't cache
        path = next((line.split(":", 2)[2] for line in text.splitlines()
                     if line.count(":") >= 2), "")
        info = self.grouper.info_for(app_id_for_cgroup(path))
        icon = info.icon if info is not None else None
        if len(self._cache) >= self.MAX_CACHE:
            self._cache.clear()          # PIDs get reused; start over
        self._cache[pid] = icon
        return icon


class AppGrouper:
    """Groups processes into apps. ``lookup`` maps an app ID to its
    ``AppInfo`` (in the app: ``System.desktop_app``)."""

    def __init__(self, lookup: Callable[[str], Optional[AppInfo]]) -> None:
        self.lookup = lookup
        self._cache: dict[str, Optional[AppInfo]] = {}

    def info_for(self, app_id: Optional[str]) -> Optional[AppInfo]:
        if not app_id:
            return None
        if app_id not in self._cache:
            self._cache[app_id] = self.lookup(app_id)
        return self._cache[app_id]

    def icon_for(self, process: ProcessInfo) -> object:
        """The icon (Gio.Icon) of the app ``process`` belongs to, or None
        (no app, or an app without an icon)."""
        info = self.info_for(process.app_id)
        return info.icon if info is not None else None

    def group(self, processes: Iterable[ProcessInfo]) -> dict[str, App]:
        apps: dict[str, App] = {}
        for p in processes:
            info = self.info_for(p.app_id)
            if info is None:
                app = apps.setdefault(SYSTEM_ID, App(SYSTEM_ID, "System Processes",
                                                     description="Processes without an app"))
            else:
                app = apps.setdefault(p.app_id, App(p.app_id, info.name, info.icon,
                                                    info.description))
            app.pids.append(p.pid)
            app.cpu += p.cpu
            app.memory += p.memory
            app.swap += p.swap
            app.read_bps += p.read_bps or 0.0
            app.write_bps += p.write_bps or 0.0
            app.read_total += p.read_total or 0
            app.write_total += p.write_total or 0
            app.gpu = min(app.gpu + p.gpu, 100.0)
            app.vram += p.vram
            app.encode = min(app.encode + p.encode, 100.0)
            app.decode = min(app.decode + p.decode, 100.0)
            app.started = p.started if app.started is None else min(app.started, p.started)
            app.containerized = app.containerized or p.containerized
        return apps
