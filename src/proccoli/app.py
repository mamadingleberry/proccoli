"""Application entry point and command-line options."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from typing import Optional, Sequence

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import APP_ID, APP_NAME, __version__  # noqa: E402

log = logging.getLogger(__name__)


class Application(Adw.Application):
    def __init__(self, args: argparse.Namespace, context_factory=None,
                 log_file=None, history_path=None, import_dir=None) -> None:
        """``context_factory(settings, demo)`` builds the AppContext; tests
        can pass their own (default: ``proccoli.context.build_context``).
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
        self.ctx = None  # created in do_startup
        self.profile = None          # core.profile.Profile, chosen in do_startup
        self.restart_requested = False

        for name, callback, accels in (
                ("quit", lambda *_: self.quit(), ["<Control>q"]),
                ("preferences", lambda *_: self.show_preferences(), ["<Control>comma"]),
                ("shortcuts", lambda *_: self.show_shortcuts(), ["<Control>question"]),
                ("about", lambda *_: self.show_about(), []),
                ("export-statistics", lambda *_: self.export_statistics(), []),
                ("restart", lambda *_: self.restart(), [])):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
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
        changes = migrate(base)                     # replaced keys, once (Idea 6)
        # Lightweight mode (Idea 1): chosen once; everything reads the
        # settings as the profile sees them.
        self.profile = choose_profile(base, getattr(self.args, "lightweight", False))
        settings = profile_settings(base, self.profile)
        from .core.applog import FileLog, log_path
        self.file_log = FileLog(settings, self.log_file or log_path())
        for change in changes:
            log.info("settings: %s", change)
        log.info("%s %s starting (demo=%s)", APP_NAME, __version__, self.args.demo)
        from .core.watchdog import StallWatchdog
        self.watchdog = StallWatchdog()     # logs stalls with stacks (M44)
        self.watchdog.start()
        if self.context_factory is None:
            from .context import build_context
            self.ctx = build_context(settings, demo=self.args.demo)
        else:
            self.ctx = self.context_factory(settings, self.args.demo)
        if self.ctx.theme is None:      # the UI half of the composition root
            from .ui.theme import Theme
            self.ctx.theme = Theme(settings, Adw.StyleManager.get_default())
        from .ui.style import ThemeCss
        self.theme_css = ThemeCss(self.ctx.theme) if self.ctx.profile.theme_css else None
        self.ctx.start()
        # Every reading, in the history database (Idea 2); never the demo's
        # made-up ones.
        if not self.args.demo and self.ctx.devices is not None:
            from .core.history_store import HistoryStore, history_path, old_stats_dir
            self.history = HistoryStore(self.ctx.devices, self.ctx.settings,
                                        self.history_path or history_path(), __version__,
                                        idle=GLib.idle_add,
                                        import_dir=self.import_dir or old_stats_dir())
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
        if getattr(self, "watchdog", None) is not None:
            self.watchdog.stop()
        if getattr(self, "file_log", None) is not None:
            log.info("%s stopping", APP_NAME)
            self.file_log.shutdown()
        Adw.Application.do_shutdown(self)

    # -- dialogs ------------------------------------------------------------------

    def _present(self, dialog) -> None:
        window = self.get_active_window()
        if isinstance(dialog, Adw.Dialog):
            dialog.present(window)
        else:                       # GtkShortcutsWindow on libadwaita < 1.8
            dialog.set_transient_for(window)
            dialog.present()

    def show_preferences(self) -> None:
        from .core.windows import extension_source
        from .devices.base import DeviceKind
        from .ui.dialogs.preferences import PreferencesDialog
        gpus = self.ctx.devices.monitors(DeviceKind.GPU) if self.ctx.devices else []
        window = self.get_active_window()
        self._present(PreferencesDialog(self.ctx.settings, gpus, self.ctx.theme,
                                        log_file=self.file_log.path,
                                        sidebar=getattr(window, "sidebar", None),
                                        history=self.history,
                                        export=self.export_statistics,
                                        restart=self.restart,
                                        windows=getattr(self.ctx, "windows", None),
                                        extension_source=extension_source()))

    def export_statistics(self) -> None:
        """Main menu → *Export Statistics…*: pick a folder, write the session."""
        if self.history is None:
            return
        if self.exporter is None:
            from .ui.export import StatisticsExport
            self.exporter = StatisticsExport(self.history, __version__)
        self.exporter.start(self.get_active_window())

    def restart(self) -> None:
        """*Restart Now* (Lightweight Mode applies at start-up): quit as
        usual (history written out), then ``main`` starts Proccoli again."""
        self.restart_requested = True
        self.quit()

    def show_shortcuts(self) -> None:
        from .ui.dialogs.about import shortcuts_dialog
        self._present(shortcuts_dialog())

    def show_about(self) -> None:
        from .ui.dialogs.about import about_dialog
        self._present(about_dialog())

    def do_activate(self) -> None:
        from .ui.window import MainWindow  # needs a display; import late

        win = self.get_active_window()
        if win is None:
            win = MainWindow(self, self.ctx)        # opens on the Overview
        else:
            win.show_overview()                     # launched again: same rule
        win.present()
        self.ctx.ticker.start()


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
        prog="proccoli", description=f"{APP_NAME}: a system resource monitor")
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
    console_level = logging.DEBUG if args.debug else logging.WARNING
    logging.basicConfig(level=console_level, format="%(levelname)s %(name)s: %(message)s")
    # The terminal keeps its level even when the log file records more.
    for handler in logging.getLogger().handlers:
        handler.setLevel(console_level)
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
