"""About and Keyboard Shortcuts dialogs."""

from __future__ import annotations

from gi.repository import Adw, Gtk

from ... import APP_ID, APP_NAME, __version__

LICENSE = ("Permission to use, copy, modify, and/or distribute this software for any "
           "purpose with or without fee is hereby granted. (Zero-Clause BSD)")

from ..shortcuts import SHORTCUTS  # noqa: F401  (the dialog's list; tests read it here too)


def about_dialog() -> Adw.AboutDialog:
    dialog = Adw.AboutDialog(
        application_name=APP_NAME, application_icon=APP_ID, version=__version__,
        developer_name=f"The {APP_NAME} contributors",
        comments="Keep an eye on your system's resources, with detailed statistics "
                 "for your GPU.",
        license_type=Gtk.License.CUSTOM, license=LICENSE)
    dialog.add_acknowledgement_section(
        "Design", ["Resources by nokyan: the layout and behaviour this app mirrors"])
    dialog.add_acknowledgement_section(
        "Built on", ["intel_gpu_top_gui: the detailed Intel GPU page",
                     "intel_gpu_top from IGT GPU Tools"])
    return dialog


def shortcuts_dialog():
    """Adw.ShortcutsDialog (libadwaita >= 1.8), else a GtkShortcutsWindow."""
    if hasattr(Adw, "ShortcutsDialog"):
        dialog = Adw.ShortcutsDialog()
        for title, items in SHORTCUTS:
            section = Adw.ShortcutsSection(title=title)
            for name, accel in items:
                section.add(Adw.ShortcutsItem(title=name, accelerator=accel))
            dialog.add(section)
        return dialog
    groups = "".join(
        f'<child><object class="GtkShortcutsGroup"><property name="title">{title}</property>'
        + "".join(f'<child><object class="GtkShortcutsShortcut">'
                  f'<property name="title">{name}</property>'
                  f'<property name="accelerator">{accel.replace("<", "&lt;").replace(">", "&gt;")}'
                  f'</property></object></child>' for name, accel in items)
        + "</object></child>" for title, items in SHORTCUTS)
    xml = ('<interface><object class="GtkShortcutsWindow" id="w"><property name="modal">1'
           '</property><child><object class="GtkShortcutsSection">'
           f"{groups}</object></child></object></interface>")
    return Gtk.Builder.new_from_string(xml, -1).get_object("w")
