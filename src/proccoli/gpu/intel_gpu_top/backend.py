"""The Intel detail source: streams ``intel_gpu_top -J`` and adds the
Details and Processes tabs (intel_gpu_top_gui's views) to the GPU page."""

from __future__ import annotations

import math
import random
from typing import Iterator, Optional

import logging

from gi.repository import GLib

from ...core.ticker import history_plan, interval_for, time_range_s
from ...core.trust import find_trusted
from ..backend import (Capability, DetailBackend, GpuBackend, GpuDeps, GpuProcessUsage,
                       GpuSummary, Probe, SupportLevel, TabSpec)
from ..info import GpuInfo, GpuVendor
from .history import History, to_float

log = logging.getLogger(__name__)

INTEL_GPU_TOP = "intel_gpu_top"
UNTRUSTED_REASON = ("intel_gpu_top isn't installed where only administrators can change it "
                    "(such as /usr/bin), so it isn't run as administrator")
VIDEO_CLASSES = ("Video", "VideoEnhance")

def has_perf_access(deps: GpuDeps, exe: str) -> bool:
    """Whether intel_gpu_top can open the GPU's perf counters without
    pkexec: as root, with a relaxed perf_event_paranoid, or when the binary
    has file capabilities (``setcap cap_perfmon=+ep``)."""
    if deps.system.geteuid() == 0:
        return True
    paranoid = deps.sysroot.read_int("/proc/sys/kernel/perf_event_paranoid")
    if paranoid is not None and paranoid <= 0:
        return True
    return deps.system.has_file_capabilities(exe)


def _engine_class(name: str) -> str:
    """"Render/3D/0" -> "Render/3D" (multi-instance engines)."""
    parts = name.split("/")
    return "/".join(parts[:-1]) if parts[-1].isdigit() else name


class IntelGpuTopBackend(DetailBackend):
    id = "intel_gpu_top"
    display_name = "intel_gpu_top"
    capabilities = (Capability.SUMMARY | Capability.PER_PROCESS | Capability.PER_ENGINE
                    | Capability.POWER | Capability.EXPORT)
    TABS = (TabSpec("details", "Details", "power-profile-performance-symbolic"),
            TabSpec("processes", "Processes", "view-list-bullet-symbolic"))

    def __init__(self, gpu: GpuInfo, deps: GpuDeps) -> None:
        super().__init__(gpu, deps)
        settings = deps.settings
        self.history = History(self._plan()[0])
        self.history.set_plan(*self._plan())
        self.latest: Optional[dict] = None
        self.paused = False
        self.started = False
        self.reader = deps.system.stream_reader()
        self.reader.connect("record", self._on_record)
        self.reader.connect("exited", self._on_exited)
        self._handlers = [
            settings.connect_changed("graph-time-range",
                                     lambda *_: self.history.set_plan(*self._plan())),
            settings.connect_changed("intel-gpu-top-interval", lambda *_: self._on_interval()),
            settings.connect_changed("update-interval", lambda *_: self._on_interval()),
        ]
        self._interval = self.interval_ms

    def _plan(self) -> tuple[int, int, float]:
        """``(points, every, step_s)`` for the app's *Graph Time Range*
        (Idea 3; was the tab's own History Length) at intel_gpu_top's
        update interval; long ranges average samples."""
        points, every = history_plan(time_range_s(self.settings.get("graph-time-range")),
                                     self.interval_ms)
        return points, every, self.interval_ms * every / 1000

    def history_readings(self) -> tuple[dict, dict]:
        return self.history.readings()

    def history_target(self):
        return self.history

    @classmethod
    def probe(cls, gpu, deps) -> Probe:
        if gpu.vendor != GpuVendor.INTEL or gpu.driver not in ("i915", "xe"):
            return Probe(SupportLevel.UNSUPPORTED, "not an Intel GPU")
        exe = deps.system.which(INTEL_GPU_TOP)
        if exe is None:
            return Probe(SupportLevel.UNSUPPORTED,
                         "intel_gpu_top is not installed (package intel-gpu-tools)")
        return Probe(SupportLevel.PREFERRED, "per-engine statistics",
                     needs_elevation=not has_perf_access(deps, exe))

    @property
    def interval_ms(self) -> int:
        own = self.settings.get("intel-gpu-top-interval")
        return interval_for(own or self.settings.get("update-interval"))

    def command(self, exe: str) -> list[str]:
        return [exe, "-J", "-s", str(self.interval_ms), "-d", f"drm:/dev/dri/{self.gpu.card}"]

    def executable(self, elevate: bool) -> Optional[str]:
        """The intel_gpu_top to run. As root (pkexec), only a copy in the
        system folders that only root can change, never one found on PATH
        (DESIGN.md §11, Security); None if there's no such copy."""
        system = self.deps.system
        if elevate:
            return find_trusted(INTEL_GPU_TOP, system.trusted_executable)
        return system.which(INTEL_GPU_TOP) or INTEL_GPU_TOP

    def start(self, elevate: bool = False) -> None:
        super().start(elevate)
        self.started = True
        if elevate and self.deps.helper is not None:
            # Through the helper, which stops intel_gpu_top when we stop
            # reading: it ignores SIGPIPE and we can't signal it (M42).
            argv = self.deps.helper.gpu_top_argv(self.interval_ms, self.gpu.card)
            if argv is not None:
                self.reader.start(argv, elevate=True)
                return
            log.warning("the installed helper can't run intel_gpu_top; running it "
                        "directly, so it may outlive Proccoli (reinstall Proccoli)")
        exe = self.executable(elevate)
        if exe is None:
            # After this call returns, as a failed stream would.
            GLib.idle_add(self._refuse_untrusted)
            return
        self.reader.start(self.command(exe), elevate=elevate)

    def _refuse_untrusted(self) -> bool:
        if self.started:
            self.emit("failed", UNTRUSTED_REASON, False)
        return False

    def stop(self) -> None:
        self.started = False
        self.reader.stop()
        for h in self._handlers:
            self.settings.disconnect(h)
        self._handlers = []

    def _on_interval(self) -> None:
        """Samples at a different rate can't share a time axis: clear the
        history and restart the stream (as intel_gpu_top_gui does)."""
        if self.interval_ms == self._interval:
            return
        self._interval = self.interval_ms
        self.history.clear()
        self.history.set_plan(*self._plan())
        if self.started:
            self.start(self.elevated)

    def clear(self) -> None:
        self.history.clear()
        self.emit("updated")

    def has_data(self) -> bool:
        return self.latest is not None

    # -- stream ---------------------------------------------------------------

    def _on_record(self, _reader, sample: dict) -> None:
        self.latest = sample
        if not self.paused:
            self.history.add(sample)
        self.emit("updated")

    def _on_exited(self, _reader, rc: int, stderr: str, count: int) -> None:
        if self.elevated and rc in (126, 127) and count == 0:
            reason = "Authentication was cancelled or refused"
        elif count == 0:
            reason = "intel_gpu_top could not read the GPU's performance counters"
        else:
            reason = f"intel_gpu_top stopped (exit status {rc})"
        self.emit("failed", reason, not self.elevated)

    # -- summary ------------------------------------------------------------------

    def _engines(self) -> dict[str, float]:
        """Busy percent per engine class (max over instances)."""
        out: dict[str, float] = {}
        for name, data in ((self.latest or {}).get("engines") or {}).items():
            busy = to_float(data.get("busy")) if isinstance(data, dict) else None
            if busy is not None:
                cls = _engine_class(name)
                out[cls] = max(out.get(cls, 0.0), busy)
        return out

    def summary(self) -> GpuSummary:
        s = GpuSummary(combined_video=True)
        if self.latest is None:
            return s
        engines = self._engines()
        compute = [v for k, v in engines.items() if k not in VIDEO_CLASSES]
        s.usage = max(compute) if compute else None
        if "Video" in engines:
            s.encode = s.decode = engines["Video"]
        freq = self.latest.get("frequency") or {}
        actual = to_float(freq.get("actual"))
        s.frequency_hz = actual * 1e6 if actual is not None else None
        power = self.latest.get("power") or {}
        s.power_w = to_float(power.get("GPU"))
        return s

    def process_usage(self) -> dict[int, GpuProcessUsage]:
        out: dict[int, GpuProcessUsage] = {}
        for data in ((self.latest or {}).get("clients") or {}).values():
            if not isinstance(data, dict):
                continue
            try:
                pid = int(data.get("pid", 0))
            except (TypeError, ValueError):
                continue
            busy = {}
            for cls, d in (data.get("engine-classes") or {}).items():
                v = to_float(d.get("busy")) if isinstance(d, dict) else None
                if v is not None:
                    busy[_engine_class(cls)] = v
            video = busy.get("Video", 0.0)
            u = GpuProcessUsage(pid, usage=max((v for k, v in busy.items()
                                                if k not in VIDEO_CLASSES), default=0.0),
                                encode=video, decode=video)
            if pid in out:
                out[pid].merge(u)
            else:
                out[pid] = u
        return out

    def create_views(self, controller, services):
        from .views import create_views
        return create_views(self, controller, services)


class DemoIntelGpuTopBackend(IntelGpuTopBackend):
    """Synthetic intel_gpu_top data for --demo (ported from intel_gpu_top_gui)."""
    id = "intel_gpu_top"

    @classmethod
    def probe(cls, gpu, deps) -> Probe:
        return Probe(SupportLevel.PREFERRED, "synthetic data")

    def start(self, elevate: bool = False) -> None:
        GpuBackend.start(self, elevate)
        self.started = True
        self.reader.start_generator(lambda: demo_samples(self.interval_ms),
                                    self.interval_ms / 1000)


def demo_samples(interval_ms: int) -> Iterator[dict]:
    rnd = random.Random(1)
    clients = {"1": ("gnome-shell", "2190"), "2": ("firefox", "4410"),
               "3": ("ffmpeg", "9120")}
    t = 0.0
    while True:
        t += interval_ms / 1000
        render = max(0.0, 35 + 30 * math.sin(t / 7) + rnd.uniform(-8, 8))
        video = max(0.0, 50 + 45 * math.sin(t / 13 + 1)) if (t // 20) % 2 else 0.0
        blit = max(0.0, rnd.uniform(0, 6))
        ve = video * 0.4
        busy = max(render, video)
        req = 300 + busy * 11
        yield {
            "period": {"duration": interval_ms, "unit": "ms"},
            "frequency": {"requested": req, "actual": req * rnd.uniform(0.85, 1.0),
                          "unit": "MHz"},
            "interrupts": {"count": busy * 12 + rnd.uniform(0, 40), "unit": "irq/s"},
            "rc6": {"value": max(0.0, 100 - busy * 1.1), "unit": "%"},
            "power": {"GPU": 0.3 + busy * 0.09, "Package": 3.0 + busy * 0.18, "unit": "W"},
            "imc-bandwidth": {"reads": 800 + busy * 40, "writes": 200 + busy * 15,
                              "unit": "MiB/s"},
            "engines": {
                "Render/3D": {"busy": min(render, 100), "sema": 0.0, "wait": 0.0, "unit": "%"},
                "Blitter": {"busy": blit, "sema": 0.0, "wait": 0.0, "unit": "%"},
                "Video": {"busy": min(video, 100), "sema": 0.0, "wait": 0.0, "unit": "%"},
                "VideoEnhance": {"busy": ve, "sema": 0.0, "wait": 0.0, "unit": "%"},
            },
            "clients": {
                cid: {"name": name, "pid": pid, "engine-classes": {
                    "Render/3D": {"busy": f"{render * share:.2f}", "unit": "%"},
                    "Blitter": {"busy": f"{blit * share:.2f}", "unit": "%"},
                    "Video": {"busy": f"{(video if name == 'ffmpeg' else 0):.2f}", "unit": "%"},
                    "VideoEnhance": {"busy": f"{(ve if name == 'ffmpeg' else 0):.2f}",
                                     "unit": "%"}}}
                for (cid, (name, pid)), share in zip(clients.items(), (0.2, 0.7, 0.1))
            },
        }
