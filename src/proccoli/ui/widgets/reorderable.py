"""Drag-and-drop and keyboard reordering for any row of widgets:
the sidebar's entries and the graph toolbar's buttons.

``make_reorderable(widget, item_id, on_drop, on_move, ...)`` adds the
controllers: dragging ``widget`` carries ``item_id`` (only while
``can_drag``), dropping another item's ID on it calls
``on_drop(dragged_id, item_id)``, and ``modifiers`` with the ``keys``
arrows calls ``on_move(item_id, -1 or 1)``: Alt+Up / Alt+Down in the
sidebar, Ctrl+Shift+Left / Right in the toolbar (Alt+Left / Right are
Back and Forward). Where the IDs end up is the caller's rule
(``ui/reorder.py``), so this module only wires events.
"""

from __future__ import annotations

from typing import Callable, Optional

from gi.repository import Gdk, GObject, Gtk

VERTICAL = (Gdk.KEY_Up, Gdk.KEY_Down)
HORIZONTAL = (Gdk.KEY_Left, Gdk.KEY_Right)
ALT = Gdk.ModifierType.ALT_MASK
CTRL_SHIFT = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
_MODIFIERS = (Gdk.ModifierType.ALT_MASK | Gdk.ModifierType.CONTROL_MASK
              | Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.SUPER_MASK)


def make_reorderable(widget: Gtk.Widget, item_id: str,
                     on_drop: Callable[[str, str], bool],
                     on_move: Optional[Callable[[str, int], None]] = None,
                     can_drag: Callable[[], bool] = lambda: True,
                     keys: tuple[int, int] = VERTICAL,
                     modifiers=ALT) -> list[Gtk.EventController]:
    """Wire ``widget`` for reordering; returns the controllers added."""
    drag = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
    drag.connect("prepare", lambda *_: Gdk.ContentProvider.new_for_value(item_id)
                 if can_drag() else None)
    widget.add_controller(drag)
    drop = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
    drop.connect("drop", lambda _t, value, _x, _y: bool(value) and value != item_id
                 and on_drop(value, item_id))
    widget.add_controller(drop)
    controllers: list[Gtk.EventController] = [drag, drop]
    if on_move is not None:
        key = Gtk.EventControllerKey()
        key.connect("key-pressed", lambda _c, keyval, _code, state: _on_key(
            item_id, keyval, state, keys, modifiers, on_move, can_drag))
        widget.add_controller(key)
        controllers.append(key)
    return controllers


def _on_key(item_id: str, keyval: int, state, keys, modifiers, on_move, can_drag) -> bool:
    if (state & _MODIFIERS) != modifiers or keyval not in keys or not can_drag():
        return False
    on_move(item_id, -1 if keyval == keys[0] else 1)
    return True
