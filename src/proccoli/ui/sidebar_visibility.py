"""Showing and hiding the sidebar.

The sidebar can be hidden at any width, not only on narrow windows, and
the main menu (the app's logo) always stays at the window's top left:

- sidebar shown and beside the content: the logo sits at the start of
  the sidebar's header;
- sidebar hidden, or folded away on a narrow window: every page header
  shows it at its start instead.

F9 shows and hides the sidebar through the stateful ``win.toggle-sidebar``
action made here. The main menu offers three modes instead
: *Full*, *Icons Only* and *Hidden*, radio items of the
stateful ``win.sidebar-mode`` action, also made here. The style (full or
icons only, ``sidebar-style``) reaches the window through the injected
``on_style`` callback, which narrows the sidebar (``sidebar_style.py``).
In Lightweight Mode the style is pinned to icons only: the menu
has no *Full*, and a request for it shows icons only.

``SidebarVisibility`` keeps ``Adw.OverlaySplitView.show-sidebar`` in line
with the user's choice (``sidebar-shown``) on wide windows. On narrow
(collapsed) windows the sidebar is an overlay: it starts hidden, closes
when a page is picked, and the user's wide-window choice is left alone
and restored when the window widens again.
"""

from __future__ import annotations

from typing import Callable, Optional

from gi.repository import Gio, GLib

from ..core.connections import Connections
from ..core.profile import is_pinned
from .sidebar_style import MODE_ACTION, STYLE_SETTING, SidebarStyle, choose, mode_of, parse_style

SETTING = "sidebar-shown"
ACTION = "toggle-sidebar"            # in the window's "win" group; F9


def header_controls_visible(show_sidebar: bool, collapsed: bool) -> bool:
    """Whether a page header shows the logo (the main menu): when
    the sidebar isn't sitting beside the content."""
    return collapsed or not show_sidebar


class SidebarVisibility:
    def __init__(self, split_view, settings,
                 on_style: Optional[Callable[[SidebarStyle], None]] = None) -> None:
        self.split = split_view
        self.settings = settings
        self.on_style = on_style
        # F9: a boolean action with no parameter, toggled on activation (GIO's
        # default for such an action goes through change-state, handled here).
        self.action = Gio.SimpleAction.new_stateful(
            ACTION, None, GLib.Variant.new_boolean(split_view.get_show_sidebar()))
        self.action.connect("change-state", self._on_change_state)
        # The main menu's Full / Icons Only / Hidden radio items.
        self.mode_action = Gio.SimpleAction.new_stateful(
            MODE_ACTION, GLib.VariantType.new("s"), GLib.Variant.new_string(self.mode().value))
        self.mode_action.connect("change-state", self._on_mode_change)
        self.connections = Connections()
        self.connections.connect(split_view, "notify::collapsed", lambda *_: self._on_collapsed())
        self.connections.connect(split_view, "notify::show-sidebar", lambda *_: self._on_shown())
        self.connections.watch(settings, STYLE_SETTING, lambda *_: self._on_style())
        self._on_collapsed()
        self._on_style()

    @property
    def preferred(self) -> bool:
        """The user's choice for wide windows."""
        return bool(self.settings.get(SETTING))

    @property
    def style(self) -> SidebarStyle:
        return parse_style(self.settings.get(STYLE_SETTING))

    def mode(self):
        """What the menu marks now (``sidebar_style.Mode``)."""
        return mode_of(self.split.get_show_sidebar(), self.style)

    @property
    def full_allowed(self) -> bool:
        return not is_pinned(self.settings, STYLE_SETTING)

    def _on_mode_change(self, _action, value: GLib.Variant) -> None:
        shown, style = choose(value.get_string(), self.style, self.full_allowed)
        if style != self.style:
            self.settings.set(STYLE_SETTING, style.value)
        self.split.set_show_sidebar(shown)
        self._sync_action()

    def _on_style(self) -> None:
        if self.on_style is not None:
            self.on_style(self.style)
        self._sync_action()

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
        mode = self.mode().value
        if self.mode_action.get_state().get_string() != mode:
            self.mode_action.set_state(GLib.Variant.new_string(mode))

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
        self.connections.disconnect_all()
