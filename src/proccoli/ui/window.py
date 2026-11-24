"""Main application window: sidebar of resources + stack of pages, in an
``AdwOverlaySplitView`` that collapses on narrow windows (DESIGN.md §9).
"""

from __future__ import annotations

from typing import Optional

from gi.repository import Adw, Gio, GLib, Gtk

from .. import APP_NAME, MEMORY_ICON, PROCESSOR_ICON
from .page import (PageContainer, PageKind, PlaceholderPage, ResourcePage,
                   main_menu_button)
from .compat import ensure_font_dpi
from .navigation import (GOTO_ACTION, GOTO_LABEL, NavigationHistory, fill_goto_menu,
                         mouse_direction)
from ..core.profile import Profile
from .lazy import LazyPages, StubPage
from .sidebar import StackSidebar
from .sidebar_style import MODE_ACTION, MODE_LABELS, SECTION_LABEL, Mode, SidebarStyle, rail_width
from .sidebar_visibility import ACTION as SIDEBAR_ACTION, SidebarVisibility
from .window_state import restore_window_state, save_window_state

COLLAPSE_CONDITION = "max-width: 780sp"   # same breakpoint as Resources

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


def primary_menu(goto: Optional[Gio.Menu] = None) -> Gio.Menu:
    """The main menu, opened from the logo. First *About Proccoli* (M61),
    then ``goto``: the *Go To* submenu (§9.2), filled by the window as
    panes come and go. Then the *Sidebar* section: *Full*, *Icons Only*
    and *Hidden* (M54)."""
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
    modes = Gio.Menu()
    for mode in Mode:
        item = Gio.MenuItem.new(MODE_LABELS[mode], None)
        item.set_action_and_target_value(f"win.{MODE_ACTION}",
                                         GLib.Variant.new_string(mode.value))
        modes.append_item(item)
    menu.append_section(SECTION_LABEL, modes)
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
        self._handlers: list[tuple[object, int]] = []
        # Lightweight Mode (Idea 1): pages built on first visit, dropped later.
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
        self._handlers.append((self.theme, self.theme.connect(
            "changed", lambda *_: redraw_tree(self))))
        self.containers: dict[str, PageContainer] = {}
        self.set_size_request(*self.MIN_SIZE)
        restore_window_state(self, settings)

        # Sidebar. The main menu (the logo) always sits at the window's top
        # left: here while the sidebar is beside the content, otherwise in
        # every page header (DESIGN.md §9.2).
        self.goto_menu = Gio.Menu()
        self.menu_model = primary_menu(self.goto_menu)
        self.sidebar = StackSidebar(settings)
        sidebar_view = Adw.ToolbarView(content=self.sidebar)

        # Pages.
        self.stack = Gtk.Stack(vhomogeneous=False, hhomogeneous=False)
        self.sidebar.bind_stack(self.stack)

        self.split_view = Adw.OverlaySplitView(sidebar=sidebar_view,
                                               content=self.stack)
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
            app.set_accels_for_action(f"win.{SIDEBAR_ACTION}", ["F9"])

        self.sidebar.connect("page-selected", self._on_page_selected)

        # Go To (M48): every pane from the main menu, current one marked.
        self.goto_action = Gio.SimpleAction.new_stateful(
            GOTO_ACTION, GLib.VariantType.new("s"), GLib.Variant("s", ""))
        self.goto_action.connect("activate",
                                 lambda _a, target: self.select_page(target.get_string()))
        self.add_action(self.goto_action)
        self.sidebar.connect("entries-changed", lambda *_: self._sync_goto_menu())

        # Back and forward (M49): mouse side buttons, Alt+Left / Alt+Right.
        self.history = NavigationHistory()
        self._navigating = False             # a page change made by back/forward
        self.nav_actions = {}
        for name, step in (("back", self.go_back), ("forward", self.go_forward)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda *_a, f=step: f())
            action.set_enabled(False)
            self.add_action(action)
            self.nav_actions[name] = action
        if app is not None:
            app.set_accels_for_action("win.back", ["<Alt>Left"])
            app.set_accels_for_action("win.forward", ["<Alt>Right"])
        # Capture phase: the side buttons work over any widget. Other buttons
        # are denied at once, so they reach their own widgets untouched.
        self.mouse_nav = Gtk.GestureClick(button=0)
        self.mouse_nav.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.mouse_nav.connect("pressed", lambda g, *_: self.on_mouse_button(g))
        self.add_controller(self.mouse_nav)

        # Overview (DESIGN.md §9.6): cards for the sidebar's charted entries.
        from .pages.overview import OverviewPage
        self.overview = OverviewPage(settings, self.select_page, processes, ctx.grouper,
                                     profile=self.profile)
        self.add_page(self.overview)
        self.sidebar.connect("entries-changed",
                             lambda *_: self.overview.sync(self.sidebar.entries()))
        self.overview.sync(self.sidebar.entries())

        if processes is not None:
            self._add_process_pages()
        if devices is not None:
            for monitor in devices.monitors():
                self._on_device_added(devices, monitor)
            self._handlers += [
                (devices, devices.connect("device-added", self._on_device_added)),
                (devices, devices.connect("device-removed",
                                          lambda _d, device_id: self.remove_page(device_id))),
            ]
        for page_id, kind, title, icon in PLACEHOLDERS:
            if page_id not in self.containers:
                self.add_page(PlaceholderPage(page_id, kind, title, icon,
                                              placeholder_reason(bool(ctx.demo))))

        self.show_overview()

        # Optional authentication (DESIGN.md §9.4): offered once, after the
        # window is up; the menu entry brings it back.
        self.auth_action = Gio.SimpleAction.new("authenticate", None)
        self.auth_action.connect("activate", lambda *_: self.offer_authentication())
        self.add_action(self.auth_action)
        self._update_auth_action()
        if settings.get("auth-at-launch") and self.elevation_offers():
            self._launch_auth_source = GLib.idle_add(self._offer_at_launch)
        self.stack.connect("notify::visible-child-name", self._on_visible_page)
        self._on_visible_page()            # the first page: Go To's mark
        self.connect("close-request", self._on_close_request)

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
        self.history.remove(page_id)
        self._update_nav_actions()
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
        if self.lazy is not None and not isinstance(monitor, FailedMonitor):
            page = self.lazy.add(monitor.info.id, lambda: self.pages.create(monitor),
                                 lambda: StubPage.for_monitor(monitor, self.settings))
        else:
            page = self.pages.create(monitor)
        was_visible = self.visible_page_id() == page.page_id
        if page.page_id in self.containers:      # replaces a placeholder (or an error page)
            self.remove_page(page.page_id)
        self.add_page(page)
        if was_visible:
            self.select_page(page.page_id)        # a retried device stays on screen

    def _on_retry(self, page) -> None:
        """An error page's *Try Again* (M55): set the device up again, or,
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
        """Every launch opens on the Overview (M55), whatever was shown last
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
        if page_id:
            self.goto_action.set_state(GLib.Variant("s", page_id))
            if not self._navigating:
                self.history.visit(page_id)
            self._update_nav_actions()

    # -- back and forward (M49) ---------------------------------------------------

    def _update_nav_actions(self) -> None:
        self.nav_actions["back"].set_enabled(self.history.can_go_back())
        self.nav_actions["forward"].set_enabled(self.history.can_go_forward())

    def _show_from_history(self, page_id) -> bool:
        if page_id is None:
            return False
        self._navigating = True
        try:
            self.select_page(page_id)
        finally:
            self._navigating = False
        self._update_nav_actions()
        return True

    def go_back(self) -> bool:
        return self._show_from_history(self.history.back())

    def go_forward(self) -> bool:
        return self._show_from_history(self.history.forward())

    def on_mouse_button(self, gesture) -> bool:
        """Mouse back/forward buttons; any other button is left alone. Not
        while a dialog is open over the window."""
        direction = mouse_direction(gesture.get_current_button())
        dialog = getattr(self, "get_visible_dialog", lambda: None)()
        if direction is None or dialog is not None:
            gesture.set_state(Gtk.EventSequenceState.DENIED)
            return False
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        return self.go_back() if direction == "back" else self.go_forward()

    def _sync_goto_menu(self) -> None:
        items = self.sidebar.items
        fill_goto_menu(self.goto_menu, [(i, items[i].page.title, items[i].page.description)
                                        for i in self.sidebar.display_order()])

    def _on_close_request(self, *_a) -> bool:
        save_window_state(self, self.settings)
        if getattr(self, "_launch_auth_source", 0):
            GLib.source_remove(self._launch_auth_source)
            self._launch_auth_source = 0
        for source, handler in self._handlers:
            source.disconnect(handler)
        self._handlers.clear()
        self.sidebar_visibility.shutdown()
        for container in self.containers.values():
            container.release()
            container.page.shutdown()
        return False  # let the window close
