"""Preferences: every setting from applied immediately."""

from __future__ import annotations

from typing import Sequence

from gi.repository import Adw, Gtk

from ... import GPU_ICON
from ...core.connections import Connections
from ...core.palette import PALETTES, hex_to_rgb
from ...core.profile import is_pinned, profile_of
from ...core.styles import STYLES
from .. import reorder
from ..sidebar_fields import FIELD_LABELS, Field
from ...core.ticker import CUSTOM, CUSTOM_KEY, clamp_range_s, update_interval_ms
from ..time_range import CUSTOM_LABEL, limit_note
from ..toolbar_items import GRAPH_TIME_RANGES
from ..widgets.range_editor import RangeEditor
from ..preferences_layout import APP_COLUMNS, PAGES, PROCESS_COLUMNS  # noqa: F401

UPDATE_INTERVALS = (("1-second", "1 Second"), ("2-seconds", "2 Seconds"),
                    ("3-seconds", "3 Seconds"), ("5-seconds", "5 Seconds"),
                    ("10-seconds", "10 Seconds"))
BASES = [("decimal", "Decimal (kB, MB, GB)"), ("binary", "Binary (KiB, MiB, GiB)")]
TEMPERATURE_UNITS = [("celsius", "Celsius"), ("fahrenheit", "Fahrenheit"), ("kelvin", "Kelvin")]
LOG_LEVELS = [("off", "Off"), ("error", "Errors"), ("warning", "Warnings"),
              ("info", "Information and Performance"), ("debug", "Everything (Debug)")]
METER_TYPES = [("progress-bar", "Progress Bar"), ("graph", "Graph")]
SIDEBAR_STYLES = [("full", "Full"), ("icons", "Icons Only")]

# (The column lists live with the layout; imported here for the dialog's users.)

FIXED_ICON = "changes-prevent-symbolic"     # a padlock: GNOME's "locked for now"
FIXED_TIP = "Fixed while Lightweight Mode is on. Your own choice comes back when it's off."


def fixed_icon() -> Gtk.Image:
    """The padlock before a setting Lightweight Mode fixes, explaining why."""
    icon = Gtk.Image(icon_name=FIXED_ICON, tooltip_text=FIXED_TIP)
    icon.update_property([Gtk.AccessibleProperty.LABEL], ["Fixed by Lightweight Mode"])
    return icon


def fixed_notice() -> Adw.PreferencesGroup:
    """The top of a page with settings Lightweight Mode fixes (hidden
    until one turns up on the page)."""
    group = Adw.PreferencesGroup(visible=False)
    row = Adw.ActionRow(title="Some settings are fixed in Lightweight Mode",
                        subtitle="They're greyed out with a padlock, and your own choices "
                                 "come back when it's off (System → Memory Use)")
    row.add_prefix(Gtk.Image(icon_name=FIXED_ICON))
    group.add(row)
    group.row = row
    return group


class PreferencesDialog(Adw.PreferencesDialog):
    def __init__(self, settings, gpu_controllers: Sequence = (), theme=None,
                 log_file=None, launcher=None, sidebar=None, history=None,
                 export=None, restart=None, windows=None, extension_source=None,
                 background=None) -> None:
        """``theme`` (ui.theme.Theme) only picks light or dark swatches;
        ``log_file`` (a Path) enables *Open Log Folder*, which
        ``launcher(folder)`` opens (default: Gtk.FileLauncher).
        ``history`` (core.history_store.HistoryStore) enables the size used
        and *Delete History…*, ``export()`` the *Export…* button,
        ``restart()`` *Restart Now* after Lightweight Mode changes,
        ``windows`` (core.windows.WindowSwitcher) the *Window Switching*
        row, which installs the extension from ``extension_source``.
        ``background`` (core.background.BackgroundService) the *Record in
        the Background* and *Start at Boot* switches."""
        super().__init__(title="Preferences", search_enabled=True)
        self.settings = settings
        self.theme = theme
        self.log_file = log_file
        self.history = history
        self.export = export
        self.background = background
        self._notices: dict = {}        # page -> its Lightweight Mode notice
        self.delete_alert = None
        self.restart = restart
        self.windows = windows
        self.extension_source = extension_source
        self.launcher = launcher
        # ui.sidebar.StackSidebar: per-entry pages (none in tests that skip it).
        self.sidebar = sidebar
        self.entry_rows: dict[str, Adw.ActionRow] = {}
        self.entry_pages: dict[str, "EntryPage"] = {}
        self.connections = Connections()
        self.rows: dict[str, Gtk.Widget] = {}      # settings key -> row (for tests)
        self._row_counts: dict = {}                 # group -> rows added

        self.gpu_controllers = list(gpu_controllers)
        self.gpu_rows = {}
        builders = self._builders()
        self.pages: dict[str, Adw.PreferencesPage] = {}
        self.groups: dict[str, Adw.PreferencesGroup] = {}
        for spec in PAGES:
            page = self.pages[spec.id] = self._page(spec.title, spec.icon)
            for group_spec in spec.groups:
                group = self._group(page, group_spec.title, group_spec.description)
                self.groups[group_spec.id] = group
                for item in group_spec.items:
                    builders[item](group)
                # A group whose rows all need a service this dialog wasn't
                # given (the history store, the background unit, …).
                group.set_visible(self._row_counts.get(group, 0) > 0)
        self.sidebar_prefs_page = self.pages["sidebar"]
        if background is not None:
            self.background.refresh(self._show_background)

        # Lightweight Mode fixes some preferences while it's on: each one
        # greyed out with a padlock before its title (the padlock's tooltip
        # says why), and a notice at the top of every page that has one.
        for key, row in self.rows.items():
            if is_pinned(settings, key):
                row.set_sensitive(False)
                row.add_prefix(fixed_icon())
                notice = self._notices.get(row.get_ancestor(Adw.PreferencesPage))
                if notice is not None:
                    notice.set_visible(True)
        self.connect("closed", self._on_closed)

    def _builders(self) -> dict:
        """Each layout item's row builder: ``item → build(group)``."""
        sw, combo, spin = self._switch, self._combo, self._spin

        def columns(title, prefix, columns):
            def build(group):
                expander = Adw.ExpanderRow(title=title,
                                           subtitle="Which columns the table shows")
                self._add(group, expander)
                for key, label in columns:
                    sw(expander, f"{prefix}-show-{key}", label)
            return build

        def when(present, build):
            return build if present else (lambda _g: None)

        return {
            # Appearance
            "color-scheme": self._style_row,
            "palette": self._palette_row,
            "show-graph-axes": lambda g: sw(g, "show-graph-axes", "Show Graph Axes",
                                            "Percentage and time labels with ticks on "
                                            "percentage graphs"),
            "show-graph-grids": lambda g: sw(g, "show-graph-grids", "Show Graph Grids"),
            "graph-time-range": lambda g: combo(
                g, "graph-time-range", "Graph Time Range",
                [*GRAPH_TIME_RANGES, (CUSTOM, CUSTOM_LABEL)],
                "How much history graphs show, whatever the update interval"),
            "custom-range": self._custom_range_row,
            "base": lambda g: combo(g, "base", "Data Unit Prefix", BASES),
            "network-bits": lambda g: sw(g, "network-bits",
                                         "Show Network Speeds in Bits per Second"),
            "temperature-unit": lambda g: combo(g, "temperature-unit", "Temperature Unit",
                                                TEMPERATURE_UNITS),
            # Sidebar
            "sidebar-style": lambda g: combo(g, "sidebar-style", "Style", SIDEBAR_STYLES,
                                             "Icons Only shows each entry's icon; hover for "
                                             "its name and usage"),
            "sidebar-details": lambda g: sw(g, "sidebar-details", "Show Usage Details",
                                            "If enabled, the usage along with other "
                                            "information will be displayed"),
            "sidebar-description": lambda g: sw(g, "sidebar-description",
                                                "Show Device Descriptions",
                                                "If enabled, a device identifier like its "
                                                "name or device type will be displayed"),
            "sidebar-meter-type": lambda g: combo(g, "sidebar-meter-type", "Meter Type",
                                                  METER_TYPES),
            "sidebar-entries": self._entry_rows,
            # Tables
            "normalize-cpu-usage": lambda g: sw(
                g, "normalize-cpu-usage", "Normalize Processor Usage",
                "Apps and Processes show each one's share of the whole processor, "
                "so they add up to the total. Off: one fully busy core is 100 %"),
            "detailed-priority": lambda g: sw(g, "detailed-priority", "Show Niceness Values",
                                              "Processes show priorities as niceness, for "
                                              "more fine-grained adjustments"),
            "apps-columns": columns("Apps", "apps", APP_COLUMNS),
            "processes-columns": columns("Processes", "processes", PROCESS_COLUMNS),
            # Recording
            "history": self._history_switch,
            "history-detail-hours": lambda g: spin(
                g, "history-detail-hours", "Keep Every Reading For (Hours)", 1, 168
            ).set_subtitle("Then averages per minute for 30 days, per hour after that"),
            "history-max-size": lambda g: spin(
                g, "history-max-size", "Maximum Size (MiB)", 16, 4096
            ).set_subtitle("The oldest readings go first"),
            "background": when(self.background is not None, self._background_rows),
            "export-hardware-addresses": when(self.export is not None, lambda g: sw(
                g, "export-hardware-addresses", "Include Hardware Addresses",
                "Network cards' addresses identify this computer")),
            "recording": when(self.background is not None, self._recording_row),
            "history-size": when(self.history is not None, self._size_row),
            "export": when(self.export is not None, self._export_row),
            # Devices
            "show-virtual-drives": lambda g: sw(g, "show-virtual-drives", "Show Virtual Drives",
                                                "Virtual drives are for example ZFS volumes "
                                                "or mapped devices"),
            "show-virtual-network-interfaces": lambda g: sw(
                g, "show-virtual-network-interfaces", "Show Virtual Network Interfaces",
                "Virtual network interfaces are for example bridges or VPN tunnels"),
            "gpu-sources": self._gpu_rows,
            "gpu-elevate": lambda g: sw(g, "gpu-elevate",
                                        "Start Detailed Statistics with Administrator Rights",
                                        "Asks for your password when the app starts, if the "
                                        "detailed data source needs it"),
            "intel-gpu-top-interval": lambda g: combo(
                g, "intel-gpu-top-interval", "intel_gpu_top Update Interval",
                [("", "Same as Update Interval"), *UPDATE_INTERVALS]),
            # System
            "lightweight": self._lightweight_rows,
            "update-interval": lambda g: combo(g, "update-interval", "Update Interval",
                                               UPDATE_INTERVALS,
                                               "How often Proccoli takes readings. Shorter "
                                               "intervals use more processor time"),
            "auth-at-launch": lambda g: sw(g, "auth-at-launch",
                                           "Ask for Administrator Rights at Start-Up",
                                           "Offers to unlock memory properties, detailed GPU "
                                           "statistics and other users' drive I/O; each page "
                                           "also has its own button"),
            "window-switching": when(self.windows is not None, self._window_switching_row),
            "log-level": lambda g: combo(g, "log-level", "Log Level", LOG_LEVELS),
            "log-max-size": lambda g: spin(g, "log-max-size", "Maximum Log Size (KiB)",
                                           64, 65536).set_subtitle(
                "One older log is kept too, so at most twice this on disk"),
            "log-performance-interval": lambda g: spin(
                g, "log-performance-interval", "Performance Line Every (Minutes)", 0, 1440
            ).set_subtitle("0 turns it off"),
            "log-file": when(self.log_file is not None, self._log_file_row),
        }

    def _log_file_row(self, group) -> None:
        row = Adw.ActionRow(title="Log File", subtitle=str(self.log_file))
        button = Gtk.Button(label="Open Folder", valign=Gtk.Align.CENTER)
        button.connect("clicked", lambda *_: self.open_log_folder())
        row.add_suffix(button)
        self._add(group, row)
        self.log_button = button

    def _gpu_rows(self, group) -> None:
        for controller in self.gpu_controllers:
            self.gpu_rows[controller.gpu.pci_slot] = self._gpu_row(group, controller)
        if not self.gpu_controllers:
            self._add(group, Adw.ActionRow(title="No GPUs found"))

    def _custom_range_row(self, group) -> None:
        """*Custom…*'s number and unit, shown only while it's chosen."""
        row = Adw.ActionRow(title="Custom Time Range",
                            subtitle="From 10 seconds to 30 days")
        self.range_editor = RangeEditor(self.settings.get(CUSTOM_KEY), self._set_custom_range)
        row.add_suffix(self.range_editor)
        self._add(group, row)
        self.rows[CUSTOM_KEY] = row
        self.custom_range_row = row

        def follow(*_a):
            row.set_visible(self.settings.get("graph-time-range") == CUSTOM)
            seconds = self.settings.get(CUSTOM_KEY)
            if self.range_editor.seconds() != seconds and not row.has_css_class("error"):
                self.range_editor.set_seconds(seconds)
        follow()
        self._watch("graph-time-range", follow)
        self._watch(CUSTOM_KEY, follow)

    def _set_custom_range(self, seconds: int) -> None:
        """Store what was typed, clamped; the subtitle says when it was."""
        note = limit_note(seconds, update_interval_ms(self.settings))
        self.custom_range_row.set_subtitle(note or "From 10 seconds to 30 days")
        if note:
            self.custom_range_row.add_css_class("error")
        else:
            self.custom_range_row.remove_css_class("error")
        self._set(CUSTOM_KEY, clamp_range_s(seconds, update_interval_ms(self.settings)))

    # -- building blocks ----------------------------------------------------------

    def _page(self, title: str, icon: str) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(title=title, icon_name=icon)
        self.add(page)
        if profile_of(self.settings).is_lightweight:
            # First on the page; shown once a fixed setting turns up on it.
            notice = fixed_notice()
            page.add(notice)
            self._notices[page] = notice
        return page

    def _add(self, container, row) -> None:
        """A row into a group, or into an expander row (the column lists)."""
        if isinstance(container, Adw.ExpanderRow):
            container.add_row(row)
        else:
            container.add(row)
            self._row_counts[container] = self._row_counts.get(container, 0) + 1

    def _group(self, page, title: str, description: str = "") -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(title=title, description=description)
        page.add(group)
        return group

    def _watch(self, key: str, callback) -> None:
        self.connections.watch(self.settings, key, callback)

    def _switch(self, group, key: str, title: str, subtitle: str = "") -> Adw.SwitchRow:
        row = Adw.SwitchRow(title=title, subtitle=subtitle,
                            active=self.settings.get(key))
        row.connect("notify::active", lambda r, _p: self._set(key, r.get_active()))
        self._watch(key, lambda _k, v: row.get_active() != v and row.set_active(v))
        self._add(group, row)
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
        self._add(group, row)
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
        self._add(group, row)
        self.rows[key] = row
        return row

    def _gpu_row(self, group, controller) -> Adw.ActionRow:
        """A GPU's detailed-statistics switch, or a note that it has none."""
        title = controller.info.description or controller.gpu.name
        if controller.detail_class is None:
            row = Adw.ActionRow(title=title, subtitle=f"{controller.gpu.pci_slot} · "
                                "No detailed data source available")
            self._add(group, row)
            return row
        name = controller.detail_class.display_name
        if controller.needs_elevation:
            name += ", needs administrator rights"
        row = Adw.SwitchRow(title=title, subtitle=f"{controller.gpu.pci_slot} · {name}",
                            active=controller.details_enabled)
        row.connect("notify::active",
                    lambda r, _p: r.get_active() != controller.details_enabled
                    and controller.set_details_enabled(r.get_active()))
        self._add(group, row)
        return row

    # -- the Sidebar page ------------------------------------------------

    def _entry_rows(self, group) -> None:
        """A row per movable sidebar entry, each opening its own subpage."""
        self.entries_group = group
        # The group (and its note) shows even with no movable entry.
        self._row_counts[group] = self._row_counts.get(group, 0) + 1
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
            self._add(group, row)

    def open_entry(self, page_id: str) -> "EntryPage":
        """Show (push) the sub-page of one sidebar entry."""
        sub = EntryPage(self.sidebar, page_id, self.settings)
        self.entry_pages[page_id] = sub
        self.push_subpage(sub)
        return sub

    # -- Lightweight Mode --------------------------------------------------

    def _lightweight_rows(self, group) -> None:
        """The switch shows the mode Proccoli runs in now (also when it was
        started with ``--lightweight``); flipping it chooses the mode for the
        next start, which *Restart to Apply* says and offers."""
        running = profile_of(self.settings).is_lightweight
        row = Adw.SwitchRow(title="Lightweight Mode", active=running,
                            subtitle="As little memory as possible: pages are built when you "
                                     "open them, the Overview is a list, and charts, icons and "
                                     "GPU details are kept to a minimum")
        row.connect("notify::active", lambda r, _p: self._choose_lightweight(r.get_active()))
        self._add(group, row)
        self.rows["lightweight"] = row
        row = Adw.ActionRow(title="Restart to Apply",
                            subtitle="Proccoli starts again with the new mode")
        button = Gtk.Button(label="Restart Now", valign=Gtk.Align.CENTER)
        button.add_css_class("suggested-action")
        button.connect("clicked", lambda *_: self.restart and self.restart())
        row.add_suffix(button)
        self._add(group, row)
        self.restart_row, self.restart_button = row, button
        self._watch("lightweight", lambda *_: self._show_restart())
        self._show_restart()

    def _choose_lightweight(self, on: bool) -> None:
        """The mode for the next start (the setting)."""
        self._set("lightweight", on)
        self._show_restart()

    def _show_restart(self) -> None:
        """While the next start's mode differs from this one's."""
        running = profile_of(self.settings).is_lightweight
        pending = bool(self.settings.get("lightweight")) != running
        self.restart_row.set_visible(self.restart is not None and pending)
        if pending:
            self.restart_row.set_subtitle(
                "Lightweight Mode turns " + ("off" if running else "on") + " at the next start")

    # -- Window Switching ---------------------------------------------------

    def _window_switching_row(self, group) -> None:
        row = Adw.ActionRow(title="Proccoli Window Switching")
        button = Gtk.Button(valign=Gtk.Align.CENTER)
        button.add_css_class("suggested-action")
        button.connect("clicked", lambda *_: self._on_window_switching())
        row.add_suffix(button)
        self._add(group, row)
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

    # -- History ---------------------------------------------------------

    def _history_switch(self, group) -> None:
        self._switch(group, "history", "Keep History")
        self._watch("history", lambda _k, on: on or self.offer_delete())

    def _size_row(self, group) -> None:
        row = Adw.ActionRow(title="Size on Disk")
        button = Gtk.Button(label="Delete History…", valign=Gtk.Align.CENTER)
        button.add_css_class("destructive-action")
        button.connect("clicked", lambda *_: self.offer_delete())
        row.add_suffix(button)
        self._add(group, row)
        self.size_row, self.delete_button = row, button
        self.show_size()

    def _export_row(self, group) -> None:
        row = Adw.ActionRow(title="Export Statistics",
                            subtitle="This session's readings as CSV files, with what "
                                     "each device is")
        button = Gtk.Button(label="Export…", valign=Gtk.Align.CENTER)
        button.connect("clicked", lambda *_: self.export())
        row.add_suffix(button)
        self._add(group, row)
        self.export_button = button

    # -- recording in the background -------------------------------------------

    def _background_rows(self, group) -> None:
        self.background_row = Adw.SwitchRow(
            title="Record in the Background",
            subtitle="Keeps the history while Proccoli is closed, from when you log in")
        self.linger_row = Adw.SwitchRow(
            title="Start at Boot",
            subtitle="Also records before you log in and after you log out")
        for row in (self.background_row, self.linger_row):
            self._add(group, row)
        self._background_busy = True                 # until the first answer
        self.background_row.connect("notify::active", lambda r, _p: self._set_background(
            r.get_active()))
        self.linger_row.connect("notify::active", lambda r, _p: self._set_linger(
            r.get_active()))
        self._watch("history", lambda *_: self._show_background(self.background.state))

    def _recording_row(self, group) -> None:
        self.recording_row = Adw.ActionRow(title="Recording")
        self._add(group, self.recording_row)

    def _show_background(self, state) -> None:
        from ...core.background import status_text
        self._background_busy = True
        self.background_row.set_active(state.enabled)
        self.background_row.set_sensitive(state.available)
        if not state.available:
            self.background_row.set_subtitle(state.reason)
        self.linger_row.set_active(state.linger)
        self.linger_row.set_sensitive(state.available and state.enabled)
        self._background_busy = False
        history = self.history
        writer = history.writer_info() if history is not None else None
        here = bool(history is not None and history.writer and history.session is not None)
        self.recording_row.set_subtitle(status_text(writer, here,
                                                    bool(self.settings.get("history")), state))

    def _set_background(self, on: bool) -> None:
        if not self._background_busy and on != self.background.state.enabled:
            self._background_busy = True
            self.background.set_enabled(on, self._show_background)

    def _set_linger(self, on: bool) -> None:
        if not self._background_busy and on != self.background.state.linger:
            self._background_busy = True
            self.background.set_linger(on, self._show_background)

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
        self.connections.disconnect_all()
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
        self.connections = Connections()
        self.connections.watch(settings, ("sidebar-hidden-fields", "sidebar-minimized",
                                          "sidebar-order"), lambda *_: self.sync())
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
        self.up.set_sensitive(reorder.can_move(order, self.page_id, -1, pinned))
        self.down.set_sensitive(reorder.can_move(order, self.page_id, 1, pinned))
        rest = [i for i in order if i not in pinned]
        if self.page_id in rest:
            self.position.set_subtitle(f"{rest.index(self.page_id) + 1} of {len(rest)}")

    def shutdown(self) -> None:
        self.connections.disconnect_all()
