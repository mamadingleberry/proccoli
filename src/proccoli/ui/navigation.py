"""Moving between panes without the sidebar.

- *Go To*: a submenu of the main menu listing every pane in
  the sidebar's order. Its items use the stateful ``win.go-to`` action,
  whose state is the visible page's ID, so the current pane is marked.
  Panes with the same name (two identical drives) are told apart by their
  description.
- *Back and forward*: ``NavigationHistory`` remembers the
  panes visited, like a browser. The mouse's back and forward side buttons
  (8 and 9) and Alt+Left / Alt+Right move through it.

The menu is a plain ``Gio.Menu`` filled in place, so an open menu stays
current, and nothing here needs a display.
"""

from __future__ import annotations

from collections import Counter
from typing import Optional, Sequence

from gi.repository import Gio, GLib

GOTO_ACTION = "go-to"             # in the window's "win" group
GOTO_LABEL = "Go To"


def goto_labels(entries: Sequence[tuple[str, str, str]]) -> list[tuple[str, str]]:
    """``[(page_id, title, description)]`` → ``[(page_id, label)]``: the
    title, or "title (description)" when another pane has the same title
    (the page ID if there's no description)."""
    counts = Counter(title for _, title, _ in entries)
    out = []
    for page_id, title, description in entries:
        label = title
        if counts[title] > 1:
            label = f"{title} ({description or page_id})"
        out.append((page_id, label))
    return out


def fill_goto_menu(menu: Gio.Menu, entries: Sequence[tuple[str, str, str]]) -> None:
    """Replace ``menu``'s items with one per pane, in order."""
    menu.remove_all()
    for page_id, label in goto_labels(entries):
        item = Gio.MenuItem.new(label, None)
        item.set_action_and_target_value(f"win.{GOTO_ACTION}", GLib.Variant("s", page_id))
        menu.append_item(item)


def menu_targets(menu: Gio.MenuModel) -> list[tuple[str, str]]:
    """``[(label, page_id)]`` of a filled Go To menu (tests, accessibility)."""
    out = []
    for i in range(menu.get_n_items()):
        label = menu.get_item_attribute_value(i, "label", GLib.VariantType("s"))
        target = menu.get_item_attribute_value(i, "target", GLib.VariantType("s"))
        out.append((label.get_string(), target.get_string()))
    return out


# Mouse buttons (GDK numbering): the thumb buttons. Most mice report them
# as BTN_SIDE / BTN_EXTRA (GDK 8 / 9); some as BTN_BACK / BTN_FORWARD,
# which GDK on Wayland numbers on from there (11 / 10).
MOUSE_BACK = 8
MOUSE_FORWARD = 9
MOUSE_BACK_ALT = 11
MOUSE_FORWARD_ALT = 10
HISTORY_LIMIT = 50


class NavigationHistory:
    """Panes visited, browser-style. ``visit`` is called for every page
    change except those made by ``back``/``forward`` themselves."""

    def __init__(self, limit: int = HISTORY_LIMIT) -> None:
        self.limit = limit
        self.current: Optional[str] = None
        self.back_stack: list[str] = []
        self.forward_stack: list[str] = []

    def visit(self, page_id: str) -> None:
        """A new page was shown: it starts a new branch (forward is lost)."""
        if page_id == self.current:
            return
        if self.current is not None:
            self.back_stack.append(self.current)
            del self.back_stack[:-self.limit]
        elif self.back_stack and self.back_stack[-1] == page_id:
            self.back_stack.pop()          # back where we were before a removed page
        self.forward_stack.clear()
        self.current = page_id

    def can_go_back(self) -> bool:
        return bool(self.back_stack)

    def can_go_forward(self) -> bool:
        return bool(self.forward_stack)

    def back(self) -> Optional[str]:
        """The page to show going back (None: nowhere to go)."""
        if not self.back_stack:
            return None
        if self.current is not None:
            self.forward_stack.append(self.current)
        self.current = self.back_stack.pop()
        return self.current

    def forward(self) -> Optional[str]:
        if not self.forward_stack:
            return None
        if self.current is not None:
            self.back_stack.append(self.current)
        self.current = self.forward_stack.pop()
        return self.current

    def remove(self, page_id: str) -> None:
        """A page went away (an unplugged drive): forget it, and merge the
        neighbours that removing it makes equal."""
        def clean(stack: list[str], neighbour: Optional[str]) -> list[str]:
            out: list[str] = []
            for p in stack:
                if p != page_id and (not out or out[-1] != p):
                    out.append(p)
            if out and out[-1] == neighbour:
                out.pop()
            return out
        if self.current == page_id:
            self.current = None
        self.back_stack = clean(self.back_stack, self.current)
        # The forward stack is stored nearest-last too.
        self.forward_stack = clean(self.forward_stack, self.current)


def mouse_direction(button: int) -> Optional[str]:
    """"back", "forward" or None for a mouse button number."""
    return {MOUSE_BACK: "back", MOUSE_FORWARD: "forward",
            MOUSE_BACK_ALT: "back", MOUSE_FORWARD_ALT: "forward"}.get(button)

