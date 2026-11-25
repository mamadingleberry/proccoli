"""Which panel each GPU gets, and why.

``plan_gpu`` asks every registered backend how well it can serve a GPU
(``probe``) and records the answer, chosen or not:

- the **summary** source (always running) feeds the Overview tab, the
  sidebar and the process columns;
- the best **detail** source, if any, adds its own tabs (Intel:
  intel_gpu_top; NVIDIA: nvidia-settings or nvidia-smi).

The plan is logged when the GPU is found, shown on the GPU page (*Detailed
Statistics* property) and, when no source can serve the GPU at all, becomes
the message of that GPU's error page. Pure: no display, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .backend import BackendRole, GpuBackend, GpuDeps, Probe, SupportLevel
from .info import GpuInfo

VENDOR_NAMES = {"INTEL": "Intel", "AMD": "AMD", "NVIDIA": "NVIDIA", "OTHER": "Other"}


@dataclass(frozen=True)
class Candidate:
    backend: type[GpuBackend]
    probe: Probe

    @property
    def usable(self) -> bool:
        return self.probe.level > SupportLevel.UNSUPPORTED


@dataclass(frozen=True)
class GpuPlan:
    gpu: GpuInfo
    summary: Optional[Candidate]
    detail: Optional[Candidate]
    candidates: tuple[Candidate, ...] = field(default_factory=tuple)

    @property
    def vendor(self) -> str:
        return VENDOR_NAMES.get(self.gpu.vendor.name, self.gpu.vendor.name.title())

    @property
    def usable(self) -> bool:
        """At least a summary source: the GPU gets its page."""
        return self.summary is not None

    def panel(self) -> str:
        """What the GPU page shows, in words."""
        if self.summary is None:
            return "error page"
        if self.detail is None:
            return "overview only"
        return f"overview + {self.detail.backend.display_name} tabs"

    def detail_text(self) -> str:
        """For the page's *Detailed Statistics* property."""
        if self.detail is not None:
            reason = self.detail.probe.reason
            return self.detail.backend.display_name + (f" ({reason})" if reason else "")
        skipped = [c for c in self.candidates
                   if c.backend.role == BackendRole.DETAIL and c.probe.reason]
        # The vendor's own tool says most about why there's nothing.
        return "None" + (f": {skipped[0].probe.reason}" if skipped else "")

    def explain(self) -> str:
        """One line per backend: chosen, or why not (for the log and the
        error page)."""
        lines = [f"{self.vendor} GPU {self.gpu.pci_slot} (driver {self.gpu.driver or 'none'}): "
                 f"{self.panel()}"]
        for c in self.candidates:
            # Nothing is used when the GPU gets the error page.
            chosen = self.usable and c in (self.summary, self.detail)
            mark = "chosen" if chosen else ("usable" if c.usable else "not usable")
            reason = f": {c.probe.reason}" if c.probe.reason else ""
            lines.append(f"  {c.backend.id} ({c.backend.role.value}) {mark}{reason}")
        return "\n".join(lines)


def plan_gpu(gpu: GpuInfo, registry, deps: GpuDeps) -> GpuPlan:
    """Probe every backend for ``gpu`` and pick the best of each role."""
    candidates = tuple(Candidate(cls, probe) for cls, probe in registry.probe_all(gpu, deps))
    usable = sorted((c for c in candidates if c.usable),
                    key=lambda c: -c.probe.level)        # stable: registration order on ties

    def best(role):
        return next((c for c in usable if c.backend.role == role), None)
    return GpuPlan(gpu, best(BackendRole.SUMMARY), best(BackendRole.DETAIL), candidates)
