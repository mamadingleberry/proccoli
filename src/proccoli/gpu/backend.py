"""The GPU backend interface (DESIGN.md §7.1).

Every GPU has a SUMMARY source (always running; feeds the Overview tab, the
sidebar and the process columns) and optionally a DETAIL source: a vendor
tool that adds its own tabs (Details, Processes) to the GPU page.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum, IntFlag
from typing import Callable, Optional

from gi.repository import GObject

from ..core.sysroot import SysRoot
from .info import GpuInfo


class BackendRole(Enum):
    SUMMARY = "summary"    # any GPU, cheap, unprivileged: always running
    DETAIL = "detail"      # a vendor tool: optional, may need privileges


@dataclass(frozen=True)
class TabSpec:
    """A tab a detail source adds to the GPU page (fixed per backend class,
    so the tab switcher doesn't change as the source starts and stops)."""
    name: str
    title: str
    icon_name: str


@dataclass
class DetailView:
    """A built tab: its content and the header buttons it wants shown while
    it's visible."""
    name: str
    widget: object                       # Gtk.Widget
    header_widgets: list = field(default_factory=list)


@dataclass(frozen=True)
class DetailServices:
    """What a detail backend's views may use (injected by the page
    factory): preferences, and the app icon of a PID (None: no icon)."""
    settings: object
    app_icon: Callable[[int], object] = lambda pid: None


@dataclass
class DetailViews:
    """What ``DetailBackend.create_views()`` returns: one view per tab, and
    the backend signal connections that feed them (the page disconnects
    them when it drops the views)."""
    views: list
    handlers: list = field(default_factory=list)


class SupportLevel(IntEnum):
    UNSUPPORTED = 0
    FALLBACK = 1      # works for any GPU, with less detail
    SUPPORTED = 2
    PREFERRED = 3     # the most detailed source for this GPU


@dataclass(frozen=True)
class Probe:
    level: SupportLevel
    reason: str = ""
    needs_elevation: bool = False   # works only with administrator rights


class Capability(IntFlag):
    SUMMARY = 1
    PER_PROCESS = 2
    PER_ENGINE = 4
    POWER = 8
    TEMPERATURE = 16
    VRAM = 32
    EXPORT = 64


@dataclass
class GpuSummary:
    """The Resources-level view of a GPU, whatever the backend."""
    usage: Optional[float] = None           # percent
    encode: Optional[float] = None          # percent
    decode: Optional[float] = None          # percent
    combined_video: bool = False            # encode and decode share one engine
    vram_used: Optional[int] = None         # bytes
    vram_total: Optional[int] = None
    frequency_hz: Optional[float] = None
    vram_frequency_hz: Optional[float] = None
    power_w: Optional[float] = None
    power_cap_w: Optional[float] = None
    temperature_c: Optional[float] = None

    @property
    def vram_usage(self) -> Optional[float]:
        if self.vram_used is None or not self.vram_total:
            return None
        return 100.0 * self.vram_used / self.vram_total


@dataclass
class GpuProcessUsage:
    pid: int
    usage: float = 0.0       # percent of the busiest non-video engine
    encode: float = 0.0
    decode: float = 0.0
    vram: int = 0            # bytes

    def merge(self, other: "GpuProcessUsage") -> None:
        self.usage += other.usage
        self.encode += other.encode
        self.decode += other.decode
        self.vram += other.vram


@dataclass(frozen=True)
class GpuDeps:
    """What a backend may use: kernel files, preferences and OS services."""
    sysroot: SysRoot
    settings: object
    system: object          # core.system.System
    # core.privileged.PrivilegedHelper, or None: runs vendor tools as root
    # in a way that stops them with Proccoli (DESIGN.md §11.1).
    helper: object = None


class GpuBackend(GObject.Object):
    """Collects data for one GPU.

    Pull-based backends read sysfs in ``refresh(now)``; streaming backends
    (intel_gpu_top) keep the latest record from their stream. Either way
    ``summary()`` and ``process_usage()`` return the latest values.
    """

    __gsignals__ = {
        "updated": (GObject.SignalFlags.RUN_FIRST, None, ()),
        # (reason, can_elevate): the backend stopped working.
        "failed": (GObject.SignalFlags.RUN_FIRST, None, (str, bool)),
    }

    id = ""
    display_name = ""
    role = BackendRole.SUMMARY
    capabilities = Capability.SUMMARY

    def __init__(self, gpu: GpuInfo, deps: GpuDeps) -> None:
        super().__init__()
        self.gpu = gpu
        self.deps = deps
        self.sysroot = deps.sysroot
        self.settings = deps.settings
        self.elevated = False

    @classmethod
    def probe(cls, gpu: GpuInfo, deps: GpuDeps) -> Probe:
        """How well this backend can serve ``gpu`` (pure: no side effects)."""
        raise NotImplementedError

    def start(self, elevate: bool = False) -> None:
        self.elevated = elevate

    def stop(self) -> None:
        pass

    def refresh(self, now: float) -> None:
        pass

    def summary(self) -> GpuSummary:
        raise NotImplementedError

    def has_data(self) -> bool:
        """Whether summary() reflects real readings yet."""
        return True

    def process_usage(self) -> dict[int, GpuProcessUsage]:
        return {}


class DetailBackend(GpuBackend):
    """A vendor tool: adds ``TABS`` to the GPU page and builds their views
    once it's running."""
    role = BackendRole.DETAIL
    TABS: tuple[TabSpec, ...] = ()

    def create_views(self, controller, services: DetailServices) -> DetailViews:
        """One DetailView per TabSpec (UI code: imported lazily)."""
        raise NotImplementedError
