"""Samples every process on each tick, while somebody is looking.

Scanning /proc is the most expensive thing Proccoli does, so it only runs
while the Apps or Processes page is visible (pages ``acquire()`` and
``release()`` it).
"""

from __future__ import annotations

from typing import Callable, Iterable, Optional

from gi.repository import GObject

from ..core.sysroot import SysRoot
from .apps import app_id_for_cgroup
from .model import ProcessInfo, RawProc, containerization, read_proc


class ProcessMonitor(GObject.Object):
    __gsignals__ = {
        "updated": (GObject.SignalFlags.RUN_FIRST, None, ()),
        # The privileged I/O stream started (True) or ended (False).
        "elevated-io": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
    }

    def __init__(self, sysroot: SysRoot, settings, system,
                 gpu_controllers: Callable[[], Iterable] = lambda: ()) -> None:
        super().__init__()
        self.sysroot = sysroot
        self.settings = settings
        self.system = system
        self.gpu_controllers = gpu_controllers
        self.clk_tck = system.clk_tck()
        self.processes: dict[int, ProcessInfo] = {}
        self.users = 0
        self._prev: dict[int, RawProc] = {}
        self._prev_time: Optional[float] = None
        self._ticker_handler = 0
        # Drive I/O of other users' processes, from the privileged helper.
        self.elevated_io: dict[int, tuple[int, int]] = {}
        self._io_reader = None

    # -- demand ---------------------------------------------------------------

    def acquire(self) -> None:
        self.users += 1

    def release(self) -> None:
        self.users = max(0, self.users - 1)

    def follow(self, ticker) -> None:
        self._ticker = ticker
        self._ticker_handler = ticker.connect("tick", lambda _t, now: self.tick(now))

    def tick(self, now: float) -> None:
        if self.users:
            self.refresh(now)

    # -- privileged I/O ------------------------------------------------------------

    @property
    def elevated(self) -> bool:
        return self._io_reader is not None

    def use_elevated_io(self, reader) -> None:
        """Merge ``{"io": {pid: [read, write]}}`` records from ``reader`` (the
        helper's ``processes`` stream) into processes we can't read."""
        self.stop_elevated_io()
        self._io_reader = reader
        reader.connect("record", self._on_io_record)
        reader.connect("exited", lambda *_: self.stop_elevated_io(stopped=True))
        self.emit("elevated-io", True)

    def stop_elevated_io(self, stopped: bool = False) -> None:
        reader, self._io_reader = self._io_reader, None
        self.elevated_io = {}
        if reader is not None:
            if not stopped:
                reader.stop()
            self.emit("elevated-io", False)

    def _on_io_record(self, _reader, record: dict) -> None:
        io = record.get("io") if isinstance(record, dict) else None
        if isinstance(io, dict):
            self.elevated_io = {int(pid): (int(v[0]), int(v[1])) for pid, v in io.items()
                                if str(pid).isdigit() and isinstance(v, list) and len(v) == 2}

    # -- sampling ---------------------------------------------------------------

    def _boot_time(self) -> float:
        for line in (self.sysroot.read_text("/proc/stat") or "").splitlines():
            if line.startswith("btime "):
                return float(line.split()[1])
        return 0.0

    def cpu_count(self) -> int:
        stat = self.sysroot.read_text("/proc/stat") or ""
        return max(1, sum(1 for line in stat.splitlines()
                          if line.startswith("cpu") and line[3:4].isdigit()))

    def refresh(self, now: float) -> None:
        raw: dict[int, RawProc] = {}
        for entry in self.sysroot.listdir("/proc"):
            if entry.isdigit():
                pid = int(entry)
                proc = read_proc(self.sysroot, pid, self._prev.get(pid))
                if proc is not None:
                    if proc.read_bytes is None and pid in self.elevated_io:
                        proc.read_bytes, proc.write_bytes = self.elevated_io[pid]
                    raw[pid] = proc
        dt = now - self._prev_time if self._prev_time is not None else 0.0
        normalize = self.settings.get("normalize-cpu-usage")
        cpus = self.cpu_count() if normalize else 1
        boot = self._boot_time()
        gpu: dict[int, list] = {}
        for controller in self.gpu_controllers():
            for pid, usage in controller.process_usage().items():
                gpu.setdefault(pid, []).append(usage)

        processes = {}
        for pid, p in raw.items():
            old = self._prev.get(pid)
            same = old is not None and old.starttime == p.starttime and dt > 0
            cpu = 0.0
            read_bps = write_bps = None
            if same:
                ticks = (p.utime + p.stime) - (old.utime + old.stime)
                cpu = max(ticks, 0) / self.clk_tck / dt * 100 / cpus
                if p.read_bytes is not None and old.read_bytes is not None:
                    read_bps = max(p.read_bytes - old.read_bytes, 0) / dt
                    write_bps = max(p.write_bytes - old.write_bytes, 0) / dt
            elif p.read_bytes is not None:
                read_bps = write_bps = 0.0
            info = ProcessInfo(
                pid=pid, ppid=p.ppid, name=p.name, commandline=p.cmdline,
                user=self.system.user_name(p.uid), uid=p.uid, state=p.state, nice=p.nice,
                cpu=cpu, memory=p.rss, swap=p.swap, read_bps=read_bps, write_bps=write_bps,
                read_total=p.read_bytes, write_total=p.write_bytes,
                cpu_time_user=p.utime / self.clk_tck, cpu_time_system=p.stime / self.clk_tck,
                started=boot + p.starttime / self.clk_tck, cgroup=p.cgroup,
                containerized=containerization(p.cgroup), app_id=app_id_for_cgroup(p.cgroup))
            for usage in gpu.get(pid, ()):
                info.gpu = min(info.gpu + usage.usage, 100.0)
                info.encode = min(info.encode + usage.encode, 100.0)
                info.decode = min(info.decode + usage.decode, 100.0)
                info.vram += usage.vram
            processes[pid] = info
        self._prev, self._prev_time = raw, now
        self.processes = processes
        self.emit("updated")
