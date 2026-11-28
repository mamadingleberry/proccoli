"""The keyboard shortcuts: one table that both sets the accelerators and
fills the Keyboard Shortcuts dialog, so the two never disagree.

The first accelerator of an action is the one menus show; the others
also work. Preferences and Keyboard Shortcuts have single keys (F2, F1)
and keep GNOME's usual Ctrl+, and Ctrl+? as well.

Pure data, unit-tested without a display.
"""

from __future__ import annotations

# The window's sidebar toggle (``sidebar_visibility.ACTION``; a test keeps
# them equal, so this module needs no GLib).
SIDEBAR_ACTION = "toggle-sidebar"

# Detailed action name -> accelerators (GTK syntax), first one shown in menus.
ACCELS: dict[str, tuple[str, ...]] = {
    f"win.{SIDEBAR_ACTION}": ("F9",),
    "win.back": ("<Alt>Left",),
    "win.forward": ("<Alt>Right",),
    "app.preferences": ("F2", "<Control>comma"),
    "app.shortcuts": ("F1", "<Control>question"),
    "app.quit": ("<Control>q",),
}

# The Apps and Processes tables set their own (ui/pages/table.py).
TABLE_SHORTCUTS = [("Search", "<Control>f"),
                   ("Information", "<Control>i"),
                   ("End", "Delete"),
                   ("Kill", "<Control>Delete")]

_GENERAL = [("Show or Hide the Sidebar", f"win.{SIDEBAR_ACTION}"),
            ("Back to the Previous Pane", "win.back"),
            ("Forward to the Next Pane", "win.forward"),
            ("Preferences", "app.preferences"),
            ("Keyboard Shortcuts", "app.shortcuts"),
            ("Quit", "app.quit")]

# (section, [(title, accelerators)]): what the dialog lists. Several
# accelerators are space-separated, which GTK and libadwaita show as
# alternatives.
SHORTCUTS = [
    ("General", [(title, " ".join(ACCELS[action])) for title, action in _GENERAL]),
    ("Apps and Processes", TABLE_SHORTCUTS),
]


def accels_for(action: str) -> list[str]:
    """The accelerators for ``action`` (``"app.preferences"``), for
    ``Gtk.Application.set_accels_for_action``."""
    return list(ACCELS.get(action, ()))
