"""The sidebar's three modes: full, icons only, or hidden (DESIGN.md §9.2,
Milestone 54).

Two settings hold the mode: ``sidebar-shown`` (shown or hidden, M46) and
``sidebar-style`` (full or icons only). Hiding keeps the style, so F9 brings
back the sidebar as it was. In the icons-only style each entry shows just
its icon, and hovering shows its name, description and usage.

Pure functions, unit-tested without a display.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

STYLE_SETTING = "sidebar-style"
MODE_ACTION = "sidebar-mode"         # in the window's "win" group; state: a Mode
SECTION_LABEL = "Sidebar"

# The narrowest the icons-only sidebar gets; it widens to fit its header
# (logo and burger).
MIN_RAIL_WIDTH = 56


class SidebarStyle(str, Enum):
    FULL = "full"
    ICONS = "icons"


class Mode(str, Enum):
    """What the main menu offers: one of three, the current one marked."""
    FULL = "full"
    ICONS = "icons"
    HIDDEN = "hidden"


MODE_LABELS = {Mode.FULL: "Full", Mode.ICONS: "Icons Only", Mode.HIDDEN: "Hidden"}


def parse_style(value) -> SidebarStyle:
    try:
        return SidebarStyle(value)
    except ValueError:
        return SidebarStyle.FULL


def mode_of(shown: bool, style) -> Mode:
    """The mode the menu marks, from whether the sidebar shows and its style."""
    if not shown:
        return Mode.HIDDEN
    return Mode.ICONS if parse_style(style) == SidebarStyle.ICONS else Mode.FULL


def choose(mode, style) -> tuple[bool, SidebarStyle]:
    """``(shown, style)`` for a mode picked from the menu. *Hidden* keeps
    the current style, so showing the sidebar again restores it."""
    mode = Mode(mode)
    if mode == Mode.HIDDEN:
        return False, parse_style(style)
    return True, SidebarStyle.ICONS if mode == Mode.ICONS else SidebarStyle.FULL


def rail_width(header_width: int) -> int:
    """The icons-only sidebar's width: its header must fit (logo, burger)."""
    return max(MIN_RAIL_WIDTH, header_width)


def compact_tooltip(title: str, description: str = "",
                    usage: Optional[str] = None) -> str:
    """The hover text of an icons-only entry: name, then description and
    usage on their own lines when there are any."""
    lines = [title] + [part for part in (description, usage) if part]
    return "\n".join(lines)
