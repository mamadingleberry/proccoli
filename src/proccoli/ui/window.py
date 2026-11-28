"""Main application window: sidebar of resources + stack of pages, in an
``AdwOverlaySplitView`` that collapses on narrow windows.
"""

from __future__ import annotations

from typing import Optional, Sequence

from gi.repository import Adw, Gio, GLib, Gtk

from .. import APP_NAME, MEMORY_ICON, PROCESSOR_ICON
from ..core.connections import Connections
from .page import (PageContainer, PageKind, PlaceholderPage, ResourcePage,
                   main_menu_button)
from .compat import ensure_font_dpi
from .navigation_controller import NavigationController
from .navigation import GOTO_LABEL
from ..core.profile import Profile, is_pinned
from .lazy import LazyPages, StubPage
from .sidebar import StackSidebar
from .sidebar_style import (MODE_ACTION, MODE_LABELS, SECTION_LABEL, STYLE_SETTING, Mode,
                            SidebarStyle, menu_modes, rail_width)
from .shortcuts import accels_for
from .sidebar_groups import GROUPS, group_for
from .sidebar_visibility import ACTION as SIDEBAR_ACTION, SidebarVisibility
from .window_state import restore_window_state, save_window_state

COLLAPSE_CONDITION = "max-width: 780sp"   # same breakpoint as Resources
TOOLBAR_ACTION = "show-toolbar"           # main menu → Show Toolbar
COLLECTOR_GRACE_S = 5                     # before saying readings aren't arriving

# Stand-ins for pages nothing provides (demo mode, a system without the
# part, tests without a device manager): (id, kind, title, icon).
PLACEHOLDERS = [
    ("apps", PageKind.APPS, "Apps", "view-app-grid-symbolic"),
    ("processes", PageKind.PROCESSES, "Processes", "view-list-bullet-symbolic"),
    ("cpu", PageKind.CPU, "Processor", PROCESSOR_ICON),
    ("memory", PageKind.MEMORY, "Memory", MEMORY_ICON),
]


def placeholder_reason(demo: bool) -> str:
    """What a placeholder page says (never anything about the project)."""
    return "Not available in demo mode." if demo else "Not available on this system."


def primary_menu(goto: Optional[Gio.Menu] = None,
                 modes: Sequence[Mode] = tuple(Mode), toolbar: bool = True) -> Gio.Menu:
    """The main menu, opened from the logo. First *About Proccoli*,
    then ``goto``: the *Go To* submenu, filled by the window as
    panes come and go. Then the *Sidebar* section: ``modes``, by default
    *Full*, *Icons Only* and *Hidden* (no *Full* in Lightweight Mode), and with ``toolbar`` *Show Toolbar*."""
    menu = Gio.Menu()
    about = Gio.Menu()
    # The actions live on the application (proccoli.app.Application).
    about.append(f"About {APP_NAME}", "app.about")
    menu.append_section(None, about)
    if goto is not None:
        nav = Gio.Menu()
        nav.append_submenu(GOTO_LABEL, goto)
        menu.append_section(None, nav)
    # Radio items: one stateful action, a target per mode (sidebar_visibility).
    section = Gio.Menu()
    for mode in modes:
        item = Gio.MenuItem.new(MODE_LABELS[mode], None)
        item.set_action_and_target_value(f"win.{MODE_ACTION}",
                                         GLib.Variant.new_string(mode.value))
        section.append_item(item)
    menu.append_section(SECTION_LABEL, section)
    if toolbar:
        section = Gio.Menu()
        section.append("Show Toolbar", f"win.{TOOLBAR_ACTION}")
        menu.append_section(None, section)
    section = Gio.Menu()
    section.append("Show All Details…", "win.authenticate")
    section.append("Export Statistics…", "app.export-statistics")
    section.append("Preferences", "app.preferences")
    section.append("Keyboard Shortcuts", "app.shortcuts")
    menu.append_section(None, section)
    return menu


def redraw_tree(widget: Gtk.Widget) -> int:
    """Queue a redraw of every drawing area under ``widget`` (GTK caches
    each widget's rendering, so redrawing the window alone isn't enough).
    Returns how many were queued."""
    count = 0
    if isinstance(widget, Gtk.DrawingArea):
        widget.queue_draw()
        count += 1
    child = widget.get_first_child()
    while child is not None:
        count += redraw_tree(child)
        child = child.get_next_sibling()
    return count


class MainWindow(Adw.ApplicationWindow):
    MIN_SIZE = (360, 240)  # same minimum as Resources

    def __init__(self, app: Adw.Application, ctx) -> None:
        """``ctx`` is the ``AppContext`` (proccoli.context) with every service;
        ``ctx.devices`` or ``ctx.processes`` may be None (placeholders then)."""
        super().__init__(application=app, title=APP_NAME)
        self.ctx = ctx
        self.settings = settings = ctx.settings
        self.devices = devices = ctx.devices
        self.processes = processes = ctx.processes
        if ctx.pages is None:
            from .pages.factory import standard_page_factory
            ctx.pages = standard_page_factory(ctx)
        self.pages = ctx.pages
        self.connections = Connections()
        # Lightweight Mode: pages built on first visit, dropped later.
        self.profile = getattr(ctx, "profile", None) or Profile.full()
        self.lazy: Optional[LazyPages] = None
        if self.profile.lazy_pages:
            self.lazy = LazyPages(self.profile.page_drop_s)
            self.lazy.on_drop = self._drop_page
        if ctx.theme is None:
            from .theme import Theme
            ctx.theme = Theme(settings, Adw.StyleManager.get_default())
        # Widgets find the theme through their window (``root.theme``).
        self.theme = ctx.theme
        self.connections.connect(self.theme, "changed", lambda *_: redraw_tree(self))
        self.containers: dict[str, PageContainer] = {}
        self.set_size_request(*self.MIN_SIZE)
        restore_window_state(self, settings)

        self.navigation = NavigationController(self, app, self.select_page)
        self._build_shell(app)
        self._build_graph_toolbar()
        self.sidebar.connect("entries-changed", lambda *_: self._sync_goto_menu())
        self._build_pages()
        self.show_overview()
        self._build_authentication()
        self.stack.connect("notify::visible-child-name", self._on_visible_page)
        self._on_visible_page()            # the first page: Go To's mark
        self.connect("close-request", self._on_close_request)

    # -- building the window ------------------------------------------------------

    def _build_shell(self, app) -> None:
        """The sidebar beside the pages, the collector banner above them, the
        main menu (the logo) in the top-left corner, and the sidebar's modes.
        The logo always sits at the window's top left: in the sidebar's
        header while the sidebar is beside the content, otherwise in every
        page header."""
        settings = self.settings
        self.menu_model = primary_menu(
            self.navigation.goto_menu, menu_modes(not is_pinned(settings, STYLE_SETTING)),
            toolbar=self.profile.graph_toolbar)
        self.sidebar = StackSidebar(settings)
        sidebar_view = Adw.ToolbarView(content=self.sidebar)

        self.stack = Gtk.Stack(vhomogeneous=False, hhomogeneous=False)
        self.sidebar.bind_stack(self.stack)

        # Above every page: when the collector's readings stop.
        self.collector_banner = Adw.Banner(button_label="Try Again", revealed=False)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(self.collector_banner)
        content.append(self.stack)
        self.stack.set_vexpand(True)
        self.split_view = Adw.OverlaySplitView(sidebar=sidebar_view, content=content)
        self.sidebar_header = Adw.HeaderBar(show_title=False)
        self.menu_button = main_menu_button(self.menu_model)   # the corner: the logo
        self.sidebar_header.pack_start(self.menu_button)
        sidebar_view.add_top_bar(self.sidebar_header)
        self.toast_overlay = Adw.ToastOverlay(child=self.split_view)
        self.set_content(self.toast_overlay)

        ensure_font_dpi(self.get_settings())          # else 780sp never matches on 1.5
        breakpoint_ = Adw.Breakpoint.new(Adw.BreakpointCondition.parse(COLLAPSE_CONDITION))
        breakpoint_.add_setter(self.split_view, "collapsed", True)
        self.add_breakpoint(breakpoint_)
        self._full_widths = (self.split_view.get_min_sidebar_width(),
                             self.split_view.get_max_sidebar_width())
        self.sidebar_visibility = SidebarVisibility(self.split_view, settings,
                                                    on_style=self._apply_sidebar_style)
        self.add_action(self.sidebar_visibility.action)       # F9
        self.add_action(self.sidebar_visibility.mode_action)  # Full / Icons Only / Hidden
        if app is not None:
            app.set_accels_for_action(f"win.{SIDEBAR_ACTION}", accels_for(f"win.{SIDEBAR_ACTION}"))
        self.sidebar.connect("page-selected", self._on_page_selected)

    def _build_graph_toolbar(self) -> None:
        """One graph toolbar, moved under the shown page's header, and the
        main menu's *Show Toolbar* (short screens may want the room)."""
        self.graph_toolbar = None
        self._toolbar_host: Optional[PageContainer] = None
        if not self.profile.graph_toolbar:
            return
        from .widgets.graph_toolbar import GraphToolbar
        from .toolbar_items import SHOW_SETTING
        settings = self.settings
        self.graph_toolbar = GraphToolbar(settings)
        self.toolbar_action = Gio.SimpleAction.new_stateful(
            TOOLBAR_ACTION, None, GLib.Variant("b", bool(settings.get(SHOW_SETTING))))
        self.toolbar_action.connect("activate", lambda a, _t: settings.set(
            SHOW_SETTING, not a.get_state().get_boolean()))
        self.connections.watch(settings, SHOW_SETTING, lambda _k, v: self.toolbar_action
                               .set_state(GLib.Variant("b", bool(v))))
        self.add_action(self.toolbar_action)

    def _build_pages(self) -> None:
        """The Overview (cards for the sidebar's charted entries), Apps and
        Processes, a page per device (and those that come later), and
        placeholders for what's missing."""
        from .pages.overview import OverviewPage
        ctx, devices, processes = self.ctx, self.devices, self.processes
        self.overview = OverviewPage(self.settings, self.select_page, processes, ctx.grouper,
                                     profile=self.profile)
        self.add_page(self.overview)
        self.sidebar.connect("entries-changed",
                             lambda *_: self.overview.sync(self.sidebar.entries()))
        self.sidebar.connect("entries-changed", lambda *_: self._fill_groups())
        self.overview.sync(self.sidebar.entries())

        if processes is not None:
            self._add_process_pages()
        if devices is not None and devices.remote:
            self._follow_collector(devices)
        if devices is not None:
            for monitor in devices.monitors():
                self._on_device_added(devices, monitor)
            self.connections.connect(devices, "device-added", self._on_device_added)
            self.connections.connect(devices, "device-removed",
                                     lambda _d, device_id: self._on_device_removed(device_id))
        for page_id, kind, title, icon in PLACEHOLDERS:
            if page_id not in self.containers:
                self.add_page(PlaceholderPage(page_id, kind, title, icon,
                                              placeholder_reason(bool(ctx.demo))))

    def _build_authentication(self) -> None:
        """Optional authentication: offered once, after the window is up;
        the menu entry brings it back."""
        self.auth_action = Gio.SimpleAction.new("authenticate", None)
        self.auth_action.connect("activate", lambda *_: self.offer_authentication())
        self.add_action(self.auth_action)
        self._update_auth_action()
        if self.settings.get("auth-at-launch") and self.elevation_offers():
            self._launch_auth_source = GLib.idle_add(self._offer_at_launch)

    # -- pages ----------------------------------------------------------------

    def add_page(self, page: ResourcePage) -> None:
        container = PageContainer(page, self.split_view, self.menu_model)
        self.containers[page.page_id] = container
        self.stack.add_named(container, page.page_id)
        self.sidebar.add_item(page)
        self._wire_error_page(page)

    def remove_page(self, page_id: str) -> None:
        """Remove a page (e.g. an unplugged drive). If it was showing, show
        its neighbour instead: the next one, or the previous at the end."""
        if self.visible_page_id() == page_id:
            order = self.sidebar.order()
            i = order.index(page_id)
            rest = order[i + 1:] + order[:i][::-1]
            if rest:
                self.select_page(rest[0])
        container = self.containers.pop(page_id)
        if self.lazy is not None:
            self.lazy.remove(page_id)
        self.navigation.forget(page_id)
        if self._toolbar_host is container:
            container.detach_toolbar(self.graph_toolbar)
            self._toolbar_host = None
        container.release()
        container.page.shutdown()
        self.stack.remove(container)
        self.sidebar.remove_item(page_id)

    def replace_page(self, page: ResourcePage) -> None:
        """Swap the page shown for an existing ID, in place: the stack entry,
        the sidebar row and the selection stay."""
        container = self.containers[page.page_id]
        old = container.page
        container.set_page(page)
        if old is not page:
            old.shutdown()
        self.sidebar.replace_page(page)
        self._wire_error_page(page)
        if self._toolbar_host is container:
            self._place_toolbar()

    def select_page(self, page_id: Optional[str]) -> bool:
        if not page_id or page_id not in self.containers:
            return False
        self.stack.set_visible_child_name(page_id)
        self.sidebar.select(page_id)
        return True

    def visible_page_id(self) -> Optional[str]:
        return self.stack.get_visible_child_name()

    def page(self, page_id: str) -> ResourcePage:
        return self.containers[page_id].page

    # -- authentication ---------------------------------------------------------------

    def elevation_offers(self) -> list:
        """What administrator rights would unlock now, in sidebar order."""
        from .elevation import collect_offers
        return collect_offers(self.containers[i].page for i in self.sidebar.order()
                              if i in self.containers)

    def offer_authentication(self):
        """Show the dialog with the current offers; returns it (or None
        when there's nothing to unlock)."""
        from .dialogs.launch_auth import LaunchAuthDialog
        offers = self.elevation_offers()
        if not offers:
            return None
        dialog = LaunchAuthDialog(offers, self.settings,
                                  finished=lambda _r: self._update_auth_action())
        self.auth_dialog = dialog
        if self.get_mapped():
            dialog.present(self)
        return dialog

    def _offer_at_launch(self) -> bool:
        self._launch_auth_source = 0
        if self.get_mapped():
            self.offer_authentication()
        else:   # not on screen yet: once it is
            handler = []
            handler.append(self.connect("map", lambda *_: (
                self.disconnect(handler[0]), self.offer_authentication())))
        return GLib.SOURCE_REMOVE

    def _update_auth_action(self) -> None:
        self.auth_action.set_enabled(bool(self.elevation_offers()))

    # -- providers -----------------------------------------------------------------

    def _on_device_added(self, _devices, monitor) -> None:
        from ..devices.base import FailedMonitor
        page_id = monitor.info.id
        was_visible = self.visible_page_id() == page_id
        # Out with a placeholder (or an error page) first: removing a page
        # forgets its lazy entry, so the new one must be registered after.
        if page_id in self.containers:
            self.remove_page(page_id)
        if self.lazy is not None and not isinstance(monitor, FailedMonitor):
            page = self.lazy.add(page_id, lambda: self.pages.create(monitor),
                                 lambda: StubPage.for_monitor(monitor, self.settings))
        else:
            page = self.pages.create(monitor)
        self.add_page(page)
        self._sync_groups()
        if was_visible:
            self.select_page(page.page_id)        # a retried device stays on screen

    def _on_device_removed(self, device_id: str) -> None:
        if device_id in self.containers:
            self.remove_page(device_id)
        self._sync_groups()

    # -- sidebar groups -------------------------------------------------------

    def _sync_groups(self) -> None:
        """A group page for every kind that groups and has a device (GPUs,
        Drives, Network, Batteries); none for a kind with none left."""
        from .pages.group import GroupPage
        for spec in GROUPS.values():
            has_members = any(not c.page.is_group and group_for(c.page.kind) is spec
                              for c in self.containers.values())
            if has_members and spec.page_id not in self.containers:
                self.add_page(GroupPage(spec, self.settings, self.select_page, self.profile))
            elif not has_members and spec.page_id in self.containers:
                self.remove_page(spec.page_id)

    def _fill_groups(self) -> None:
        """Each group page shows its devices, in sidebar order and colors."""
        group_of = self.sidebar.group_of()
        entries = self.sidebar.entries()
        for spec in GROUPS.values():
            container = self.containers.get(spec.page_id)
            if container is not None:
                container.page.sync([(p, c) for p, c in entries
                                     if group_of.get(p.page_id) == spec.page_id])

    def _on_retry(self, page) -> None:
        """An error page's *Try Again*: set the device up again, or,
        if only its page failed, build the page again."""
        from ..devices.base import FailedMonitor
        if isinstance(page.monitor, FailedMonitor):
            if self.ctx.devices is not None:
                shown = self.visible_page_id() == page.page_id
                self.ctx.devices.retry(page.page_id)   # device-removed, device-added
                if shown:
                    self.select_page(page.page_id)     # stay on it, fixed or not
            return
        self.replace_page(self.pages.create(page.monitor))

    def _wire_error_page(self, page: ResourcePage) -> None:
        from .pages.error import ErrorPage
        if isinstance(page, ErrorPage):
            page.track(page, page.connect("retry", self._on_retry))

    def _add_process_pages(self) -> None:
        """Apps and Processes pages."""
        from .pages.apps import AppsPage
        from .pages.processes import ProcessesPage

        def apps() -> ResourcePage:
            return AppsPage(self.processes, self.settings, self.ctx.grouper,
                            self.ctx.actions, self.ctx.system,
                            getattr(self.ctx, "windows", None))

        def processes() -> ResourcePage:
            return ProcessesPage(self.processes, self.settings, self.ctx.actions,
                                 self.ctx.system, self.ctx.helper,
                                 self.processes.cpu_count(), self.ctx.grouper)

        for page_id, kind, title, icon in PLACEHOLDERS[:2]:
            build = apps if page_id == "apps" else processes
            if self.lazy is not None:
                stub = (lambda p=page_id, k=kind, t=title, i=icon: StubPage(p, k, t, i))
                self.add_page(self.lazy.add(page_id, build, stub))
            else:
                self.add_page(build())

    # -- events -------------------------------------------------------------------

    def _apply_sidebar_style(self, style: SidebarStyle) -> None:
        """Icons only: every row just its icon, the sidebar as narrow as its
        header (the logo) allows. Full: the split view's own widths."""
        compact = style == SidebarStyle.ICONS
        self.sidebar.set_compact(compact)
        if compact:
            # The minimum: the logo and padding (the natural width adds
            # room for a title the sidebar header never shows).
            header = self.sidebar_header.measure(Gtk.Orientation.HORIZONTAL, -1)[0]
            width = rail_width(header)
            self.split_view.set_min_sidebar_width(width)
            self.split_view.set_max_sidebar_width(width)
        else:
            self.split_view.set_min_sidebar_width(self._full_widths[0])
            self.split_view.set_max_sidebar_width(self._full_widths[1])

    def _drop_page(self, page_id: str) -> None:
        """A lazily built page left a while ago: back to its stub."""
        if page_id in self.containers:
            self.replace_page(self.lazy.stub(page_id))

    def show_overview(self) -> None:
        """Every launch opens on the Overview, whatever was shown last
        time; the first entry if there's somehow none."""
        if not self.select_page(PageKind.OVERVIEW.value):
            self.select_page(self.sidebar.order()[0])

    def _on_page_selected(self, _sidebar, _page_id) -> None:
        self.sidebar_visibility.page_selected()

    def _on_visible_page(self, *_a) -> None:
        page_id = self.visible_page_id()
        if self.lazy is not None:
            built = self.lazy.shown(page_id)
            if built is not None:
                self.replace_page(built)
        self._place_toolbar()
        self.navigation.shown(page_id)

    # -- the collector ---------------------------------------------------

    def _follow_collector(self, devices) -> None:
        """Show the banner while no readings arrive: once the collector
        goes, or if it isn't there 5 seconds after opening (not during the
        first moment's connecting)."""
        self._collector_waited = False

        def waited() -> bool:
            self._collector_waited = True
            self._show_collector(devices)
            return False

        self._collector_wait = GLib.timeout_add_seconds(COLLECTOR_GRACE_S, waited)
        self.connections.connect(devices, "connection-changed",
                                 lambda d: self._show_collector(d))
        self.collector_banner.connect("button-clicked", lambda _b: devices.reconnect())

    def _show_collector(self, devices) -> None:
        lost = not devices.connected and (self._collector_waited or devices.readings > 0
                                          or "isn't running" in devices.status)
        self.collector_banner.set_title(devices.status if lost else "")
        self.collector_banner.set_revealed(lost)

    def _place_toolbar(self) -> None:
        """Move the graph toolbar under the shown page's header and show
        the items that apply to it."""
        container = self.containers.get(self.visible_page_id() or "")
        if self.graph_toolbar is None or container is None:
            return
        if self._toolbar_host is not container:
            if self._toolbar_host is not None:
                self._toolbar_host.detach_toolbar(self.graph_toolbar)
            container.attach_toolbar(self.graph_toolbar)
            self._toolbar_host = container
        page = container.page
        self.graph_toolbar.set_page(page.kind.value, page.has_graphs)

    def _sync_goto_menu(self) -> None:
        items = self.sidebar.items
        group_of = self.sidebar.group_of()
        # a group's devices are indented beneath it
        self.navigation.set_entries([(i, ("\u2003" if i in group_of else "") + items[i].page.title,
                                      items[i].page.description)
                                     for i in self.sidebar.display_order()])

    def _on_close_request(self, *_a) -> bool:
        save_window_state(self, self.settings)
        if getattr(self, "_collector_wait", 0):
            GLib.source_remove(self._collector_wait)
            self._collector_wait = 0
        if getattr(self, "_launch_auth_source", 0):
            GLib.source_remove(self._launch_auth_source)
            self._launch_auth_source = 0
        self.connections.disconnect_all()
        self.sidebar_visibility.shutdown()
        if self.graph_toolbar is not None:
            self.graph_toolbar.release()
        for container in self.containers.values():
            container.release()
            container.page.shutdown()
        return False  # let the window close
