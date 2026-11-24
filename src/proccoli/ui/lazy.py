"""Pages built on first visit and dropped after (Lightweight Mode, Idea 1).

GTK's own memory is mostly the widget trees of pages and what drawing them
leaves behind, so in Lightweight Mode a page exists only while it's being
looked at, and a little after:

- ``StubPage`` stands in for a page that isn't built: its sidebar entry
  and Overview card work from the monitor alone (``ui.summaries``), and it
  draws nothing.
- ``LazyPages`` decides when: the window tells it which page became
  visible (``shown``); it returns the page to build now, and schedules
  dropping the one left after ``drop_s`` seconds (``schedule(seconds,
  callback)``, ``GLib.timeout_add_seconds`` by default; tests pass their
  own). Building and swapping are the window's (``replace_page``).
"""

from __future__ import annotations

from typing import Callable, Optional

from gi.repository import GLib, Gtk

from .page import PageKind, ResourcePage, SidebarSummary


class StubPage(ResourcePage):
    """An unbuilt page: the entry's name, icon and summary, nothing drawn."""

    def __init__(self, page_id: str, kind: PageKind, title: str, icon_name: str,
                 description: str = "", sort_name: str = "",
                 summary: Optional[Callable[[], Optional[SidebarSummary]]] = None,
                 source=None) -> None:
        """``summary()`` answers ``sidebar_summary``; ``source`` (a
        monitor) has an ``updated`` signal that means it changed."""
        super().__init__(page_id, kind, title, icon_name, description, sort_name)
        self._summary = summary
        self.set_child(Gtk.Box())
        if source is not None:
            self.track(source, source.connect("updated", lambda *_: self.summary_changed()))

    def sidebar_summary(self) -> Optional[SidebarSummary]:
        return self._summary() if self._summary is not None else None

    @classmethod
    def for_monitor(cls, monitor, settings) -> "StubPage":
        from .summaries import sort_name_for, summary_for
        info = monitor.info
        return cls(info.id, PageKind(info.kind.value), info.name, info.icon_name,
                   info.description, sort_name_for(monitor),
                   lambda: summary_for(monitor, settings), monitor)


class LazyPages:
    """Which lazily built pages to build and drop, and when."""

    def __init__(self, drop_s: int, schedule: Optional[Callable] = None) -> None:
        self.drop_s = drop_s
        self.schedule = schedule or GLib.timeout_add_seconds
        self.builders: dict[str, Callable[[], ResourcePage]] = {}
        self.stubs: dict[str, Callable[[], ResourcePage]] = {}
        self.built: set[str] = set()
        self.visible: Optional[str] = None
        self._pending: dict[str, int] = {}     # page id -> generation of its drop timer
        self._generation = 0
        self.on_drop: Callable[[str], None] = lambda page_id: None

    def add(self, page_id: str, build: Callable[[], ResourcePage],
            stub: Callable[[], ResourcePage]) -> ResourcePage:
        """Register a page; returns its stub (what the window adds first)."""
        self.builders[page_id] = build
        self.stubs[page_id] = stub
        self.built.discard(page_id)
        return stub()

    def remove(self, page_id: str) -> None:
        for d in (self.builders, self.stubs, self._pending):
            d.pop(page_id, None)
        self.built.discard(page_id)

    def shown(self, page_id: Optional[str]) -> Optional[ResourcePage]:
        """``page_id`` is now on screen: the real page to swap in, if it
        isn't built yet. The page left gets its drop timer."""
        previous, self.visible = self.visible, page_id
        if previous and previous != page_id and previous in self.built:
            self._generation += 1
            generation = self._pending[previous] = self._generation
            self.schedule(self.drop_s, lambda: self._expire(previous, generation))
        if page_id is None or page_id not in self.builders:
            return None
        self._pending.pop(page_id, None)          # back before its timer
        if page_id in self.built:
            return None
        self.built.add(page_id)
        return self.builders[page_id]()

    def _expire(self, page_id: str, generation: int) -> bool:
        if self._pending.get(page_id) == generation and page_id != self.visible:
            del self._pending[page_id]
            self.built.discard(page_id)
            self.on_drop(page_id)
        return False                              # a one-shot timer

    def stub(self, page_id: str) -> ResourcePage:
        return self.stubs[page_id]()
