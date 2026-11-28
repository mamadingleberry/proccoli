"""Preferences: every setting from applied immediately."""

from __future__ import annotations

from typing import Sequence

from gi.repository import Adw, Gtk

from ...core.connections import Connections
from ...core.profile import is_pinned
from .. import sidebar_groups as groups
from ..sidebar_fields import FIELD_LABELS, Field
from ...core.ticker import CUSTOM, CUSTOM_KEY, clamp_range_s, update_interval_ms
from ..time_range import CUSTOM_LABEL, limit_note
from ..toolbar_items import GRAPH_TIME_RANGES
from ..widgets.range_editor import RangeEditor
from ..preferences_layout import APP_COLUMNS, PAGES, PROCESS_COLUMNS  # noqa: F401
from .preferences_rows import FIXED_ICON, FIXED_TIP, RowBuilders, fixed_icon, fixed_notice  # noqa: F401
from .preferences_appearance import AppearanceRows
from .preferences_history import HistoryRows
from .preferences_system import SystemRows

UPDATE_INTERVALS = (("1-second", "1 Second"), ("2-seconds", "2 Seconds"),
                    ("3-seconds", "3 Seconds"), ("5-seconds", "5 Seconds"),
                    ("10-seconds", "10 Seconds"))
BASES = [("decimal", "Decimal (kB, MB, GB)"), ("binary", "Binary (KiB, MiB, GiB)")]
TEMPERATURE_UNITS = [("celsius", "Celsius"), ("fahrenheit", "Fahrenheit"), ("kelvin", "Kelvin")]
LOG_LEVELS = [("off", "Off"), ("error", "Errors"), ("warning", "Warnings"),
              ("info", "Information and Performance"), ("debug", "Everything (Debug)")]
GRAPH_TYPES = [("progress-bar", "Progress Bar"), ("graph", "Graph")]
# An entry's own: the default first ("Default (Graph)", named when shown).
ENTRY_GRAPH_TYPES = [("default", "Default"), ("graph", "Graph"), ("progress-bar", "Progress Bar")]
SIDEBAR_STYLES = [("full", "Full"), ("icons", "Icons Only")]

# (The column lists live with the layout; imported here for the dialog's users.)

class PreferencesDialog(Adw.PreferencesDialog, RowBuilders, AppearanceRows, HistoryRows, SystemRows):
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
            "sidebar-meter-type": lambda g: combo(g, "sidebar-meter-type", "Graph Type",
                                                  GRAPH_TYPES, "Each entry can have its own"),
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

    # -- Window Switching ---------------------------------------------------

    # -- History ---------------------------------------------------------

    # -- recording in the background -------------------------------------------

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
        # Its own Graph Type, or the default one (Sidebar → All Entries).
        self.graph_type = Adw.ComboRow(title="Graph Type",
                                       model=Gtk.StringList.new([label for _, label in
                                                                 ENTRY_GRAPH_TYPES]))
        self.graph_type.connect("notify::selected", lambda r, _p: self._on_graph_type(r))
        layout.add(self.graph_type)
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
                                          "sidebar-order", "sidebar-graph-types",
                                          "sidebar-meter-type"), lambda *_: self.sync())
        self.sync()

    def _on_graph_type(self, row) -> None:
        choice = ENTRY_GRAPH_TYPES[row.get_selected()][0]
        if choice != self.sidebar.graph_type_choice(self.page_id):
            self.sidebar.set_graph_type(self.page_id, choice)

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
        default = dict(GRAPH_TYPES)[self.settings.get("sidebar-meter-type")]
        self.graph_type.get_model().splice(0, 1, [f"Default ({default})"])
        index = [c for c, _ in ENTRY_GRAPH_TYPES].index(
            self.sidebar.graph_type_choice(self.page_id))
        if self.graph_type.get_selected() != index:
            self.graph_type.set_selected(index)
        order, pinned = self.sidebar.order(), self.sidebar.pinned_ids()
        group_of = self.sidebar.group_of()
        self.up.set_sensitive(groups.can_move(order, self.page_id, -1, pinned, group_of))
        self.down.set_sensitive(groups.can_move(order, self.page_id, 1, pinned, group_of))
        rest = [i for i in order if i not in pinned]
        if self.page_id in rest:
            self.position.set_subtitle(f"{rest.index(self.page_id) + 1} of {len(rest)}")

    def shutdown(self) -> None:
        self.connections.disconnect_all()
