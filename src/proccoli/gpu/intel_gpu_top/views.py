"""The Intel detail tabs: intel_gpu_top_gui's interface inside the GPU page.

- Details: the device caption and the adaptive grid of graph sections
  (engines, frequency, power, RC6, memory bandwidth, interrupts), compact on
  small sizes.
- Processes: per-client engine-class utilisation.
- Header (both tabs): pause, and the menu with Update Interval, History
  Length, Export as CSV and Clear History.
"""

from __future__ import annotations

import os
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from ..backend import DetailView, DetailViews  # noqa: E402
from .backend import HISTORY_LENGTHS  # noqa: E402
from .clients import ClientsView  # noqa: E402
from .graph import AxisGroup, GraphSection  # noqa: E402
from .grid import GraphGrid  # noqa: E402

# group -> (title, subtitle, relative graph height, fixed y max or None)
GROUPS = {
    "engines": ("Engine Utilization", "Busy time of each GPU engine", 200, 100.0),
    "frequency": ("Frequency", "Requested and actual GPU clock", 140, None),
    "power": ("Power", "GPU and package power draw", 140, None),
    "rc6": ("RC6 Residency", "Share of time the GPU spent in its idle power state", 110, 100.0),
    "imc-bandwidth": ("Memory Bandwidth", "Integrated memory controller traffic", 140, None),
    "interrupts": ("Interrupts", "GPU interrupts per second", 110, None),
}
GROUP_ORDER = list(GROUPS)

# The Update Interval and History Length menus (intel_gpu_top_gui's choices;
# intervals are refresh-speed nicks, "" follows the app's refresh speed).
INTERVALS = [("very-fast", "0.25 Seconds"), ("fast", "0.5 Seconds"), ("normal", "1 Second"),
             ("slow", "2 Seconds"), ("very-slow", "4 Seconds"), ("", "Same as Refresh Speed")]
HISTORY_S = HISTORY_LENGTHS

COMPACT_CONDITIONS = ("max-height: 720sp", "max-width: 600sp")


def group_meta(group: str, unit: str):
    """(title, subtitle, height, fixed max), also for per-GT and unknown groups."""
    base = group.split("-gt")[0] if "-gt" in group else group
    if base in GROUPS:
        title, sub, h, fixed = GROUPS[base]
        if base != group:
            title = f"{title} ({group[len(base) + 1:].upper()})"
        return title, sub, h, fixed
    title = group.replace("-", " ").replace("_", " ").title()
    return title, "", 130, (100.0 if unit == "%" else None)


def group_rank(group: str):
    base = group.split("-gt")[0]
    return (GROUP_ORDER.index(base) if base in GROUP_ORDER else len(GROUP_ORDER), group)


def caption_text(backend) -> str:
    parts = [backend.gpu.name, f"updated every {backend.interval_ms / 1000:g} s"]
    if backend.elevated:
        parts.append("running as administrator")
    return " · ".join(parts)


class IntelGraphsView(Adw.BreakpointBin):
    """intel_gpu_top_gui's Resources tab."""

    def __init__(self, backend) -> None:
        super().__init__(width_request=320, height_request=200)
        self.backend = backend
        self.sections: dict[str, GraphSection] = {}
        self.axis_group = AxisGroup()
        self.compact = False

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                           margin_top=6, margin_bottom=18, margin_start=12, margin_end=18)
        self.caption = Gtk.Label(xalign=0, margin_top=6)
        for cls in ("dim-label", "caption", "device-caption"):
            self.caption.add_css_class(cls)
        self.box.append(self.caption)
        self.grid = GraphGrid()
        self.box.append(self.grid)
        self.waiting = Adw.StatusPage(title="Waiting for intel_gpu_top…",
                                      icon_name="power-profile-performance-symbolic",
                                      vexpand=True)
        self.box.append(self.waiting)
        self.set_child(Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                          child=self.box))
        for cond in COMPACT_CONDITIONS:
            bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse(cond))
            bp.connect("apply", lambda *_: self.set_compact(True))
            bp.connect("unapply", lambda *_: self.set_compact(False))
            self.add_breakpoint(bp)
        self.refresh()

    def set_compact(self, compact: bool) -> None:
        if compact == self.compact:
            return
        self.compact = compact
        if compact:
            self.box.add_css_class("compact")
        else:
            self.box.remove_css_class("compact")
        self.caption.set_visible(not compact)
        self.box.set_margin_start(6 if compact else 12)
        self.box.set_margin_end(6 if compact else 18)
        for sec in self.sections.values():
            sec.set_compact(compact)

    def _add_section(self, group: str) -> None:
        series = self.backend.history.group_series(group)
        unit = series[0].unit if series else ""
        title, sub, height, fixed = group_meta(group, unit)
        sec = GraphSection(self.backend.history, group, title, unit, fixed, height, sub,
                           self.axis_group)
        sec.set_compact(self.compact)
        self.sections[group] = sec
        self.grid.set_sections([self.sections[g] for g in sorted(self.sections,
                                                                 key=group_rank)])

    def refresh(self) -> None:
        history = self.backend.history
        for group in history.group_order:
            if group not in self.sections:
                self._add_section(group)
        interval = self.backend.interval_ms / 1000
        for sec in self.sections.values():
            sec.set_interval(interval)
        self.caption.set_label(caption_text(self.backend))
        has_data = bool(history.times)
        self.grid.set_visible(has_data)
        self.waiting.set_visible(not has_data)
        if self.get_mapped():
            for sec in self.sections.values():
                sec.refresh()

    def do_map(self) -> None:
        Adw.BreakpointBin.do_map(self)
        for sec in self.sections.values():
            sec.refresh()


class IntelClientsView(Gtk.Box):
    """intel_gpu_top_gui's Processes tab, with app icons."""

    def __init__(self, backend, app_icon=None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.backend = backend
        self.table = ClientsView(app_icon)
        self.table.set_vexpand(True)
        self.append(self.table)
        self.refresh()

    def refresh(self) -> None:
        if self.get_mapped() or not self.table.rows:
            self.table.update((self.backend.latest or {}).get("clients"))

    def do_map(self) -> None:
        Gtk.Box.do_map(self)
        self.refresh()


class IntelDetailHeader:
    """Pause and the menu: shared by both tabs."""

    def __init__(self, backend, settings) -> None:
        self.backend = backend
        self.settings = settings
        self.pause = Gtk.ToggleButton(icon_name="media-playback-pause-symbolic",
                                      tooltip_text="Pause Graphs")
        self.pause.connect("toggled", self._on_pause)

        group = Gio.SimpleActionGroup()
        interval = Gio.SimpleAction.new_stateful(
            "interval", GLib.VariantType.new("s"),
            GLib.Variant.new_string(settings.get("intel-gpu-top-interval")))
        interval.connect("change-state", self._on_interval)
        history = Gio.SimpleAction.new_stateful(
            "history", GLib.VariantType.new("s"),
            GLib.Variant.new_string(str(settings.get("intel-gpu-top-history"))))
        history.connect("change-state", self._on_history)
        export = Gio.SimpleAction.new("export", None)
        export.connect("activate", lambda *_: self.export())
        clear = Gio.SimpleAction.new("clear", None)
        clear.connect("activate", lambda *_: backend.clear())
        for a in (interval, history, export, clear):
            group.add_action(a)
        self.actions = group

        menu = Gio.Menu()
        settings_section = Gio.Menu()
        intervals = Gio.Menu()
        for nick, label in INTERVALS:
            intervals.append(label, f"igt.interval('{nick}')")
        settings_section.append_submenu("Update Interval", intervals)
        lengths = Gio.Menu()
        for seconds, label in HISTORY_S:
            lengths.append(label, f"igt.history('{seconds}')")
        settings_section.append_submenu("History Length", lengths)
        menu.append_section(None, settings_section)
        data = Gio.Menu()
        data.append("Export as CSV…", "igt.export")
        data.append("Clear History", "igt.clear")
        menu.append_section(None, data)
        self.menu = Gtk.MenuButton(icon_name="view-more-symbolic", menu_model=menu,
                                   tooltip_text="Detailed Statistics Menu")
        # The menu lives in the page's header, outside this view's widgets:
        # give it the actions directly.
        self.menu.insert_action_group("igt", group)
        self.widgets = [self.pause, self.menu]

    def _on_pause(self, button) -> None:
        paused = button.get_active()
        self.backend.paused = paused
        button.set_icon_name("media-playback-start-symbolic" if paused
                             else "media-playback-pause-symbolic")
        button.set_tooltip_text("Resume Graphs" if paused else "Pause Graphs")
        if not paused:
            self.backend.history.add_gap()

    def _on_interval(self, action, value) -> None:
        action.set_state(value)
        self.settings.set("intel-gpu-top-interval", value.get_string())

    def _on_history(self, action, value) -> None:
        action.set_state(value)
        self.settings.set("intel-gpu-top-history", int(value.get_string()))

    def export(self) -> None:
        dialog = Gtk.FileDialog(title="Export History")
        dialog.set_initial_name(time.strftime("intel-gpu-%Y%m%d-%H%M%S.csv"))
        dialog.save(self.menu.get_root(), None, self._on_export_done)

    def _on_export_done(self, dialog, result) -> None:
        try:
            path = dialog.save_finish(result).get_path()
        except GLib.Error:
            return  # cancelled
        self.write_csv(path)

    def write_csv(self, path: str) -> str:
        try:
            self.backend.history.write_csv(path)
            message = f"Saved {os.path.basename(path)}"
        except OSError as exc:
            message = f"Export failed: {exc}"
        overlay = self.menu.get_ancestor(Adw.ToastOverlay)
        if overlay is not None:
            overlay.add_toast(Adw.Toast(title=GLib.markup_escape_text(message), timeout=3))
        return message


def create_views(backend, controller, services) -> DetailViews:
    header = IntelDetailHeader(backend, services.settings)
    graphs = IntelGraphsView(backend)
    clients = IntelClientsView(backend, services.app_icon)

    def on_updated(_backend) -> None:
        if not backend.paused:
            graphs.refresh()
            clients.refresh()
    handler = backend.connect("updated", on_updated)
    return DetailViews([DetailView("details", graphs, header.widgets),
                        DetailView("processes", clients, header.widgets)], [handler])
