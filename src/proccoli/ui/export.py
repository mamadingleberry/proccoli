"""*Export Statistics…* (main menu and Preferences → History, Idea 2): the
user picks a folder, the running session's readings are written to a new
folder in it off the main loop (``core.history_export``), and toasts on the
window tell how it went.

Everything that touches the desktop is injected: ``choose_folder(window,
callback)`` (default: ``Gtk.FileDialog``, which goes through the desktop
portal), ``run(work, done)`` (default: a worker thread, ``done`` back on the
main loop) and ``launcher(folder)`` for *Open Folder*.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable, Optional

from gi.repository import Adw, Gio, GLib, Gtk

from ..core.history_export import export_session

log = logging.getLogger(__name__)


def choose_folder_with_dialog(window, callback: Callable[[Optional[Path]], None]) -> None:
    dialog = Gtk.FileDialog(title="Export Statistics", accept_label="Export",
                            modal=True)

    def finished(d, result):
        try:
            folder = d.select_folder_finish(result)
        except GLib.Error:                  # cancelled
            callback(None)
            return
        path = folder.get_path() if folder is not None else None
        callback(Path(path) if path else None)

    dialog.select_folder(window, None, finished)


def run_in_thread(work: Callable[[], object], done: Callable[[object], None]) -> None:
    def target():
        try:
            result = work()
        except Exception as exc:  # noqa: BLE001 - reported to the user
            result = exc
        GLib.idle_add(lambda: done(result) and False)

    threading.Thread(target=target, name="proccoli-export", daemon=True).start()


def open_with_launcher(window, folder: Path) -> None:
    Gtk.FileLauncher.new(Gio.File.new_for_path(str(folder))).launch(window, None, None)


class StatisticsExport:
    def __init__(self, history, version: str = "", choose_folder=None, run=None,
                 launcher=None, wall_clock=None) -> None:
        self.history = history
        self.version = version
        self.choose_folder = choose_folder or choose_folder_with_dialog
        self.run = run or run_in_thread
        self.launcher = launcher
        self.wall_clock = wall_clock or history.wall_clock
        self.window = None
        self.busy = False
        self.toast: Optional[Adw.Toast] = None
        self.last_folder: Optional[Path] = None

    def start(self, window) -> None:
        if self.busy:
            self._toast("An export is already running")
            return
        self.window = window
        self.choose_folder(window, self._chosen)

    def _chosen(self, folder: Optional[Path]) -> None:
        if folder is None:
            return
        self.history.commit()                  # what's buffered goes too
        start = self.history.session
        if start is None or self.history.db is None:
            self._toast("Nothing has been recorded yet")
            return
        end = int(round(self.wall_clock() * 1000))
        path, version = self.history.path, self.version
        self.busy = True
        self._toast("Exporting statistics…", timeout=0)

        def progress(done: int, total: int) -> None:
            GLib.idle_add(lambda: self._progress(done, total) and False)

        self.run(lambda: export_session(path, folder, start, end, version,
                                        progress=progress), self._done)

    def _progress(self, done: int, total: int) -> None:
        if self.busy and self.toast is not None:
            self.toast.set_title(f"Exporting statistics… {done} of {total} devices")

    def _done(self, result) -> None:
        self.busy = False
        if self.toast is not None:
            self.toast.dismiss()
        if isinstance(result, Exception):
            log.warning("statistics export failed: %s", result)
            self._toast(f"Couldn't export statistics: {result}")
            return
        self.last_folder = result.folder
        log.info("statistics exported to %s (%d rows)", result.folder, result.rows)
        toast = self._toast(f"Statistics exported to {result.folder.name}")
        if toast is not None:
            toast.set_button_label("Open Folder")
            toast.connect("button-clicked", lambda *_: self.open_folder(result.folder))

    def open_folder(self, folder: Path) -> None:
        if self.launcher is not None:
            self.launcher(folder)
        else:
            open_with_launcher(self.window, folder)

    def _toast(self, text: str, timeout: int = 5) -> Optional[Adw.Toast]:
        overlay = getattr(self.window, "toast_overlay", None)
        self.toast = Adw.Toast(title=text, timeout=timeout, use_markup=False)
        if overlay is not None:
            overlay.add_toast(self.toast)
        return self.toast
