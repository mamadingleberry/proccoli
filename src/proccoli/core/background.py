"""Turning ``proccoli`` on and off:
its systemd user unit, and lingering (so the user's systemd, and the unit,
start at boot). Display-free; everything runs through ``System.run_async()``
(``systemctl --user``, ``loginctl``), so tests fake it.

There's no settings key for this: the unit's enabled state *is* the
choice, so a change made with ``systemctl`` shows in Preferences too.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .. import COLLECTOR

UNIT = f"{COLLECTOR}.service"


@dataclass
class BackgroundState:
    available: bool = False      # systemctl and the unit are there
    enabled: bool = False        # starts with the user's session
    active: bool = False         # running now
    linger: bool = False         # the user's systemd starts at boot
    reason: str = ""             # why it isn't available


def parse_enabled(rc: int, out: str, err: str) -> tuple[bool, bool, str]:
    """``(available, enabled, reason)`` from ``systemctl --user
    is-enabled``: "enabled" or "disabled" mean the unit is installed."""
    word = out.strip().splitlines()[0] if out.strip() else ""
    if word in ("enabled", "enabled-runtime", "linked", "linked-runtime"):
        return True, True, ""
    if word in ("disabled", "static", "indirect"):
        return True, False, ""
    if "not-found" in (out + err) or "No such file" in err or "not found" in err:
        return False, False, "proccoli isn't installed"
    return False, False, "No user systemd to start it (" + (err.strip() or word or
                                                           f"exit {rc}") + ")"


class BackgroundService:
    def __init__(self, system) -> None:
        self.system = system
        self.state = BackgroundState()

    @property
    def uid(self) -> str:
        return str(self.system.geteuid())

    def refresh(self, done: Callable[[BackgroundState], None]) -> None:
        """Ask systemd and logind; ``done(state)`` on the main loop."""
        if self.system.which("systemctl") is None:
            self.state = BackgroundState(reason="systemctl isn't available")
            done(self.state)
            return

        def got_enabled(rc, out, err):
            available, enabled, reason = parse_enabled(rc, out, err)
            self.state = BackgroundState(available, enabled, reason=reason)
            if not available:
                done(self.state)
                return
            self.system.run_async(["systemctl", "--user", "is-active", UNIT], got_active)

        def got_active(_rc, out, _err):
            self.state.active = out.strip() == "active"
            if self.system.which("loginctl") is None:
                done(self.state)
                return
            self.system.run_async(["loginctl", "show-user", self.uid, "--property=Linger",
                                   "--value"], got_linger)

        def got_linger(_rc, out, _err):
            self.state.linger = out.strip() == "yes"
            done(self.state)

        self.system.run_async(["systemctl", "--user", "is-enabled", UNIT], got_enabled)

    def set_enabled(self, on: bool, done: Callable[[BackgroundState], None]) -> None:
        """Enable and start, or disable and stop, then ``refresh``."""
        argv = ["systemctl", "--user", "enable" if on else "disable", "--now", UNIT]
        self.system.run_async(argv, lambda *_r: self.refresh(done))

    def set_linger(self, on: bool, done: Callable[[BackgroundState], None]) -> None:
        """``loginctl enable-linger`` (logind may ask for a password)."""
        argv = ["loginctl", "enable-linger" if on else "disable-linger", self.uid]
        self.system.run_async(argv, lambda *_r: self.refresh(done))


def status_text(writer: Optional[dict], recording_here: bool, history_on: bool,
                state: Optional[BackgroundState] = None) -> str:
    """Preferences' *Recording* line."""
    from .units import iso_utc
    if not history_on:
        return "Not recording: Keep History is off"
    if recording_here:
        return "Recording while Proccoli is open"
    if writer and writer.get("program") == COLLECTOR:
        since = iso_utc(writer.get("since", 0) / 1000)[:16].replace("T", " ")
        return f"Recording in the background since {since} UTC"
    if state is not None and state.enabled and not state.active:
        return "Background recording is on but not running"
    return "Recording"
