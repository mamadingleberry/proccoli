"""Apps page: running apps, each the sum of its processes."""

from __future__ import annotations

import logging

from gi.repository import Adw, GLib

from ...core.windows import WindowSwitcher
from ...core.units import Base, format_bytes, format_percent, format_rate
from ...processes.apps import SYSTEM_ID, App, AppGrouper
from ...processes.monitor import ProcessMonitor
from ..dialogs.info import AppInfoDialog
from ..page import PageKind
from .table import Column, TablePage

log = logging.getLogger(__name__)


def _cols(settings) -> list[Column]:
    base = lambda: Base(settings.get("base"))  # noqa: E731
    size = lambda v: format_bytes(v, base())   # noqa: E731
    rate = lambda v: format_rate(v, base())    # noqa: E731
    s = "apps-show-"
    return [
        Column("name", "App", lambda a: a.name.lower(), lambda a: a.name, numeric=False,
               expand=True, width=240, icon=lambda a: a.icon),
        Column("memory", "Memory", lambda a: a.memory, lambda a: size(a.memory), f"{s}memory"),
        Column("cpu", "Processor", lambda a: a.cpu, lambda a: format_percent(a.cpu), f"{s}cpu"),
        Column("drive-read-speed", "Drive Read", lambda a: a.read_bps,
               lambda a: rate(a.read_bps), f"{s}drive-read-speed"),
        Column("drive-read-total", "Drive Read Total", lambda a: a.read_total,
               lambda a: size(a.read_total), f"{s}drive-read-total"),
        Column("drive-write-speed", "Drive Write", lambda a: a.write_bps,
               lambda a: rate(a.write_bps), f"{s}drive-write-speed"),
        Column("drive-write-total", "Drive Write Total", lambda a: a.write_total,
               lambda a: size(a.write_total), f"{s}drive-write-total"),
        Column("gpu", "GPU", lambda a: a.gpu, lambda a: format_percent(a.gpu), f"{s}gpu"),
        Column("gpu-memory", "Video Memory", lambda a: a.vram, lambda a: size(a.vram),
               f"{s}gpu-memory"),
        Column("encoder", "Video Encoder", lambda a: a.encode,
               lambda a: format_percent(a.encode), f"{s}encoder"),
        Column("decoder", "Video Decoder", lambda a: a.decode,
               lambda a: format_percent(a.decode), f"{s}decoder"),
        Column("swap", "Swap", lambda a: a.swap, lambda a: size(a.swap), f"{s}swap"),
        Column("combined-memory", "Combined Memory", lambda a: a.combined_memory,
               lambda a: size(a.combined_memory), f"{s}combined-memory"),
    ]


class AppsPage(TablePage):
    SORT_KEY = "apps"
    NOUN = "App"

    def __init__(self, monitor: ProcessMonitor, settings, grouper: AppGrouper,
                 actions, system=None, windows=None) -> None:
        """``system`` (core.system.System) brings apps to the front; it
        defaults to the one ``actions`` uses. ``windows``
        (core.windows.WindowSwitcher) decides how (default: over
        ``system``)."""
        self.COLUMNS = _cols(settings)
        self.grouper = grouper
        self.system = system if system is not None else actions.system
        self.windows = windows if windows is not None else WindowSwitcher(self.system)
        super().__init__("apps", PageKind.APPS, "Apps", "view-app-grid-symbolic", settings,
                         monitor, actions)
        self.refresh()

    # -- Switch To -----------------------------------------------------

    def extra_actions(self) -> list:
        return [("switch-to", self.switch_to)]

    def switchable(self, selected: list) -> bool:
        """One app, a real one. *Switch To* is offered for every app (Idea
        5); one Proccoli can't reach says how to set up window switching."""
        return len(selected) == 1 and selected[0].id != SYSTEM_ID

    def update_extra_actions(self, selected: list) -> None:
        self.action_group.lookup_action("switch-to").set_enabled(self.switchable(selected))

    def extra_menu_items(self, selected: list) -> list:
        return [("Switch To", "table.switch-to")] if self.switchable(selected) else []

    def switch_to(self) -> None:
        selected = self.selected()
        if not self.switchable(selected):
            return
        app = selected[0]
        if self.windows.way(app) is None:
            self.offer_setup(app)
            return
        display = self.get_display()
        context = display.get_app_launch_context() if display is not None else None
        try:
            ok = self.windows.switch(app, context)
        except Exception as exc:          # D-Bus or launch errors
            ok = False
            log.info("switching to %s failed: %s", app.id, exc)
        if not ok:
            self.toast(f"Could not switch to {app.name}")

    def offer_setup(self, app) -> None:
        """GNOME lets an app raise only its own windows: say how to let
        Proccoli raise any (Preferences → General → *Window Switching*)."""
        self.last_message = (f"{app.name} can only be brought to the front with "
                             "window switching turned on")
        toast = Adw.Toast(title=GLib.markup_escape_text(self.last_message), timeout=6,
                          button_label="Set Up…", action_name="app.preferences")
        self.toast_overlay.add_toast(toast)

    def search_text(self, a: App) -> str:
        return f"{a.name} {a.id} {a.description}"

    def items(self) -> dict:
        return self.grouper.group(self.monitor.processes.values())

    def info_dialog(self, item):
        return AppInfoDialog(self.monitor, self.settings, self.grouper, item.id)

    def targets(self, selected: list) -> list[tuple[int, str]]:
        """Every process of the selected apps, named after their app (so a
        message reads "Ended Firefox", not "Ended 14 processes")."""
        return [(pid, a.name) for a in selected for pid in a.pids]
