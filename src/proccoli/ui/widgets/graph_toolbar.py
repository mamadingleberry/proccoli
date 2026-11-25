"""The graph toolbar: the view settings people
change while looking at graphs, one click away under the page's header.

One toolbar per window; the window moves it into the page shown
(``PageContainer.attach_toolbar()``) and tells it the page (``set_page``),
so items that do nothing there are hidden, and so is the bar when none
is left. Each item changes its setting directly and follows it, so
Preferences, the toolbar and the graphs stay in step; a setting fixed by
Lightweight Mode shows its value greyed out.

Each item is a cell: its title above its control (a menu showing the
current choice, or a ``Gtk.Switch`` for a toggle: no text, it slides
right and takes the accent color when on). Items are dragged by their
cell to reorder (or moved with Ctrl+Shift+Left / Right,
the shared ``make_reorderable``); the menu at the end (or a right-click on
the bar) shows and hides them and resets the toolbar. The order and the
shown items are ``toolbar-items``.
"""

from __future__ import annotations

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from ...core.connections import Connections
from ...core.profile import is_pinned
from ...core.ticker import CUSTOM, CUSTOM_KEY, clamp_range_s, update_interval_ms
from .. import reorder
from ..toolbar_items import (BY_ID, FIXED, ITEMS, SETTING, SHOW_SETTING, ToolbarItem,
                             applies, set_shown, shown)
from ..time_range import CUSTOM_LABEL, limit_note
from .range_editor import RangeEditor
from .reorderable import CTRL_SHIFT, HORIZONTAL, make_reorderable

ACTION_GROUP = "toolbar"
PINNED_NOTE = "fixed by Lightweight Mode"


class GraphToolbar(Gtk.Box):
    def __init__(self, settings) -> None:
        super().__init__(spacing=6)
        self.add_css_class("toolbar")
        self.settings = settings
        self.page_kind = ""
        self.has_graphs = True
        self.buttons: dict[str, Gtk.Widget] = {}     # each item's control
        self.cells: dict[str, Gtk.Box] = {}          # its title above its control

        self.items_box = Gtk.Box(spacing=18)       # room between the titles
        # A narrow window scrolls the items rather than squeezing them.
        self.scroller = Gtk.ScrolledWindow(child=self.items_box, hexpand=True,
                                           vscrollbar_policy=Gtk.PolicyType.NEVER,
                                           hscrollbar_policy=Gtk.PolicyType.EXTERNAL,
                                           propagate_natural_height=True)
        self.append(self.scroller)

        self.actions = Gio.SimpleActionGroup()
        self.insert_action_group(ACTION_GROUP, self.actions)
        self.menu_actions: dict[str, Gio.SimpleAction] = {}
        self.show_actions: dict[str, Gio.SimpleAction] = {}
        for item in ITEMS:
            self._add_actions(item)
        reset = Gio.SimpleAction.new("reset", None)
        reset.connect("activate", lambda *_: self.settings.reset(SETTING))
        self.actions.add_action(reset)

        self.customize = Gtk.MenuButton(icon_name="view-more-symbolic",
                                        menu_model=customize_menu(),
                                        tooltip_text="Customize Toolbar")
        self.customize.add_css_class("flat")
        self.append(self.customize)
        click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        click.connect("pressed", lambda *_: self.customize.popup())
        self.add_controller(click)

        self.connections = Connections()
        self.connections.watch(settings, SETTING, lambda *_: self.rebuild())
        self.connections.watch(settings, SHOW_SETTING,
                               lambda *_: self.set_page(self.page_kind, self.has_graphs))
        for item in ITEMS:
            self.connections.watch(settings, [k for k in (item.key, item.custom_key) if k],
                                   lambda _k, _v, i=item: self._sync(i))
        custom = Gio.SimpleAction.new("custom-range", None)
        custom.connect("activate", lambda *_: self.edit_custom_range())
        self.actions.add_action(custom)
        self.custom_dialog = None
        self.rebuild()

    # -- actions -------------------------------------------------------------------

    def _add_actions(self, item: ToolbarItem) -> None:
        if item.kind == "menu":
            action = Gio.SimpleAction.new_stateful(
                item.id, GLib.VariantType.new("s"),
                GLib.Variant("s", str(self.settings.get(item.key))))
            action.connect("activate", lambda a, target, i=item: self.choose(
                i, target.get_string()))
            action.set_enabled(not is_pinned(self.settings, item.key))
            self.actions.add_action(action)
            self.menu_actions[item.id] = action
        if item.fixed:
            return                         # not the user's to show or hide
        show = Gio.SimpleAction.new_stateful(f"show-{item.id}", None,
                                             GLib.Variant("b", item.id in self.order()))
        show.connect("activate", lambda a, _t, i=item: self.set_item_shown(
            i.id, not a.get_state().get_boolean()))
        self.actions.add_action(show)
        self.show_actions[item.id] = show

    def choose(self, item: ToolbarItem, nick: str) -> None:
        if not is_pinned(self.settings, item.key) and self.settings.get(item.key) != nick:
            self.settings.set(item.key, nick)

    def set_item_shown(self, item_id: str, show: bool) -> None:
        self.settings.set(SETTING, set_shown(self.order(), item_id, show))

    # -- items ---------------------------------------------------------------------

    def order(self) -> list[str]:
        return shown(self.settings.get(SETTING))

    def rebuild(self) -> None:
        """A cell for each shown item, in order."""
        for cell in self.cells.values():
            self.items_box.remove(cell)
        self.buttons, self.cells = {}, {}
        order = self.order()
        for item_id in order + FIXED:
            item = BY_ID[item_id]
            button = self._button(item)
            cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            cell.add_css_class("toolbar-item")
            title = Gtk.Label(label=item.title, xalign=0)
            title.add_css_class("caption")
            title.add_css_class("dim-label")
            cell.append(title)
            cell.append(button)
            if not item.fixed:
                make_reorderable(cell, item_id, self.move_before, self.move,
                                 keys=HORIZONTAL, modifiers=CTRL_SHIFT)
            self.items_box.append(cell)
            self.buttons[item_id] = button
            self.cells[item_id] = cell
            self._sync(item)
        for item_id, action in self.show_actions.items():
            action.set_state(GLib.Variant("b", item_id in order))
        self.set_page(self.page_kind, self.has_graphs)

    def _button(self, item: ToolbarItem) -> Gtk.Widget:
        pinned = is_pinned(self.settings, item.key)
        tooltip = f"{item.tooltip} ({PINNED_NOTE})" if pinned else item.tooltip
        if item.kind == "menu":            # shows the current choice (``_sync``)
            button = Gtk.MenuButton(menu_model=choices_menu(item), tooltip_text=tooltip,
                                    always_show_arrow=True)
            button.add_css_class("flat")
        else:                              # slides right, accent color when on
            button = Gtk.Switch(tooltip_text=tooltip, halign=Gtk.Align.START,
                                valign=Gtk.Align.CENTER)
            button.connect("notify::active",
                           lambda b, _p, i=item: self._toggled(i, b.get_active()))
        button.set_sensitive(not pinned)
        return button

    def text(self, item_id: str) -> str:
        """What an item shows: its title, then a menu's current choice."""
        button = self.buttons[item_id]
        if isinstance(button, Gtk.Switch):
            return BY_ID[item_id].title
        return f"{BY_ID[item_id].title} {button.get_label()}"

    def _toggled(self, item: ToolbarItem, active: bool) -> None:
        if not is_pinned(self.settings, item.key) and bool(self.settings.get(item.key)) != active:
            self.settings.set(item.key, active)

    def _sync(self, item: ToolbarItem) -> None:
        """Show ``item``'s setting as it is now."""
        value = self.settings.get(item.key)
        action = self.menu_actions.get(item.id)
        if action is not None:
            action.set_state(GLib.Variant("s", str(value)))
        button = self.buttons.get(item.id)
        if button is None:
            return
        if item.kind == "menu":
            button.set_label(item.choice_label(str(value), self.settings))
            button.update_property([Gtk.AccessibleProperty.LABEL],
                                   [f"{item.title}: {button.get_label()}"])
        else:
            if button.get_active() != bool(value):
                button.set_active(bool(value))
            button.update_property([Gtk.AccessibleProperty.LABEL], [item.title])

    # -- a custom time range ---------------------------------------------------

    def edit_custom_range(self):
        """*Custom…*: a number and a unit; *Set* stores and picks it."""
        dialog = Adw.AlertDialog(heading="Custom Time Range",
                                 body="From 10 seconds to 30 days")
        editor = RangeEditor(self.settings.get(CUSTOM_KEY))
        editor.set_halign(Gtk.Align.CENTER)

        def changed(seconds):
            note = limit_note(seconds, update_interval_ms(self.settings))
            dialog.set_body(note or "From 10 seconds to 30 days")
        editor.on_change = changed
        dialog.set_extra_child(editor)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("set", "Set")
        dialog.set_response_appearance("set", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("set")

        def respond(_d, response):
            if response == "set":
                self.set_custom_range(clamp_range_s(editor.seconds(),
                                                    update_interval_ms(self.settings)))
            self.custom_dialog = None
        dialog.connect("response", respond)
        self.custom_dialog = dialog
        dialog.editor = editor
        if self.get_root() is not None:
            dialog.present(self.get_root())
        return dialog

    def set_custom_range(self, seconds: int) -> None:
        item = BY_ID["time-range"]
        self.settings.set(CUSTOM_KEY, seconds)
        if self.settings.get(item.key) != CUSTOM:
            self.settings.set(item.key, CUSTOM)
        else:
            self._sync(item)

    # -- reordering ------------------------------------------------------------------

    def move(self, item_id: str, delta: int) -> None:
        self.settings.set(SETTING, reorder.move(self.order(), item_id, delta, ()))

    def move_before(self, item_id: str, target: str) -> bool:
        order = self.order()
        if item_id not in order:
            return False
        self.settings.set(SETTING, reorder.move_before(order, item_id, target, ()))
        return True

    # -- the page shown --------------------------------------------------------------

    def set_page(self, page_kind: str, has_graphs: bool) -> None:
        """Show the items that do something on this page; the bar shows on
        every page with graphs (so it can be customized) and elsewhere
        only when an item applies, unless *Show Toolbar* is off."""
        self.page_kind, self.has_graphs = page_kind, has_graphs
        any_shown = False
        for item_id, cell in self.cells.items():
            visible = applies(BY_ID[item_id], page_kind, has_graphs)
            cell.set_visible(visible)
            any_shown |= visible
        self.set_visible(bool(self.settings.get(SHOW_SETTING)) and (has_graphs or any_shown))

    def visible_items(self) -> list[str]:
        return [i for i, c in self.cells.items() if c.get_visible()]

    def release(self) -> None:
        self.connections.disconnect_all()


def choices_menu(item: ToolbarItem) -> Gio.Menu:
    """Radio items for a menu item's choices, then *Custom…* where it has
    one (the time range)."""
    menu = Gio.Menu()
    presets = Gio.Menu()
    for nick, label in item.choices:
        entry = Gio.MenuItem.new(label, None)
        entry.set_action_and_target_value(f"{ACTION_GROUP}.{item.id}", GLib.Variant("s", nick))
        presets.append_item(entry)
    menu.append_section(None, presets)
    if item.custom_key:
        custom = Gio.Menu()
        custom.append(CUSTOM_LABEL, f"{ACTION_GROUP}.custom-range")
        menu.append_section(None, custom)
    return menu


def customize_menu() -> Gio.Menu:
    """A check item per toolbar item the user places, then *Reset Toolbar*."""
    menu = Gio.Menu()
    items = Gio.Menu()
    for item in (i for i in ITEMS if not i.fixed):
        items.append(item.tooltip, f"{ACTION_GROUP}.show-{item.id}")
    menu.append_section("Show in Toolbar", items)
    reset = Gio.Menu()
    reset.append("Reset Toolbar", f"{ACTION_GROUP}.reset")
    menu.append_section(None, reset)
    return menu
