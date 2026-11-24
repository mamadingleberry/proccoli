"""Saving and restoring the main window's size and maximized state.

Kept free of Gtk imports: the functions take any object with the few window
methods used, so they can be tested without a display.
"""

from __future__ import annotations


def restore_window_state(window, settings) -> None:
    window.set_default_size(settings.get("window-width"),
                            settings.get("window-height"))
    if settings.get("is-maximized"):
        window.maximize()


def save_window_state(window, settings) -> None:
    maximized = window.is_maximized()
    settings.set("is-maximized", maximized)
    if maximized:
        # Keep the last unmaximized size, so unmaximizing after a restart
        # returns to it rather than to the screen size.
        return
    width, height = window.get_default_size()
    if width > 0 and height > 0:
        settings.set("window-width", width)
        settings.set("window-height", height)
