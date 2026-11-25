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

    def probe_all(self, gpu: GpuInfo, deps: GpuDeps) -> list[tuple[type[GpuBackend], Probe]]:
        """Every backend's probe for ``gpu``, in registration order, the
        unsupported ones too (their reasons explain the choice:
        ``detect.plan_gpu()``)."""
        return [(cls, cls.probe(gpu, deps)) for cls in self._classes]

    def candidates(self, gpu: GpuInfo, deps: GpuDeps) -> list[tuple[type[GpuBackend], Probe]]:
        """Backends that can serve ``gpu``, best first."""
        probed = [(order, cls, probe)
                  for order, (cls, probe) in enumerate(self.probe_all(gpu, deps))
                  if probe.level > SupportLevel.UNSUPPORTED]
        probed.sort(key=lambda t: (-t[2].level, t[0]))
        return [(cls, probe) for _, cls, probe in probed]


def standard_registry() -> GpuBackendRegistry:
    """Every real backend, most detailed first."""
    from .amdgpu.backend import AmdgpuBackend
    from .generic_drm import GenericDrmBackend
    from .intel_gpu_top.backend import IntelGpuTopBackend
    from .nvidia.backend import NvidiaBackend

    return GpuBackendRegistry((IntelGpuTopBackend, NvidiaBackend, AmdgpuBackend,
                               GenericDrmBackend))
