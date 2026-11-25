"""The optional start-up authentication dialog."""

from __future__ import annotations

from typing import Callable, Optional, Sequence

from gi.repository import Adw, Gtk

from ..elevation import ElevationOffer, ElevationRunner


class LaunchAuthDialog(Adw.AlertDialog):
    """Lists what administrator rights would unlock, one switch each.
    *Authenticate* runs the chosen offers one after another; *Not Now*
    does nothing. Either way "Don't ask at start-up" can turn it off."""

    def __init__(self, offers: Sequence[ElevationOffer], settings,
                 finished: Optional[Callable[[dict[str, bool]], None]] = None) -> None:
        super().__init__(
            heading="Show All Details?",
            body="Some details need administrator rights. You may be asked for your "
                 "password more than once. You can also do this later from each "
                 "page, or from the main menu.")
        self.offers = list(offers)
        self.settings = settings
        self.finished = finished
        self.runner: Optional[ElevationRunner] = None

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        group = Adw.PreferencesGroup()
        self.switches: dict[str, Adw.SwitchRow] = {}
        for offer in self.offers:
            row = Adw.SwitchRow(title=offer.title, subtitle=offer.subtitle, active=True)
            row.connect("notify::active", lambda *_: self._update_response())
            self.switches[offer.id] = row
            group.add(row)
        box.append(group)
        self.dont_ask = Gtk.CheckButton(label="Don't ask at start-up",
                                        active=not settings.get("auth-at-launch"))
        box.append(self.dont_ask)
        self.set_extra_child(box)

        self.add_response("not-now", "Not Now")
        self.add_response("authenticate", "Authenticate")
        self.set_response_appearance("authenticate", Adw.ResponseAppearance.SUGGESTED)
        self.set_default_response("authenticate")
        self.set_close_response("not-now")
        self.connect("response", lambda _d, response: self.respond(response))

    def chosen(self) -> list[ElevationOffer]:
        return [o for o in self.offers if self.switches[o.id].get_active()]

    def _update_response(self) -> None:
        self.set_response_enabled("authenticate", bool(self.chosen()))

    def respond(self, response: str) -> None:
        """What a response does (also called by tests)."""
        ask = not self.dont_ask.get_active()
        if self.settings.get("auth-at-launch") != ask:
            self.settings.set("auth-at-launch", ask)
        if response == "authenticate":
            self.runner = ElevationRunner(self.chosen(), self.finished)
            self.runner.start()
