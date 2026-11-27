"""One GpuController per GPU.

It owns the GPU's summary source (always running) and, if the GPU has a
vendor tool, its detail source with its lifecycle (``DetailState``). To the
rest of the app it's an ordinary device monitor.
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional

from gi.repository import GObject

from .. import GPU_ICON
from ..core.connections import Connections
from ..core.units import format_percent
from ..devices.base import DeviceInfo, DeviceKind, Monitor, Snapshot
from ..devices.manager import Discoverer
from .backend import DetailBackend, GpuBackend, GpuDeps, GpuSummary, Probe, frequency_text
from .detect import GpuPlan, plan_gpu
from .info import GpuInfo, discover_gpus
from .registry import GpuBackendRegistry
from ..core.history import DETAIL_PREFIX
from ..core.profile import profile_of
from ..core.ticker import graph_points

log = logging.getLogger(__name__)


class DetailState(Enum):
    UNAVAILABLE = "unavailable"   # no vendor tool for this GPU
    OFF = "off"                   # turned off in Preferences
    NEEDS_AUTH = "needs-auth"     # waiting for the user to authenticate
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"


@dataclass
class GpuSnapshot(Snapshot):
    summary: Optional[GpuSummary] = None
    # The Details tab's readings while it runs (``DetailBackend.
    # history_readings``), recorded as "detail/<key>" (history follow-ups).
    detail: dict = dataclasses.field(default_factory=dict)
    detail_units: dict = dataclasses.field(default_factory=dict)

    def history_values(self):
        s = self.summary
        return {"usage": s.usage, "encode": s.encode, "decode": s.decode,
                "vram": s.memory_usage, "temperature": s.temperature_c,
                "power": s.power_w, "frequency": s.frequency_hz}

    def history_units(self) -> Mapping[str, str]:
        return {"usage": "%", "encode": "%", "decode": "%", "vram": "%",
                "temperature": "°C", "power": "W", "frequency": "Hz"}

    def stats_values(self):
        s = self.summary
        return {**self.history_values(), "vram-used": s.vram_used, "vram-total": s.vram_total,
                "gtt-used": s.gtt_used, "gtt-total": s.gtt_total,
                "vram-frequency": s.vram_frequency_hz,
                **{DETAIL_PREFIX + k: v for k, v in self.detail.items()}}

    def stats_units(self) -> Mapping[str, str]:
        return {**self.history_units(), "vram-used": "B", "vram-total": "B",
                "gtt-used": "B", "gtt-total": "B",
                "vram-frequency": "Hz",
                **{DETAIL_PREFIX + k: self.detail_units.get(k, "") for k in self.detail}}


def merge_summaries(primary: GpuSummary, fallback: GpuSummary) -> GpuSummary:
    """``primary``'s values, with gaps filled from ``fallback`` (e.g. the
    detail tool knows engine use; sysfs knows temperature and VRAM)."""
    merged = dataclasses.replace(primary)
    for f in dataclasses.fields(GpuSummary):
        if getattr(merged, f.name) is None:
            setattr(merged, f.name, getattr(fallback, f.name))
    return merged


class GpuController(Monitor):
    __gsignals__ = {
        "detail-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, info: DeviceInfo, gpu: GpuInfo, registry: GpuBackendRegistry,
                 deps: GpuDeps, history_points: int = 60) -> None:
        super().__init__(info, history_points)
        self.gpu = gpu
        self.registry = registry
        self.deps = deps
        self.settings = deps.settings
        # Which panel this GPU gets, and why: logged, shown on the page,
        # and the error page's text if nothing can serve it.
        self.plan: GpuPlan = plan_gpu(gpu, registry, deps)
        log.info("%s: %s", info.id, self.plan.explain())
        if not self.plan.usable:
            raise RuntimeError("No statistics source can read this GPU.\n" + self.plan.explain())
        self.summary_class: type[GpuBackend] = self.plan.summary.backend
        detail = self.plan.detail
        self.detail_class: Optional[type[DetailBackend]] = detail.backend if detail else None
        self.detail_probe: Optional[Probe] = detail.probe if detail else None
        self.summary_backend: Optional[GpuBackend] = None
        self.detail_backend: Optional[DetailBackend] = None
        self.detail_state = DetailState.UNAVAILABLE
        self.detail_message = ""
        self.detail_can_elevate = False
        self._detail_connections = Connections()
        for name, unit in GpuSnapshot(0, summary=GpuSummary()).history_units().items():
            self.history.define(name, unit)


    def sort_name(self) -> str:
        return self.gpu.pci_slot
    def described_properties(self) -> dict[str, str]:
        """The GPU's properties and its detail source, as its page lists them."""
        return {**super().described_properties(),
                "Detailed Statistics": self.plan.detail_text()}

    # -- lifecycle ------------------------------------------------------------

    @property
    def details_enabled(self) -> bool:
        return self.gpu.pci_slot not in self.settings.get("gpu-details-disabled")

    @property
    def needs_elevation(self) -> bool:
        return bool(self.detail_probe and self.detail_probe.needs_elevation)

    def start(self) -> None:
        self.summary_backend = self.summary_class(self.gpu, self.deps)
        self.summary_backend.start(False)
        self._start_details_if_allowed()
        # Another process may turn this GPU's details on or off (the window
        # changes the setting; the collector does the reading).
        self._disabled_handler = self.settings.connect_changed(
            "gpu-details-disabled", lambda *_: self._follow_details_setting())

    def _follow_details_setting(self) -> None:
        if self.detail_class is None:
            return
        if self.details_enabled and self.detail_state == DetailState.OFF:
            self._start_details_if_allowed()
        elif not self.details_enabled and self.detail_backend is not None:
            self.stop_details()

    def stop(self) -> None:
        if getattr(self, "_disabled_handler", 0):
            self.settings.disconnect(self._disabled_handler)
            self._disabled_handler = 0
        if self.summary_backend is not None:
            self.summary_backend.stop()
        self._drop_detail_backend()

    def _start_details_if_allowed(self) -> None:
        """Start the detail source unless that would need a password the
        user hasn't asked for."""
        if self.detail_class is None:
            self._set_state(DetailState.UNAVAILABLE)
        elif not profile_of(self.settings).gpu_details:
            self._set_state(DetailState.OFF, "Detailed statistics are off in Lightweight Mode "
                            "(Preferences → General)")
        elif not self.details_enabled:
            self._set_state(DetailState.OFF, "Detailed statistics are turned off")
        elif self.needs_elevation and not profile_of(self.settings).gpu_elevate:
            # The background collector: nobody to ask for a password.
            self._set_state(DetailState.OFF, "Detailed statistics need administrator rights")
        elif self.needs_elevation and not self.settings.get("gpu-elevate"):
            self._set_state(DetailState.NEEDS_AUTH,
                            "Detailed statistics need administrator rights",
                            can_elevate=True)
        else:
            self.start_details(elevate=self.needs_elevation)

    def start_details(self, elevate: bool = False) -> None:
        """(Re)start the detail source; ``elevate`` runs it through pkexec."""
        if self.detail_class is None:
            raise RuntimeError(f"{self.gpu.pci_slot} has no detail source")
        self._drop_detail_backend()
        backend = self.detail_class(self.gpu, self.deps)
        self.detail_backend = backend
        self._detail_connections.connect(backend, "failed", self._on_detail_failed)
        self._detail_connections.connect(backend, "updated", self._on_detail_updated)
        self._set_state(DetailState.STARTING, "Starting " + self.detail_class.display_name)
        backend.start(elevate)

    def stop_details(self) -> None:
        self._drop_detail_backend()
        self._set_state(DetailState.OFF, "Detailed statistics are turned off")

    def set_details_enabled(self, on: bool) -> None:
        """Preferences: turn this GPU's detailed statistics on or off."""
        disabled = [s for s in self.settings.get("gpu-details-disabled")
                    if s != self.gpu.pci_slot]
        if not on:
            disabled.append(self.gpu.pci_slot)
        self.settings.set("gpu-details-disabled", disabled)
        if on and self.detail_state == DetailState.OFF:
            self._start_details_if_allowed()
        elif not on and self.detail_class is not None:
            self.stop_details()

    def _drop_detail_backend(self) -> None:
        backend, self.detail_backend = self.detail_backend, None
        if backend is not None:
            self._detail_connections.disconnect_all()
            backend.stop()

    def _set_state(self, state: DetailState, message: str = "",
                   can_elevate: bool = False) -> None:
        self.detail_state = state
        self.detail_message = message
        self.detail_can_elevate = can_elevate
        log.debug("%s: details %s (%s)", self.info.id, state.value, message)
        self.emit("detail-changed", state.value)

    def _on_detail_updated(self, backend) -> None:
        if backend is self.detail_backend and self.detail_state == DetailState.STARTING \
                and backend.has_data():
            self._set_state(DetailState.RUNNING)

    def _on_detail_failed(self, backend, reason: str, can_elevate: bool) -> None:
        if backend is not self.detail_backend:
            return
        log.info("%s: %s failed: %s", self.info.id, backend.id, reason)
        self._drop_detail_backend()
        self._set_state(DetailState.FAILED, reason, can_elevate=can_elevate)

    # -- data ---------------------------------------------------------------------

    @property
    def detail_running(self) -> bool:
        return (self.detail_state == DetailState.RUNNING and self.detail_backend is not None
                and self.detail_backend.has_data())

    def summary(self) -> GpuSummary:
        base = self.summary_backend.summary() if self.summary_backend else GpuSummary()
        if self.detail_running:
            return merge_summaries(self.detail_backend.summary(), base)
        return base

    def process_usage(self):
        # The detail source's figures while it has any (NVIDIA's tools have
        # none), otherwise the summary source's.
        if self.detail_running:
            usage = self.detail_backend.process_usage()
            if usage:
                return usage
        return self.summary_backend.process_usage() if self.summary_backend else {}

    def describe(self, encode) -> dict:
        """The GPU's identity, what detection chose and its Details source."""
        detail = self.detail_class
        return {**super().describe(encode),
                "gpu": {"info": encode(self.gpu),
                        "plan_text": self.plan.detail_text(),
                        "plan_explain": self.plan.explain(),
                        "detail_source": detail.id if detail is not None else None,
                        "needs_elevation": self.needs_elevation}}

    def reading(self, encode) -> Optional[dict]:
        """The Details state, sample and per-process use too."""
        out = super().reading(encode)
        if out is None:
            return None
        backend = self.detail_backend
        out["gpu"] = {
            "detail_state": self.detail_state.name,
            "detail_message": self.detail_message,
            "detail_source": getattr(backend, "id", None),
            "detail_note": getattr(backend, "source_note", ""),
            "detail_sample": encode(getattr(backend, "sample", None)),
            "processes": encode(self.process_usage()),
        }
        return out

    def refresh(self, now: float) -> None:
        if self.summary_backend is not None:
            self.summary_backend.refresh(now)
        if self.detail_backend is not None:
            self.detail_backend.refresh(now)
        super().refresh(now)

    def sample(self, now: float) -> Optional[GpuSnapshot]:
        if self.summary_backend is None:
            return None
        s = self.summary()
        detail, units = (self.detail_backend.history_readings() if self.detail_running
                         else ({}, {}))
        return GpuSnapshot(time=now, usage=s.usage,
                           usage_text=format_percent(s.usage) if s.usage is not None else "",
                           detail_text=frequency_text(s.frequency_hz) or "",
                           summary=s, detail=detail, detail_units=units)

    def detail_history(self):
        """The running Details tab's history, to fill from the database."""
        return self.detail_backend.history_target() if self.detail_running else None


class GpuDiscoverer(Discoverer):
    kind = DeviceKind.GPU

    def __init__(self, registry: GpuBackendRegistry, pci, system, helper=None) -> None:
        self.registry = registry
        self.pci = pci
        self.system = system
        self.helper = helper

    def discover(self, sysroot, settings) -> list[DeviceInfo]:
        self._gpus = {f"gpu-{g.pci_slot}": g for g in discover_gpus(sysroot, self.pci)}
        return [DeviceInfo(gid, DeviceKind.GPU, "GPU", g.name, GPU_ICON,
                           g.properties)
                for gid, g in self._gpus.items()]

    def create_monitor(self, info, sysroot, settings) -> Monitor:
        return GpuController(info, self._gpus[info.id], self.registry,
                             GpuDeps(sysroot, settings, self.system, self.helper),
                             graph_points(settings))
