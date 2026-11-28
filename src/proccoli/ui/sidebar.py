"""The resource sidebar: one row per page, each showing the page's name,
description and (for devices) its usage and a meter.

Follows the sidebar preferences: *Show Usage Details*, *Show Device
Descriptions* and *Graph Type* (each entry may have its own). Overview, Apps and Processes stay
at the top;
the user can reorder the rest (row menu or drag and drop) and minimise
them to icon and name (``sidebar-order``, ``sidebar-minimized``; the order
rules are in ``reorder.py``). In the icons-only style (``set_compact``,
``sidebar_style.py``) every row shows just its icon, with its name,
description and usage as hover text.
"""

from __future__ import annotations

from typing import Optional

from gi.repository import GObject, Gtk, Pango

from .sidebar_fields import (GRAPH_TYPES_SETTING, Field, graph_type_for, hidden,
                             set_graph_type, visible)
from .sidebar_style import compact_tooltip
from .chart_settings import ChartKind, ChartSettings
from .page import ResourcePage, SidebarSummary
from .widgets.meter import Meter, MeterType
from .sidebar_arrangement import PINNED, UNCHARTED, SidebarArrangement
from .sidebar_groups import group_for
from .sidebar_row_menu import SidebarRowMenu


NEST_INDENT = 16          # a device beneath its group
ICON_SIZE = 16
ICON_SPACING = 10


class StackSidebarItem(Gtk.ListBoxRow):
    def __init__(self, page: ResourcePage, charts: Optional[ChartSettings] = None,
                 compact: bool = False) -> None:
        """``charts`` binds the meter's graph when it's built;
        ``compact``: icons only from the start (no meter is built)."""
        super().__init__()
        self.charts = charts
        self.page: Optional[ResourcePage] = None
        self._summary_handler = 0
        self.show_details = True
        self.show_description = True
        self.compact = compact           # icons only (sidebar-style)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        for side in ("top", "bottom"):
            getattr(box, f"set_margin_{side}")(6)
        # The icon sits left of the name; everything else lines up under the
        # name, as in Resources.
        self.top = top = Gtk.Box(spacing=ICON_SPACING)
        self.image = Gtk.Image(pixel_size=ICON_SIZE)
        self.label = Gtk.Label(xalign=0, hexpand=True,
                               ellipsize=Pango.EllipsizeMode.END)
        self.label.add_css_class("heading")
        # A group's entry: show or hide its devices.
        self.expander = Gtk.Button(icon_name="pan-down-symbolic", valign=Gtk.Align.CENTER,
                                   visible=False, tooltip_text="Hide Devices")
        self.expander.add_css_class("flat")
        self.expander.add_css_class("circular")
        self.expanded = True
        self.nested = False                  # a device beneath its group
        top.append(self.image)
        top.append(self.label)
        top.append(self.expander)
        # Minimise / expand (movable entries only; set_page shows it).
        self.minimize_button = Gtk.Button(icon_name="pan-down-symbolic",
                                          valign=Gtk.Align.CENTER, visible=False)
        self.minimize_button.add_css_class("flat")
        self.minimize_button.add_css_class("circular")
        self.minimized = False
        self.hidden_fields: set = set()
        top.append(self.minimize_button)
        box.append(top)

        self.detail_label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.detail_label.add_css_class("caption")
        self.detail_label.add_css_class("dim-label")
        self.usage_label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.usage_label.add_css_class("caption")
        self.usage_label.add_css_class("numeric")
        # The meter is built when the entry first shows one: an
        # icons-only sidebar never does.
        self._meter: Optional[Meter] = None
        self.meter_type = MeterType.GRAPH
        self.entry_color: Optional[int] = None
        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                          margin_start=ICON_SIZE + ICON_SPACING)
        details.append(self.detail_label)
        details.append(self.usage_label)
        self.details = details
        box.append(details)
        self.set_child(box)
        self.set_page(page)

    @property
    def page_id(self) -> str:
        return self.page.page_id

    @property
    def has_meter(self) -> bool:
        return self._meter is not None

    @property
    def meter(self) -> Meter:
        """The usage meter, built on first use."""
        if self._meter is None:
            meter = Meter(self.meter_type)
            meter.set_visible(False)              # update shows it when wanted
            meter.progress.update_property([Gtk.AccessibleProperty.LABEL], ["Usage"])
            meter.set_entry_color(self.entry_color)
            self.details.append(meter)
            if self.charts is not None:
                self.charts.bind(meter.graph, ChartKind.METER, show_axes=meter.set_show_axes)
            self._meter = meter
        return self._meter

    def set_entry_color(self, index: Optional[int]) -> None:
        self.entry_color = index
        if self._meter is not None:
            self._meter.set_entry_color(index)

    def release_meter(self) -> None:
        if self._meter is not None and self.charts is not None:
            self.charts.unbind(self._meter.graph)

    def set_page(self, page: ResourcePage) -> None:
        """Show ``page`` (also used when a page is swapped in place)."""
        if self.page is not None and self._summary_handler:
            self.page.disconnect(self._summary_handler)
        self.page = page
        # a group's arrow shows or hides its devices instead
        self.minimize_button.set_visible(self.movable and not self.compact and not page.is_group)
        self.expander.set_visible(page.is_group and not self.compact)
        self.label.set_label(page.title)
        self.image.set_from_icon_name(page.icon_name)
        self.detail_label.set_label(page.description)
        self.update_property([Gtk.AccessibleProperty.LABEL], [page.title])
        self._summary_handler = page.connect("summary-changed",
                                             lambda *_: self.update())
        self.update()

    @property
    def movable(self) -> bool:
        return self.page.kind not in PINNED

    def set_minimized(self, minimized: bool) -> None:
        """Only icon and name (description, usage and chart hidden)."""
        self.minimized = minimized and self.movable
        self.minimize_button.set_icon_name("pan-end-symbolic" if self.minimized
                                           else "pan-down-symbolic")
        text = "Expand" if self.minimized else "Minimize"
        self.minimize_button.set_tooltip_text(text)
        self.minimize_button.update_property([Gtk.AccessibleProperty.LABEL],
                                             [f"{text} {self.page.title}"])
        self.update()

    def set_hidden_fields(self, fields: set) -> None:
        """This entry's own choices (``sidebar_fields``; pinned entries
        show everything)."""
        self.hidden_fields = set(fields) if self.movable else set()
        self.update()

    def shows(self, field: Field) -> bool:
        if self.compact:
            return False                 # only the icon; the rest is hover text
        return visible(field, self.hidden_fields, show_details=self.show_details,
                       show_description=self.show_description, minimized=self.minimized)

    def set_compact(self, compact: bool) -> None:
        """Icons only: the icon, centred, with the rest as hover text."""
        self.compact = compact
        self.top.set_halign(Gtk.Align.CENTER if compact else Gtk.Align.FILL)
        self.minimize_button.set_visible(self.movable and not compact and not self.page.is_group)
        self.expander.set_visible(self.page.is_group and not compact)
        self._indent()
        self.update()

    def set_nested(self, nested: bool) -> None:
        """A device beneath its group: indented (not in icons-only)."""
        self.nested = nested
        self._indent()

    def _indent(self) -> None:
        self.get_child().set_margin_start(NEST_INDENT if self.nested and not self.compact else 0)

    def set_expanded(self, expanded: bool) -> None:
        """A group's arrow: down while its devices show, right while hidden."""
        self.expanded = expanded
        self.expander.set_icon_name("pan-down-symbolic" if expanded else "pan-end-symbolic")
        self.expander.set_tooltip_text("Hide Devices" if expanded else "Show Devices")

    def set_style(self, show_details: bool, show_description: bool,
                  meter_type: str) -> None:
        self.show_details = show_details
        self.show_description = show_description
        self.meter_type = MeterType(meter_type)
        if self._meter is not None:
            self._meter.set_meter_type(self.meter_type)
        self.update()

    def update(self) -> None:
        summary: Optional[SidebarSummary] = self.page.sidebar_summary()
        if self.detail_label.get_label() != self.page.description:
            self.detail_label.set_label(self.page.description)   # a group's count changes
        self.label.set_visible(self.shows(Field.NAME))
        self.detail_label.set_visible(self.shows(Field.DESCRIPTION)
                                      and bool(self.page.description))
        has_summary = summary is not None
        self.usage_label.set_visible(has_summary and self.shows(Field.USAGE)
                                     and bool(summary.text()))
        # Without a percentage there's nothing for a progress bar to show;
        # the graph meter still works, scaled to the data.
        graph_mode = self.meter_type == MeterType.GRAPH
        wants_meter = (has_summary and self.shows(Field.CHART)
                       and (summary.usage is not None or (graph_mode and bool(summary.series))))
        if wants_meter or self._meter is not None:
            self.meter.set_visible(wants_meter)
        self.details.set_visible(self.detail_label.get_visible()
                                 or self.usage_label.get_visible() or wants_meter)
        text = summary.text() if has_summary else None
        tooltip = (compact_tooltip(self.page.title, self.page.description, text)
                   if self.compact else None)
        if self.get_tooltip_text() != tooltip:
            self.set_tooltip_text(tooltip)
        if not has_summary:
            return
        self.usage_label.set_label(text)
        self.update_property([Gtk.AccessibleProperty.DESCRIPTION], [text])
        meter = self._meter
        if meter is None:
            return
        meter.set_fraction(None if summary.usage is None else summary.usage / 100)
        if meter.graph.series != summary.series:
            meter.set_series(summary.series)
        if meter.graph.max_value != summary.max_value:
            meter.graph.set_max(summary.max_value)
        meter.refresh()


class StackSidebar(Gtk.ScrolledWindow, SidebarArrangement, SidebarRowMenu):
    """Rows sorted by ``ResourcePage.sort_key()``; selecting one shows that
    page in the bound ``Gtk.Stack`` and emits ``page-selected``."""

    __gsignals__ = {
        "page-selected": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        # The charted entries, their order or their colors changed
        # (``entries()``); the Overview page follows it.
        "entries-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, settings=None) -> None:
        super().__init__(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        self.settings = settings
        self.stack: Optional[Gtk.Stack] = None
        self.items: dict[str, StackSidebarItem] = {}
        self._syncing = False
        self._rank: dict[str, int] = {}
        # Without settings (tests), the user's order lives here.
        self._saved_order: list[str] = []
        self._minimized: set[str] = set()
        self._hidden_fields: dict[str, list[str]] = {}
        self._collapsed: set[str] = set()
        self.colors: dict[str, int] = {}      # page ID -> entry color index
        self.compact = False                  # icons only (sidebar_style.py)
        self._install_actions()

        self.list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.list_box.add_css_class("navigation-sidebar")
        self.list_box.set_sort_func(self._sort)
        self.list_box.connect("row-selected", self._on_row_selected)
        self.set_child(self.list_box)

        # The meters' axes and time span.
        self.charts = ChartSettings(settings) if settings is not None else None
        if settings is not None:
            for key in ("sidebar-details", "sidebar-description", "sidebar-meter-type",
                        GRAPH_TYPES_SETTING):
                settings.connect_changed(key, lambda *_: self._apply_style())
            settings.connect_changed("sidebar-order", lambda *_: self._rearrange())
            settings.connect_changed("sidebar-minimized", lambda *_: self._apply_minimized())
            settings.connect_changed("sidebar-collapsed-groups",
                                     lambda *_: self._apply_groups(self.group_of()))
            settings.connect_changed("sidebar-hidden-fields", lambda *_: self._apply_fields())

    # -- items ------------------------------------------------------------------

    def add_item(self, page: ResourcePage) -> StackSidebarItem:
        if page.page_id in self.items:
            raise ValueError(f"duplicate page {page.page_id!r}")
        item = StackSidebarItem(page, self.charts, self.compact)
        item.expander.connect("clicked", lambda *_: self.toggle_group(item.page_id))
        self.items[page.page_id] = item
        item.set_compact(self.compact)
        self._style(item)
        self._wire_row(item)
        self._rearrange(sort=False)
        self.list_box.append(item)
        item.set_minimized(page.page_id in self.minimized_ids())
        item.set_hidden_fields(hidden(self.hidden_fields_map(), page.page_id))
        self.assign_colors()
        return item

    def remove_item(self, page_id: str) -> None:
        item = self.items.pop(page_id)
        item.release_meter()
        self.list_box.remove(item)
        self._rearrange()
        self.assign_colors()

    def replace_page(self, page: ResourcePage) -> None:
        self.items[page.page_id].set_page(page)
        self._rearrange()
        self.assign_colors()

    def set_compact(self, compact: bool) -> None:
        """Icons only (True) or full entries, for every row."""
        self.compact = compact
        for item in self.items.values():
            item.set_compact(compact)

    def default_order(self) -> list[str]:
        """The built-in order (by kind, then name), ignoring the user's."""
        return [i for i, _ in sorted(self.items.items(), key=lambda kv: kv[1].page.sort_key())]

    # -- each entry's Graph Type ------------------------------------------------------

    def graph_type_overrides(self) -> dict[str, str]:
        return dict(self.settings.get("sidebar-graph-types")) if self.settings is not None else {}

    def graph_type_choice(self, page_id: str) -> str:
        """``page_id``'s own Graph Type, or ``"default"``."""
        return self.graph_type_overrides().get(page_id, "default")

    def set_graph_type(self, page_id: str, choice: str) -> None:
        """Give ``page_id`` its own Graph Type, or ``"default"`` to follow
        the default again."""
        if self.settings is not None:
            self.settings.set("sidebar-graph-types",
                              set_graph_type(self.graph_type_overrides(), page_id, choice))

    def group_of(self) -> dict[str, str]:
        """``{device page ID: its group's page ID}`` for devices whose group
        entry is in the sidebar."""
        out = {}
        for page_id, item in self.items.items():
            spec = None if item.page.is_group else group_for(item.page.kind)
            if spec is not None and spec.page_id in self.items:
                out[page_id] = spec.page_id
        return out

    def assign_colors(self) -> None:
        """Give every entry with a chart its own palette color, numbered
        in the built-in order, so moving an entry keeps its color (Apps
        and Processes have none)."""
        index = 0
        self.colors = {}
        for page_id in self.default_order():
            item = self.items[page_id]
            if item.page.is_group:
                continue                      # takes its first device's, below
            if item.page.kind in UNCHARTED:
                item.set_entry_color(None)
            else:
                item.set_entry_color(index)
                item.page.set_entry_color(index)
                self.colors[page_id] = index
                index += 1
        group_of = self.group_of()
        for page_id, item in self.items.items():
            if item.page.is_group:
                first = next((c for c in self.display_order() if group_of.get(c) == page_id), None)
                color = self.colors.get(first)
                item.set_entry_color(color)
                item.page.set_entry_color(color)
        self.emit("entries-changed")

    def entries(self) -> list[tuple[ResourcePage, int]]:
        """``(page, color index)`` of every charted entry, in display
        order (what the Overview page shows)."""
        ids = sorted(self.colors, key=lambda i: self._rank.get(i, len(self._rank)))
        return [(self.items[i].page, self.colors[i]) for i in ids]

    def display_order(self) -> list[str]:
        """Every page ID in the order the sidebar shows them, already right
        while a row is being added (``order()`` reads the rows)."""
        big = len(self._rank)
        return sorted(self.items, key=lambda i: (self._rank.get(i, big),
                                                 self.items[i].page.sort_key()))

    def order(self) -> list[str]:
        """Page IDs in display order."""
        ids, row = [], self.list_box.get_first_child()
        while row is not None:
            if isinstance(row, StackSidebarItem):
                ids.append(row.page_id)
            row = row.get_next_sibling()
        return ids

    def select(self, page_id: str) -> None:
        item = self.items.get(page_id)
        if item is not None and self.list_box.get_selected_row() is not item:
            self.list_box.select_row(item)

    def selected_id(self) -> Optional[str]:
        row = self.list_box.get_selected_row()
        return row.page_id if row is not None else None

    # -- stack binding --------------------------------------------------------------

    def bind_stack(self, stack: Gtk.Stack) -> None:
        self.stack = stack
        stack.connect("notify::visible-child-name", self._on_stack_changed)

    def _on_row_selected(self, _box, row) -> None:
        if row is None or self._syncing:
            return
        if self.stack is not None:
            self._syncing = True
            self.stack.set_visible_child_name(row.page_id)
            self._syncing = False
        self.emit("page-selected", row.page_id)

    def _on_stack_changed(self, stack, _pspec) -> None:
        if self._syncing:
            return
        name = stack.get_visible_child_name()
        if name:
            self._syncing = True
            self.select(name)
            self._syncing = False

    # -- the user's order and minimised entries ------------------------

    # -- row menu and drag and drop -------------------------------------------------------

    # -- style --------------------------------------------------------------------------

    def _style(self, item: StackSidebarItem) -> None:
        if self.settings is None:
            return
        item.set_style(self.settings.get("sidebar-details"),
                       self.settings.get("sidebar-description"),
                       graph_type_for(item.page_id, self.graph_type_overrides(),
                                      self.settings.get("sidebar-meter-type")))

    def _apply_style(self) -> None:
        for item in self.items.values():
            self._style(item)

    def _sort(self, a: StackSidebarItem, b: StackSidebarItem) -> int:
        big = len(self._rank)
        ka = (self._rank.get(a.page_id, big), a.page.sort_key())
        kb = (self._rank.get(b.page_id, big), b.page.sort_key())
        return (ka > kb) - (ka < kb)
