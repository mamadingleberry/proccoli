"""Per-process GPU usage from DRM fdinfo (/proc/<pid>/fdinfo/<fd>).

Every DRM client reports cumulative busy time per engine
("drm-engine-render: 123 ns") and its memory per region. Usage is the
change in busy time over the change in wall time. Only processes we may
inspect are visible (our own, or all when running privileged).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..core.sysroot import SysRoot
from .backend import GpuProcessUsage

# Engine names that do video work, per driver family.
DECODE_ENGINES = {"video", "dec", "vcn", "video-decode", "jpeg", "nvdec"}
ENCODE_ENGINES = {"video", "enc", "enc_1", "vcn", "video-encode", "nvenc"}
VIDEO_ENGINES = DECODE_ENGINES | ENCODE_ENGINES | {"video-enhance", "vecs"}
# Memory regions that are dedicated video memory (not shared system RAM).
VRAM_REGIONS = ("vram", "local")
# amdgpu's system memory mapped for the GPU: an APU's graphics memory too.
GTT_REGIONS = ("gtt",)

_UNITS = {"B": 1, "KiB": 2 ** 10, "MiB": 2 ** 20, "GiB": 2 ** 30}


@dataclass
class DrmClient:
    pid: int
    pdev: str
    engines_ns: dict[str, int] = field(default_factory=dict)
    capacity: dict[str, int] = field(default_factory=dict)
    vram: int = 0


def _bytes(value: str) -> int:
    n, _, unit = value.partition(" ")
    return int(n) * _UNITS.get(unit.strip() or "B", 1)


def parse_fdinfo(text: str, pid: int,
                 regions: tuple[str, ...] = VRAM_REGIONS) -> Optional[tuple[str, DrmClient]]:
    """(client id, client) for a DRM fdinfo file, or None for other fds.
    ``vram`` adds up the memory ``regions`` (an APU's include GTT)."""
    fields = {}
    for line in text.splitlines():
        k, _, v = line.partition(":")
        fields[k.strip()] = v.strip()
    if "drm-driver" not in fields or "drm-client-id" not in fields:
        return None
    client = DrmClient(pid, fields.get("drm-pdev", ""))
    total: dict[str, int] = {}
    legacy: dict[str, int] = {}
    for k, v in fields.items():
        if k.startswith("drm-engine-capacity-"):
            client.capacity[k[len("drm-engine-capacity-"):]] = int(v or 1)
        elif k.startswith("drm-engine-") and v.endswith("ns"):
            client.engines_ns[k[len("drm-engine-"):]] = int(v.split()[0])
        elif k.startswith(("drm-total-", "drm-memory-")):
            region = k.split("-", 2)[2]
            if region.startswith(regions):
                (total if k.startswith("drm-total-") else legacy)[region] = _bytes(v)
    # amdgpu reports each region twice: "drm-total-vram" and the older
    # "drm-memory-vram" (resident). Count each region once,
    # preferring the total, as i915 and xe report.
    client.vram = sum({**legacy, **total}.values())
    return fields["drm-client-id"], client


def shared_reader(deps, pci_slot: str, shared_memory: bool = False) -> "FdinfoReader":
    """The GPU's one reader: the summary backend and a detail
    backend (amdgpu) both use it, and it reads once per update."""
    key = (pci_slot, shared_memory)
    reader = deps.fdinfo.get(key)
    if reader is None:
        reader = deps.fdinfo[key] = FdinfoReader(deps.sysroot, pci_slot, shared_memory)
    return reader


class FdinfoReader:
    """Tracks the DRM clients of one GPU and turns their counters into
    per-process and per-engine usage. Reading again at the same ``now``
    does nothing, so several backends can share one."""

    # Reads between full scans of every process's fds (the expensive part:
    # a readlink per open file). New GPU clients appear within this many ticks.
    FD_RESCAN_EVERY = 10

    def __init__(self, sysroot: SysRoot, pci_slot: str, shared_memory: bool = False) -> None:
        """``shared_memory``: an APU, whose clients' GTT counts as their
        graphics memory too."""
        self.sysroot = sysroot
        self.pci_slot = pci_slot
        self.regions = VRAM_REGIONS + GTT_REGIONS if shared_memory else VRAM_REGIONS
        self._drm_fds: dict[int, list[str]] = {}    # pid -> fds pointing at /dev/dri
        self._reads = 0
        self._prev: Optional[tuple[float, dict[str, DrmClient]]] = None
        self.processes: dict[int, GpuProcessUsage] = {}
        self.engines: dict[str, float] = {}          # engine -> percent, all clients

    def _scan_fds(self) -> None:
        found = {}
        for entry in self.sysroot.listdir("/proc"):
            if not entry.isdigit():
                continue
            fds = [fd for fd in self.sysroot.listdir(f"/proc/{entry}/fd")
                   if (self.sysroot.readlink(f"/proc/{entry}/fd/{fd}") or "")
                   .startswith("/dev/dri/")]
            if fds:
                found[int(entry)] = fds
        self._drm_fds = found

    def _clients(self) -> dict[str, DrmClient]:
        clients: dict[str, DrmClient] = {}
        for pid in sorted(self._drm_fds):
            for fd in self._drm_fds[pid]:
                text = self.sysroot.read_text(f"/proc/{pid}/fdinfo/{fd}")
                parsed = parse_fdinfo(text, pid, self.regions) if text else None
                if parsed is None:
                    continue
                cid, client = parsed
                # A client shared by several fds or processes counts once,
                # for the lowest pid.
                if client.pdev == self.pci_slot and cid not in clients:
                    clients[cid] = client
        return clients

    def read(self, now: float) -> None:
        if self._prev is not None and self._prev[0] == now:
            return                          # already read this update
        if self._reads % self.FD_RESCAN_EVERY == 0:
            self._scan_fds()
        self._reads += 1
        clients = self._clients()
        prev, self._prev = self._prev, (now, clients)
        processes: dict[int, GpuProcessUsage] = {}
        engines: dict[str, float] = {}
        dt_ns = (now - prev[0]) * 1e9 if prev else 0
        for cid, client in clients.items():
            usage = processes.setdefault(client.pid, GpuProcessUsage(client.pid))
            usage.vram += client.vram
            old = prev[1].get(cid) if prev and dt_ns > 0 else None
            if old is None:
                continue
            per_engine = {}
            for engine, ns in client.engines_ns.items():
                delta = ns - old.engines_ns.get(engine, ns)
                cap = client.capacity.get(engine, 1) or 1
                pct = min(max(100.0 * delta / dt_ns / cap, 0.0), 100.0)
                per_engine[engine] = pct
                engines[engine] = min(engines.get(engine, 0.0) + pct, 100.0)
            compute = [v for e, v in per_engine.items() if e not in VIDEO_ENGINES]
            usage.usage = min(usage.usage + max(compute, default=0.0), 100.0)
            usage.decode = min(usage.decode + max((v for e, v in per_engine.items()
                                                   if e in DECODE_ENGINES), default=0.0), 100.0)
            usage.encode = min(usage.encode + max((v for e, v in per_engine.items()
                                                   if e in ENCODE_ENGINES), default=0.0), 100.0)
        self.processes = processes
        self.engines = engines if prev else {}
