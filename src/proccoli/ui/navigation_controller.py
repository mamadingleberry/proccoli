"""The window's ways of moving between panes besides the sidebar: back and
forward (the actions, Alt+Left / Alt+Right, the mouse's side buttons) and
the *Go To* submenu with the current pane marked.

The history and the menu's contents are worked out by the display-free
``navigation.py``; this class owns the actions and the gesture, and asks
the window to show a page.
"""

from __future__ import annotations

from typing import Callable, Optional, Sequence

from gi.repository import Gio, GLib, Gtk

from .navigation import GOTO_ACTION, NavigationHistory, fill_goto_menu, mouse_direction
from .shortcuts import accels_for


class NavigationController:
    def __init__(self, window: Gtk.ApplicationWindow, app,
                 select_page: Callable[[str], bool]) -> None:
        """``select_page(page_id)`` shows a page (the window's)."""
        self.window = window
        self.select_page = select_page
        self.history = NavigationHistory()
        self._navigating = False             # a page change made by back/forward
        self.goto_menu = Gio.Menu()          # the main menu's Go To submenu

        self.goto_action = Gio.SimpleAction.new_stateful(
            GOTO_ACTION, GLib.VariantType.new("s"), GLib.Variant("s", ""))
        self.goto_action.connect("activate",
                                 lambda _a, target: select_page(target.get_string()))
        window.add_action(self.goto_action)

        self.actions = {}
        for name, step in (("back", self.go_back), ("forward", self.go_forward)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda *_a, f=step: f())
            action.set_enabled(False)
            window.add_action(action)
            self.actions[name] = action
        if app is not None:
            for name in ("win.back", "win.forward"):
                app.set_accels_for_action(name, accels_for(name))
        # Capture phase: the side buttons work over any widget. Other buttons
        # are denied at once, so they reach their own widgets untouched.
        self.mouse_gesture = Gtk.GestureClick(button=0)
        self.mouse_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.mouse_gesture.connect("pressed", lambda g, *_: self.on_mouse_button(g))
        window.add_controller(self.mouse_gesture)

    # -- following the window ------------------------------------------------------------

    def shown(self, page_id: Optional[str]) -> None:
        """The window shows ``page_id`` now: mark it in Go To, and remember
        it unless back or forward brought it."""
        if not page_id:
            return
        self.goto_action.set_state(GLib.Variant("s", page_id))
        if not self._navigating:
            self.history.visit(page_id)
        self._update_actions()

    def forget(self, page_id: str) -> None:
        """A page went away (an unplugged drive)."""
        self.history.remove(page_id)
        self._update_actions()

    def set_entries(self, entries: Sequence[tuple[str, str, str]]) -> None:
        """Go To's items: ``[(page_id, title, description)]`` in sidebar order."""
        fill_goto_menu(self.goto_menu, entries)

    # -- back and forward ------------------------------------------------------------

    def go_back(self) -> bool:
        return self._show_from_history(self.history.back())

    def go_forward(self) -> bool:
        return self._show_from_history(self.history.forward())

    def on_mouse_button(self, gesture) -> bool:
        """Mouse back/forward buttons; any other button is left alone. Not
        while a dialog is open over the window."""
        direction = mouse_direction(gesture.get_current_button())
        dialog = getattr(self.window, "get_visible_dialog", lambda: None)()
        if direction is None or dialog is not None:
            gesture.set_state(Gtk.EventSequenceState.DENIED)
            return False
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        return self.go_back() if direction == "back" else self.go_forward()

    def _show_from_history(self, page_id) -> bool:
        if page_id is None:
            return False
        self._navigating = True
        try:
            self.select_page(page_id)
        finally:
            self._navigating = False
        self._update_actions()
        return True

    def _update_actions(self) -> None:
        self.actions["back"].set_enabled(self.history.can_go_back())
        self.actions["forward"].set_enabled(self.history.can_go_forward())
