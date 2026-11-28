"""Base of the Apps and Processes pages: a sortable, searchable, diff-updated
``Gtk.ColumnView`` with an action bar (Information, Options, End)."""

from __future__ import annotations

import logging
import time

from typing import Any, Optional

import gi

gi.require_version("Graphene", "1.0")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Graphene, Gtk, Pango  # noqa: E402

from ...processes.actions import Action
from ..widgets.app_icon import set_app_icon  # noqa: F401 (re-exported)
from ..page import PageKind, ResourcePage
from ..compat import toplevel_suspended
from ..columns import Column, ColumnSet, compare, shown_column  # noqa: F401 (Column re-exported)
from ..table_diff import plan_splice


log = logging.getLogger(__name__)

# A refresh slower than this is noted in the debug log, with its sizes.
SLOW_REFRESH_S = 0.1


class Row(GObject.Object):
    """One table row. ``revision`` changes whenever ``data`` does, which
    re-binds the visible cells."""
    __gtype_name__ = "ProccoliTableRow"

    revision = GObject.Property(type=int, default=0)

    def __init__(self, key, data) -> None:
        super().__init__()
        self.key = key
        self.data = data

    def update(self, data) -> None:
        self.data = data
        self.revision += 1


class TablePage(ResourcePage):
    COLUMNS: list[Column] = []
    SORT_KEY = ""          # settings key prefix: "processes" or "apps"
    NOUN = "Process"       # for labels: "End Process"
    HAS_OPTIONS = False    # a Process Options button
    clock = staticmethod(time.perf_counter)   # times a refresh (tests replace it)

    def __init__(self, page_id: str, kind: PageKind, title: str, icon_name: str,
                 settings, monitor, actions) -> None:
        super().__init__(page_id, kind, title, icon_name)
        self.settings = settings
        self.monitor = monitor
        self.actions = actions          # processes.actions.ProcessActions
        self._acquired = False
        self._surface = None            # the window's Gdk surface, while mapped
        self._surface_handler = 0
        self.rows: dict[Any, Row] = {}
        self.store = Gio.ListStore(item_type=Row)

        self.search_entry = Gtk.SearchEntry(hexpand=True,
                                            placeholder_text=f"Search {title.lower()}")
        self.search_bar = Gtk.SearchBar(child=self.search_entry, show_close_button=True)
        self.search_bar.connect_entry(self.search_entry)
        self.filter = Gtk.CustomFilter.new(self._matches, None)
        self.search_entry.connect("search-changed",
                                  lambda *_: self.filter.changed(Gtk.FilterChange.DIFFERENT))

        self.view = Gtk.ColumnView(reorderable=True, show_column_separators=False)
        self.view.add_css_class("data-table")
        self.column_set = ColumnSet(self.COLUMNS, self.SORT_KEY)
        self.columns: dict[str, Gtk.ColumnViewColumn] = {}
        for spec in self.COLUMNS:
            self.columns[spec.id] = self._add_column(spec)
        filtered = Gtk.FilterListModel(model=self.store, filter=self.filter)
        self.sorted = Gtk.SortListModel(model=filtered, sorter=self.view.get_sorter())
        self.selection = Gtk.MultiSelection(model=self.sorted)
        self.view.set_model(self.selection)
        self.selection.connect("selection-changed", lambda *_: self._update_actions())

        scroller = Gtk.ScrolledWindow(child=self.view, vexpand=True)
        self.toast_overlay = Adw.ToastOverlay(child=scroller)

        self.action_bar = Gtk.ActionBar()
        self.info_button = Gtk.Button(label="Information", tooltip_text="Information (Ctrl+I)")
        self.info_button.connect("clicked", lambda *_: self._show_info())
        self.action_bar.pack_start(self.info_button)
        self.options_button = None
        if self.HAS_OPTIONS:
            self.options_button = Gtk.Button(label="Options")
            self.options_button.connect("clicked", lambda *_: self._show_options())
            self.action_bar.pack_start(self.options_button)
        self.end_button = Adw.SplitButton(label=f"End {self.NOUN}",
                                          menu_model=self._action_menu())
        self.end_button.add_css_class("destructive-action")
        self.end_button.connect("clicked", lambda *_: self.run_action(Action.END))
        self.action_bar.pack_end(self.end_button)
        self._install_actions()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        # The context menu's parent: a box, which positions
        # popovers through its layout manager, and never recycled the way
        # table cells are.
        self.menu_parent = box
        self.context_popover: Optional[Gtk.PopoverMenu] = None
        box.append(self.search_bar)
        box.append(self.toast_overlay)
        box.append(self.action_bar)
        self.set_child(box)

        self._apply_column_settings()
        for key in self.column_set.setting_keys():
            self.track(settings, settings.connect_changed(
                key, lambda *_: self._apply_column_settings()))
        self._restore_sort()
        self.view.get_sorter().connect("changed", lambda *_: self._save_sort())
        self.track(monitor, monitor.connect("updated", lambda *_: self.refresh()))
        self.track(settings, settings.connect_changed("base", lambda *_: self.refresh()))
        self._update_actions()

    # -- columns ------------------------------------------------------------------

    def _add_column(self, spec: Column) -> Gtk.ColumnViewColumn:
        spec = shown_column(spec, self.settings)
        factory = Gtk.SignalListItemFactory()

        def setup(_f, item):
            label = Gtk.Label(xalign=1.0 if spec.numeric else 0.0,
                              ellipsize=Pango.EllipsizeMode.END)
            if spec.numeric:
                label.add_css_class("numeric")
            if spec.icon is not None:
                box = Gtk.Box(spacing=8)
                box.append(Gtk.Image(pixel_size=16))
                box.append(label)
                item.set_child(box)
            else:
                item.set_child(label)
            self._add_cell_menu(item)

        def fill(item):
            row = item.get_item()
            child = item.get_child()
            label = child.get_last_child() if spec.icon is not None else child
            label.set_label(spec.text(row.data))
            if spec.icon is not None:
                set_app_icon(child.get_first_child(), spec.icon(row.data))

        def bind(_f, item):
            fill(item)
            item._proccoli_handler = item.get_item().connect(
                "notify::revision", lambda *_: fill(item))

        def unbind(_f, item):
            handler = getattr(item, "_proccoli_handler", 0)
            if handler:
                item.get_item().disconnect(handler)
                item._proccoli_handler = 0

        factory.connect("setup", setup)
        factory.connect("bind", bind)
        factory.connect("unbind", unbind)
        col = Gtk.ColumnViewColumn(title=spec.title, factory=factory, resizable=True,
                                   expand=spec.expand)
        # Also for the expanding name column: its fixed width is its minimum,
        # so many visible columns scroll sideways instead of squeezing names.
        col.set_fixed_width(spec.width)
        col.set_sorter(Gtk.CustomSorter.new(
            lambda a, b, _d: compare(spec.value(a.data), spec.value(b.data)), None))
        self.view.append_column(col)
        return col

    def _apply_column_settings(self) -> None:
        for column_id, shown in self.column_set.visibility(self.settings).items():
            self.columns[column_id].set_visible(shown)

    def _restore_sort(self) -> None:
        column_id, ascending = self.column_set.sort_choice(self.settings)
        self.view.sort_by_column(self.columns[column_id], Gtk.SortType.ASCENDING if ascending
                                 else Gtk.SortType.DESCENDING)

    def _save_sort(self) -> None:
        sorter = self.view.get_sorter()
        column = sorter.get_primary_sort_column()
        if column is None:
            return
        column_id = next(i for i, c in self.columns.items() if c is column)
        ascending = sorter.get_primary_sort_order() == Gtk.SortType.ASCENDING
        for key, value in self.column_set.sort_settings(column_id, ascending).items():
            self.settings.set(key, value)

    # -- data -----------------------------------------------------------------------

    def items(self) -> dict:
        """``{key: data}`` for the rows (subclasses)."""
        return {}

    def refresh(self) -> None:
        self.update_rows(self.items())

    # The process monitor only scans /proc while a table is on screen: the
    # page mapped, and its window not suspended (the screen locked, the
    # window minimized or hidden), since then nothing is drawn while
    # processes keep coming and going. Shown again, the next scan refreshes
    # the table once.

    def do_map(self) -> None:
        ResourcePage.do_map(self)
        native = self.get_native()
        surface = native.get_surface() if native is not None else None
        if surface is not None and self._surface is None:
            self._surface = surface
            self._surface_handler = surface.connect(
                "notify::state", lambda s, _p: self.set_window_suspended(
                    toplevel_suspended(s.get_state())))
        suspended = surface is not None and hasattr(surface, "get_state") \
            and toplevel_suspended(surface.get_state())
        self.set_window_suspended(suspended)

    def do_unmap(self) -> None:
        if self._surface is not None:
            self._surface.disconnect(self._surface_handler)
            self._surface = None
        self._release()
        ResourcePage.do_unmap(self)

    def set_window_suspended(self, suspended: bool) -> None:
        """Stop scanning while the window can't be seen; start again when
        it can (only while the page is mapped)."""
        if suspended:
            self._release()
        elif self.get_mapped() and not self._acquired:
            self.monitor.acquire()
            self._acquired = True

    def shutdown(self) -> None:
        self._release()
        if self.context_popover is not None:
            self.context_popover.unparent()
            self.context_popover = None
        super().shutdown()

    def _release(self) -> None:
        if self._acquired:
            self.monitor.release()
            self._acquired = False

    def search_text(self, data) -> str:
        """What the search box matches against (subclasses)."""
        return ""

    def _matches(self, row: Row, _data=None) -> bool:
        query = self.search_entry.get_text().strip().lower()
        return not query or query in self.search_text(row.data).lower()

    def update_rows(self, items: dict) -> None:
        """Diff ``{key: data}`` into the store: existing rows are updated in
        place, and the rows that went and came are one splice
        (``table_diff.plan_splice``), so the list and the view react once
        per refresh rather than once per row. ``self.rows`` keeps the
        store's order (new rows at the end). Selected rows the splice puts
        back stay selected."""
        started = self.clock()
        new = []
        for key, data in items.items():
            row = self.rows.get(key)
            if row is None:
                new.append(Row(key, data))
            else:
                row.update(data)
        gone = {k for k in self.rows if k not in items}
        splice = plan_splice(list(self.rows), gone, [r.key for r in new])
        if not splice.empty:
            selected = self._selected_rows() if splice.removed else []
            for key in gone:
                del self.rows[key]
            for row in new:
                self.rows[row.key] = row
            self.store.splice(splice.position, splice.removed,
                              [self.rows[k] for k in splice.added])
            if selected:
                self._reselect([r for r in selected if r.key not in gone])
        sorter = self.view.get_sorter()
        if sorter is not None:
            sorter.changed(Gtk.SorterChange.DIFFERENT)
        self._update_actions()
        took = self.clock() - started
        if took > SLOW_REFRESH_S:
            log.debug("%s: refresh took %.0f ms (%d rows, %d gone, %d new)",
                      self.SORT_KEY, took * 1000, len(self.rows), len(gone), len(new))

    def _selected_rows(self) -> list:
        bitset = self.selection.get_selection()
        return [r for r in (self.sorted.get_item(bitset.get_nth(i))
                            for i in range(bitset.get_size())) if r is not None]

    def _reselect(self, rows: list) -> None:
        """Select ``rows`` again (by their place in the sorted view)."""
        wanted = {id(r) for r in rows}
        for i in range(self.sorted.get_n_items()):
            if id(self.sorted.get_item(i)) in wanted:
                self.selection.select_item(i, False)

    def selected(self) -> list:
        out = []
        bitset = self.selection.get_selection()
        for i in range(bitset.get_size()):
            row = self.sorted.get_item(bitset.get_nth(i))
            if row is not None:
                out.append(row.data)
        return out

    # -- actions ------------------------------------------------------------------------

    def _action_menu(self) -> Gio.Menu:
        menu = Gio.Menu()
        for action in (Action.KILL, Action.HALT, Action.CONTINUE):
            menu.append(f"{action.verb.title()} {self.NOUN}", f"table.{action.verb}")
        return menu

    def _install_actions(self) -> None:
        group = Gio.SimpleActionGroup()
        self.action_objects = {}
        for action in Action:
            a = Gio.SimpleAction.new(action.verb, None)
            a.connect("activate", lambda _a, _p, act=action: self.run_action(act))
            group.add_action(a)
            self.action_objects[action] = a
        info = Gio.SimpleAction.new("info", None)
        info.connect("activate", lambda *_: self._show_info())
        group.add_action(info)
        self.info_action = info
        if self.HAS_OPTIONS:
            options = Gio.SimpleAction.new("options", None)
            options.connect("activate", lambda *_: self._show_options())
            group.add_action(options)
            self.options_action = options
        search = Gio.SimpleAction.new("search", None)
        search.connect("activate", lambda *_: self.search_bar.set_search_mode(
            not self.search_bar.get_search_mode()))
        group.add_action(search)
        self.action_group = group
        for name, callback in self.extra_actions():
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", lambda *_, cb=callback: cb())
            group.add_action(a)
        self.insert_action_group("table", group)
        menu_key = Gtk.EventControllerKey()
        menu_key.connect("key-pressed", self._on_menu_key)
        self.view.add_controller(menu_key)

        shortcuts = Gtk.ShortcutController(scope=Gtk.ShortcutScope.MANAGED)
        for trigger, name in (("Delete", "table.end"), ("<Control>Delete", "table.kill"),
                              ("<Control>f", "table.search"), ("<Control>i", "table.info")):
            shortcuts.add_shortcut(Gtk.Shortcut.new(Gtk.ShortcutTrigger.parse_string(trigger),
                                                    Gtk.NamedAction.new(name)))
        self.add_controller(shortcuts)

    def _update_actions(self) -> None:
        selected = self.selected()
        has = bool(selected)
        self.end_button.set_sensitive(has)
        for a in self.action_objects.values():
            a.set_enabled(has)
        one = len(selected) == 1          # dialogs show a single row
        self.info_button.set_sensitive(one)
        self.info_action.set_enabled(one)
        if self.options_button is not None:
            self.options_button.set_sensitive(one)
            self.options_action.set_enabled(one)
        self.update_extra_actions(selected)

    # -- context menu ---------------------------------------------------

    def extra_actions(self) -> list:
        """``[(name, callback)]`` added to the ``table`` actions (subclasses)."""
        return []

    def update_extra_actions(self, selected: list) -> None:
        """Enable or disable the extra actions for the selection (subclasses)."""

    def extra_menu_items(self, selected: list) -> list:
        """``[(label, "table.<action>")]`` at the top of the context menu."""
        return []

    def context_menu(self) -> Gio.Menu:
        """Right-click menu for the selected rows: extra items (Apps:
        Switch To), Information, Options, then End, Kill, Halt, Continue."""
        selected = self.selected()
        menu = Gio.Menu()
        top = Gio.Menu()
        for label, action in self.extra_menu_items(selected):
            top.append(label, action)
        if top.get_n_items():
            menu.append_section(None, top)
        dialogs = Gio.Menu()
        dialogs.append("Information", "table.info")
        if self.HAS_OPTIONS:
            dialogs.append("Options", "table.options")
        menu.append_section(None, dialogs)
        signals = Gio.Menu()
        for action in Action:
            signals.append(f"{action.verb.title()} {self.NOUN}", f"table.{action.verb}")
        menu.append_section(None, signals)
        return menu

    def menu_point(self, widget: Gtk.Widget, x: float, y: float) -> Optional[tuple[int, int]]:
        """``(x, y)`` in ``widget`` (a cell) as a point in the menu's parent,
        or None (no position: the menu points at the whole table)."""
        if x < 0:
            return None
        ok, point = widget.compute_point(self.menu_parent, Graphene.Point().init(x, y))
        return (int(point.x), int(point.y)) if ok else None

    def popup_context_menu(self, widget: Gtk.Widget, x: float = -1, y: float = -1):
        """Show the context menu at ``(x, y)`` in ``widget`` (a cell), or
        at the table. One popover per table, reused."""
        if not self.selected():
            return None
        popover = self.context_popover
        if popover is None:
            popover = Gtk.PopoverMenu(has_arrow=False, halign=Gtk.Align.START)
            popover.set_parent(self.menu_parent)
            self.context_popover = popover
        popover.set_menu_model(self.context_menu())
        point = self.menu_point(widget, x, y)
        rect = Gdk.Rectangle()
        if point is not None:
            rect.x, rect.y, rect.width, rect.height = point[0], point[1], 1, 1
        else:                            # keyboard: at the table's top left
            ok, bounds = self.view.compute_bounds(self.menu_parent)
            rect.x, rect.y = (int(bounds.get_x()), int(bounds.get_y())) if ok else (0, 0)
            rect.width = rect.height = 1
        popover.set_pointing_to(rect)
        if self.menu_parent.get_native() is not None:
            popover.popup()
        return popover

    def select_position(self, position: int) -> None:
        """Right-clicking a row that isn't selected selects only it (as in
        file managers); one that is keeps the selection."""
        if position == Gtk.INVALID_LIST_POSITION:
            return
        if not self.selection.is_selected(position):
            self.selection.select_item(position, True)

    def _add_cell_menu(self, item) -> None:
        cell = item.get_child()
        click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        click.connect("pressed", lambda g, _n, x, y: self.open_cell_menu(g, item, cell, x, y))
        cell.add_controller(click)
        press = Gtk.GestureLongPress(touch_only=True)
        press.connect("pressed", lambda g, x, y: self.open_cell_menu(g, item, cell, x, y))
        cell.add_controller(press)

    def open_cell_menu(self, gesture: Gtk.Gesture, item, cell: Gtk.Widget,
                       x: float, y: float):
        """Right-click or long-press on a cell. The gesture is claimed first:
        the row's own click gesture would otherwise stay mid-click while the
        popup takes the button release, and on Wayland the window then
        ignores all input (it looked frozen)."""
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self.select_position(item.get_position())
        return self.popup_context_menu(cell, x, y)

    def _on_menu_key(self, _controller, key, _code, state) -> bool:
        if key == Gdk.KEY_Menu or (key == Gdk.KEY_F10 and state & Gdk.ModifierType.SHIFT_MASK):
            return self.popup_context_menu(self.view) is not None
        return False

    def _show_info(self) -> None:
        selected = self.selected()
        if len(selected) == 1:
            self.present_dialog(self.info_dialog(selected[0]))

    def _show_options(self) -> None:
        selected = self.selected()
        if len(selected) == 1:
            self.present_dialog(self.options_dialog(selected[0]))

    def info_dialog(self, item):
        raise NotImplementedError

    def options_dialog(self, item):
        raise NotImplementedError

    def present_dialog(self, dialog) -> None:
        self.last_dialog = dialog
        dialog.present(self.get_root())

    def targets(self, selected: list) -> list[tuple[int, str]]:
        """``[(pid, name), ...]`` for the selected rows (subclasses)."""
        return []

    def run_action(self, action: Action) -> None:
        targets = self.targets(self.selected())
        if targets:
            self.actions.signal(action, targets, self.toast)

    def toast(self, text: str) -> None:
        self.last_message = text
        self.toast_overlay.add_toast(Adw.Toast(title=GLib.markup_escape_text(text),
                                               timeout=3))

    def header_widgets(self) -> list[Gtk.Widget]:
        button = Gtk.ToggleButton(icon_name="system-search-symbolic",
                                  tooltip_text="Search (Ctrl+F)")
        self.search_bar.bind_property("search-mode-enabled", button, "active",
                                      GObject.BindingFlags.BIDIRECTIONAL
                                      | GObject.BindingFlags.SYNC_CREATE)
        return [button]
