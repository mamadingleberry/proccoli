"""Preferences: every setting from DESIGN.md §11, applied immediately."""

from __future__ import annotations

from typing import Sequence

from gi.repository import Adw, Gtk

from ... import GPU_ICON
from ...core.palette import PALETTES, hex_to_rgb
from ...core.profile import is_pinned, profile_of
from ...core.styles import STYLES
from .. import sidebar_order
from ..sidebar_fields import FIELD_LABELS, Field

UPDATE_INTERVALS = [("1-second", "1 Second"), ("2-seconds", "2 Seconds"),
                    ("3-seconds", "3 Seconds"), ("5-seconds", "5 Seconds"),
                    ("10-seconds", "10 Seconds")]
BASES = [("decimal", "Decimal (kB, MB, GB)"), ("binary", "Binary (KiB, MiB, GiB)")]
TEMPERATURE_UNITS = [("celsius", "Celsius"), ("fahrenheit", "Fahrenheit"), ("kelvin", "Kelvin")]
LOG_LEVELS = [("off", "Off"), ("error", "Errors"), ("warning", "Warnings"),
              ("info", "Information and Performance"), ("debug", "Everything (Debug)")]
GRAPH_TIME_RANGES = [("30-seconds", "30 Seconds"), ("1-minute", "1 Minute"),
                     ("2-minutes", "2 Minutes"), ("5-minutes", "5 Minutes"),
                     ("10-minutes", "10 Minutes"), ("30-minutes", "30 Minutes"),
                     ("1-hour", "1 Hour"), ("6-hours", "6 Hours"), ("1-day", "1 Day")]
METER_TYPES = [("progress-bar", "Progress Bar"), ("graph", "Graph")]
SIDEBAR_STYLES = [("full", "Full"), ("icons", "Icons Only")]

APP_COLUMNS = [("memory", "Memory"), ("cpu", "Processor"), ("drive-read-speed", "Drive Read"),
               ("drive-read-total", "Drive Read Total"), ("drive-write-speed", "Drive Write"),
               ("drive-write-total", "Drive Write Total"), ("gpu", "GPU"),
               ("gpu-memory", "Video Memory"), ("encoder", "Video Encoder"),
               ("decoder", "Video Decoder"), ("swap", "Swap"),
               ("combined-memory", "Combined Memory")]
PROCESS_COLUMNS = [("id", "Process ID"), ("user", "User")] + APP_COLUMNS + [
    ("total-cpu-time", "Total CPU Time"), ("user-cpu-time", "User CPU Time"),
    ("system-cpu-time", "System CPU Time"), ("priority", "Priority"),
    ("commandline", "Commandline")]


class PreferencesDialog(Adw.PreferencesDialog):
    def __init__(self, settings, gpu_controllers: Sequence = (), theme=None,
                 log_file=None, launcher=None, sidebar=None, history=None,
                 export=None, restart=None, windows=None, extension_source=None) -> None:
        """``theme`` (ui.theme.Theme) only picks light or dark swatches;
        ``log_file`` (a Path) enables *Open Log Folder*, which
        ``launcher(folder)`` opens (default: Gtk.FileLauncher).
        ``history`` (core.history_store.HistoryStore) enables the size used
        and *Delete History…*, ``export()`` the *Export…* button,
        ``restart()`` *Restart Now* after Lightweight Mode changes,
        ``windows`` (core.windows.WindowSwitcher) the *Window Switching*
        row, which installs the extension from ``extension_source``."""
        super().__init__(title="Preferences", search_enabled=True)
        self.settings = settings
        self.theme = theme
        self.log_file = log_file
        self.history = history
        self.export = export
        self.delete_alert = None
        self.restart = restart
        self.windows = windows
        self.extension_source = extension_source
        self.launcher = launcher
        # ui.sidebar.StackSidebar: per-entry pages (none in tests that skip it).
        self.sidebar = sidebar
        self.entry_rows: dict[str, Adw.ActionRow] = {}
        self.entry_pages: dict[str, "EntryPage"] = {}
        self._handlers: list[int] = []
        self.rows: dict[str, Gtk.Widget] = {}      # settings key -> row (for tests)

        general = self._page("General", "preferences-system-symbolic")
        self._lightweight_group(general)
        appearance = self._group(general, "Appearance")
        self._style_row(appearance)
        self._palette_row(appearance)
        security = self._group(general, "Administrator Rights")
        self._switch(security, "auth-at-launch", "Ask for Administrator Rights at Start-Up",
                     "Offers to unlock memory properties, detailed GPU statistics and "
                     "other users' drive I/O; each page also has its own button")
        units = self._group(general, "Units")
        self._combo(units, "base", "Data Unit Prefix", BASES)
        self._switch(units, "network-bits", "Show Network Speeds in Bits per Second")
        self._combo(units, "temperature-unit", "Temperature Unit", TEMPERATURE_UNITS)
        ui = self._group(general, "User Interface")
        self._combo(ui, "update-interval", "Update Interval", UPDATE_INTERVALS,
                    "How often Proccoli takes readings. Shorter intervals use more processor time")
        self._switch(ui, "show-graph-grids", "Show Graph Grids")
        self._switch(ui, "show-graph-axes", "Show Graph Axes",
                     "Percentage and time labels with ticks on percentage graphs")
        self._combo(ui, "graph-time-range", "Graph Time Range", GRAPH_TIME_RANGES,
                    "How much history graphs show, whatever the refresh speed")
        self._switch(ui, "normalize-cpu-usage", "Normalize Processor Usage",
                     "Apps and Processes show each one's share of the whole processor, "
                     "so they add up to the total. Off: one fully busy core is 100 %")

        diagnostics = self._group(general, "Diagnostics",
                                  "A small log of Proccoli's messages and performance, "
                                  "for reporting problems")
        self._combo(diagnostics, "log-level", "Log Level", LOG_LEVELS)
        size = self._spin(diagnostics, "log-max-size", "Maximum Log Size (KiB)", 64, 65536)
        size.set_subtitle("One older log is kept too, so at most twice this on disk")
        self._spin(diagnostics, "log-performance-interval",
                   "Performance Line Every (Minutes)", 0, 1440).set_subtitle("0 turns it off")
        if log_file is not None:
            row = Adw.ActionRow(title="Log File", subtitle=str(log_file))
            button = Gtk.Button(label="Open Folder", valign=Gtk.Align.CENTER)
            button.connect("clicked", lambda *_: self.open_log_folder())
            row.add_suffix(button)
            diagnostics.add(row)
            self.log_button = button

        self._history_group(general)
        if windows is not None:
            self._window_switching_group(general)

        self._sidebar_page()

        apps = self._page("Apps", "view-app-grid-symbolic")
        columns = self._group(apps, "Information Columns")
        for key, title in APP_COLUMNS:
            self._switch(columns, f"apps-show-{key}", title)

        processes = self._page("Processes", "view-list-bullet-symbolic")
        options = self._group(processes, "Options")
        self._switch(options, "detailed-priority", "Show Niceness Values",
                     "Display priorities as niceness to allow for more fine-grained "
                     "adjustments")
        columns = self._group(processes, "Information Columns")
        for key, title in PROCESS_COLUMNS:
            self._switch(columns, f"processes-show-{key}", title)

        devices = self._page("Devices", "computer-symbolic")
        drives = self._group(devices, "Drives")
        self._switch(drives, "show-virtual-drives", "Show Virtual Drives",
                     "Virtual drives are for example ZFS volumes or mapped devices")
        nets = self._group(devices, "Network Interfaces")
        self._switch(nets, "show-virtual-network-interfaces",
                     "Show Virtual Network Interfaces",
                     "Virtual network interfaces are for example bridges or VPN tunnels")

        gpu = self._page("GPU", GPU_ICON)
        sources = self._group(gpu, "Detailed Statistics",
                              "Each GPU always shows an overview. Where a vendor tool "
                              "such as intel_gpu_top is installed, it adds detailed tabs")
        self.gpu_rows = {}
        for controller in gpu_controllers:
            self.gpu_rows[controller.gpu.pci_slot] = self._gpu_row(sources, controller)
        if not gpu_controllers:
            sources.add(Adw.ActionRow(title="No GPUs found"))
        detail = self._group(gpu, "Detailed Statistics Options")
        self._switch(detail, "gpu-elevate",
                     "Start Detailed Statistics with Administrator Rights",
                     "Asks for your password when the app starts, if the detailed "
                     "data source needs it")
        self._combo(detail, "intel-gpu-top-interval", "intel_gpu_top Update Interval",
                    [("", "Same as Update Interval")] + UPDATE_INTERVALS)

        # Lightweight Mode fixes some preferences while it's on (Idea 1).
        for key, row in self.rows.items():
            if is_pinned(settings, key):
                row.set_sensitive(False)
                row.set_tooltip_text("Fixed while Lightweight Mode is on")
        self.connect("closed", self._on_closed)

    # -- building blocks ----------------------------------------------------------

    def _page(self, title: str, icon: str) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(title=title, icon_name=icon)
        self.add(page)
        return page

    def _group(self, page, title: str, description: str = "") -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(title=title, description=description)
        page.add(group)
        return group

    def _watch(self, key: str, callback) -> None:
        self._handlers.append(self.settings.connect_changed(key, callback))

    def _switch(self, group, key: str, title: str, subtitle: str = "") -> Adw.SwitchRow:
        row = Adw.SwitchRow(title=title, subtitle=subtitle,
                            active=self.settings.get(key))
        row.connect("notify::active", lambda r, _p: self._set(key, r.get_active()))
        self._watch(key, lambda _k, v: row.get_active() != v and row.set_active(v))
        group.add(row)
        self.rows[key] = row
        return row

    def _combo(self, group, key: str, title: str, choices, subtitle: str = "") -> Adw.ComboRow:
        nicks = [n for n, _ in choices]
        row = Adw.ComboRow(title=title, subtitle=subtitle,
                           model=Gtk.StringList.new([label for _, label in choices]))
        current = self.settings.get(key)
        row.set_selected(nicks.index(current) if current in nicks else 0)
        row.connect("notify::selected", lambda r, _p: self._set(key, nicks[r.get_selected()]))
        self._watch(key, lambda _k, v: v in nicks and row.get_selected() != nicks.index(v)
                    and row.set_selected(nicks.index(v)))
        group.add(row)
        self.rows[key] = row
        return row

    def _style_row(self, group) -> Adw.ComboRow:
        """The *Style* combo: each entry shows its window and text colors."""
        row = self._combo(group, "color-scheme", "Style", [(s.id, s.name) for s in STYLES],
                          "Follow System uses the desktop's light or dark style")
        factory = Gtk.SignalListItemFactory()

        def setup(_f, item):
            box = Gtk.Box(spacing=12)
            box.append(Gtk.Label(xalign=0, hexpand=True))
            box.append(Gtk.DrawingArea(content_width=28, content_height=16,
                                       valign=Gtk.Align.CENTER))
            item.set_child(box)

        def bind(_f, item):
            box = item.get_child()
            name = item.get_item().get_string()
            style = next(s for s in STYLES if s.name == name)
            box.get_first_child().set_label(style.name)
            box.get_last_child().set_draw_func(self._draw_style_swatch, style)
        factory.connect("setup", setup)
        factory.connect("bind", bind)
        row.set_factory(factory)
        return row

    @staticmethod
    def style_swatch_colors(style) -> tuple[str, str]:
        """(background, text) for a style's swatch."""
        if style.tinted:
            return style.colors["window-bg-color"], style.colors["window-fg-color"]
        return {"light": ("#fafafb", "#323232"), "dark": ("#222226", "#ffffff"),
                "system": ("#fafafb", "#222226")}[style.base]

    def _draw_style_swatch(self, _area, cr, width, height, style) -> None:
        bg, fg = self.style_swatch_colors(style)
        cr.set_source_rgb(*hex_to_rgb(bg))
        cr.rectangle(0, 0, width, height)
        cr.fill()
        if style.base == "system":           # half light, half dark
            cr.set_source_rgb(*hex_to_rgb(fg))
            cr.rectangle(width / 2, 0, width / 2, height)
            cr.fill()
            return
        cr.set_source_rgb(*hex_to_rgb(fg))
        cr.arc(width / 2, height / 2, height / 4, 0, 6.2832)
        cr.fill()

    def _palette_row(self, group) -> Adw.ComboRow:
        """The *Color Palette* combo: each entry shows its colors."""
        row = self._combo(group, "palette", "Color Palette",
                          [(p.id, p.name) for p in PALETTES],
                          "Colors of graphs, meters and the accent")
        factory = Gtk.SignalListItemFactory()

        def setup(_f, item):
            box = Gtk.Box(spacing=12)
            box.append(Gtk.Label(xalign=0, hexpand=True))
            swatch = Gtk.DrawingArea(content_width=6 * 14, content_height=12,
                                     valign=Gtk.Align.CENTER)
            box.append(swatch)
            item.set_child(box)

        def bind(_f, item):
            box = item.get_child()
            label, swatch = box.get_first_child(), box.get_last_child()
            # Look the palette up by name: the row's own button binds the
            # selected item without a list position.
            name = item.get_item().get_string()
            palette = next(p for p in PALETTES if p.name == name)
            label.set_label(palette.name)
            swatch.set_draw_func(self._draw_swatch, palette)
            swatch.update_property([Gtk.AccessibleProperty.LABEL],
                                   [f"{palette.name} colors"])
        factory.connect("setup", setup)
        factory.connect("bind", bind)
        row.set_factory(factory)
        return row

    def _draw_swatch(self, _area, cr, width, height, palette) -> None:
        dark = self.theme.dark if self.theme is not None else False
        colors = palette.colors(dark)[:6]
        if palette.follows_accent and self.theme is not None:
            colors = [None] + list(colors[:5])        # the desktop's accent first
        r = height / 2
        for i, color in enumerate(colors):
            rgb = self.theme.system_accent() if color is None else hex_to_rgb(color)
            cr.set_source_rgb(*rgb)
            cr.arc(r + i * 14, height / 2, r, 0, 6.2832)
            cr.fill()

    def _spin(self, group, key: str, title: str, low: int, high: int) -> Adw.SpinRow:
        row = Adw.SpinRow.new_with_range(low, high, 10)
        row.set_title(title)
        row.set_value(self.settings.get(key))
        row.connect("notify::value", lambda r, _p: self._set(key, int(r.get_value())))
        self._watch(key, lambda _k, v: int(row.get_value()) != v and row.set_value(v))
        group.add(row)
        self.rows[key] = row
        return row

    def _gpu_row(self, group, controller) -> Adw.ActionRow:
        """A GPU's detailed-statistics switch, or a note that it has none."""
        title = controller.info.description or controller.gpu.name
        if controller.detail_class is None:
            row = Adw.ActionRow(title=title, subtitle=f"{controller.gpu.pci_slot} · "
                                "No detailed data source available")
            group.add(row)
            return row
        name = controller.detail_class.display_name
        if controller.needs_elevation:
            name += ", needs administrator rights"
        row = Adw.SwitchRow(title=title, subtitle=f"{controller.gpu.pci_slot} · {name}",
                            active=controller.details_enabled)
        row.connect("notify::active",
                    lambda r, _p: r.get_active() != controller.details_enabled
                    and controller.set_details_enabled(r.get_active()))
        group.add(row)
        return row

    # -- the Sidebar page (DESIGN.md §9.5) ------------------------------------------------

    def _sidebar_page(self) -> None:
        page = self.sidebar_prefs_page = self._page("Sidebar", "sidebar-show-symbolic")
        everything = self._group(page, "All Entries")
        self._combo(everything, "sidebar-style", "Style", SIDEBAR_STYLES,
                    "Icons Only shows each entry's icon; hover for its name and usage")
        self._switch(everything, "sidebar-details", "Show Usage Details",
                     "If enabled, the usage along with other information will be displayed")
        self._switch(everything, "sidebar-description", "Show Device Descriptions",
                     "If enabled, a device identifier like its name or device type "
                     "will be displayed")
        self._combo(everything, "sidebar-meter-type", "Meter Type", METER_TYPES)
        self.entries_group = self._group(
            page, "Entries", "Apps and Processes always stay at the top")
        if self.sidebar is None:
            return
        for page_id in self.sidebar.order():
            item = self.sidebar.items[page_id]
            if not item.movable:
                continue
            row = Adw.ActionRow(title=item.page.title, subtitle=item.page.description,
                                activatable=True)
            row.add_prefix(Gtk.Image(icon_name=item.page.icon_name))
            row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
            row.connect("activated", lambda _r, pid=page_id: self.open_entry(pid))
            self.entry_rows[page_id] = row
            self.entries_group.add(row)

    def open_entry(self, page_id: str) -> "EntryPage":
        """Show (push) the sub-page of one sidebar entry."""
        sub = EntryPage(self.sidebar, page_id, self.settings)
        self.entry_pages[page_id] = sub
        self.push_subpage(sub)
        return sub

    # -- Lightweight Mode (Idea 1) --------------------------------------------------

    def _lightweight_group(self, page) -> None:
        group = self._group(page, "Memory Use")
        self._switch(group, "lightweight", "Lightweight Mode",
                     "As little memory as possible: pages are built when you open them, "
                     "the Overview is a list, and charts, icons and GPU details are kept "
                     "to a minimum. Applies at the next start")
        row = Adw.ActionRow(title="Restart to Apply",
                            subtitle="Proccoli starts again with the new mode")
        button = Gtk.Button(label="Restart Now", valign=Gtk.Align.CENTER)
        button.add_css_class("suggested-action")
        button.connect("clicked", lambda *_: self.restart and self.restart())
        row.add_suffix(button)
        group.add(row)
        self.restart_row, self.restart_button = row, button
        self._watch("lightweight", lambda *_: self._show_restart())
        self._show_restart()

    def _show_restart(self) -> None:
        running = profile_of(self.settings).is_lightweight
        self.restart_row.set_visible(self.restart is not None
                                     and bool(self.settings.get("lightweight")) != running)

    # -- Window Switching (Idea 5) ---------------------------------------------------

    def _window_switching_group(self, page) -> None:
        group = self._group(page, "Window Switching",
                            "GNOME lets an app bring only its own windows to the front. "
                            "A small GNOME Shell extension lets Apps → Switch To bring "
                            "any app's window forward. It can only list windows and "
                            "activate one")
        row = Adw.ActionRow(title="Proccoli Window Switching")
        button = Gtk.Button(valign=Gtk.Align.CENTER)
        button.add_css_class("suggested-action")
        button.connect("clicked", lambda *_: self._on_window_switching())
        row.add_suffix(button)
        group.add(row)
        self.switching_row, self.switching_button = row, button
        self.show_window_switching()

    def show_window_switching(self) -> None:
        from ...core.windows import ExtensionState
        state = self.windows.extension_state()
        texts = {
            ExtensionState.ENABLED: "On: Switch To works for every app with a window",
            ExtensionState.DISABLED: "Installed, but turned off",
            ExtensionState.NEEDS_LOGIN: "Installed: log out and back in to start it",
            ExtensionState.NOT_INSTALLED: "Not installed: Switch To works only for apps "
                                          "that can be asked to show their window",
            ExtensionState.UNAVAILABLE: "Needs GNOME Shell (this desktop isn't GNOME)",
        }
        self.switching_row.set_subtitle(texts[state])
        label = {ExtensionState.DISABLED: "Turn On"}.get(state)
        if state == ExtensionState.NOT_INSTALLED and self.extension_source is not None:
            label = "Install"
        self.switching_button.set_visible(label is not None)
        if label:
            self.switching_button.set_label(label)
        self.switching_state = state

    def _on_window_switching(self) -> None:
        from ...core.windows import ExtensionState
        if self.switching_state == ExtensionState.DISABLED:
            ok = self.windows.enable()
        else:
            ok = self.windows.install(self.extension_source)
        if not ok:
            self.add_toast(Adw.Toast(title="Couldn't set up window switching", timeout=4))
        self.show_window_switching()

    # -- History (Idea 2) ---------------------------------------------------------

    def _history_group(self, page) -> None:
        group = self._group(page, "History",
                            "Every reading, with times in UTC. Graphs show it at once, "
                            "even from earlier runs")
        self._switch(group, "history", "Keep History")
        self._spin(group, "history-detail-hours", "Keep Every Reading For (Hours)", 1, 168
                   ).set_subtitle("Then averages per minute for 30 days, per hour after that")
        self._spin(group, "history-max-size", "Maximum Size (MiB)", 16, 4096
                   ).set_subtitle("The oldest readings go first")
        self._watch("history", lambda _k, on: on or self.offer_delete())
        if self.history is not None:
            row = Adw.ActionRow(title="Size on Disk")
            button = Gtk.Button(label="Delete History…", valign=Gtk.Align.CENTER)
            button.add_css_class("destructive-action")
            button.connect("clicked", lambda *_: self.offer_delete())
            row.add_suffix(button)
            group.add(row)
            self.size_row, self.delete_button = row, button
            self.show_size()
        if self.export is not None:
            row = Adw.ActionRow(title="Export Statistics",
                                subtitle="This session's readings as CSV files")
            button = Gtk.Button(label="Export…", valign=Gtk.Align.CENTER)
            button.connect("clicked", lambda *_: self.export())
            row.add_suffix(button)
            group.add(row)
            self.export_button = button

    def show_size(self) -> None:
        from ...core.units import Base, format_bytes
        if self.history is not None:
            size = self.history.size_on_disk()
            self.size_row.set_subtitle(format_bytes(size, Base.BINARY) if size else "Empty")

    def offer_delete(self) -> None:
        """*Delete History…*, and on turning *Keep History* off."""
        if self.history is None or not self.history.size_on_disk():
            return
        alert = Adw.AlertDialog(heading="Delete History?",
                                body="Every reading kept so far is removed. "
                                     "This can't be undone.")
        alert.add_response("keep", "Keep")
        alert.add_response("delete", "Delete")
        alert.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        alert.set_default_response("keep")
        alert.set_close_response("keep")
        alert.connect("response", self._on_delete_response)
        self.delete_alert = alert
        alert.present(self)

    def _on_delete_response(self, alert, response: str) -> None:
        self.delete_alert = None
        if response == "delete":
            self.history.delete()
            self.show_size()

    def open_log_folder(self) -> None:
        self.open_folder(self.log_file.parent)

    def open_folder(self, folder) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        if self.launcher is not None:
            self.launcher(folder)
            return
        from gi.repository import Gio
        Gtk.FileLauncher.new(Gio.File.new_for_path(str(folder))).launch(
            self.get_root(), None, None)

    def _set(self, key: str, value) -> None:
        if self.settings.get(key) != value:
            self.settings.set(key, value)

    def _on_closed(self, *_a) -> None:
        for handler in self._handlers:
            self.settings.disconnect(handler)
        self._handlers = []
        for sub in self.entry_pages.values():
            sub.shutdown()


class EntryPage(Adw.NavigationPage):
    """One sidebar entry's settings: which parts it shows, minimised, and
    its place. Bound both ways to the sidebar's settings."""

    def __init__(self, sidebar, page_id: str, settings) -> None:
        item = sidebar.items[page_id]
        super().__init__(title=item.page.title, tag=page_id)
        self.sidebar = sidebar
        self.page_id = page_id
        self.settings = settings
        self.switches: dict[Field, Adw.SwitchRow] = {}
        prefs = Adw.PreferencesPage()
        shown = Adw.PreferencesGroup(title="Shown in the Sidebar")
        details = {Field.NAME: item.page.title,
                   Field.DESCRIPTION: item.page.description or "None for this entry",
                   Field.USAGE: "Usage and the values beside it",
                   Field.CHART: "Area chart or progress bar"}
        for field in Field:
            row = Adw.SwitchRow(title=FIELD_LABELS[field], subtitle=details[field],
                                active=sidebar.field_shown(page_id, field))
            row.connect("notify::active", lambda r, _p, f=field: self._on_switch(f, r))
            self.switches[field] = row
            shown.add(row)
        prefs.add(shown)
        layout = Adw.PreferencesGroup(title="Layout")
        self.minimized = Adw.SwitchRow(title="Minimized", subtitle="Only the icon and name",
                                       active=page_id in sidebar.minimized_ids())
        self.minimized.connect("notify::active", lambda r, _p: r.get_active() != (
            page_id in sidebar.minimized_ids()) and sidebar.set_minimized(page_id, r.get_active()))
        layout.add(self.minimized)
        self.position = Adw.ActionRow(title="Position")
        self.up = Gtk.Button(icon_name="go-up-symbolic", tooltip_text="Move Up",
                             valign=Gtk.Align.CENTER)
        self.down = Gtk.Button(icon_name="go-down-symbolic", tooltip_text="Move Down",
                               valign=Gtk.Align.CENTER)
        for button, delta in ((self.up, -1), (self.down, 1)):
            button.add_css_class("flat")
            button.connect("clicked", lambda _b, d=delta: sidebar.move(page_id, d))
            self.position.add_suffix(button)
        layout.add(self.position)
        prefs.add(layout)
        self.set_child(Adw.ToolbarView(content=prefs))
        self.get_child().add_top_bar(Adw.HeaderBar())
        self._handlers = [settings.connect_changed(k, lambda *_: self.sync())
                          for k in ("sidebar-hidden-fields", "sidebar-minimized",
                                    "sidebar-order")]
        self.sync()

    def _on_switch(self, field: Field, row) -> None:
        if row.get_active() != self.sidebar.field_shown(self.page_id, field):
            self.sidebar.set_field_shown(self.page_id, field, row.get_active())

    def sync(self) -> None:
        """Follow changes made elsewhere (the sidebar's row menu)."""
        for field, row in self.switches.items():
            shown = self.sidebar.field_shown(self.page_id, field)
            if row.get_active() != shown:
                row.set_active(shown)
        minimized = self.page_id in self.sidebar.minimized_ids()
        if self.minimized.get_active() != minimized:
            self.minimized.set_active(minimized)
        order, pinned = self.sidebar.order(), self.sidebar.pinned_ids()
        self.up.set_sensitive(sidebar_order.can_move(order, self.page_id, -1, pinned))
        self.down.set_sensitive(sidebar_order.can_move(order, self.page_id, 1, pinned))
        rest = [i for i in order if i not in pinned]
        if self.page_id in rest:
            self.position.set_subtitle(f"{rest.index(self.page_id) + 1} of {len(rest)}")

    def shutdown(self) -> None:
        for h in self._handlers:
            self.settings.disconnect(h)
        self._handlers = []
