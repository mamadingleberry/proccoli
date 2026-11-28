"""Preferences' System rows: Lightweight Mode (and the restart it needs),
window switching through the GNOME Shell extension, and each GPU's
detailed statistics."""

from __future__ import annotations

from gi.repository import Adw, Gtk
from ...core.profile import profile_of


class SystemRows:
    """Lightweight Mode, window switching and GPU rows (a part of ``PreferencesDialog``)."""

    def _lightweight_rows(self, group) -> None:
        """The switch shows the mode Proccoli runs in now (also when it was
        started with ``--lightweight``); flipping it chooses the mode for the
        next start, which *Restart to Apply* says and offers."""
        running = profile_of(self.settings).is_lightweight
        row = Adw.SwitchRow(title="Lightweight Mode", active=running,
                            subtitle="As little memory as possible: pages are built when you "
                                     "open them, the Overview is a list, and charts, icons and "
                                     "GPU details are kept to a minimum")
        row.connect("notify::active", lambda r, _p: self._choose_lightweight(r.get_active()))
        self._add(group, row)
        self.rows["lightweight"] = row
        row = Adw.ActionRow(title="Restart to Apply",
                            subtitle="Proccoli starts again with the new mode")
        button = Gtk.Button(label="Restart Now", valign=Gtk.Align.CENTER)
        button.add_css_class("suggested-action")
        button.connect("clicked", lambda *_: self.restart and self.restart())
        row.add_suffix(button)
        self._add(group, row)
        self.restart_row, self.restart_button = row, button
        self._watch("lightweight", lambda *_: self._show_restart())
        self._show_restart()

    def _choose_lightweight(self, on: bool) -> None:
        """The mode for the next start (the setting)."""
        self._set("lightweight", on)
        self._show_restart()

    def _show_restart(self) -> None:
        """While the next start's mode differs from this one's."""
        running = profile_of(self.settings).is_lightweight
        pending = bool(self.settings.get("lightweight")) != running
        self.restart_row.set_visible(self.restart is not None and pending)
        if pending:
            self.restart_row.set_subtitle(
                "Lightweight Mode turns " + ("off" if running else "on") + " at the next start")

    def _window_switching_row(self, group) -> None:
        row = Adw.ActionRow(title="Proccoli Window Switching")
        button = Gtk.Button(valign=Gtk.Align.CENTER)
        button.add_css_class("suggested-action")
        button.connect("clicked", lambda *_: self._on_window_switching())
        row.add_suffix(button)
        self._add(group, row)
        self.switching_row, self.switching_button = row, button
        self.show_window_switching()

    def show_window_switching(self) -> None:
        from ...core.windows import ExtensionState
        state = self.windows.extension_state()
        texts = {
            ExtensionState.ENABLED: "On: Switch To works for every app with a window",
            ExtensionState.DISABLED: "Installed, but turned off",
            ExtensionState.NEEDS_LOGIN: "Installed: log out and back in to start it",
            ExtensionState.NOT_INSTALLED: "Not installed: Switch To works only for apps "
                                          "that can be asked to show their window",
            ExtensionState.UNAVAILABLE: "Needs GNOME Shell (this desktop isn't GNOME)",
        }
        self.switching_row.set_subtitle(texts[state])
        label = {ExtensionState.DISABLED: "Turn On"}.get(state)
        if state == ExtensionState.NOT_INSTALLED and self.extension_source is not None:
            label = "Install"
        self.switching_button.set_visible(label is not None)
        if label:
            self.switching_button.set_label(label)
        self.switching_state = state

    def _on_window_switching(self) -> None:
        from ...core.windows import ExtensionState
        if self.switching_state == ExtensionState.DISABLED:
            ok = self.windows.enable()
        else:
            ok = self.windows.install(self.extension_source)
        if not ok:
            self.add_toast(Adw.Toast(title="Couldn't set up window switching", timeout=4))
        self.show_window_switching()

    def _gpu_rows(self, group) -> None:
        for controller in self.gpu_controllers:
            self.gpu_rows[controller.gpu.pci_slot] = self._gpu_row(group, controller)
        if not self.gpu_controllers:
            self._add(group, Adw.ActionRow(title="No GPUs found"))

    def _gpu_row(self, group, controller) -> Adw.ActionRow:
        """A GPU's detailed-statistics switch, or a note that it has none."""
        title = controller.info.description or controller.gpu.name
        if controller.detail_class is None:
            row = Adw.ActionRow(title=title, subtitle=f"{controller.gpu.pci_slot} · "
                                "No detailed data source available")
            self._add(group, row)
            return row
        name = controller.detail_class.display_name
        if controller.needs_elevation:
            name += ", needs administrator rights"
        row = Adw.SwitchRow(title=title, subtitle=f"{controller.gpu.pci_slot} · {name}",
                            active=controller.details_enabled)
        row.connect("notify::active",
                    lambda r, _p: r.get_active() != controller.details_enabled
                    and controller.set_details_enabled(r.get_active()))
        self._add(group, row)
        return row
