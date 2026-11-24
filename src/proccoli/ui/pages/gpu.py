"""The GPU page (DESIGN.md §7.3): one page per GPU with up to three tabs.

- **Overview** (always): Resources' GPU page, fed by the controller's
  summary, which comes from the detail source while it runs.
- **Vendor tabs** (only if the GPU has a detail source): one ``DetailHost``
  per ``TabSpec``. Until the source runs, a host shows a status page with
  the right button; then it shows the view the backend built.

The page is never replaced: the tabs are fixed by the detail class, so the
switcher stays put while the source starts, fails and restarts.
"""

from __future__ import annotations

from typing import Optional

from gi.repository import Adw, Gtk

from ...core.units import (format_bytes, format_frequency, format_percent, format_power,
                           format_temperature)
from ...gpu.backend import DetailServices, DetailView, GpuSummary
from ...gpu.controller import DetailState, GpuController, GpuSnapshot
from ..page import PageKind
from ..widgets.double_graph_box import DoubleGraphBox
from ..widgets.info_row import InfoRow
from .device import DevicePage

OVERVIEW = "overview"
# Below this width the tab switcher moves from the header to a bottom bar.
NARROW_CONDITION = "max-width: 550sp"

# state -> (title, button label or None, icon; None shows a spinner)
STATE_TEXT = {
    DetailState.OFF: ("Detailed Statistics Are Off", "Turn On", "video-display-symbolic"),
    DetailState.NEEDS_AUTH: ("Administrator Rights Needed", "Show Detailed Statistics",
                             "system-lock-screen-symbolic"),
    DetailState.STARTING: ("Starting…", None, None),
    DetailState.RUNNING: ("Starting…", None, None),      # running, view not built yet
    DetailState.FAILED: ("Detailed Statistics Stopped", "Try Again", "dialog-warning-symbolic"),
    DetailState.UNAVAILABLE: ("No Detailed Statistics", None, "video-display-symbolic"),
}


def is_intel(controller: GpuController) -> bool:
    return controller.gpu.driver in ("i915", "xe")


class DetailHost(Gtk.Stack):
    """One vendor tab: a status page until its view exists."""

    def __init__(self, name: str) -> None:
        super().__init__(vexpand=True, hexpand=True)
        self.name = name
        self.view: Optional[DetailView] = None
        self.status = Adw.StatusPage()
        self.spinner = Adw.Spinner(width_request=32, height_request=32, visible=False)
        self.button = Gtk.Button(halign=Gtk.Align.CENTER)
        self.button.add_css_class("pill")
        self.button.add_css_class("suggested-action")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.append(self.spinner)
        box.append(self.button)
        self.status.set_child(box)
        self.add_named(self.status, "status")

    def set_view(self, view: Optional[DetailView]) -> None:
        if self.view is not None:
            self.remove(self.view.widget)
        self.view = view
        if view is not None:
            self.add_named(view.widget, "view")
            self.set_visible_child_name("view")
        else:
            self.set_visible_child_name("status")

    def show_state(self, state: DetailState, message: str) -> None:
        if state == DetailState.RUNNING and self.view is not None:
            self.set_visible_child_name("view")
            return
        title, button, icon = STATE_TEXT[state]
        self.status.set_title(title)
        self.status.set_description(message or None)
        self.status.set_icon_name(icon)
        self.spinner.set_visible(icon is None)
        self.button.set_visible(button is not None)
        if button:
            self.button.set_label(button)
        self.set_visible_child_name("status")


class GpuPage(DevicePage):
    def __init__(self, controller: GpuController, settings, app_icon=None) -> None:
        """``app_icon(pid)`` (processes.apps.AppIconLookup.icon_for_pid) gives
        the vendor Processes tab its app icons."""
        super().__init__(controller, settings, PageKind.GPU,
                         sort_name=controller.gpu.pci_slot)
        self.controller = controller
        self.services = (DetailServices(settings, app_icon) if app_icon is not None
                         else DetailServices(settings))
        self._build_overview()

        tabs = controller.detail_class.TABS if controller.detail_class else ()
        self.hosts: dict[str, DetailHost] = {}
        self._views_from = None          # the backend the current views came from
        self._view_handlers = None       # (backend, handler ids) feeding those views
        self.stack = Adw.ViewStack(vexpand=True)
        overview = self.get_child()
        self.set_child(None)
        self.stack.add_titled_with_icon(overview, OVERVIEW, "Overview",
                                        controller.info.icon_name)
        for tab in tabs:
            host = DetailHost(tab.name)
            host.button.connect("clicked", lambda _b: self._on_status_button())
            self.hosts[tab.name] = host
            self.stack.add_titled_with_icon(host, tab.name, tab.title, tab.icon_name)

        self.switcher = Adw.ViewSwitcher(stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        self.switcher_bar = Adw.ViewSwitcherBar(stack=self.stack)
        # Header buttons of the vendor tabs (pause, menu): shown on those only.
        self.detail_header = Gtk.Box(spacing=6, visible=False)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(self.stack)
        content.append(self.switcher_bar)
        bin_ = Adw.BreakpointBin(width_request=280, height_request=150, child=content)
        if tabs:
            narrow = Adw.Breakpoint.new(Adw.BreakpointCondition.parse(NARROW_CONDITION))
            narrow.add_setter(self.switcher_bar, "reveal", True)
            narrow.add_setter(self.switcher, "visible", False)
            bin_.add_breakpoint(narrow)
        self.set_child(bin_)

        self.show_tab(settings.get("gpu-view"))      # before anything saves a tab
        self.track(controller, controller.connect("detail-changed",
                                                  lambda *_: self._on_detail_changed()))
        self.stack.connect("notify::visible-child-name", lambda *_: self._on_tab_changed())
        self._on_detail_changed()

    def shutdown(self) -> None:
        self._set_views(None)
        super().shutdown()

    # -- overview ------------------------------------------------------------------

    def _build_overview(self) -> None:
        c = self.controller
        self.usage_group = usage = self.add_group("Usage")
        self.usage = self.graph_box(usage, "GPU Usage", [("usage", "%")])
        # One video engine on Intel; separate encoder and decoder elsewhere.
        combined = is_intel(c)
        self.video_combined = self.graph_box(usage, "Video Encoder/Decoder",
                                             [("decode", "%")], color_offset=1)
        self.video = DoubleGraphBox("Video Encoder", "Video Decoder")
        self.video.start.set_series([c.history.define("encode", "%")], color_offset=1)
        self.video.end.set_series([c.history.define("decode", "%")], color_offset=2)
        self.add_pair(usage, self.video)
        self.video_combined.set_visible(combined)
        self.video.set_visible(not combined)
        self.vram = self.graph_box(usage, "Video Memory", [("vram", "%")], color_offset=3)
        self.vram.set_visible(False)
        self.frequency = InfoRow("GPU Frequency")
        self.vram_frequency = InfoRow("Video Memory Frequency")
        self.power = InfoRow("Power Usage")
        for row in (self.frequency, self.vram_frequency, self.power):
            usage.add(row)
        self.details_row: Optional[Adw.ActionRow] = None
        if c.detail_class is not None:
            self.details_row = Adw.ActionRow(title="Detailed Statistics", activatable=True)
            self.details_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
            self.details_row.connect("activated",
                                     lambda _r: self.show_tab(c.detail_class.TABS[0].name))
            usage.add(self.details_row)

        self.sensors = self.add_group("Sensors")
        self.temperature = self.graph_box(self.sensors, "Temperature",
                                          [("temperature", "°C")], max_value=None,
                                          min_max=100.0)
        self.sensors.set_visible(False)
        props = dict(c.info.properties)
        props["Max Power Cap"] = ""
        self.add_properties(props)

    def update_labels(self, snap: GpuSnapshot) -> None:
        s: GpuSummary = snap.summary
        self.usage.set_info(format_percent(s.usage))
        self.video_combined.set_info(format_percent(s.decode))
        self.video.start.set_info(format_percent(s.encode))
        self.video.end.set_info(format_percent(s.decode))
        self.vram.set_visible(bool(s.vram_total))
        if s.vram_total:
            self.vram.set_info(f"{format_bytes(s.vram_used, self.base)} of "
                               f"{format_bytes(s.vram_total, self.base)}")
        self.frequency.set_value(format_frequency(s.frequency_hz) if s.frequency_hz else None)
        self.vram_frequency.set_value(
            format_frequency(s.vram_frequency_hz) if s.vram_frequency_hz else None)
        if s.power_w is not None:
            text = format_power(s.power_w)
            if s.power_cap_w:
                text += f" / {format_power(s.power_cap_w)}"
            self.power.set_value(text)
        else:
            self.power.set_value(None)
        self.sensors.set_visible(s.temperature_c is not None)
        if s.temperature_c is not None:
            self.temperature.set_info(format_temperature(s.temperature_c,
                                                         self.temperature_unit))
        self.property_rows["Max Power Cap"].set_value(
            format_power(s.power_cap_w) if s.power_cap_w else None)

    # -- tabs ----------------------------------------------------------------------

    def title_widget(self) -> Optional[Gtk.Widget]:
        """The tab switcher, in the header (None without vendor tabs)."""
        return self.switcher if self.hosts else None

    def header_widgets(self) -> list[Gtk.Widget]:
        return [self.detail_header] if self.hosts else []

    def current_tab(self) -> str:
        return self.stack.get_visible_child_name() or OVERVIEW

    def show_tab(self, name: str) -> bool:
        if name != OVERVIEW and name not in self.hosts:
            return False
        self.stack.set_visible_child_name(name)
        return True

    def _on_tab_changed(self) -> None:
        tab = self.current_tab()
        self.detail_header.set_visible(tab in self.hosts and self._views_from is not None)
        if self.settings.get("gpu-view") != tab:
            self.settings.set("gpu-view", tab)

    def elevation_offer(self):
        c = self.controller
        if c.detail_state != DetailState.NEEDS_AUTH:
            return None
        from ..elevation import ElevationOffer

        def run(done) -> None:
            def changed(*_a) -> None:
                if c.detail_state in (DetailState.RUNNING, DetailState.FAILED,
                                      DetailState.OFF):
                    c.disconnect(handler)
                    done(c.detail_state == DetailState.RUNNING)
            handler = c.connect("detail-changed", changed)
            c.start_details(elevate=True)
        return ElevationOffer(self.page_id, "Detailed GPU statistics",
                              c.info.description or c.gpu.name, run)

    def _on_status_button(self) -> None:
        c = self.controller
        if c.detail_state == DetailState.OFF:
            c.set_details_enabled(True)
        elif c.detail_state == DetailState.NEEDS_AUTH:
            c.start_details(elevate=True)
        elif c.detail_state == DetailState.FAILED:
            c.start_details(elevate=c.detail_can_elevate or c.needs_elevation)

    def _on_detail_changed(self) -> None:
        c = self.controller
        state, backend = c.detail_state, c.detail_backend
        if backend is not self._views_from:             # stopped or restarted
            self._set_views(None)
        if state == DetailState.RUNNING and backend is not None and self._views_from is None:
            self._set_views(backend)
        for host in self.hosts.values():
            host.show_state(state, c.detail_message)
        if self.details_row is not None:
            self.details_row.set_subtitle(
                "Running" if state == DetailState.RUNNING
                else (c.detail_message or STATE_TEXT[state][0]))
        own_only = is_intel(c) and state != DetailState.RUNNING
        self.usage_group.set_description(
            "Counts your own processes only. Detailed statistics include every process."
            if own_only else None)
        self._on_tab_changed()

    def _set_views(self, backend) -> None:
        if self._view_handlers:
            source, handlers = self._view_handlers
            for h in handlers:
                source.disconnect(h)
        self._view_handlers = None
        for w in list(self.detail_header):
            self.detail_header.remove(w)
        self._views_from = backend
        views = []
        if backend is not None:
            built = backend.create_views(self.controller, self.services)
            views = built.views
            self._view_handlers = (backend, built.handlers)
        by_name = {v.name: v for v in views}
        seen: list[Gtk.Widget] = []
        for name, host in self.hosts.items():
            view = by_name.get(name)
            host.set_view(view)
            for w in (view.header_widgets if view else []):
                if not any(w is s for s in seen):    # tabs may share their buttons
                    seen.append(w)
                    self.detail_header.append(w)
