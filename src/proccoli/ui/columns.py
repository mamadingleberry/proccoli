"""A table's columns, without a display: which there are, which the
settings show, how rows compare, and which column (and direction) the
table is sorted by, as saved in the settings.

``TablePage`` renders a ``ColumnSet``; the decisions are here, so they're
unit-tested without building a ``Gtk.ColumnView``.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from ..core.profile import profile_of


@dataclass
class Column:
    id: str
    title: str
    value: Callable[[Any], Any]                 # data -> sortable value
    text: Callable[[Any], str]                  # data -> cell text
    setting: Optional[str] = None               # visibility key, None = always
    numeric: bool = True
    expand: bool = False
    width: int = 110
    icon: Optional[Callable[[Any], Any]] = None  # data -> Gio.Icon (name column)


def shown_column(spec: Column, settings) -> Column:
    """``spec`` as the running profile shows it: no icon in Lightweight
    Mode (no icon lookups or textures)."""
    if spec.icon is not None and not profile_of(settings).app_icons:
        return dataclasses.replace(spec, icon=None)
    return spec


def compare(a, b) -> int:
    """-1, 0 or 1; a missing value (None) sorts first."""
    if a is None:
        return 0 if b is None else -1
    if b is None:
        return 1
    return (a > b) - (a < b)


class ColumnSet:
    """The columns of one table; ``sort_key`` prefixes its sort settings
    (``processes-sort-by``, ``processes-sort-by-ascending``)."""

    DEFAULT_SORT = "cpu"

    def __init__(self, columns: Sequence[Column], sort_key: str) -> None:
        self.columns = list(columns)
        self.sort_key = sort_key

    def ids(self) -> list[str]:
        return [c.id for c in self.columns]

    def setting_keys(self) -> list[str]:
        """The settings that show or hide a column."""
        return [c.setting for c in self.columns if c.setting]

    def visibility(self, settings) -> dict[str, bool]:
        """``{column id: shown}`` for the columns a setting controls."""
        return {c.id: bool(settings.get(c.setting)) for c in self.columns if c.setting}

    def sort_choice(self, settings) -> tuple[str, bool]:
        """The saved sort: ``(column id, ascending)``. A saved index that's
        out of range (or the first column, never offered) means the
        processor column, else the first."""
        index = settings.get(f"{self.sort_key}-sort-by")
        ascending = bool(settings.get(f"{self.sort_key}-sort-by-ascending"))
        ids = self.ids()
        default = ids.index(self.DEFAULT_SORT) if self.DEFAULT_SORT in ids else 0
        chosen = index if 0 < index < len(ids) else default
        return ids[chosen], ascending

    def sort_settings(self, column_id: str, ascending: bool) -> dict[str, Any]:
        """What to save for sorting by ``column_id``."""
        return {f"{self.sort_key}-sort-by": self.ids().index(column_id),
                f"{self.sort_key}-sort-by-ascending": ascending}
