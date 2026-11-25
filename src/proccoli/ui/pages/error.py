"""The error page: shown instead of a device's page when the
device couldn't be set up (``devices.base.FailedMonitor``, e.g. no source
can read a GPU) or its page couldn't be built.

It says what went wrong in words, keeps the technical details (the
traceback, the GPU detection plan) one click away with *Copy Details*, and
offers *Try Again*, which emits ``retry``: the window asks the device
manager to set the device up again, or the factory to rebuild the page.
The device keeps its sidebar entry, so nothing silently disappears.
"""

from __future__ import annotations

from typing import Optional

from gi.repository import Adw, Gdk, GObject, Gtk

from ...devices.base import FailedMonitor
from ..page import PageKind, ResourcePage

ERROR_ICON = "dialog-error-symbolic"


def error_text(monitor, exc: Optional[BaseException] = None) -> tuple[str, str]:
    """(message, details) for a failed monitor or a page that raised."""
    if isinstance(monitor, FailedMonitor):
        return monitor.message, monitor.details
    import traceback
    details = "".join(traceback.format_exception(exc)) if exc is not None else ""
    return f"Proccoli couldn't show this device: {exc}", details


class ErrorPage(ResourcePage):
    __gsignals__ = {
        "retry": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, monitor, message: str, details: str = "") -> None:
        info = monitor.info
        super().__init__(info.id, PageKind(info.kind.value), info.name, info.icon_name,
                         description=info.description, sort_name=info.id)
        self.monitor = monitor
        self.message = message
        self.details = details
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      halign=Gtk.Align.CENTER)
        self.retry_button = Gtk.Button(label="Try Again", halign=Gtk.Align.CENTER)
        self.retry_button.add_css_class("pill")
        self.retry_button.add_css_class("suggested-action")
        self.retry_button.connect("clicked", lambda _b: self.emit("retry"))
        box.append(self.retry_button)
        self.details_view: Optional[Gtk.TextView] = None
        if details:
            self.details_view = Gtk.TextView(editable=False, monospace=True,
                                             wrap_mode=Gtk.WrapMode.WORD_CHAR,
                                             top_margin=8, bottom_margin=8,
                                             left_margin=8, right_margin=8)
            self.details_view.get_buffer().set_text(details)
            scroller = Gtk.ScrolledWindow(child=self.details_view, min_content_height=160,
                                          max_content_height=320, propagate_natural_height=True,
                                          width_request=480)
            scroller.add_css_class("card")
            copy = Gtk.Button(label="Copy Details", halign=Gtk.Align.START)
            copy.connect("clicked", lambda _b: self.copy_details())
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            inner.append(scroller)
            inner.append(copy)
            self.expander = Gtk.Expander(label="Technical Details", child=inner)
            box.append(self.expander)
        self.status = Adw.StatusPage(icon_name=ERROR_ICON, title=f"{info.name} Isn't Available",
                                     description=message, child=box)
        self.set_child(self.status)

    def copy_details(self) -> None:
        display = self.get_display() or Gdk.Display.get_default()
        if display is not None:
            display.get_clipboard().set(f"{self.message}\n\n{self.details}".strip())
