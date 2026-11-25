"""The NVIDIA detail source.

Polls NVIDIA's tools once per refresh, without blocking the main loop
(``System.run_async()``; a poll still running is never doubled up):

1. **nvidia-settings**, if installed: find this GPU's ``[gpu:N]`` target by
   PCI slot, then read it each refresh.
2. **nvidia-smi**, when nvidia-settings is missing or can't reach the GPU
   (it needs NV-CONTROL, i.e. an X11 session; Wayland, Ubuntu's default,
   doesn't have it). ``source_note`` says why, for the Details tab.

If neither can read the GPU, the source fails with the reason, and the
GPU's Details tab shows it with *Try Again*. A source that was running
fails only after ``MAX_MISSES`` polls in a row went wrong.

No administrator rights are needed. Per-process GPU use isn't available
from these tools cheaply (``nvidia-smi pmon`` takes a second per sample),
so the process columns keep the summary source's figures.
"""

from __future__ import annotations

import logging
from typing import Optional

from ...core.connections import Connections
from ...core.history import History
from ...core.ticker import PLAN_KEYS, graph_plan
from ..backend import (Capability, DetailBackend, GpuDeps, GpuSummary, Probe, SupportLevel,
                       TabSpec)
from ..info import GpuInfo, GpuVendor
from .query import (HISTORY_UNITS, NvidiaError, NvidiaSample, parse_settings,
                    parse_settings_targets, parse_smi, settings_argv, settings_targets_argv,
                    smi_argv)

log = logging.getLogger(__name__)

NVIDIA_SETTINGS = "nvidia-settings"
NVIDIA_SMI = "nvidia-smi"
MAX_MISSES = 3
# Shown on the Details tab when nvidia-settings can't do the job.
UNREACHABLE = "nvidia-settings can't read this GPU's usage without an X11 session"


class NvidiaBackend(DetailBackend):
    id = "nvidia"
    display_name = "NVIDIA"
    capabilities = (Capability.SUMMARY | Capability.POWER | Capability.TEMPERATURE
                    | Capability.VRAM)
    TABS = (TabSpec("details", "Details", "power-profile-performance-symbolic"),)

    def __init__(self, gpu: GpuInfo, deps: GpuDeps) -> None:
        super().__init__(gpu, deps)
        self.system = deps.system
        self.history = History(graph_plan(deps.settings)[0])
        self.history.set_plan(*graph_plan(deps.settings))
        # The graphs' time range, as on every page (history follow-ups).
        self._plan_connections = Connections()
        self._plan_connections.watch(
            deps.settings, PLAN_KEYS, lambda *_: self.history.set_plan(*graph_plan(self.settings)))
        for name, unit in HISTORY_UNITS.items():
            self.history.define(name, unit)
        self.sample: Optional[NvidiaSample] = None
        self.tool: Optional[str] = None          # the tool in use
        self.source_note = ""                     # why that one (the Details tab says)
        self._settings_index: Optional[int] = None
        self._busy = False
        self._running = False
        self._generation = 0                      # answers from before a stop are dropped
        self._misses = 0
        self._now = 0.0                           # the last tick's time (readings use it)

    # -- which tools ---------------------------------------------------------------------

    @classmethod
    def probe(cls, gpu: GpuInfo, deps: GpuDeps) -> Probe:
        if gpu.vendor != GpuVendor.NVIDIA:
            return Probe(SupportLevel.UNSUPPORTED, "not an NVIDIA GPU")
        if gpu.driver == "nouveau":
            return Probe(SupportLevel.UNSUPPORTED,
                         "uses the open nouveau driver; NVIDIA's tools need NVIDIA's driver")
        if gpu.driver != "nvidia":
            return Probe(SupportLevel.UNSUPPORTED,
                         f"driver {gpu.driver or 'none'}; NVIDIA's tools need NVIDIA's driver")
        tools = [t for t in (NVIDIA_SETTINGS, NVIDIA_SMI) if deps.system.which(t)]
        if not tools:
            return Probe(SupportLevel.UNSUPPORTED,
                         "neither nvidia-settings nor nvidia-smi is installed")
        return Probe(SupportLevel.PREFERRED, ", then ".join(tools))

    # -- lifecycle -----------------------------------------------------------------------

    def start(self, elevate: bool = False) -> None:
        super().start(False)                      # never needs administrator rights
        self._running = True
        self._generation += 1
        self._misses = 0
        if self.system.which(NVIDIA_SETTINGS):
            self.tool = NVIDIA_SETTINGS
            self._run(settings_targets_argv(self.system.which(NVIDIA_SETTINGS)),
                      self._on_targets)
        else:
            self._use_smi("nvidia-settings isn't installed")

    def stop(self) -> None:
        self._running = False
        self._generation += 1
        self._busy = False
        self._plan_connections.disconnect_all()

    def history_readings(self) -> tuple[dict, dict]:
        """The Details tab's readings, recorded in the history database."""
        if self.sample is None:
            return {}, {}
        return dict(self.sample.history_values()), dict(HISTORY_UNITS)

    def history_target(self):
        return self.history

    def refresh(self, now: float) -> None:
        self._now = now
        if self._running and not self._busy and self._ready:
            self._poll()

    @property
    def _ready(self) -> bool:
        return self.tool == NVIDIA_SMI or self._settings_index is not None

    # -- polling -------------------------------------------------------------------------

    def _run(self, argv, handler) -> None:
        generation = self._generation
        self._busy = True

        def done(rc: int, out: str, err: str) -> None:
            if generation != self._generation or not self._running:
                return                            # stopped or restarted meanwhile
            self._busy = False
            handler(rc, out, err)
        self.system.run_async(argv, done)

    def _poll(self) -> None:
        if self.tool == NVIDIA_SMI:
            self._run(smi_argv(self.system.which(NVIDIA_SMI), self.gpu.pci_slot),
                      lambda *r: self._on_reading(parse_smi, *r))
        else:
            self._run(settings_argv(self.system.which(NVIDIA_SETTINGS), self._settings_index),
                      lambda *r: self._on_reading(parse_settings, *r))

    def _on_targets(self, rc: int, out: str, err: str) -> None:
        try:
            targets = parse_settings_targets(rc, out, err)
        except NvidiaError as exc:
            self._use_smi(UNREACHABLE, str(exc))
            return
        index = targets.get(self.gpu.pci_slot)
        if index is None:
            self._use_smi("nvidia-settings doesn't list this GPU")
            return
        self._settings_index = index
        self.source_note = f"nvidia-settings, GPU {index}"
        self._poll()

    def _use_smi(self, why: str, detail: str = "") -> None:
        """Switch to nvidia-smi; ``why`` is shown, ``detail`` (the tool's own
        words) only logged."""
        if not self.system.which(NVIDIA_SMI):
            self._fail(f"{why}, and nvidia-smi isn't installed" + (f" ({detail})" if detail
                                                                    else ""))
            return
        log.info("%s: %s%s; using nvidia-smi", self.gpu.pci_slot, why,
                 f" ({detail})" if detail else "")
        self.tool = NVIDIA_SMI
        self.source_note = f"nvidia-smi ({why})"
        self._poll()

    def _on_reading(self, parse, rc: int, out: str, err: str) -> None:
        try:
            sample = parse(rc, out, err)
        except NvidiaError as exc:
            if self.tool == NVIDIA_SETTINGS and exc.unreachable:
                self._use_smi(UNREACHABLE, str(exc))
                return
            self._misses += 1
            log.debug("%s: %s reading failed (%d): %s", self.gpu.pci_slot, self.tool,
                      self._misses, exc)
            if self.sample is None or self._misses >= MAX_MISSES:
                self._fail(f"{self.tool} couldn't read this GPU: {exc}")
            return
        self._misses = 0
        self.sample = sample
        self.history.add(self._now, sample.history_values(), HISTORY_UNITS)
        self.emit("updated")

    def _fail(self, reason: str) -> None:
        self.stop()
        self.emit("failed", reason, False)

    # -- data ----------------------------------------------------------------------------

    def summary(self) -> GpuSummary:
        return self.sample.to_summary() if self.sample else GpuSummary()

    def has_data(self) -> bool:
        return self.sample is not None

    def create_views(self, controller, services):
        from .views import create_views
        return create_views(self, controller, services)
