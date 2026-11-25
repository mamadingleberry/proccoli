"""Lightweight mode: what Proccoli builds and
how, as a ``Profile`` chosen once at start-up.

``Profile.full()`` is Proccoli as usual; ``Profile.lightweight()`` keeps
memory low while still showing every device's usage and the process list:

- **What isn't built** (flags the composition root and the window read):
  pages are built on first visit and dropped ``page_drop_s`` after leaving
  them (``lazy_pages``), the Overview is a list of cards with the small
  sidebar-style chart (``overview_chart``) and the five busiest
  apps and processes without icons, no graph toolbar (its settings are
  pinned anyway), no app or process icons anywhere, GPU
  detail sources aren't started, pci.ids is looked up on demand instead
  of parsed whole, and no theme CSS provider. The sidebar is pinned to
  icons only (or hidden), so its meters are never built.
- **What's pinned** (``pins``): preferences that cost memory or drawing
  take a fixed value while the mode is on, whatever the user chose; the
  choice is kept and comes back when the mode is off. ``ProfileSettings``
  is the settings everything reads: the same store, with pinned keys
  answered by the profile (also in change notifications), so pages,
  graphs, the theme and the log follow without knowing about the mode.
  Preferences greys pinned rows out.

The profile applies at the next start (``lightweight`` setting or
``--lightweight``); Preferences offers *Restart Now*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .settings import Settings
from .ticker import CUSTOM, CUSTOM_KEY, TIME_RANGES_S

# Log levels from the most to the least detailed (applog's nicks).
_LOG_ORDER = ("debug", "info", "warning", "error", "off")


def _at_most_one_minute(nick: str) -> str:
    """A preset over a minute reads as 1 minute; a custom range stays
    custom, capped by its own pin below."""
    return nick if nick == CUSTOM or TIME_RANGES_S.get(nick, 61) <= 60 else "1-minute"


def _at_most_warnings(nick: str) -> str:
    order = {n: i for i, n in enumerate(_LOG_ORDER)}
    return nick if order.get(nick, 0) >= order["warning"] else "warning"


# Table columns kept in Lightweight Mode: every other column is a cell per
# row (hundreds of rows on Processes), so they go.
_ESSENTIAL_COLUMNS = ("id", "cpu", "memory")
_COLUMNS = ("combined-memory", "cpu", "decoder", "drive-read-speed", "drive-read-total",
            "drive-write-speed", "drive-write-total", "encoder", "gpu", "gpu-memory",
            "memory", "swap", "commandline", "id", "priority", "system-cpu-time",
            "total-cpu-time", "user", "user-cpu-time")


_PROCESS_ONLY = ("commandline", "priority", "system-cpu-time", "total-cpu-time", "user",
                 "user-cpu-time")


def _column_pin(column: str) -> Callable[[Any], Any]:
    if column in _ESSENTIAL_COLUMNS:
        return lambda value: value                   # the user's choice
    return lambda _value: False


LIGHTWEIGHT_PINS: Mapping[str, Callable[[Any], Any]] = {
    "graph-time-range": _at_most_one_minute,     # short histories
    CUSTOM_KEY: lambda seconds: min(seconds, 60),
    "show-graph-axes": lambda _v: False,
    "show-graph-grids": lambda _v: False,
    "show-logical-cpus": lambda _v: False,        # no per-CPU chart and legend
    "sidebar-style": lambda _v: "icons",          # the Overview has the charts
    "color-scheme": lambda _v: "system",          # no tinted styles
    "palette": lambda _v: "system",
    "log-level": _at_most_warnings,
    "log-performance-interval": lambda _v: 0,
    **{f"{table}-show-{column}": _column_pin(column)
       for table in ("apps", "processes") for column in _COLUMNS
       if column not in _ESSENTIAL_COLUMNS
       and (table == "processes" or column not in _PROCESS_ONLY)},
}


@dataclass(frozen=True)
class Profile:
    name: str = "full"
    lazy_pages: bool = False          # build pages on first visit, drop them later
    page_drop_s: int = 60             # seconds after leaving a lazy page
    # The Overview cards' chart: "full" (with axes, fitted to the page) or
    # "small" (the sidebar's).
    overview_chart: str = "full"
    overview_tables: bool = True      # the busiest apps and processes
    overview_top_count: int = 10      # rows in each of those tables
    extra_graphs: bool = True         # device pages: every graph, or only the first
    graph_toolbar: bool = True        # the toolbar under page headers
    app_icons: bool = True
    gpu_details: bool = True          # start GPU detail sources (intel_gpu_top, NVIDIA)
    pci_on_demand: bool = False
    theme_css: bool = True            # palette CSS provider
    keep_process_data: bool = True    # the process list while nobody shows it
    # The background collector: no window, so nobody to ask for
    # a password; detail sources that need one stay off.
    gpu_elevate: bool = True
    # GTK's renderer ("" = GTK's choice). Lightweight Mode draws with Cairo:
    # OpenGL's driver memory costs the same whatever the window shows.
    renderer: str = ""
    pins: Mapping[str, Callable[[Any], Any]] = field(default_factory=dict)

    @classmethod
    def full(cls) -> "Profile":
        return cls()

    @classmethod
    def lightweight(cls) -> "Profile":
        return cls(name="lightweight", lazy_pages=True, overview_chart="small",
                   overview_tables=True, overview_top_count=5, extra_graphs=False,
                   graph_toolbar=False,
                   app_icons=False,
                   gpu_details=False, pci_on_demand=True, theme_css=False,
                   keep_process_data=False, renderer="cairo",
                   pins=LIGHTWEIGHT_PINS)

    @classmethod
    def metrics(cls) -> "Profile":
        """``proccoli``: device readings for the history,
        no UI, never elevated, the user's real settings (no pins)."""
        return cls(name="metrics", lazy_pages=False, overview_tables=False,
                   extra_graphs=False, app_icons=False, graph_toolbar=False,
                   pci_on_demand=True, theme_css=False, keep_process_data=False,
                   gpu_elevate=False)

    @property
    def is_lightweight(self) -> bool:
        return self.name == "lightweight"


RENDERER_ENV = "GSK_RENDERER"
OURS_ENV = "PROCCOLI_SET_GSK_RENDERER"    # marks a renderer Proccoli chose itself


def apply_renderer(profile: Profile, env) -> str:
    """Set GTK's renderer for ``profile`` in ``env`` (``os.environ``) before
    any window is shown; returns the one in effect ("" = GTK's choice). A
    ``GSK_RENDERER`` the user set is left alone; one Proccoli set (and that
    *Restart Now* carried over) goes when the profile has none."""
    ours = env.get(OURS_ENV) == "1"
    if RENDERER_ENV in env and not ours:
        return env[RENDERER_ENV]                  # the user's choice
    if profile.renderer:
        env[RENDERER_ENV], env[OURS_ENV] = profile.renderer, "1"
        return profile.renderer
    if ours:
        env.pop(RENDERER_ENV, None)
        env.pop(OURS_ENV, None)
    return ""


def choose_profile(settings, flag: bool = False) -> Profile:
    """``--lightweight`` or the ``lightweight`` setting."""
    return Profile.lightweight() if flag or settings.get("lightweight") else Profile.full()


class ProfileSettings(Settings):
    """``settings`` as seen under ``profile``: the same store (so changes
    persist and notify as usual), with pinned keys answered by the
    profile."""

    def __init__(self, settings: Settings, profile: Profile) -> None:
        super().__init__(settings.spec, settings._store)
        self.base = settings
        self.profile = profile

    def is_pinned(self, key: str) -> bool:
        return key in self.profile.pins

    def get(self, key: str) -> Any:
        value = super().get(key)
        pin = self.profile.pins.get(key)
        return value if pin is None else pin(value)

    def bind(self, key: str, obj, prop: str) -> None:
        if self.is_pinned(key):
            obj.set_property(prop, self.get(key))      # shown, not changeable
            return
        super().bind(key, obj, prop)


def profile_settings(settings: Settings, profile: Profile):
    """The settings to hand out: ``settings`` itself for the full profile
    (any other carries its profile, even without pins)."""
    if not profile.pins and profile.name == "full":
        return settings
    return ProfileSettings(settings, profile)


def is_pinned(settings, key: str) -> bool:
    """True when ``key`` is fixed by the running profile."""
    check = getattr(settings, "is_pinned", None)
    return bool(check and check(key))


def profile_of(settings) -> Profile:
    """The running profile (full unless ``settings`` carries one)."""
    return getattr(settings, "profile", None) or Profile.full()
