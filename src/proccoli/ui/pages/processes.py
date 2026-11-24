"""Processes page: every process, with configurable columns."""

from __future__ import annotations

from ...core.units import Base, format_bytes, format_duration, format_percent, format_rate
from ...processes.model import ProcessInfo
from ...processes.monitor import ProcessMonitor
from gi.repository import Gtk

from ...core.ticker import update_interval_ms
from ..dialogs.info import ProcessInfoDialog
from ..dialogs.process_options import ProcessOptionsDialog
from ..page import PageKind
from .table import Column, TablePage


def nice_name(nice: int) -> str:
    """Priority names like Resources' (detailed values with *Show Niceness*)."""
    if nice <= -15:
        return "Very High"
    if nice < 0:
        return "High"
    if nice == 0:
        return "Normal"
    if nice < 15:
        return "Low"
    return "Very Low"


def _opt(fmt):
    return lambda v: "" if v is None else fmt(v)


def _cols(settings, grouper=None) -> list[Column]:
    """``grouper`` (processes.apps.AppGrouper) supplies each process's app
    icon; without one every row shows the missing-icon puzzle piece."""
    base = lambda: Base(settings.get("base"))  # noqa: E731
    size = lambda v: format_bytes(v, base())   # noqa: E731
    rate = lambda v: format_rate(v, base())    # noqa: E731
    prio = (lambda p: str(p.nice) if settings.get("detailed-priority") else nice_name(p.nice))
    s = "processes-show-"
    return [
        Column("name", "Process", lambda p: p.name.lower(), lambda p: p.name,
               numeric=False, expand=True, width=240,
               icon=(grouper.icon_for if grouper is not None else lambda p: None)),
        Column("id", "Process ID", lambda p: p.pid, lambda p: str(p.pid), f"{s}id", width=90),
        Column("user", "User", lambda p: p.user, lambda p: p.user, f"{s}user", numeric=False),
        Column("memory", "Memory", lambda p: p.memory, lambda p: size(p.memory), f"{s}memory"),
        Column("cpu", "Processor", lambda p: p.cpu, lambda p: format_percent(p.cpu), f"{s}cpu"),
        Column("drive-read-speed", "Drive Read", lambda p: p.read_bps,
               lambda p: _opt(rate)(p.read_bps), f"{s}drive-read-speed"),
        Column("drive-read-total", "Drive Read Total", lambda p: p.read_total,
               lambda p: _opt(size)(p.read_total), f"{s}drive-read-total"),
        Column("drive-write-speed", "Drive Write", lambda p: p.write_bps,
               lambda p: _opt(rate)(p.write_bps), f"{s}drive-write-speed"),
        Column("drive-write-total", "Drive Write Total", lambda p: p.write_total,
               lambda p: _opt(size)(p.write_total), f"{s}drive-write-total"),
        Column("gpu", "GPU", lambda p: p.gpu, lambda p: format_percent(p.gpu), f"{s}gpu"),
        Column("gpu-memory", "Video Memory", lambda p: p.vram, lambda p: size(p.vram),
               f"{s}gpu-memory"),
        Column("encoder", "Video Encoder", lambda p: p.encode,
               lambda p: format_percent(p.encode), f"{s}encoder"),
        Column("decoder", "Video Decoder", lambda p: p.decode,
               lambda p: format_percent(p.decode), f"{s}decoder"),
        Column("total-cpu-time", "Total CPU Time", lambda p: p.cpu_time_total,
               lambda p: format_duration(p.cpu_time_total), f"{s}total-cpu-time"),
        Column("user-cpu-time", "User CPU Time", lambda p: p.cpu_time_user,
               lambda p: format_duration(p.cpu_time_user), f"{s}user-cpu-time"),
        Column("system-cpu-time", "System CPU Time", lambda p: p.cpu_time_system,
               lambda p: format_duration(p.cpu_time_system), f"{s}system-cpu-time"),
        Column("priority", "Priority", lambda p: -p.nice, prio, f"{s}priority"),
        Column("swap", "Swap", lambda p: p.swap, lambda p: size(p.swap), f"{s}swap"),
        Column("combined-memory", "Combined Memory", lambda p: p.combined_memory,
               lambda p: size(p.combined_memory), f"{s}combined-memory"),
        Column("commandline", "Commandline", lambda p: p.commandline,
               lambda p: p.commandline, f"{s}commandline", numeric=False, width=240),
    ]


class ProcessesPage(TablePage):
    SORT_KEY = "processes"
    NOUN = "Process"
    HAS_OPTIONS = True

    def __init__(self, monitor: ProcessMonitor, settings, actions, system,
                 helper=None, cpu_count: int = 1, grouper=None) -> None:
        self.COLUMNS = _cols(settings, grouper)
        self.grouper = grouper
        self.system = system
        self.helper = helper
        self.cpu_count = cpu_count
        super().__init__("processes", PageKind.PROCESSES, "Processes",
                         "view-list-bullet-symbolic", settings, monitor, actions)
        self.io_button = Gtk.ToggleButton(
            icon_name="dialog-password-symbolic", visible=helper is not None,
            tooltip_text="Show Drive I/O of All Processes (administrator)")
        self.io_button.connect("toggled", self._on_io_toggled)
        self.track(monitor, monitor.connect("elevated-io", self._on_elevated_io))
        self.track(settings, settings.connect_changed(
            "detailed-priority", lambda *_: self.refresh()))
        self.refresh()

    def search_text(self, p: ProcessInfo) -> str:
        return f"{p.name} {p.commandline} {p.pid} {p.user}"

    def items(self) -> dict:
        return self.monitor.processes

    def header_widgets(self):
        return [self.io_button] + super().header_widgets()

    def _on_io_toggled(self, button) -> None:
        if button.get_active() and not self.monitor.elevated:
            self.start_elevated_io()
        elif not button.get_active() and self.monitor.elevated:
            self.monitor.stop_elevated_io()

    def start_elevated_io(self, done=None) -> None:
        """Read every process's drive I/O through the helper; ``done(ok)``
        once the first record arrives or the helper exits."""
        interval = update_interval_ms(self.settings)
        reader = self.helper.io_stream(interval)
        if done is not None:
            handlers = []

            def finish(ok: bool) -> None:
                for h in handlers:
                    reader.disconnect(h)
                handlers.clear()
                done(ok)
            handlers += [reader.connect("record", lambda *_: finish(True)),
                         reader.connect("exited", lambda *_: finish(False))]
        self.monitor.use_elevated_io(reader)

    def elevation_offer(self):
        if self.helper is None or self.monitor.elevated:
            return None
        from ..elevation import ElevationOffer
        return ElevationOffer(self.page_id, "Drive I/O of all processes",
                              "Including other users' and system processes",
                              self.start_elevated_io)

    def _on_elevated_io(self, _monitor, on: bool) -> None:
        if self.io_button.get_active() != on:
            self.io_button.set_active(on)
            if not on:
                self.toast("Stopped showing other users' drive I/O")

    def info_dialog(self, item):
        return ProcessInfoDialog(self.monitor, self.settings, item.pid)

    def options_dialog(self, item):
        return ProcessOptionsDialog(item, self.system, self.actions, self.settings,
                                    self.cpu_count, report=self.toast)

    def targets(self, selected: list) -> list[tuple[int, str]]:
        return [(p.pid, p.name) for p in selected]
