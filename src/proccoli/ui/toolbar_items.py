"""What the graph toolbar can hold. Display-free.

Each ``ToolbarItem`` has a ``title``, shown above its control (a menu
showing the current choice, or a switch for a toggle), and changes
one setting, the same one Preferences does,
so the toolbar, Preferences and every graph agree: a ``menu`` picks one of
``choices`` (the schema's enum nicks with their labels, shared with
Preferences), a ``toggle`` turns a boolean on or off.

``toolbar-items`` holds the shown items in the user's order; the rest are
hidden. A ``fixed`` item isn't the user's to place: it's always shown, at
the end, on the pages it applies to (*Logical CPUs*, on the Processor
pane only), and never listed or stored. ``set_shown`` puts an item back where the default order has it
(``reorder.arrange()``), so showing one never jumbles the others.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from ..core.ticker import CUSTOM, CUSTOM_KEY, time_range_s
from . import reorder
from .time_range import describe

SETTING = "toolbar-items"
SHOW_SETTING = "show-toolbar"         # the whole bar (main menu → Show Toolbar)

# (nick, label), in the order the menu lists them; Preferences uses them too.
GRAPH_TIME_RANGES = (("30-seconds", "30 Seconds"), ("1-minute", "1 Minute"),
                     ("2-minutes", "2 Minutes"), ("5-minutes", "5 Minutes"),
                     ("10-minutes", "10 Minutes"), ("30-minutes", "30 Minutes"),
                     ("1-hour", "1 Hour"), ("6-hours", "6 Hours"), ("1-day", "1 Day"))


@dataclass(frozen=True)
class ToolbarItem:
    id: str
    title: str                      # shown above the control, always
    key: str                        # the setting it changes
    kind: str                       # "menu" or "toggle"
    tooltip: str
    choices: tuple = ()             # menus: (nick, label)
    page_kinds: Optional[frozenset] = None   # only on these kinds of page
    fixed: bool = False             # always there where it applies; not customizable
    custom_key: str = ""            # a menu's *Custom…* value (the time range)

    def choice_label(self, nick: str, settings=None) -> str:
        """The menu button's text: a choice's label, or for *Custom…* the
        range itself ("2 Hours")."""
        if nick == CUSTOM and self.custom_key and settings is not None:
            return describe(time_range_s(settings))
        return dict(self.choices).get(nick, nick)


ITEMS: tuple[ToolbarItem, ...] = (
    ToolbarItem("time-range", "Time Range", "graph-time-range", "menu",
                "Graph Time Range", GRAPH_TIME_RANGES, custom_key=CUSTOM_KEY),
    ToolbarItem("axes", "Graph Axes", "show-graph-axes", "toggle", "Show Graph Axes"),
    ToolbarItem("grids", "Graph Grid", "show-graph-grids", "toggle", "Show Graph Grids"),
    ToolbarItem("logical-cpus", "Logical CPUs", "show-logical-cpus", "toggle",
                "Show Each Logical CPU", page_kinds=frozenset({"cpu"}), fixed=True),
)
BY_ID = {item.id: item for item in ITEMS}
DEFAULT_ORDER = [item.id for item in ITEMS if not item.fixed]     # the user's to arrange
FIXED = [item.id for item in ITEMS if item.fixed]


def shown(saved: Sequence[str]) -> list[str]:
    """The items to show, in the user's order (unknown and fixed IDs
    dropped)."""
    return [i for i in dict.fromkeys(saved) if i in DEFAULT_ORDER]


def set_shown(saved: Sequence[str], item_id: str, show: bool) -> list[str]:
    """``saved`` with ``item_id`` shown (at its default place) or hidden."""
    current = shown(saved)
    if not show:
        return [i for i in current if i != item_id]
    if item_id in current or item_id not in DEFAULT_ORDER:
        return current
    wanted = set(current) | {item_id}
    return reorder.arrange([i for i in DEFAULT_ORDER if i in wanted], current, ())


def toolbar_shown(settings) -> bool:
    """Whether the window shows the graph toolbar (not in Lightweight
    Mode, nor with *Show Toolbar* off): pages with a control the toolbar
    also has show their own only when it doesn't."""
    from ..core.profile import profile_of
    return profile_of(settings).graph_toolbar and bool(settings.get(SHOW_SETTING))


def applies(item: ToolbarItem, page_kind: str, has_graphs: bool) -> bool:
    """Whether ``item`` does anything on a page of ``page_kind``: every
    item is about graphs, so never on a page without them (Apps,
    Processes). *Update Interval* isn't an item: it changes every reading
    everywhere, not a page's view, so it stays in Preferences."""
    if not has_graphs:
        return False
    return item.page_kinds is None or page_kind in item.page_kinds
