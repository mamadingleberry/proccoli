"""The resource sidebar: one row per page, each showing the page's name,
description and (for devices) its usage and a meter.

Follows the sidebar preferences: *Show Usage Details*, *Show Device
Descriptions* and *Sidebar Meter Type*. Overview, Apps and Processes stay
at the top;
the user can reorder the rest (row menu or drag and drop) and minimise
them to icon and name (``sidebar-order``, ``sidebar-minimized``; the order
rules are in ``sidebar_order.py``).
"""

from __future__ import annotations

from typing import Optional

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

from . import sidebar_order
from .sidebar_fields import FIELD_LABELS, Field, hidden, set_shown, visible
from .axes import history_span_s
from .page import PageKind, ResourcePage, SidebarSummary
from .widgets.meter import Meter, MeterType


# Pages without a sidebar chart (so without an entry colour), pinned at the
# top: they can't be moved or minimised.
UNCHARTED = (PageKind.OVERVIEW, PageKind.APPS, PageKind.PROCESSES)
PINNED = UNCHARTED

ICON_SIZE = 16
ICON_SPACING = 10


class StackSidebarItem(Gtk.ListBoxRow):
    def __init__(self, page: ResourcePage) -> None:
        super().__init__()
        self.page: Optional[ResourcePage] = None
        self._summary_handler = 0
        self.show_details = True
        self.show_description = True

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        for side in ("top", "bottom"):
            getattr(box, f"set_margin_{side}")(6)
        # The icon sits left of the name; everything else lines up under the
        # name, as in Resources.
        top = Gtk.Box(spacing=ICON_SPACING)
        self.image = Gtk.Image(pixel_size=ICON_SIZE)
        self.label = Gtk.Label(xalign=0, hexpand=True,
                               ellipsize=Pango.EllipsizeMode.END)
        self.label.add_css_class("heading")
        top.append(self.image)
        top.append(self.label)
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
        self.meter = Meter()
        self.meter.progress.update_property([Gtk.AccessibleProperty.LABEL], ["Usage"])
        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                          margin_start=ICON_SIZE + ICON_SPACING)
        details.append(self.detail_label)
        details.append(self.usage_label)
        details.append(self.meter)
        self.details = details
        box.append(details)
        self.set_child(box)
        self.set_page(page)

    @property
    def page_id(self) -> str:
        return self.page.page_id

    def set_page(self, page: ResourcePage) -> None:
        """Show ``page`` (also used when a page is swapped in place)."""
        if self.page is not None and self._summary_handler:
            self.page.disconnect(self._summary_handler)
        self.page = page
        self.minimize_button.set_visible(self.movable)
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
        return visible(field, self.hidden_fields, show_details=self.show_details,
                       show_description=self.show_description, minimized=self.minimized)

    def set_style(self, show_details: bool, show_description: bool,
                  meter_type: str) -> None:
        self.show_details = show_details
        self.show_description = show_description
        self.meter.set_meter_type(MeterType(meter_type))
        self.update()

    def update(self) -> None:
        summary: Optional[SidebarSummary] = self.page.sidebar_summary()
        self.label.set_visible(self.shows(Field.NAME))
        self.detail_label.set_visible(self.shows(Field.DESCRIPTION)
                                      and bool(self.page.description))
        has_summary = summary is not None
        self.usage_label.set_visible(has_summary and self.shows(Field.USAGE))
        # Without a percentage there's nothing for a progress bar to show;
        # the graph meter still works, scaled to the data.
        graph_mode = self.meter.meter_type == MeterType.GRAPH
        self.meter.set_visible(has_summary and self.shows(Field.CHART)
                               and (summary.usage is not None
                                    or (graph_mode and bool(summary.series))))
        self.details.set_visible(self.detail_label.get_visible()
                                 or self.usage_label.get_visible() or self.meter.get_visible())
        if not has_summary:
            return
        text = summary.text()
        self.usage_label.set_label(text)
        self.update_property([Gtk.AccessibleProperty.DESCRIPTION], [text])
        self.meter.set_fraction(None if summary.usage is None else summary.usage / 100)
        if self.meter.graph.series != summary.series:
            self.meter.set_series(summary.series)
        if self.meter.graph.max_value != summary.max_value:
            self.meter.graph.set_max(summary.max_value)
        self.meter.refresh()


class StackSidebar(Gtk.ScrolledWindow):
    """Rows sorted by ``ResourcePage.sort_key()``; selecting one shows that
    page in the bound ``Gtk.Stack`` and emits ``page-selected``."""

    __gsignals__ = {
        "page-selected": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        # The charted entries, their order or their colours changed
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
        self.colors: dict[str, int] = {}      # page ID -> entry colour index
        self._install_actions()

        self.list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.list_box.add_css_class("navigation-sidebar")
        self.list_box.set_sort_func(self._sort)
        self.list_box.connect("row-selected", self._on_row_selected)
        self.set_child(self.list_box)

        if settings is not None:
            for key in ("sidebar-details", "sidebar-description", "sidebar-meter-type",
                        "show-graph-axes", "graph-data-points", "refresh-speed"):
                settings.connect_changed(key, lambda *_: self._apply_style())
            settings.connect_changed("sidebar-order", lambda *_: self._rearrange())
            settings.connect_changed("sidebar-minimized", lambda *_: self._apply_minimized())
            settings.connect_changed("sidebar-hidden-fields", lambda *_: self._apply_fields())

    # -- items ------------------------------------------------------------------

    def add_item(self, page: ResourcePage) -> StackSidebarItem:
        if page.page_id in self.items:
            raise ValueError(f"duplicate page {page.page_id!r}")
        item = StackSidebarItem(page)
        self.items[page.page_id] = item
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
        self.list_box.remove(item)
        self._rearrange()
        self.assign_colors()

    def replace_page(self, page: ResourcePage) -> None:
        self.items[page.page_id].set_page(page)
        self._rearrange()
        self.assign_colors()

    def default_order(self) -> list[str]:
        """The built-in order (by kind, then name), ignoring the user's."""
        return [i for i, _ in sorted(self.items.items(), key=lambda kv: kv[1].page.sort_key())]

    def assign_colors(self) -> None:
        """Give every entry with a chart its own palette colour, numbered
        in the built-in order, so moving an entry keeps its colour (Apps
        and Processes have none)."""
        index = 0
        self.colors = {}
        for page_id in self.default_order():
            item = self.items[page_id]
            if item.page.kind in UNCHARTED:
                item.meter.set_entry_color(None)
            else:
                item.meter.set_entry_color(index)
                item.page.set_entry_color(index)
                self.colors[page_id] = index
                index += 1
        self.emit("entries-changed")

    def entries(self) -> list[tuple[ResourcePage, int]]:
        """``(page, colour index)`` of every charted entry, in display
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

    # -- the user's order and minimised entries (DESIGN.md §9.2) ------------------------

    def saved_order(self) -> list[str]:
        return list(self.settings.get("sidebar-order")) if self.settings else self._saved_order

    def minimized_ids(self) -> set[str]:
        return set(self.settings.get("sidebar-minimized")) if self.settings else self._minimized

    def pinned_ids(self) -> list[str]:
        return [i for i in self.default_order() if self.items[i].page.kind in PINNED]

    def _rearrange(self, sort: bool = True) -> None:
        order = sidebar_order.arrange(self.default_order(), self.saved_order(),
                                      self.pinned_ids())
        self._rank = {page_id: i for i, page_id in enumerate(order)}
        if sort:
            self.list_box.invalidate_sort()
            self.assign_colors()

    def _save_order(self, order: list[str]) -> None:
        rest = [i for i in order if i not in self.pinned_ids()]
        if self.settings is not None:
            self.settings.set("sidebar-order", rest)
        else:
            self._saved_order = rest
            self._rearrange()

    def move(self, page_id: str, delta: int) -> None:
        """Move an entry ``delta`` places (negative: up)."""
        self._save_order(sidebar_order.move(self.order(), page_id, delta, self.pinned_ids()))

    def move_before(self, page_id: str, target: str) -> None:
        """Drop ``page_id`` where ``target`` is."""
        self._save_order(sidebar_order.move_before(self.order(), page_id, target,
                                                   self.pinned_ids()))

    def set_minimized(self, page_id: str, minimized: bool) -> None:
        ids = self.minimized_ids()
        if minimized and self.items[page_id].movable:
            ids.add(page_id)
        else:
            ids.discard(page_id)
        if self.settings is not None:
            self.settings.set("sidebar-minimized", sorted(ids))
        else:
            self._minimized = ids
            self._apply_minimized()

    def hidden_fields_map(self) -> dict[str, list[str]]:
        return dict(self.settings.get("sidebar-hidden-fields")) if self.settings \
            else self._hidden_fields

    def field_shown(self, page_id: str, field: Field) -> bool:
        """The entry's own choice (not the global preferences)."""
        return field not in hidden(self.hidden_fields_map(), page_id)

    def set_field_shown(self, page_id: str, field: Field, shown: bool) -> None:
        mapping = set_shown(self.hidden_fields_map(), page_id, Field(field), shown)
        if self.settings is not None:
            self.settings.set("sidebar-hidden-fields", mapping)
        else:
            self._hidden_fields = mapping
            self._apply_fields()

    def _apply_fields(self) -> None:
        mapping = self.hidden_fields_map()
        for page_id, item in self.items.items():
            item.set_hidden_fields(hidden(mapping, page_id))

    def reset_order(self) -> None:
        """Back to the built-in order, nothing minimised."""
        if self.settings is not None:
            self.settings.set("sidebar-order", [])
            self.settings.set("sidebar-minimized", [])
            self.settings.set("sidebar-hidden-fields", {})
        else:
            self._saved_order, self._minimized, self._hidden_fields = [], set(), {}
            self._rearrange()
            self._apply_minimized()
            self._apply_fields()

    def _apply_minimized(self) -> None:
        ids = self.minimized_ids()
        for page_id, item in self.items.items():
            item.set_minimized(page_id in ids)

    # -- row menu and drag and drop -------------------------------------------------------

    def _install_actions(self) -> None:
        group = Gio.SimpleActionGroup()
        s = GLib.VariantType.new("s")
        for name, callback in (
                ("move-up", lambda pid: self.move(pid, -1)),
                ("move-down", lambda pid: self.move(pid, 1)),
                ("toggle-minimized", lambda pid: self.set_minimized(
                    pid, pid not in self.minimized_ids()))):
            action = Gio.SimpleAction.new(name, s)
            action.connect("activate", lambda _a, v, cb=callback: cb(v.get_string()))
            group.add_action(action)
        reset = Gio.SimpleAction.new("reset", None)
        reset.connect("activate", lambda *_: self.reset_order())
        group.add_action(reset)
        self.actions = group
        self.insert_action_group("sidebar", group)

    def row_menu(self, page_id: str) -> Gio.Menu:
        """Move Up, Move Down, Minimize/Expand, Reset Order."""
        order, pinned = self.order(), self.pinned_ids()
        target = GLib.Variant.new_string(page_id)
        menu, entries = Gio.Menu(), Gio.Menu()
        for label, action, enabled in (
                ("Move Up", "move-up", sidebar_order.can_move(order, page_id, -1, pinned)),
                ("Move Down", "move-down", sidebar_order.can_move(order, page_id, 1, pinned)),
                ("Expand" if page_id in self.minimized_ids() else "Minimize",
                 "toggle-minimized", True)):
            if enabled:
                item = Gio.MenuItem.new(label, None)
                item.set_action_and_target_value(f"sidebar.{action}", target)
                entries.append_item(item)
        menu.append_section(None, entries)
        fields = Gio.Menu()
        for field in Field:
            fields.append(f"Show {FIELD_LABELS[field]}", f"row.show-{field.value}")
        menu.append_section(None, fields)
        reset = Gio.Menu()
        reset.append("Reset Order", "sidebar.reset")
        menu.append_section(None, reset)
        return menu

    def row_actions(self, page_id: str) -> Gio.SimpleActionGroup:
        """The menu's *Show …* check items for one entry (``row.show-<field>``)."""
        group = Gio.SimpleActionGroup()
        for field in Field:
            action = Gio.SimpleAction.new_stateful(
                f"show-{field.value}", None,
                GLib.Variant.new_boolean(self.field_shown(page_id, field)))
            action.connect("change-state", lambda a, v, f=field: (
                a.set_state(v), self.set_field_shown(page_id, f, v.get_boolean())))
            group.add_action(action)
        return group

    def popup_menu(self, item: StackSidebarItem, x: float = -1, y: float = -1):
        if not item.movable:
            return None
        popover = Gtk.PopoverMenu.new_from_model(self.row_menu(item.page_id))
        popover.insert_action_group("row", self.row_actions(item.page_id))
        popover.set_parent(item)
        popover.set_has_arrow(False)
        if x >= 0:
            rect = Gdk.Rectangle()
            rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
            popover.set_pointing_to(rect)
        popover.connect("closed", lambda p: GLib.idle_add(p.unparent))
        if item.get_native() is not None:      # only a row on screen can pop up
            popover.popup()
        return popover

    def _wire_row(self, item: StackSidebarItem) -> None:
        item.minimize_button.connect("clicked", lambda _b: self.set_minimized(
            item.page_id, not item.minimized))
        click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        click.connect("pressed", lambda _g, _n, x, y: self.popup_menu(item, x, y))
        item.add_controller(click)
        press = Gtk.GestureLongPress(touch_only=True)
        press.connect("pressed", lambda _g, x, y: self.popup_menu(item, x, y))
        item.add_controller(press)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", lambda _c, key, _code, state: self._on_key(item, key, state))
        item.add_controller(keys)

        drag = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        drag.connect("prepare", lambda *_: Gdk.ContentProvider.new_for_value(item.page_id)
                     if item.movable else None)
        item.add_controller(drag)
        drop = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        drop.connect("drop", lambda _t, value, _x, _y: self._on_drop(value, item.page_id))
        item.add_controller(drop)

    def _on_key(self, item: StackSidebarItem, key: int, state) -> bool:
        if key == Gdk.KEY_Menu or (key == Gdk.KEY_F10 and state & Gdk.ModifierType.SHIFT_MASK):
            return self.popup_menu(item) is not None
        if state & Gdk.ModifierType.ALT_MASK and key in (Gdk.KEY_Up, Gdk.KEY_Down) \
                and item.movable:
            self.move(item.page_id, -1 if key == Gdk.KEY_Up else 1)
            return True
        return False

    def _on_drop(self, page_id, target: str) -> bool:
        if page_id not in self.items or page_id == target \
                or not self.items[page_id].movable:
            return False
        self.move_before(page_id, target)
        return True

    # -- style --------------------------------------------------------------------------

    def _style(self, item: StackSidebarItem) -> None:
        if self.settings is None:
            return
        item.set_style(self.settings.get("sidebar-details"),
                       self.settings.get("sidebar-description"),
                       self.settings.get("sidebar-meter-type"))
        item.meter.set_show_axes(self.settings.get("show-graph-axes"))
        item.meter.graph.set_time_span(history_span_s(self.settings))

    def _apply_style(self) -> None:
        for item in self.items.values():
            self._style(item)

    def _sort(self, a: StackSidebarItem, b: StackSidebarItem) -> int:
        big = len(self._rank)
        ka = (self._rank.get(a.page_id, big), a.page.sort_key())
        kb = (self._rank.get(b.page_id, big), b.page.sort_key())
        return (ka > kb) - (ka < kb)
