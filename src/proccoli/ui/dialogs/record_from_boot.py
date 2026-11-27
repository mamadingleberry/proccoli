"""Asked once: should the recorder also run from boot?"""

from __future__ import annotations

from typing import Callable, Optional

from gi.repository import Adw

TURN_ON = "turn-on"
NOT_NOW = "not-now"


class RecordFromBootDialog(Adw.AlertDialog):
    """*Turn On* turns lingering on for this account (logind may ask for a
    password); *Not Now* leaves it off. Either way the question isn't
    asked again: *Start at Boot* in Preferences changes it any time."""

    def __init__(self, settings, background,
                 finished: Optional[Callable[[str], None]] = None) -> None:
        super().__init__(
            heading="Record from Boot?",
            body="Proccoli records its history while you're logged in. It can also "
                 "record from when the computer starts, before you log in, and after "
                 "you log out, so the history has no gaps. This is for your account "
                 "only. You can change it any time in Preferences → Recording → "
                 "Start at Boot.")
        self.settings = settings
        self.background = background
        self.finished = finished
        self.add_response(NOT_NOW, "Not Now")
        self.add_response(TURN_ON, "Turn On")
        self.set_response_appearance(TURN_ON, Adw.ResponseAppearance.SUGGESTED)
        self.set_default_response(TURN_ON)
        self.set_close_response(NOT_NOW)
        self.connect("response", self._on_response)

    def _on_response(self, _dialog, response: str) -> None:
        self.settings.set("linger-offered", True)
        if response == TURN_ON:
            self.background.set_linger(True, lambda _state: None)
        if self.finished is not None:
            self.finished(response)
