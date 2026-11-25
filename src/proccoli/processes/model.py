"""Reading one process from /proc, and the computed per-process record."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..core.sysroot import SysRoot


@dataclass
class RawProc:
    """Counters straight from /proc/<pid>/... (no rates yet)."""
    pid: int
    ppid: int
    name: str
    state: str
    utime: int              # clock ticks
    stime: int
    starttime: int          # clock ticks after boot
    nice: int
    uid: Optional[int] = None
    rss: int = 0            # bytes
    swap: int = 0
    read_bytes: Optional[int] = None   # None: not permitted to read /proc/<pid>/io
    write_bytes: Optional[int] = None
    cgroup: str = ""
    cmdline: str = ""


def parse_stat(text: str, pid: int) -> Optional[RawProc]:
    """/proc/<pid>/stat. The command name is in parentheses and may itself
    contain spaces and parentheses, so split at the *last* ")"."""
    try:
        name = text[text.index("(") + 1:text.rindex(")")]
        f = text[text.rindex(")") + 2:].split()
        return RawProc(pid=pid, ppid=int(f[1]), name=name, state=f[0], utime=int(f[11]),
                       stime=int(f[12]), starttime=int(f[19]), nice=int(f[16]))
    except (ValueError, IndexError):
        return None


def read_start_time(sysroot: SysRoot, pid: int) -> Optional[int]:
    """When ``pid`` started (clock ticks after boot), None if it's gone:
    with the PID, it names one process even after the PID is reused."""
    text = sysroot.read_text(f"/proc/{pid}/stat")
    raw = parse_stat(text, pid) if text else None
    return raw.starttime if raw is not None else None


def parse_status(text: str, proc: RawProc) -> None:
    for line in text.splitlines():
        key, _, value = line.partition(":")
        parts = value.split()
        if key == "Uid" and parts:
            proc.uid = int(parts[0])
        elif key == "VmRSS" and parts:
            proc.rss = int(parts[0]) * 1024
        elif key == "VmSwap" and parts:
            proc.swap = int(parts[0]) * 1024


def parse_io(text: str, proc: RawProc) -> None:
    for line in text.splitlines():
        key, _, value = line.partition(":")
        if key == "read_bytes":
            proc.read_bytes = int(value)
        elif key == "write_bytes":
            proc.write_bytes = int(value)


def parse_cgroup(text: str) -> str:
    """The unified (v2) cgroup path."""
    for line in text.splitlines():
        if line.startswith("0::"):
            return line[3:]
    return ""


def display_name(comm: str, cmdline: str) -> str:
    """comm is cut at 15 characters; use the executable's name when it's the
    longer version of the same name. For a script run by an interpreter
    (``/usr/bin/python3 /usr/bin/gnome-shell-calendar-server``) that's the
    script, the second word."""
    if len(comm) == 15 and cmdline:
        for word in cmdline.split(" ", 2)[:2]:
            exe = word.rsplit("/", 1)[-1]
            if exe.startswith(comm):
                return exe
    return comm


def read_proc(sysroot: SysRoot, pid: int,
              cached: Optional[RawProc] = None) -> Optional[RawProc]:
    """Read a process; ``cached`` (the same process last time) saves
    re-reading what doesn't change: the command line and the cgroup."""
    base = f"/proc/{pid}"
    stat = sysroot.read_text(f"{base}/stat")
    proc = parse_stat(stat, pid) if stat else None
    if proc is None:
        return None          # exited, or not a process
    status = sysroot.read_text(f"{base}/status")
    if status:
        parse_status(status, proc)
    io = sysroot.read_text(f"{base}/io")
    if io:
        parse_io(io, proc)
    if cached is not None and cached.starttime == proc.starttime:
        proc.cmdline, proc.cgroup = cached.cmdline, cached.cgroup
    else:
        raw = sysroot.read_text(f"{base}/cmdline") or ""
        proc.cmdline = raw.replace("\0", " ").strip()
        proc.cgroup = parse_cgroup(sysroot.read_text(f"{base}/cgroup") or "")
    proc.name = display_name(proc.name, proc.cmdline)
    return proc


@dataclass
class ProcessInfo:
    """A process with its rates computed, as shown in the tables."""
    pid: int
    ppid: int
    name: str
    commandline: str
    user: str
    uid: Optional[int]
    state: str
    nice: int
    cpu: float                  # percent
    memory: int                 # bytes (resident)
    swap: int
    read_bps: Optional[float]   # None: not permitted
    write_bps: Optional[float]
    read_total: Optional[int]
    write_total: Optional[int]
    cpu_time_user: float        # seconds
    cpu_time_system: float
    started: float              # epoch seconds
    cgroup: str
    containerized: Optional[str]
    app_id: Optional[str]
    gpu: float = 0.0
    vram: int = 0
    encode: float = 0.0
    decode: float = 0.0

    @property
    def combined_memory(self) -> int:
        return self.memory + self.swap

    @property
    def cpu_time_total(self) -> float:
        return self.cpu_time_user + self.cpu_time_system


def containerization(cgroup: str) -> Optional[str]:
    if "app-flatpak-" in cgroup:
        return "Flatpak"
    if "/snap." in cgroup or cgroup.startswith("snap."):
        return "Snap"
    if any(m in cgroup for m in ("docker-", "/docker/", "libpod-", "/lxc/", "containerd")):
        return "Container"
    return None
