"""A sidebar entry's right-click menu (move up or down, minimise, reset the
order), its keyboard shortcuts (Alt+Up, Alt+Down) and dragging an entry
to a new place."""

from __future__ import annotations

from gi.repository import Gdk, Gio, GLib, Gtk
from . import reorder
from .widgets.reorderable import make_reorderable
from .sidebar_fields import FIELD_LABELS, Field


class SidebarRowMenu:
    """Each row's menu, keys and drag and drop (a part of ``StackSidebar``)."""

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
                ("Move Up", "move-up", reorder.can_move(order, page_id, -1, pinned)),
                ("Move Down", "move-down", reorder.can_move(order, page_id, 1, pinned)),
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
        # Drag and drop, Alt+Up / Alt+Down (shared with the graph toolbar).
        make_reorderable(item, item.page_id, self._on_drop, self.move,
                         can_drag=lambda: item.movable)

    def _on_key(self, item: StackSidebarItem, key: int, state) -> bool:
        if key == Gdk.KEY_Menu or (key == Gdk.KEY_F10 and state & Gdk.ModifierType.SHIFT_MASK):
            return self.popup_menu(item) is not None
        return False

    def _on_drop(self, page_id, target: str) -> bool:
        if page_id not in self.items or page_id == target \
                or not self.items[page_id].movable:
            return False
        self.move_before(page_id, target)
        return True
