"""Processor page: total usage or one chart of every logical CPU (with a
legend), temperature, properties."""

from __future__ import annotations

from gi.repository import Adw, Gtk

from ...core.units import (device_facts, format_duration, format_frequency, format_percent,
                           format_temperature)
from ...devices.cpu import CpuMonitor, CpuSnapshot, busiest_thread
from ..page import PageKind
from .device import DevicePage


class CpuPage(DevicePage):
    def __init__(self, monitor: CpuMonitor, settings) -> None:
        super().__init__(monitor, settings, PageKind.CPU)
        self.thread_names: list[str] = []

        options = self.add_group("Options")
        self.logical_switch = Adw.SwitchRow(title="Show Usages of Logical CPUs")
        options.add(self.logical_switch)
        settings.bind("show-logical-cpus", self.logical_switch, "active")

        # Total usage, or one chart with a line per logical CPU and a legend
        # (M55; it replaced a grid of small graphs).
        self.usage_stack = Gtk.Stack(vhomogeneous=False, interpolate_size=True)
        total_group = Adw.PreferencesGroup(title="Usage")
        self.total = self.graph_box(total_group, "Total Usage", [("usage", "%")])
        self.usage_stack.add_named(total_group, "total")
        logical_group = Adw.PreferencesGroup(title="Usage")
        # A reusable LegendChart (M59): one line per CPU, the legend in its
        # card, chart and legend fitted into the total chart's area (M57).
        self.threads = self.add_legend_chart(logical_group, "Usage per Logical CPU")
        self.legend = self.threads.legend
        self.usage_stack.add_named(logical_group, "logical")
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
        self._ensure_threads()

    def _show_logical(self, show: bool) -> None:
        self.usage_stack.set_visible_child_name("logical" if show else "total")
        self.refit()                    # the other chart takes the same area

    def fit_key(self) -> tuple:
        # Which chart shows (the legend's height is in the base's key).
        return (*super().fit_key(), self.usage_stack.get_visible_child_name())

    def _ensure_threads(self) -> None:
        """One line and one legend item per logical CPU (known after the
        first sample)."""
        count = len(self.monitor.thread_names())
        if count == len(self.thread_names):
            return
        self.thread_names = [f"CPU {i}" for i in range(count)]
        self.threads.set_lines([self.monitor.history.define(f"cpu{i}", "%")
                                for i in range(count)], self.thread_names)

    def sidebar_summary(self):
        summary = super().sidebar_summary()
        snap = self.monitor.latest
        if snap is not None:
            summary.facts = device_facts(snap.temperature_c, self.temperature_unit)
        return summary

    def update_labels(self, snap: CpuSnapshot) -> None:
        self._ensure_threads()
        info = format_percent(snap.usage)
        if snap.frequency_hz:
            info += f" · {format_frequency(snap.frequency_hz)}"
        self.total.set_info(info)
        self.threads.set_values([format_percent(v) for v in snap.per_thread])
        info = f"{len(self.thread_names)} logical CPUs"
        busiest = busiest_thread(snap.per_thread)
        if busiest is not None:
            index, value = busiest
            info += f" · busiest: CPU {index}, {format_percent(value)}"
        self.threads.set_info(info)
        if snap.temperature_c is not None:
            self.temperature.set_info(format_temperature(snap.temperature_c,
                                                         self.temperature_unit))
        if snap.uptime_s is not None:
            self.property_rows["Uptime"].set_value(format_duration(snap.uptime_s))
