"""The GPU backend interface.

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
from ..core.units import format_frequency
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
    factory): preferences, the app icon of a PID (None: no icon), and
    ``charts`` (``ui.chart_settings.ChartSettings``): where every graph
    gets its preferences, units and the GPU entry's color. The
    GPU page makes a new one for each set of views and releases it with
    them."""
    settings: object
    app_icon: Callable[[int], object] = lambda pid: None
    charts: object = None


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


def frequency_text(hz: Optional[float]) -> Optional[str]:
    """A GPU clock for display: None when there's no reading, "Idle" for
    0 Hz (an Intel GT asleep reads 0 MHz: a reading, not a missing one)."""
    if hz is None:
        return None
    return "Idle" if hz == 0 else format_frequency(hz)


@dataclass
class GpuSummary:
    """The Resources-level view of a GPU, whatever the backend."""
    usage: Optional[float] = None           # percent
    encode: Optional[float] = None          # percent
    decode: Optional[float] = None          # percent
    combined_video: bool = False            # encode and decode share one engine
    vram_used: Optional[int] = None         # bytes
    vram_total: Optional[int] = None
    # amdgpu's GTT: system memory the GPU has mapped (bytes).
    gtt_used: Optional[int] = None
    gtt_total: Optional[int] = None
    # An APU: its "VRAM" is a carve-out of system memory and it
    # uses GTT as much, so its graphics memory is both together.
    shared_memory: bool = False
    frequency_hz: Optional[float] = None
    vram_frequency_hz: Optional[float] = None
    power_w: Optional[float] = None
    power_cap_w: Optional[float] = None
    # ``power_w`` is the whole processor package's (an APU's PPT),
    # not the GPU's own.
    power_is_package: bool = False
    temperature_c: Optional[float] = None

    @property
    def memory_used(self) -> Optional[int]:
        """The GPU's memory in use: VRAM, plus GTT on an APU."""
        if self.shared_memory and self.gtt_used is not None:
            return (self.vram_used or 0) + self.gtt_used
        return self.vram_used

    @property
    def memory_total(self) -> Optional[int]:
        if self.shared_memory and self.gtt_total:
            return (self.vram_total or 0) + self.gtt_total
        return self.vram_total

    @property
    def memory_usage(self) -> Optional[float]:
        """``memory_used`` as a percentage of ``memory_total``."""
        used, total = self.memory_used, self.memory_total
        if used is None or not total:
            return None
        return 100.0 * used / total


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
    # in a way that stops them with Proccoli.
    helper: object = None
    # One GPU's fdinfo readers, shared by its summary and detail backends
    # so each update reads /proc/*/fdinfo once (fdinfo.shared_reader()).
    fdinfo: dict = field(default_factory=dict, compare=False, hash=False)


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

    # The history database (history follow-ups): what the Details tab
    # graphs, recorded with the GPU's readings, and the history to fill
    # from them again. None / empty: nothing to record or fill.

    def history_readings(self) -> tuple[dict, dict]:
        """``({key: latest value}, {key: unit})``, base units."""
        return {}, {}

    def history_target(self):
        """The Details tab's history (``room()``, ``times``, ``keys()``,
        ``step_s``, ``WALL_TIMES``, ``backfill(times, values)``), or None."""
        return None
