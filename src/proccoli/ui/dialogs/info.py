"""Process Information and App Information dialogs: live while open."""

from __future__ import annotations

import time
from typing import Optional

from gi.repository import Adw, Gtk, Pango

from ...core.units import Base, format_bytes, format_duration, format_percent, format_rate
from ..widgets.info_row import InfoRow


def _since(epoch: Optional[float]) -> Optional[str]:
    if not epoch:
        return None
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch))


class _InfoDialog(Adw.Dialog):
    """Usage and Properties groups, refreshed on every process scan."""

    USAGE: tuple[str, ...] = ()
    PROPERTIES: tuple[str, ...] = ()

    def __init__(self, title: str, monitor, settings) -> None:
        super().__init__(title=title, content_width=460, content_height=640)
        self.monitor = monitor
        self.settings = settings
        page = Adw.PreferencesPage()
        self.header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                                  margin_top=12)
        self.name_label = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER,
                                    ellipsize=Pango.EllipsizeMode.END)
        self.name_label.add_css_class("title-2")
        self.header_box.append(self.name_label)
        header_group = Adw.PreferencesGroup()
        header_group.add(self.header_box)
        page.add(header_group)
        self.rows: dict[str, InfoRow] = {}
        for title_, keys in (("Usage", self.USAGE), ("Properties", self.PROPERTIES)):
            group = Adw.PreferencesGroup(title=title_)
            for key in keys:
                self.rows[key] = InfoRow(key)
                group.add(self.rows[key])
            page.add(group)
        toolbar = Adw.ToolbarView(content=page)
        toolbar.add_top_bar(Adw.HeaderBar())
        self.set_child(toolbar)
        self._handler = monitor.connect("updated", lambda *_: self.refresh())
        self.connect("closed", self._on_closed)
        monitor.acquire()            # keep the scan running while this is open
        self.refresh()

    @property
    def base(self) -> Base:
        return Base(self.settings.get("base"))

    def refresh(self) -> None:
        raise NotImplementedError

    def set_values(self, values: dict) -> None:
        for key, row in self.rows.items():
            row.set_value(values.get(key))

    def _on_closed(self, *_a) -> None:
        if self._handler:
            self.monitor.disconnect(self._handler)
            self._handler = 0
            self.monitor.release()


class ProcessInfoDialog(_InfoDialog):
    USAGE = ("Processor", "Memory", "Swap", "Drive Read", "Drive Read Total", "Drive Write",
             "Drive Write Total", "GPU", "Video Memory", "Video Encoder", "Video Decoder",
             "Total CPU Time", "User CPU Time", "System CPU Time")
    PROPERTIES = ("Process ID", "Running Since", "Commandline", "User", "Control Group",
                  "Containerized")

    def __init__(self, monitor, settings, pid: int) -> None:
        self.pid = pid
        self.ended = False
        super().__init__("Process Information", monitor, settings)

    def refresh(self) -> None:
        p = self.monitor.processes.get(self.pid)
        if p is None:
            self.ended = True
            self.name_label.set_label(f"{self.name_label.get_label() or self.pid} (ended)")
            return
        b = self.base
        self.name_label.set_label(p.name)
        opt_rate = (lambda v: None if v is None else format_rate(v, b))
        opt_size = (lambda v: None if v is None else format_bytes(v, b))
        self.set_values({
            "Processor": format_percent(p.cpu), "Memory": format_bytes(p.memory, b),
            "Swap": format_bytes(p.swap, b), "Drive Read": opt_rate(p.read_bps),
            "Drive Read Total": opt_size(p.read_total), "Drive Write": opt_rate(p.write_bps),
            "Drive Write Total": opt_size(p.write_total), "GPU": format_percent(p.gpu),
            "Video Memory": format_bytes(p.vram, b), "Video Encoder": format_percent(p.encode),
            "Video Decoder": format_percent(p.decode),
            "Total CPU Time": format_duration(p.cpu_time_total),
            "User CPU Time": format_duration(p.cpu_time_user),
            "System CPU Time": format_duration(p.cpu_time_system),
            "Process ID": str(p.pid), "Running Since": _since(p.started),
            "Commandline": p.commandline or None, "User": p.user or None,
            "Control Group": p.cgroup or None,
            "Containerized": p.containerized or "No"})


class AppInfoDialog(_InfoDialog):
    USAGE = ("Processor", "Memory", "Swap", "Drive Read", "Drive Read Total", "Drive Write",
             "Drive Write Total", "GPU", "Video Memory", "Video Encoder", "Video Decoder")
    PROPERTIES = ("ID", "Running Since", "Running Processes", "Containerized")

    def __init__(self, monitor, settings, grouper, app_id: str) -> None:
        self.grouper = grouper
        self.app_id = app_id
        super().__init__("App Information", monitor, settings)
        self.icon = Gtk.Image(pixel_size=96)
        self.description = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self.description.add_css_class("dim-label")
        self.header_box.prepend(self.icon)
        self.header_box.append(self.description)
        self.refresh()

    def refresh(self) -> None:
        if not hasattr(self, "icon"):
            return                     # called once before the header exists
        app = self.grouper.group(self.monitor.processes.values()).get(self.app_id)
        if app is None:
            self.name_label.set_label(f"{self.name_label.get_label()} (ended)")
            return
        b = self.base
        self.name_label.set_label(app.name)
        self.description.set_label(app.description)
        self.description.set_visible(bool(app.description))
        if app.icon is not None:
            self.icon.set_from_gicon(app.icon)
        else:
            self.icon.set_from_icon_name("application-x-executable-symbolic")
        self.set_values({
            "Processor": format_percent(app.cpu), "Memory": format_bytes(app.memory, b),
            "Swap": format_bytes(app.swap, b), "Drive Read": format_rate(app.read_bps, b),
            "Drive Read Total": format_bytes(app.read_total, b),
            "Drive Write": format_rate(app.write_bps, b),
            "Drive Write Total": format_bytes(app.write_total, b),
            "GPU": format_percent(app.gpu), "Video Memory": format_bytes(app.vram, b),
            "Video Encoder": format_percent(app.encode),
            "Video Decoder": format_percent(app.decode),
            "ID": app.id, "Running Since": _since(app.started),
            "Running Processes": str(len(app.pids)),
            "Containerized": app.containerized or "No"})
