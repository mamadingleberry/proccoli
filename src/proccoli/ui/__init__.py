"""User interface: windows, pages, widgets and dialogs.

Importing any UI module pins the GTK and libadwaita versions first, so the
order modules happen to be imported in doesn't matter.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
