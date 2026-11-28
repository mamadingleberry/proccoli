"""The sidebar's arrangement as the user made it: their order of the
entries, the minimised ones, and the details each entry hides, saved in
the settings. The order itself is worked out by the display-free
``sidebar_order.py``; this part of ``StackSidebar`` applies and saves it."""

from __future__ import annotations

from . import reorder
from . import sidebar_groups as groups
from .page import PageKind
from .sidebar_fields import Field, hidden, set_shown

# Pages without a sidebar chart (so without an entry color), pinned at the
# top: they can't be moved or minimised.
UNCHARTED = (PageKind.OVERVIEW, PageKind.APPS, PageKind.PROCESSES)
PINNED = UNCHARTED


class SidebarArrangement:
    """Order, minimised entries and hidden details (a part of ``StackSidebar``)."""

    def saved_order(self) -> list[str]:
        return list(self.settings.get("sidebar-order")) if self.settings else self._saved_order

    def minimized_ids(self) -> set[str]:
        return set(self.settings.get("sidebar-minimized")) if self.settings else self._minimized

    def pinned_ids(self) -> list[str]:
        return [i for i in self.default_order() if self.items[i].page.kind in PINNED]

    def _rearrange(self, sort: bool = True) -> None:
        group_of = self.group_of()
        order = groups.nest(reorder.arrange(self.default_order(), self.saved_order(),
                                            self.pinned_ids()), group_of)
        self._rank = {page_id: i for i, page_id in enumerate(order)}
        self._apply_groups(group_of)
        if sort:
            self.list_box.invalidate_sort()
            self.assign_colors()

    # -- groups ---------------------------------------------------------------

    def collapsed_groups(self) -> set[str]:
        return set(self.settings.get(groups.COLLAPSED_SETTING)) if self.settings \
            else self._collapsed

    def toggle_group(self, group_id: str) -> None:
        """Show or hide a group's devices; remembered."""
        ids = self.collapsed_groups()
        ids ^= {group_id}
        if self.settings is not None:
            self.settings.set(groups.COLLAPSED_SETTING, sorted(ids))
        else:
            self._collapsed = ids
            self._apply_groups(self.group_of())

    def _apply_groups(self, group_of: dict) -> None:
        """Indent each group's devices, and hide those of collapsed groups."""
        collapsed = self.collapsed_groups()
        hidden = groups.hidden_children(group_of, collapsed)
        for page_id, item in self.items.items():
            item.set_nested(page_id in group_of)
            item.set_visible(page_id not in hidden)
            if item.page.is_group:
                item.set_expanded(page_id not in collapsed)

    def _save_order(self, order: list[str]) -> None:
        rest = [i for i in order if i not in self.pinned_ids()]
        if self.settings is not None:
            self.settings.set("sidebar-order", rest)
        else:
            self._saved_order = rest
            self._rearrange()

    def move(self, page_id: str, delta: int) -> None:
        """Move an entry ``delta`` places (negative: up): a device within its
        group, a group with its devices."""
        self._save_order(groups.move(self.order(), page_id, delta, self.pinned_ids(),
                                     self.group_of()))

    def move_before(self, page_id: str, target: str) -> None:
        """Drop ``page_id`` where ``target`` is."""
        self._save_order(groups.move_before(self.order(), page_id, target,
                                            self.pinned_ids(), self.group_of()))

    def set_minimized(self, page_id: str, minimized: bool) -> None:
        ids = self.minimized_ids()
        if minimized and self.items[page_id].movable:
            ids.add(page_id)
        else:
            ids.discard(page_id)
        if self.settings is not None:
            self.settings.set("sidebar-minimized", sorted(ids))
        else:
            self._minimized = ids
            self._apply_minimized()

    def hidden_fields_map(self) -> dict[str, list[str]]:
        return dict(self.settings.get("sidebar-hidden-fields")) if self.settings \
            else self._hidden_fields

    def field_shown(self, page_id: str, field: Field) -> bool:
        """The entry's own choice (not the global preferences)."""
        return field not in hidden(self.hidden_fields_map(), page_id)

    def set_field_shown(self, page_id: str, field: Field, shown: bool) -> None:
        mapping = set_shown(self.hidden_fields_map(), page_id, Field(field), shown)
        if self.settings is not None:
            self.settings.set("sidebar-hidden-fields", mapping)
        else:
            self._hidden_fields = mapping
            self._apply_fields()

    def _apply_fields(self) -> None:
        mapping = self.hidden_fields_map()
        for page_id, item in self.items.items():
            item.set_hidden_fields(hidden(mapping, page_id))

    def reset_order(self) -> None:
        """Back to the built-in order, nothing minimised."""
        if self.settings is not None:
            self.settings.set("sidebar-order", [])
            self.settings.set("sidebar-minimized", [])
            self.settings.set("sidebar-hidden-fields", {})
        else:
            self._saved_order, self._minimized, self._hidden_fields = [], set(), {}
            self._rearrange()
            self._apply_minimized()
            self._apply_fields()

    def _apply_minimized(self) -> None:
        ids = self.minimized_ids()
        for page_id, item in self.items.items():
            item.set_minimized(page_id in ids)
