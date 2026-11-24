"""Which GPU backends exist, and which suit a given GPU."""

from __future__ import annotations

from typing import Optional

from .backend import BackendRole, GpuBackend, GpuDeps, Probe, SupportLevel
from .info import GpuInfo


class GpuBackendRegistry:
    def __init__(self, classes: tuple[type[GpuBackend], ...] = ()) -> None:
        self._classes: list[type[GpuBackend]] = []
        for cls in classes:
            self.register(cls)

    def register(self, cls: type[GpuBackend]) -> None:
        """Earlier registrations win ties between equal support levels."""
        self._classes.append(cls)

    def classes(self) -> list[type[GpuBackend]]:
        return list(self._classes)

    def by_id(self, backend_id: str) -> Optional[type[GpuBackend]]:
        return next((c for c in self._classes if c.id == backend_id), None)

    def best(self, gpu: GpuInfo, deps: GpuDeps,
             role: BackendRole) -> Optional[tuple[type[GpuBackend], Probe]]:
        """The best backend of ``role`` for ``gpu`` (and its probe), or None."""
        return next(((c, p) for c, p in self.candidates(gpu, deps) if c.role == role), None)

    def candidates(self, gpu: GpuInfo, deps: GpuDeps) -> list[tuple[type[GpuBackend], Probe]]:
        """Backends that can serve ``gpu``, best first."""
        probed = []
        for order, cls in enumerate(self._classes):
            probe = cls.probe(gpu, deps)
            if probe.level > SupportLevel.UNSUPPORTED:
                probed.append((order, cls, probe))
        probed.sort(key=lambda t: (-t[2].level, t[0]))
        return [(cls, probe) for _, cls, probe in probed]


def standard_registry() -> GpuBackendRegistry:
    """Every real backend, most detailed first. (NVIDIA and AMD backends
    register here when they exist: DESIGN.md §7, PLAN.md Milestone 16.)"""
    from .generic_drm import GenericDrmBackend
    from .intel_gpu_top.backend import IntelGpuTopBackend

    return GpuBackendRegistry((IntelGpuTopBackend, GenericDrmBackend))
