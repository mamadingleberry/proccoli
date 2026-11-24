"""Processor page: total or per-thread usage, temperature, properties."""

from __future__ import annotations

from gi.repository import Adw, Gtk

from ...core.units import format_duration, format_frequency, format_percent, format_temperature
from ...devices.cpu import CpuMonitor, CpuSnapshot
from ..page import PageKind
from ..widgets.graph import Graph, GraphStyle
from .device import DevicePage


THREAD_GRAPH_ASPECT = 0.6     # height / width of a per-thread graph
THREAD_CELL_MIN_WIDTH = 120   # the grid fits as many as this allows per line


class ThreadCell(Gtk.Box):
    """A small graph for one logical CPU, for the per-thread grid."""

    def __init__(self, name: str, series) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True,
                         width_request=THREAD_CELL_MIN_WIDTH)
        self.graph = Graph(GraphStyle.SMALL, max_value=100.0)
        # Grows with the grid's column width (DESIGN.md §9.1).
        self.graph.set_aspect(THREAD_GRAPH_ASPECT, minimum=48, maximum=240)
        self.graph.set_series([series])
        header = Gtk.Box(spacing=6)
        self.name_label = Gtk.Label(label=name, xalign=0, hexpand=True)
        self.name_label.add_css_class("caption-heading")
        self.value_label = Gtk.Label(xalign=1)
        self.value_label.add_css_class("caption")
        self.value_label.add_css_class("numeric")
        header.append(self.name_label)
        header.append(self.value_label)
        self.append(self.graph)
        self.append(header)


class CpuPage(DevicePage):
    def __init__(self, monitor: CpuMonitor, settings) -> None:
        super().__init__(monitor, settings, PageKind.CPU)
        self.cells: list[ThreadCell] = []

        options = self.add_group("Options")
        self.logical_switch = Adw.SwitchRow(title="Show Usages of Logical CPUs")
        options.add(self.logical_switch)
        settings.bind("show-logical-cpus", self.logical_switch, "active")

        # Total usage, or one small graph per logical CPU.
        self.usage_stack = Gtk.Stack(vhomogeneous=False, interpolate_size=True)
        total_group = Adw.PreferencesGroup(title="Usage")
        self.total = self.graph_box(total_group, "Total Usage", [("usage", "%")])
        self.usage_stack.add_named(total_group, "total")
        logical = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        title = Gtk.Label(label="Usage", xalign=0)
        title.add_css_class("heading")
        self.flow = Gtk.FlowBox(homogeneous=True, min_children_per_line=2,
                                max_children_per_line=8, column_spacing=12,
                                row_spacing=12, selection_mode=Gtk.SelectionMode.NONE)
        logical.append(title)
        logical.append(self.flow)
        self.usage_stack.add_named(logical, "logical")
        self.box.append(self.usage_stack)
        self.track(settings, settings.connect_changed(
            "show-logical-cpus", lambda _k, v: self._show_logical(v)))
        self._show_logical(settings.get("show-logical-cpus"))

        self.sensors = self.add_group("Sensors")
        self.temperature = self.graph_box(self.sensors, "Temperature",
                                          [("temperature", "°C")], max_value=None,
                                          min_max=100.0)
        self.sensors.set_visible(monitor.temperature_path is not None)

        self.add_properties({**monitor.info.properties, "Uptime": ""})

    def _show_logical(self, show: bool) -> None:
        self.usage_stack.set_visible_child_name("logical" if show else "total")

    def _ensure_cells(self) -> None:
        names = self.monitor.thread_names()
        if len(self.cells) == len(names):
            return
        for i in range(len(self.cells), len(names)):
            cell = ThreadCell(f"CPU {i}", self.monitor.history.define(f"cpu{i}", "%"))
            self.add_graph(cell.graph)
            self.cells.append(cell)
            self.flow.append(cell)

    def update_labels(self, snap: CpuSnapshot) -> None:
        self._ensure_cells()
        info = format_percent(snap.usage)
        if snap.frequency_hz:
            info += f" · {format_frequency(snap.frequency_hz)}"
        self.total.set_info(info)
        for cell, value in zip(self.cells, snap.per_thread):
            cell.value_label.set_label(format_percent(value))
        if snap.temperature_c is not None:
            self.temperature.set_info(format_temperature(snap.temperature_c,
                                                         self.temperature_unit))
        if snap.uptime_s is not None:
            self.property_rows["Uptime"].set_value(format_duration(snap.uptime_s))
