"""Application entry point and command-line options."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
from typing import Callable, Optional, Sequence

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import APP_ID, APP_NAME, WINDOW, __version__  # noqa: E402
from .ui.shortcuts import accels_for  # noqa: E402

log = logging.getLogger(__name__)


class Application(Adw.Application):
    def __init__(self, args: argparse.Namespace, context_factory=None,
                 log_file=None, history_path=None, import_dir=None) -> None:
        """``context_factory(settings, demo)`` builds the AppContext; tests
        can pass their own (default: ``proccoli.context.build_context()``).
        ``log_file`` is the diagnostics log (default: ``applog.log_path()``),
        ``history_path`` the history database (``history_store.history_path()``)
        and ``import_dir`` the old statistics files to import once
        (``history_store.old_stats_dir()``)."""
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.args = args
        self.context_factory = context_factory
        self.log_file = log_file
        self.history_path = history_path
        self.import_dir = import_dir
        self.history = None         # core.history_store.HistoryStore (not in --demo)
        self.exporter = None        # ui.export.StatisticsExport
        self.record_from_boot = None   # the one-time Record from Boot? dialog
        self.ctx = None  # created in do_startup
        self.profile = None          # core.profile.Profile, chosen in do_startup
        self.restart_requested = False
        self._open_dialogs: dict[str, object] = {}   # name -> the one open dialog

        for name, callback in (
                ("quit", lambda *_: self.quit()),
                ("preferences", lambda *_: self.show_preferences()),
                ("shortcuts", lambda *_: self.show_shortcuts()),
                ("about", lambda *_: self.show_about()),
                ("export-statistics", lambda *_: self.export_statistics()),
                ("restart", lambda *_: self.restart())):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            accels = accels_for(f"app.{name}")
            if accels:
                self.set_accels_for_action(f"app.{name}", accels)

    @property
    def settings(self):
        return self.ctx.settings if self.ctx else None

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        from .core.settings import Settings
        from .ui.style import add_source_icons, install_css

        from .ui.compat import ensure_font_dpi
        ensure_font_dpi(Gtk.Settings.get_default())   # sp breakpoints on libadwaita 1.5
        install_css()
        add_source_icons()
        Gtk.Window.set_default_icon_name(APP_ID)
        from .core.profile import choose_profile, profile_settings
        from .core.settings import migrate
        base = Settings.load()
        changes = migrate(base)                     # replaced keys, once
        # Lightweight mode: chosen once; everything reads the
        # settings as the profile sees them.
        self.profile = choose_profile(base, getattr(self.args, "lightweight", False))
        from .core.profile import apply_renderer
        renderer = apply_renderer(self.profile, os.environ)   # before any window
        settings = profile_settings(base, self.profile)
        from .core.applog import log_path
        from .core.runtime import Runtime
        # the log file, the stall watchdog (logs stalls with stacks) and the
        # uncaught-exception hook
        self.runtime = Runtime(settings, self.log_file or log_path()).start()
        self.file_log = self.runtime.file_log
        self.watchdog = self.runtime.watchdog
        for change in changes:
            log.info("settings: %s", change)
        if renderer:
            log.info("renderer: %s", renderer)
        log.info("%s %s starting (demo=%s)", APP_NAME, __version__, self.args.demo)
        if self.context_factory is None:
            from .context import build_context
            # The window reads no devices: proccoli does.
            self.ctx = build_context(settings, demo=self.args.demo, remote=True)
        else:
            self.ctx = self.context_factory(settings, self.args.demo)
        if self.ctx.theme is None:      # the UI half of the composition root
            from .ui.theme import Theme
            self.ctx.theme = Theme(settings, Adw.StyleManager.get_default())
        from .ui.style import ThemeCss
        self.theme_css = ThemeCss(self.ctx.theme) if self.ctx.profile.theme_css else None
        self.ctx.start()
        # Every reading, in the history database; never the demo's
        # made-up ones.
        if not self.args.demo and self.ctx.devices is not None:
            from .core.history_lock import HistoryLock, lock_path
            from .core.history_store import HistoryStore, history_path, old_stats_dir
            path = self.history_path or history_path()
            remote = self.ctx.devices.remote
            # proccoli is the only writer; the window reads
            # the history (graphs, exports). A window reading devices itself
            # (tests) writes when it holds the lock.
            self.history = HistoryStore(self.ctx.devices, self.ctx.settings, path, __version__,
                                        idle=GLib.idle_add,
                                        import_dir=None if remote else
                                        self.import_dir or old_stats_dir(),
                                        lock=None if remote else
                                        HistoryLock(self.ctx.system, lock_path(path)),
                                        read_only=remote)
        export = self.lookup_action("export-statistics")
        export.set_enabled(self.history is not None and self.ctx.settings.get("history"))
        self.ctx.settings.connect_changed("history", lambda _k, on: export.set_enabled(
            self.history is not None and bool(on)))

    def do_shutdown(self) -> None:
        if self.history is not None:
            self.history.shutdown()               # writes out buffered rows
        if self.ctx is not None:
            self.ctx.stop()
            if self.theme_css is not None:
                self.theme_css.shutdown()
            self.ctx.theme.shutdown()
        if getattr(self, "runtime", None) is not None:
            log.info("%s stopping", APP_NAME)
            self.runtime.shutdown()
        Adw.Application.do_shutdown(self)

    # -- dialogs ------------------------------------------------------------------

    def _present(self, dialog) -> None:
        window = self.get_active_window()
        if isinstance(dialog, Adw.Dialog):
            dialog.present(window)
        else:                       # GtkShortcutsWindow on libadwaita < 1.8
            dialog.set_transient_for(window)
            dialog.present()

    def _present_once(self, name: str, build: Callable[[], object]) -> object:
        """Show the ``name`` dialog: the one already open, brought to the
        front, or a new one from ``build()``. Asking again (a shortcut held
        down, the menu clicked twice) never stacks another copy, each of
        which would hold its rows, swatches and settings handlers."""
        dialog = self._open_dialogs.get(name)
        if dialog is None:
            dialog = build()
            self._open_dialogs[name] = dialog
            signal = "closed" if isinstance(dialog, Adw.Dialog) else "close-request"

            def forget(*_a):
                if self._open_dialogs.get(name) is dialog:
                    del self._open_dialogs[name]
                return False                     # let a window close
            dialog.connect(signal, forget)
        self._present(dialog)
        return dialog

    def show_preferences(self) -> None:
        from .core.windows import extension_source
        from .devices.base import DeviceKind
        from .ui.dialogs.preferences import PreferencesDialog
        gpus = self.ctx.devices.monitors(DeviceKind.GPU) if self.ctx.devices else []
        window = self.get_active_window()
        self._present_once("preferences", lambda: PreferencesDialog(
            self.ctx.settings, gpus, self.ctx.theme, log_file=self.file_log.path,
            sidebar=getattr(window, "sidebar", None), history=self.history,
            export=self.export_statistics, restart=self.restart,
            windows=getattr(self.ctx, "windows", None),
            extension_source=extension_source(), background=self._background_service()))

    def _background_service(self):
        """*Record in the Background*: not in --demo, whose
        readings are made up."""
        if self.args.demo or self.history is None:
            return None
        from .core.background import BackgroundService
        return BackgroundService(self.ctx.system)

    def export_statistics(self) -> None:
        """Main menu → *Export Statistics…*: pick a folder, write the session."""
        if self.history is None:
            return
        if self.exporter is None:
            from .ui.export import StatisticsExport, export_details
            self.exporter = StatisticsExport(self.history, __version__,
                                             describe=lambda: export_details(self.ctx),
                                             settings=self.ctx.settings)
        self.exporter.start(self.get_active_window())

    def restart(self) -> None:
        """*Restart Now* (Lightweight Mode applies at start-up): quit as
        usual (history written out), then ``main`` starts Proccoli again."""
        self.restart_requested = True
        self.quit()

    def show_shortcuts(self) -> None:
        from .ui.dialogs.about import shortcuts_dialog
        self._present_once("shortcuts", shortcuts_dialog)

    def show_about(self) -> None:
        from .ui.dialogs.about import about_dialog
        self._present_once("about", about_dialog)

    def do_activate(self) -> None:
        from .ui.window import MainWindow  # needs a display; import late

        win = self.get_active_window()
        if win is None:
            win = MainWindow(self, self.ctx)        # opens on the Overview
        else:
            win.show_overview()                     # launched again: same rule
        win.present()
        self.ctx.ticker.start()
        self.offer_record_from_boot(win)

    def offer_record_from_boot(self, window, background=None) -> None:
        """Once: ask whether the recorder should also run from boot, when it
        would help (``core.background.should_offer_linger``). Not while
        another dialog is up (the start-up authentication): then next time."""
        if self.ctx.settings.get("linger-offered"):
            return
        background = background or self._background_service()
        if background is None:
            return

        def answered(state) -> None:
            from .core.background import should_offer_linger
            if not should_offer_linger(state, bool(self.ctx.settings.get("linger-offered")),
                                       bool(self.ctx.settings.get("history"))):
                return
            if window.get_visible_dialog() is not None:
                return
            from .ui.dialogs.record_from_boot import RecordFromBootDialog
            self.record_from_boot = RecordFromBootDialog(self.ctx.settings, background)
            self.record_from_boot.present(window)
        background.refresh(answered)


def signal_adder(glib_unix, glib):
    """The best "call this on a Unix signal" function the system has:
    ``GLibUnix.signal_add`` (GLib >= 2.82), ``GLibUnix.signal_add_full``
    (GLib 2.80, Ubuntu 24.04: it has GLibUnix but not ``signal_add``), or
    the deprecated ``GLib.unix_signal_add`` on older systems. All take
    ``(priority, signum, handler)``. ``glib_unix`` is None when GLibUnix
    can't be imported."""
    for module, name in ((glib_unix, "signal_add"), (glib_unix, "signal_add_full"),
                         (glib, "unix_signal_add")):
        if module is not None and hasattr(module, name):
            return getattr(module, name)
    raise RuntimeError("GLib has no Unix signal function")


def on_sigint(callback) -> None:
    """Call ``callback`` on Ctrl+C in the terminal."""
    try:
        gi.require_version("GLibUnix", "2.0")
        from gi.repository import GLibUnix
    except (ImportError, ValueError):
        GLibUnix = None
    signal_adder(GLibUnix, GLib)(GLib.PRIORITY_DEFAULT, signal.SIGINT, callback)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=WINDOW, description=f"{APP_NAME}: a system resource monitor")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")
    parser.add_argument("--demo", action="store_true",
                        help="show synthetic data instead of reading the system")
    parser.add_argument("--debug", action="store_true",
                        help="log debugging information to stderr")
    parser.add_argument("--lightweight", action="store_true",
                        help="use as little memory as possible (Lightweight Mode)")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    from .core.runtime import console_logging
    console_logging(logging.DEBUG if args.debug else logging.WARNING)
    log.debug("starting %s %s (demo=%s)", APP_NAME, __version__, args.demo)

    GLib.set_prgname(APP_ID)
    GLib.set_application_name(APP_NAME)
    app = Application(args)
    on_sigint(app.quit)
    # Our options are already parsed; GApplication only gets the program name.
    status = app.run(sys.argv[:1])
    if app.restart_requested:
        system = app.ctx.system if app.ctx is not None else None
        if system is not None:
            system.restart_self([a for a in sys.argv[1:] if a != "--lightweight"])
    return status
