"""Which parts of each sidebar entry are shown (DESIGN.md §9.2).

Every entry except Apps and Processes can hide its name, description
(model, device ID, interface name...), usage line and chart. The choices
live in ``sidebar-hidden-fields``: page ID → hidden field names. The global
*Show Usage Details* and *Show Device Descriptions* preferences still apply
to every entry, and a minimised entry (M28) shows only its icon and name.

Pure functions, unit-tested without a display.
"""

from __future__ import annotations

from enum import Enum
from typing import Mapping, Sequence


class Field(str, Enum):
    NAME = "name"
    DESCRIPTION = "description"
    USAGE = "usage"
    CHART = "chart"


FIELD_LABELS = {Field.NAME: "Name", Field.DESCRIPTION: "Description",
                Field.USAGE: "Usage Details", Field.CHART: "Chart"}


def hidden(mapping: Mapping[str, Sequence[str]], page_id: str) -> set[Field]:
    """The fields ``page_id`` hides (unknown names ignored)."""
    out = set()
    for name in mapping.get(page_id, ()):
        try:
            out.add(Field(name))
        except ValueError:
            pass
    return out


def set_shown(mapping: Mapping[str, Sequence[str]], page_id: str, field: Field,
              shown: bool) -> dict[str, list[str]]:
    """A new mapping with ``field`` of ``page_id`` shown or hidden (entries
    with nothing hidden are dropped, so the setting stays small)."""
    out = {k: list(v) for k, v in mapping.items()}
    fields = hidden(out, page_id)
    if shown:
        fields.discard(field)
    else:
        fields.add(field)
    if fields:
        out[page_id] = sorted(f.value for f in fields)
    else:
        out.pop(page_id, None)
    return out


def visible(field: Field, hidden_fields: set[Field], *, show_details: bool = True,
            show_description: bool = True, minimized: bool = False) -> bool:
    """Whether ``field`` shows, given the entry's own choices, the global
    preferences and minimising."""
    if field in hidden_fields:
        return False
    if field == Field.NAME:
        return True
    if minimized:
        return False
    if field == Field.DESCRIPTION:
        return show_description
    return show_details
