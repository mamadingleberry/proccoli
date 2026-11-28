"""Preferences' History and Diagnostics rows: keeping the history, its size
and deletion, exporting, recording in the background and from boot, and
the log file's folder."""

from __future__ import annotations

from gi.repository import Adw, Gtk


class HistoryRows:
    """History, background recording and log rows (a part of ``PreferencesDialog``)."""

    def _history_switch(self, group) -> None:
        self._switch(group, "history", "Keep History")
        self._watch("history", lambda _k, on: on or self.offer_delete())

    def _size_row(self, group) -> None:
        row = Adw.ActionRow(title="Size on Disk")
        button = Gtk.Button(label="Delete History…", valign=Gtk.Align.CENTER)
        button.add_css_class("destructive-action")
        button.connect("clicked", lambda *_: self.offer_delete())
        row.add_suffix(button)
        self._add(group, row)
        self.size_row, self.delete_button = row, button
        self.show_size()

    def _export_row(self, group) -> None:
        row = Adw.ActionRow(title="Export Statistics",
                            subtitle="This session's readings as CSV files, with what "
                                     "each device is")
        button = Gtk.Button(label="Export…", valign=Gtk.Align.CENTER)
        button.connect("clicked", lambda *_: self.export())
        row.add_suffix(button)
        self._add(group, row)
        self.export_button = button

    def _background_rows(self, group) -> None:
        self.background_row = Adw.SwitchRow(
            title="Record in the Background",
            subtitle="Keeps the history while Proccoli is closed, from when you log in")
        self.linger_row = Adw.SwitchRow(
            title="Start at Boot",
            subtitle="Also records before you log in and after you log out")
        for row in (self.background_row, self.linger_row):
            self._add(group, row)
        self._background_busy = True                 # until the first answer
        self.background_row.connect("notify::active", lambda r, _p: self._set_background(
            r.get_active()))
        self.linger_row.connect("notify::active", lambda r, _p: self._set_linger(
            r.get_active()))
        self._watch("history", lambda *_: self._show_background(self.background.state))

    def _recording_row(self, group) -> None:
        self.recording_row = Adw.ActionRow(title="Recording")
        self._add(group, self.recording_row)

    def _show_background(self, state) -> None:
        from ...core.background import status_text
        self._background_busy = True
        self.background_row.set_active(state.enabled)
        self.background_row.set_sensitive(state.available)
        if not state.available:
            self.background_row.set_subtitle(state.reason)
        self.linger_row.set_active(state.linger)
        self.linger_row.set_sensitive(state.available and state.enabled)
        self._background_busy = False
        history = self.history
        writer = history.writer_info() if history is not None else None
        here = bool(history is not None and history.writer and history.session is not None)
        self.recording_row.set_subtitle(status_text(writer, here,
                                                    bool(self.settings.get("history")), state))

    def _set_background(self, on: bool) -> None:
        if not self._background_busy and on != self.background.state.enabled:
            self._background_busy = True
            self.background.set_enabled(on, self._show_background)

    def _set_linger(self, on: bool) -> None:
        if not self._background_busy and on != self.background.state.linger:
            self._background_busy = True
            self.background.set_linger(on, self._show_background)

    def show_size(self) -> None:
        from ...core.units import Base, format_bytes
        if self.history is not None:
            size = self.history.size_on_disk()
            self.size_row.set_subtitle(format_bytes(size, Base.BINARY) if size else "Empty")

    def offer_delete(self) -> None:
        """*Delete History…*, and on turning *Keep History* off."""
        if self.history is None or not self.history.size_on_disk():
            return
        alert = Adw.AlertDialog(heading="Delete History?",
                                body="Every reading kept so far is removed. "
                                     "This can't be undone.")
        alert.add_response("keep", "Keep")
        alert.add_response("delete", "Delete")
        alert.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        alert.set_default_response("keep")
        alert.set_close_response("keep")
        alert.connect("response", self._on_delete_response)
        self.delete_alert = alert
        alert.present(self)

    def _on_delete_response(self, alert, response: str) -> None:
        self.delete_alert = None
        if response == "delete":
            self.history.delete()
            self.show_size()

    def _log_file_row(self, group) -> None:
        row = Adw.ActionRow(title="Log File", subtitle=str(self.log_file))
        button = Gtk.Button(label="Open Folder", valign=Gtk.Align.CENTER)
        button.connect("clicked", lambda *_: self.open_log_folder())
        row.add_suffix(button)
        self._add(group, row)
        self.log_button = button

    def open_log_folder(self) -> None:
        self.open_folder(self.log_file.parent)

    def open_folder(self, folder) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        if self.launcher is not None:
            self.launcher(folder)
            return
        from gi.repository import Gio
        Gtk.FileLauncher.new(Gio.File.new_for_path(str(folder))).launch(
            self.get_root(), None, None)
