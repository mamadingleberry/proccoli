"""Showing and hiding the sidebar (DESIGN.md §9.2, Milestone 46).

The sidebar can be hidden at any width, not only on narrow windows, and
the main menu (the "burger") always stays at the window's top left:

- sidebar shown and beside the content: the logo and the burger sit at
  the start of the sidebar's header;
- sidebar hidden, or folded away on a narrow window: every page header
  shows them at its start instead.

The sidebar is shown and hidden from the main menu's *Show Sidebar* check
item or F9 (Milestone 52), both the stateful ``win.toggle-sidebar``
action made here.

``SidebarVisibility`` keeps ``Adw.OverlaySplitView.show-sidebar`` in line
with the user's choice (``sidebar-shown``) on wide windows. On narrow
(collapsed) windows the sidebar is an overlay: it starts hidden, closes
when a page is picked, and the user's wide-window choice is left alone
and restored when the window widens again.
"""

from __future__ import annotations

from gi.repository import Gio, GLib

SETTING = "sidebar-shown"
ACTION = "toggle-sidebar"            # in the window's "win" group
LABEL = "Show Sidebar"


def header_controls_visible(show_sidebar: bool, collapsed: bool) -> bool:
    """Whether a page header shows the logo and the burger: when
    the sidebar isn't sitting beside the content."""
    return collapsed or not show_sidebar


class SidebarVisibility:
    def __init__(self, split_view, settings) -> None:
        self.split = split_view
        self.settings = settings
        # The menu item: checked while the sidebar is shown. Activating it
        # toggles (GIO's default for a boolean action with no parameter
        # goes through change-state, handled here).
        self.action = Gio.SimpleAction.new_stateful(
            ACTION, None, GLib.Variant.new_boolean(split_view.get_show_sidebar()))
        self.action.connect("change-state", self._on_change_state)
        self._handlers = [
            split_view.connect("notify::collapsed", lambda *_: self._on_collapsed()),
            split_view.connect("notify::show-sidebar", lambda *_: self._on_shown()),
        ]
        self._on_collapsed()
        self._sync_action()

    @property
    def preferred(self) -> bool:
        """The user's choice for wide windows."""
        return bool(self.settings.get(SETTING))

    def _on_collapsed(self) -> None:
        if self.split.get_collapsed():
            self.split.set_show_sidebar(False)        # overlay: closed until asked
        else:
            self.split.set_show_sidebar(self.preferred)

    def _on_change_state(self, _action, value: GLib.Variant) -> None:
        self.split.set_show_sidebar(value.get_boolean())

    def _sync_action(self) -> None:
        shown = self.split.get_show_sidebar()
        if self.action.get_state().get_boolean() != shown:
            self.action.set_state(GLib.Variant.new_boolean(shown))

    def _on_shown(self) -> None:
        self._sync_action()
        if not self.split.get_collapsed():
            shown = self.split.get_show_sidebar()
            if shown != self.preferred:
                self.settings.set(SETTING, shown)

    def toggle(self) -> None:
        self.split.set_show_sidebar(not self.split.get_show_sidebar())

    def page_selected(self) -> None:
        """Like a phone layout: picking a page closes the overlaid sidebar."""
        if self.split.get_collapsed():
            self.split.set_show_sidebar(False)

    def shutdown(self) -> None:
        for h in self._handlers:
            self.split.disconnect(h)
        self._handlers = []
