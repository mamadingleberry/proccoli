"""A short ranked table for the Overview:
icon, name, processor use and memory, in a boxed list.

The rows are made once (``count`` of them) and refilled in place on every
update, so the list doesn't flicker or lose keyboard focus as the ranking
changes. Unused rows are hidden. The table's size never depends on what
it shows: names fill the width the page gives them and end in "…" past
it (the full name is the tooltip), and the numbers have fixed columns, so
the Overview doesn't shift as the busiest apps change. Without icons (Lightweight Mode)
the rows have no image at all.
"""

from __future__ import annotations

from typing import Callable, Optional, Sequence

from gi.repository import Gtk, Pango

from .app_icon import set_app_icon

NAME_CHARS = 18
CPU_CHARS = 7          # "100.0 %"
MEMORY_CHARS = 9       # "1023.9 MB"


def _value_label(chars: int) -> Gtk.Label:
    # Exactly ``chars`` wide, whatever the value: a fixed column.
    label = Gtk.Label(xalign=1, width_chars=chars, max_width_chars=chars)
    label.add_css_class("numeric")
    return label


class TopRow(Gtk.ListBoxRow):
    def __init__(self, icons: bool = True) -> None:
        super().__init__(activatable=True)
        box = Gtk.Box(spacing=10, margin_top=6, margin_bottom=6, margin_start=10, margin_end=10)
        self.rank_label = Gtk.Label(width_chars=2, xalign=1)
        self.rank_label.add_css_class("dim-label")
        self.rank_label.add_css_class("numeric")
        self.icon = Gtk.Image(pixel_size=16) if icons else None
        # Its natural width is capped too: otherwise a long name would make
        # the table ask for more room and the page re-lay out on each change.
        self.name_label = Gtk.Label(xalign=0, hexpand=True, width_chars=NAME_CHARS,
                                    max_width_chars=NAME_CHARS,
                                    ellipsize=Pango.EllipsizeMode.END)
        self.cpu_label = _value_label(CPU_CHARS)
        self.memory_label = _value_label(MEMORY_CHARS)
        for w in (self.rank_label, self.icon, self.name_label, self.cpu_label,
                  self.memory_label):
            if w is not None:
                box.append(w)
        self.set_child(box)

    def fill(self, rank: int, name: str, icon, cpu: str, memory: str) -> None:
        self.rank_label.set_label(str(rank))
        if self.name_label.get_label() != name:
            self.name_label.set_label(name)
            self.name_label.set_tooltip_text(name)
        if self.icon is not None:
            set_app_icon(self.icon, icon)
        self.cpu_label.set_label(cpu)
        self.memory_label.set_label(memory)
        self.update_property([Gtk.AccessibleProperty.LABEL],
                             [f"{rank}. {name}: processor {cpu}, memory {memory}"])


class TopTable(Gtk.Box):
    """A titled boxed list of ``count`` ranked rows; activating any row
    calls ``activated()`` (the Overview opens the full page)."""

    def __init__(self, title: str, count: int,
                 activated: Optional[Callable[[], None]] = None, icons: bool = True) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        header = Gtk.Box(spacing=10, margin_start=10, margin_end=10)
        self.title_label = Gtk.Label(label=title, xalign=0, hexpand=True)
        self.title_label.add_css_class("heading")
        self.cpu_header = Gtk.Label(label="Processor", xalign=1, width_chars=CPU_CHARS)
        self.memory_header = Gtk.Label(label="Memory", xalign=1, width_chars=MEMORY_CHARS)
        for w in (self.cpu_header, self.memory_header):
            w.add_css_class("caption")
            w.add_css_class("dim-label")
        header.append(self.title_label)
        header.append(self.cpu_header)
        header.append(self.memory_header)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.list.add_css_class("boxed-list")
        self.rows = [TopRow(icons) for _ in range(count)]
        for row in self.rows:
            self.list.append(row)
        self.empty = Gtk.Label(label="Waiting for data…", margin_top=12, margin_bottom=12)
        self.empty.add_css_class("dim-label")
        self.append(header)
        self.append(self.list)
        self.append(self.empty)
        self.activated = activated
        self.list.connect("row-activated", lambda *_: self.activated and self.activated())
        self.set_rows([])

    def set_sorted_by(self, metric: str) -> None:
        """Highlight the column the ranking uses ("cpu" or "memory")."""
        for label, key in ((self.cpu_header, "cpu"), (self.memory_header, "memory")):
            if key == metric:
                label.remove_css_class("dim-label")
                label.add_css_class("heading")
            else:
                label.remove_css_class("heading")
                label.add_css_class("dim-label")

    def set_rows(self, rows: Sequence[tuple[str, object, str, str]]) -> None:
        """``[(name, icon, cpu text, memory text), ...]``, best first."""
        for i, row in enumerate(self.rows):
            if i < len(rows):
                row.fill(i + 1, *rows[i])
                row.set_visible(True)
            else:
                row.set_visible(False)
        self.list.set_visible(bool(rows))
        self.empty.set_visible(not rows)

    def shown(self) -> list[str]:
        """Names in the visible rows, in order (for tests)."""
        return [r.name_label.get_label() for r in self.rows if r.get_visible()]
