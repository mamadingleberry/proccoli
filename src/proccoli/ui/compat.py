"""Fallbacks for the oldest supported platform: libadwaita 1.5 and GTK 4.14
(Ubuntu 24.04).

Every use of a libadwaita class newer than 1.5 goes through here (or sits
behind a ``hasattr(Adw, ...)`` check), which ``tests/test_static.py``
enforces. The ``adw`` argument is injectable, so tests can check the
fallback on a system that has the newer class.
"""

from __future__ import annotations

import re

from gi.repository import Adw, Gtk

_ROOT_RULE = re.compile(r":root\s*\{[^}]*\}\s*")


def has_css_variables(gtk=Gtk) -> bool:
    """Whether GTK reads CSS custom properties (``--accent-bg-color``):
    GTK >= 4.16. Older GTK warns at a ``:root`` rule and ignores it; the
    ``@define-color`` names next to it still work there."""
    return (gtk.get_major_version(), gtk.get_minor_version()) >= (4, 16)


def without_css_variables(css: str) -> str:
    """``css`` without its ``:root { --name: value; }`` rules, for GTK < 4.16."""
    return _ROOT_RULE.sub("", css)


# GTK's ``gtk-xft-dpi`` is in 1/1024 dots per inch; 96 dpi is GTK's own default.
DEFAULT_XFT_DPI = 96 * 1024


def ensure_font_dpi(gtk_settings) -> bool:
    """Give GTK a font DPI when the desktop didn't set one; True if it did.

    libadwaita 1.5 turns ``sp`` and ``pt`` breakpoints (the window's
    ``max-width: 780sp``) into pixels with ``gtk-xft-dpi``. When that is
    unset (-1: an X11 session without an XSETTINGS daemon, or the headless
    Broadway display) they never match, so the sidebar never folds away.
    Newer libadwaita assumes 96 dpi; this does the same."""
    if gtk_settings is None or gtk_settings.props.gtk_xft_dpi > 0:
        return False
    gtk_settings.props.gtk_xft_dpi = DEFAULT_XFT_DPI
    return True


def spinner(adw=Adw, **props) -> Gtk.Widget:
    """A spinning indicator: ``Adw.Spinner()`` (libadwaita >= 1.6), else a
    ``Gtk.Spinner()`` that is already spinning."""
    if hasattr(adw, "Spinner"):
        return adw.Spinner(**props)
    return Gtk.Spinner(spinning=True, **props)
