"""Building blocks of the Preferences pages: a page, a group, and rows for a
switch, a choice or a number, each bound to its setting (and greyed out
with a padlock while Lightweight Mode fixes it)."""

from __future__ import annotations

from gi.repository import Adw, Gtk
from ...core.profile import profile_of


FIXED_ICON = "changes-prevent-symbolic"     # a padlock: GNOME's "locked for now"
FIXED_TIP = "Fixed while Lightweight Mode is on. Your own choice comes back when it's off."


def fixed_icon() -> Gtk.Image:
    """The padlock before a setting Lightweight Mode fixes, explaining why."""
    icon = Gtk.Image(icon_name=FIXED_ICON, tooltip_text=FIXED_TIP)
    icon.update_property([Gtk.AccessibleProperty.LABEL], ["Fixed by Lightweight Mode"])
    return icon


def fixed_notice() -> Adw.PreferencesGroup:
    """The top of a page with settings Lightweight Mode fixes (hidden
    until one turns up on the page)."""
    group = Adw.PreferencesGroup(visible=False)
    row = Adw.ActionRow(title="Some settings are fixed in Lightweight Mode",
                        subtitle="They're greyed out with a padlock, and your own choices "
                                 "come back when it's off (System → Memory Use)")
    row.add_prefix(Gtk.Image(icon_name=FIXED_ICON))
    group.add(row)
    group.row = row
    return group


class RowBuilders:
    """Pages, groups and setting-bound rows (a part of ``PreferencesDialog``)."""

    def _page(self, title: str, icon: str) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(title=title, icon_name=icon)
        self.add(page)
        if profile_of(self.settings).is_lightweight:
            # First on the page; shown once a fixed setting turns up on it.
            notice = fixed_notice()
            page.add(notice)
            self._notices[page] = notice
        return page

    def _add(self, container, row) -> None:
        """A row into a group, or into an expander row (the column lists)."""
        if isinstance(container, Adw.ExpanderRow):
            container.add_row(row)
        else:
            container.add(row)
            self._row_counts[container] = self._row_counts.get(container, 0) + 1

    def _group(self, page, title: str, description: str = "") -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(title=title, description=description)
        page.add(group)
        return group

    def _watch(self, key: str, callback) -> None:
        self.connections.watch(self.settings, key, callback)

    def _switch(self, group, key: str, title: str, subtitle: str = "") -> Adw.SwitchRow:
        row = Adw.SwitchRow(title=title, subtitle=subtitle,
                            active=self.settings.get(key))
        row.connect("notify::active", lambda r, _p: self._set(key, r.get_active()))
        self._watch(key, lambda _k, v: row.get_active() != v and row.set_active(v))
        self._add(group, row)
        self.rows[key] = row
        return row

    def _combo(self, group, key: str, title: str, choices, subtitle: str = "") -> Adw.ComboRow:
        nicks = [n for n, _ in choices]
        row = Adw.ComboRow(title=title, subtitle=subtitle,
                           model=Gtk.StringList.new([label for _, label in choices]))
        current = self.settings.get(key)
        row.set_selected(nicks.index(current) if current in nicks else 0)
        row.connect("notify::selected", lambda r, _p: self._set(key, nicks[r.get_selected()]))
        self._watch(key, lambda _k, v: v in nicks and row.get_selected() != nicks.index(v)
                    and row.set_selected(nicks.index(v)))
        self._add(group, row)
        self.rows[key] = row
        return row

    def _spin(self, group, key: str, title: str, low: int, high: int) -> Adw.SpinRow:
        row = Adw.SpinRow.new_with_range(low, high, 10)
        row.set_title(title)
        row.set_value(self.settings.get(key))
        row.connect("notify::value", lambda r, _p: self._set(key, int(r.get_value())))
        self._watch(key, lambda _k, v: int(row.get_value()) != v and row.set_value(v))
        self._add(group, row)
        self.rows[key] = row
        return row

    def _set(self, key: str, value) -> None:
        if self.settings.get(key) != value:
            self.settings.set(key, value)
