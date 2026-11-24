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
                 log_file=None) -> None:
        """``context_factory(settings, demo)`` builds the AppContext; tests
        can pass their own (default: ``proccoli.context.build_context``).
        ``log_file`` is the diagnostics log (default: ``applog.log_path()``)."""
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.args = args
        self.context_factory = context_factory
        self.log_file = log_file
        self.ctx = None  # created in do_startup

        for name, callback, accels in (
                ("quit", lambda *_: self.quit(), ["<Control>q"]),
                ("preferences", lambda *_: self.show_preferences(), ["<Control>comma"]),
                ("shortcuts", lambda *_: self.show_shortcuts(), ["<Control>question"]),
                ("about", lambda *_: self.show_about(), [])):
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

        install_css()
        add_source_icons()
        Gtk.Window.set_default_icon_name(APP_ID)
        settings = Settings.load()
        from .core.applog import FileLog, log_path
        self.file_log = FileLog(settings, self.log_file or log_path())
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
        self.theme_css = ThemeCss(self.ctx.theme)
        self.ctx.start()

    def do_shutdown(self) -> None:
        if self.ctx is not None:
            self.ctx.stop()
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
        from .devices.base import DeviceKind
        from .ui.dialogs.preferences import PreferencesDialog
        gpus = self.ctx.devices.monitors(DeviceKind.GPU) if self.ctx.devices else []
        window = self.get_active_window()
        self._present(PreferencesDialog(self.ctx.settings, gpus, self.ctx.theme,
                                        log_file=self.file_log.path,
                                        sidebar=getattr(window, "sidebar", None)))

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
            win = MainWindow(self, self.ctx)
        win.present()
        self.ctx.ticker.start()


def on_sigint(callback) -> None:
    """Call ``callback`` on Ctrl+C in the terminal (GLib >= 2.80 moved this
    into GLibUnix; older systems only have the deprecated GLib function)."""
    try:
        gi.require_version("GLibUnix", "2.0")
        from gi.repository import GLibUnix
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, callback)
    except (ImportError, ValueError):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, callback)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="proccoli", description=f"{APP_NAME}: a system resource monitor")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")
    parser.add_argument("--demo", action="store_true",
                        help="show synthetic data instead of reading the system")
    parser.add_argument("--debug", action="store_true",
                        help="log debugging information to stderr")
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
    return app.run(sys.argv[:1])
