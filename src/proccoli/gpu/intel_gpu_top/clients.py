"""Per-process ("clients") table, similar to System Monitor's Processes tab."""

from __future__ import annotations

from gi.repository import GObject, Gio, Gtk

from ...ui.widgets.app_icon import set_app_icon
from .history import to_float


class ClientRow(GObject.Object):
    __gtype_name__ = "IgtgClientRow"

    revision = GObject.Property(type=int, default=0)

    def __init__(self, cid: str) -> None:
        super().__init__()
        self.cid = cid
        self.name = ""
        self.pid = 0
        self.busy: dict[str, float] = {}

    @property
    def total(self) -> float:
        return sum(self.busy.values())

    def update(self, data: dict) -> None:
        self.name = str(data.get("name", ""))
        try:
            self.pid = int(data.get("pid", 0))
        except (TypeError, ValueError):
            self.pid = 0
        busy = {}
        classes = data.get("engine-classes") or {}
        if isinstance(classes, dict):
            for eng, d in classes.items():
                if isinstance(d, dict):
                    v = to_float(d.get("busy"))
                    if v is not None:
                        busy[eng] = v
        self.busy = busy
        self.revision += 1


def _cmp(a, b) -> int:
    return (a > b) - (a < b)


class ClientsView(Gtk.Box):
    def __init__(self, app_icon=None) -> None:
        """``app_icon(pid)`` gives a process's app icon (Gio.Icon or None);
        without it every row shows the missing-icon puzzle piece."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.app_icon = app_icon or (lambda pid: None)
        self.rows: dict[str, ClientRow] = {}
        self.store = Gio.ListStore(item_type=ClientRow)
        self.engine_columns: dict[str, Gtk.ColumnViewColumn] = {}

        self.view = Gtk.ColumnView()
        self.view.add_css_class("data-table")
        self.view.set_reorderable(True)
        self.sorted = Gtk.SortListModel(model=self.store, sorter=self.view.get_sorter())
        self.view.set_model(Gtk.NoSelection(model=self.sorted))

        self._add_text_column("Process", lambda r: r.name, expand=True, icon=True,
                              sort=lambda a, b: _cmp(a.name.lower(), b.name.lower()))
        self._add_text_column("PID", lambda r: str(r.pid) if r.pid else "",
                              numeric=True, sort=lambda a, b: _cmp(a.pid, b.pid))
        total = self._add_text_column(
            "Total", lambda r: f"{r.total:.1f} %", numeric=True,
            sort=lambda a, b: _cmp(a.total, b.total))
        self.view.sort_by_column(total, Gtk.SortType.DESCENDING)

        scroller = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scroller.set_child(self.view)

        self.empty = Gtk.Label(
            label="No processes are using the GPU.",
            vexpand=True, valign=Gtk.Align.CENTER)
        self.empty.add_css_class("dim-label")

        self.stack = Gtk.Stack()
        self.stack.add_named(scroller, "table")
        self.stack.add_named(self.empty, "empty")
        self.stack.set_visible_child_name("empty")
        self.append(self.stack)

        note = Gtk.Label(
            label="“Total” is the sum of the per-engine-class utilisation, so it can exceed 100 %.",
            xalign=0, wrap=True)
        note.add_css_class("caption")
        note.add_css_class("dim-label")
        note.set_margin_start(12)
        note.set_margin_end(12)
        note.set_margin_top(6)
        note.set_margin_bottom(6)
        self.append(note)

    def _add_text_column(self, title, getter, *, numeric=False, expand=False,
                         sort=None, icon=False) -> Gtk.ColumnViewColumn:
        """``icon``: the row's app icon left of the text, as in Apps and
        Processes."""
        factory = Gtk.SignalListItemFactory()

        def setup(_f, item):
            label = Gtk.Label(xalign=1.0 if numeric else 0.0)
            if numeric:
                label.add_css_class("numeric")
            if icon:
                box = Gtk.Box(spacing=8)
                box.append(Gtk.Image(pixel_size=16))
                box.append(label)
                item.set_child(box)
            else:
                item.set_child(label)

        def label_of(item):
            child = item.get_child()
            return child.get_last_child() if icon else child

        def fill(item, row):
            label_of(item).set_label(getter(row))
            if icon:
                set_app_icon(item.get_child().get_first_child(), self.app_icon(row.pid))

        def bind(_f, item):
            row = item.get_item()
            label = label_of(item)
            fill(item, row)
            handler = row.connect("notify::revision", lambda r, _p: fill(item, r))
            label._igtg_handler = (row, handler)

        def unbind(_f, item):
            label = label_of(item)
            row, handler = getattr(label, "_igtg_handler", (None, None))
            if row is not None:
                row.disconnect(handler)
                label._igtg_handler = (None, None)

        factory.connect("setup", setup)
        factory.connect("bind", bind)
        factory.connect("unbind", unbind)
        col = Gtk.ColumnViewColumn(title=title, factory=factory)
        col.set_resizable(True)
        col.set_expand(expand)
        if not expand:
            col.set_fixed_width(110)
        if sort is not None:
            col.set_sorter(Gtk.CustomSorter.new(lambda a, b, _d: sort(a, b), None))
        self.view.append_column(col)
        return col

    def _ensure_engine_column(self, eng: str) -> None:
        if eng in self.engine_columns:
            return
        col = self._add_text_column(
            eng,
            lambda r, e=eng: f"{r.busy[e]:.1f} %" if e in r.busy else "",
            numeric=True,
            sort=lambda a, b, e=eng: _cmp(a.busy.get(e, 0.0), b.busy.get(e, 0.0)),
        )
        self.engine_columns[eng] = col

    def update(self, clients) -> None:
        if not isinstance(clients, dict):
            clients = {}
        seen = set()
        for cid, data in clients.items():
            if not isinstance(data, dict):
                continue
            seen.add(cid)
            row = self.rows.get(cid)
            if row is None:
                row = ClientRow(cid)
                self.rows[cid] = row
                row.update(data)
                self.store.append(row)
            else:
                row.update(data)
            for eng in row.busy:
                self._ensure_engine_column(eng)
        for cid in list(self.rows):
            if cid not in seen:
                row = self.rows.pop(cid)
                ok, pos = self.store.find(row)
                if ok:
                    self.store.remove(pos)
        sorter = self.view.get_sorter()
        if sorter is not None:
            sorter.changed(Gtk.SorterChange.DIFFERENT)
        self.stack.set_visible_child_name("table" if self.rows else "empty")

    def clear(self) -> None:
        self.update({})
