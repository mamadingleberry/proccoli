"""Pages and the container that gives each page its header bar.

Every sidebar entry is backed by a ``ResourcePage``. The window wraps each
page in a ``PageContainer`` (header bar + sidebar toggle) and puts the
container into its ``Gtk.Stack``. Swapping a page only replaces the
container's content, so the stack entry and the sidebar selection stay put.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from gi.repository import Adw, GLib, GObject, Gtk

from .. import APP_ID, APP_NAME
from ..core.connections import Connections
from ..core.history import Series
from ..core.units import format_percent
from .layout import CONTENT_TIGHTENING, MAX_CONTENT_WIDTH


class PageKind(str, Enum):
    """Sidebar groups, in sidebar order."""
    OVERVIEW = "overview"
    APPS = "apps"
    PROCESSES = "processes"
    CPU = "cpu"
    MEMORY = "memory"
    GPU = "gpu"
    DRIVE = "drive"
    NETWORK = "network"
    BATTERY = "battery"
    DEMO = "demo"


_ORDER = list(PageKind)


def sidebar_rank(kind: PageKind, sort_name: str = "") -> tuple[int, str]:
    """Sort key of a sidebar entry: by kind, then by name within a kind
    (GPUs by PCI slot, drives by name, ...)."""
    return (_ORDER.index(PageKind(kind)), sort_name)


@dataclass
class SidebarSummary:
    """What a sidebar item shows below the page name."""
    usage: Optional[float] = None       # percent, drives the meter
    usage_text: str = ""                # e.g. "42 %"
    detail: str = ""                    # e.g. "3.1 of 16.0 GB"
    # The sidebar's area chart: one percentage, or several series sharing
    # an automatic scale (network: receive and send).
    series: list[Series] = field(default_factory=list)
    # Graph meter scale: 100 for percentages, None to scale to the data
    # (network speeds, which have no percentage and no progress bar).
    max_value: Optional[float] = 100.0
    # Current readings for the Overview card: processor temperature;
    # GPU temperature and memory ("Memory 598.7 MB / 8.5 GB").
    facts: list[str] = field(default_factory=list)

    def text(self) -> str:
        """One line: usage, then detail ("42 % · 3.1 of 16.0 GB")."""
        text = self.usage_text or (format_percent(self.usage)
                                   if self.usage is not None else "")
        if self.detail:
            text = f"{text} · {self.detail}" if text else self.detail
        return text

    def has_chart(self) -> bool:
        """A chart is worth drawing once some series holds a reading; a
        device with none yet says "No data" instead of an empty frame."""
        return any(s is not None and s.has_values() for s in self.series)


class ResourcePage(Adw.Bin):
    """Base class of every page.

    Subclasses set ``kind``, ``title`` and ``icon_name`` (and optionally
    ``description`` and ``sort_name``), and call ``summary_changed()``
    whenever ``sidebar_summary()`` would return something new.

    Connections to longer-lived objects (monitors, settings) are registered
    with ``track()``. The window calls ``shutdown()`` when the page is
    removed, swapped out or the window closes, which disconnects them all,
    so a discarded page neither leaks nor keeps updating.
    """

    __gsignals__ = {
        "summary-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }
    # The graph toolbar's graph items show only on pages with graphs.
    has_graphs = False

    def __init__(self, page_id: str, kind: PageKind, title: str, icon_name: str,
                 description: str = "", sort_name: str = "") -> None:
        super().__init__()
        self.page_id = page_id
        self.kind = PageKind(kind)
        self.title = title
        self.icon_name = icon_name
        self.description = description
        self.sort_name = sort_name
        self._connections: list[tuple[object, int]] = []

    def track(self, source, handler_id: int) -> int:
        """Remember a signal connection to disconnect in ``shutdown()``.
        ``source`` is anything with ``disconnect(handler_id)``."""
        self._connections.append((source, handler_id))
        return handler_id

    def shutdown(self) -> None:
        for source, handler_id in self._connections:
            source.disconnect(handler_id)
        self._connections.clear()

    def sort_key(self) -> tuple[int, str]:
        return sidebar_rank(self.kind, self.sort_name)

    @property
    def is_group(self) -> bool:
        """A sidebar group's own page (``pages/group.py``)."""
        return False

    def sidebar_summary(self) -> Optional[SidebarSummary]:
        """None: the sidebar shows only the name (Apps, Processes)."""
        return None

    def header_widgets(self) -> list[Gtk.Widget]:
        """Extra buttons for the end of this page's header bar."""
        return []

    def elevation_offer(self):
        """What this page could show with administrator rights right now,
        as a ``ui.elevation.ElevationOffer``, or None."""
        return None

    def set_entry_color(self, index: Optional[int]) -> None:
        """The color index of this page's sidebar entry (device pages
        color their graphs to match)."""

    def title_widget(self) -> Optional[Gtk.Widget]:
        """A widget for the header's centre instead of the page title
        (the GPU page's tab switcher), or None."""
        return None

    def summary_changed(self) -> None:
        self.emit("summary-changed")

    def report(self, text: str) -> None:
        """Show a short message (a toast in the window)."""
        overlay = self.get_ancestor(Adw.ToastOverlay)
        if overlay is not None:
            overlay.add_toast(Adw.Toast(title=GLib.markup_escape_text(text), timeout=3))


class ScrollingPage(ResourcePage):
    """A page of preference groups in a scrolled, width-clamped column:
    the shape of every device page."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        for side in ("top", "bottom", "start", "end"):
            getattr(self.box, f"set_margin_{side}")(24)
        # Wide enough that graphs use the window, but text
        # rows don't stretch across a whole 4K screen.
        self.clamp = Adw.Clamp(maximum_size=MAX_CONTENT_WIDTH,
                               tightening_threshold=CONTENT_TIGHTENING, child=self.box)
        self.scroller = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER, child=self.clamp, vexpand=True)
        self.set_child(self.scroller)

    def add_group(self, title: str = "", description: str = "") -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(title=title)
        if description:
            group.set_description(description)
        self.box.append(group)
        return group


class FittingPage(ScrollingPage):
    """A ``ScrollingPage`` that sizes its content to the visible area:
    whenever the scroller's size changes, ``fit(width, height)`` runs
    once, on idle (never during allocation). Device pages fit their
    graphs, the Overview its grid of cards.

    ``fit`` returns True when it changed the layout in a way it needs to
    see laid out before fitting again (stacking a pair of graphs)."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._fit_source = 0
        self._fitted_for: tuple = ()     # fit_key() at the last fit
        # AdwBin lays out through a layout manager, which bypasses the
        # size_allocate vfunc; drop it, and do the (trivial) single-child
        # layout in do_measure / do_size_allocate.
        self.set_layout_manager(None)

    def do_measure(self, orientation, for_size):
        child = self.get_child()
        if child is None or not child.get_visible():
            return 0, 0, -1, -1
        return child.measure(orientation, for_size)

    def do_size_allocate(self, width: int, height: int, baseline: int) -> None:
        child = self.get_child()
        if child is not None and child.get_visible():
            child.allocate(width, height, baseline, None)
        if self.fit_key() != self._fitted_for:
            self.refit()

    def viewport_size(self) -> tuple[int, int]:
        return self.scroller.get_width(), self.scroller.get_height()

    def fit_key(self) -> tuple:
        """What the last fit depends on: when it changes, fit again. The
        viewport's size; a page can add its own (the Overview: its tables'
        height)."""
        return self.viewport_size()

    def refit(self) -> None:
        """Fit again on idle (also when content, not size, changed)."""
        if not self._fit_source:
            self._fit_source = GLib.idle_add(self._run_fit)

    def _run_fit(self) -> bool:
        self._fit_source = 0
        if not self.get_mapped():
            return GLib.SOURCE_REMOVE
        self._fitted_for = self.fit_key()
        if self.fit(*self.viewport_size()):
            self._fitted_for = ()
            self.queue_resize()
        return GLib.SOURCE_REMOVE

    def fit(self, width: int, height: int) -> bool:
        return False

    def shutdown(self) -> None:
        if self._fit_source:
            GLib.source_remove(self._fit_source)
            self._fit_source = 0
        super().shutdown()


class PlaceholderPage(ResourcePage):
    """Stands in for a page with nothing to show: demo mode has no real
    processor, memory or processes, and a system may lack a part."""

    def __init__(self, page_id: str, kind: PageKind, title: str, icon_name: str,
                 reason: str = "Not available on this system.") -> None:
        super().__init__(page_id, kind, title, icon_name)
        self.reason = reason
        self.set_child(Adw.StatusPage(title=title, icon_name=icon_name, description=reason))


LOGO_SIZE = 24


def main_menu_button(menu_model) -> Gtk.MenuButton:
    """The main menu, always at the window's top left: the app's
    logo is its button (it replaced the logo-and-burger pair). F10
    opens it too (``primary``)."""
    image = Gtk.Image(icon_name=APP_ID, pixel_size=LOGO_SIZE)
    button = Gtk.MenuButton(child=image, menu_model=menu_model, primary=True,
                            has_frame=False, tooltip_text="Main Menu")
    button.add_css_class("app-logo")
    button.update_property([Gtk.AccessibleProperty.LABEL], [f"{APP_NAME} Main Menu"])
    return button


class PageContainer(Adw.Bin):
    """Header bar (title, page buttons and, when the sidebar isn't beside
    the content, the logo and the main menu at the start) around a page.
    The sidebar is shown again from the main menu (*Sidebar* → *Full* or
    *Icons Only*) or F9."""

    def __init__(self, page: ResourcePage,
                 split_view: Optional[Adw.OverlaySplitView] = None,
                 menu_model=None) -> None:
        super().__init__()
        self.page: Optional[ResourcePage] = None
        self.window_title = Adw.WindowTitle()
        self.header = Adw.HeaderBar(title_widget=self.window_title)
        self.header.add_css_class("flat")

        # Start of the header: the logo, which opens the main menu.
        self.start_controls = Gtk.Box(spacing=6)
        self.menu_button: Optional[Gtk.MenuButton] = None
        if menu_model is not None:
            self.menu_button = main_menu_button(menu_model)
            self.start_controls.append(self.menu_button)
        self.split_view = split_view
        self.split_connections = Connections()
        if split_view is not None:
            for p in ("collapsed", "show-sidebar"):
                self.split_connections.connect(split_view, f"notify::{p}",
                                               lambda *_: self._sync_controls())
            self._sync_controls()
        else:
            self.start_controls.set_visible(False)
        self.header.pack_start(self.start_controls)
        self._extras: list[Gtk.Widget] = []

        self.toolbar = Adw.ToolbarView()
        self.toolbar.add_top_bar(self.header)
        self.set_child(self.toolbar)
        self.set_page(page)

    @property
    def page_id(self) -> str:
        return self.page.page_id

    def _sync_controls(self) -> None:
        from .sidebar_visibility import header_controls_visible
        self.start_controls.set_visible(header_controls_visible(
            self.split_view.get_show_sidebar(), self.split_view.get_collapsed()))

    def release(self) -> None:
        """Stop following the split view (the page is being removed)."""
        self.split_connections.disconnect_all()

    def set_page(self, page: ResourcePage) -> None:
        if self.page is not None and page.page_id != self.page.page_id:
            raise ValueError("a container keeps its page ID; use a new container")
        for w in self._extras:
            self.header.remove(w)
        self.page = page
        self.window_title.set_title(page.title)
        self.window_title.set_subtitle(page.description)
        self.header.set_title_widget(page.title_widget() or self.window_title)
        self._extras = list(page.header_widgets())
        for w in reversed(self._extras):
            self.header.pack_end(w)
        self.toolbar.set_content(page)

    # -- the graph toolbar: one per window, under the shown page's header --

    def attach_toolbar(self, toolbar: Gtk.Widget) -> None:
        if toolbar.get_parent() is None:
            self.toolbar.add_top_bar(toolbar)

    def detach_toolbar(self, toolbar: Gtk.Widget) -> None:
        if self.has_toolbar(toolbar):
            self.toolbar.remove(toolbar)

    def has_toolbar(self, toolbar: Gtk.Widget) -> bool:
        parent = toolbar.get_parent()
        while parent is not None and parent is not self.toolbar:
            parent = parent.get_parent()
        return parent is self.toolbar
