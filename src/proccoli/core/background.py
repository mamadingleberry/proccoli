"""Turning ``proccoli`` on and off:
its systemd user unit, and lingering (so the user's systemd, and the unit,
start at boot). Display-free; everything runs through ``System.run_async()``
(``systemctl --user``, ``loginctl``), so tests fake it.

There's no settings key for this: the unit's enabled state *is* the
choice, so a change made with ``systemctl`` shows in Preferences too.
Lingering, too, is logind's own state; only whether the window has
offered it once is a setting (``linger-offered``).
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
        self.system.run_async(linger_argv(on, self.uid), lambda *_r: self.refresh(done))


# -- recording from boot (lingering) -----------------------------------------------------


def linger_argv(on: bool, uid: str) -> list[str]:
    return ["loginctl", "enable-linger" if on else "disable-linger", uid]


def linger_query_argv(uid: str) -> list[str]:
    return ["loginctl", "show-user", uid, "--property=Linger", "--value"]


def should_offer_linger(state: BackgroundState, offered: bool, history_on: bool) -> bool:
    """Whether the window asks, once, to record from boot: the recorder is
    installed and on, the history kept, lingering off, and never asked
    before. Each person decides for their own account."""
    return (state.available and state.enabled and history_on and not state.linger
            and not offered)


def linger_on(system) -> Optional[bool]:
    """Lingering for this user, or None when logind can't say."""
    if system.which("loginctl") is None:
        return None
    rc, out, _err = system.run(linger_query_argv(str(system.geteuid())))
    if rc != 0:
        return None
    return out.strip() == "yes"


def start_at_boot(system, on: bool) -> tuple[bool, str]:
    """``proccoli --start-at-boot`` / ``--no-start-at-boot``: ``(ok, text)``."""
    if system.which("loginctl") is None:
        return False, "loginctl isn't available: no systemd-logind to start it at boot."
    rc, _out, err = system.run(linger_argv(on, str(system.geteuid())))
    if rc != 0:
        return False, f"loginctl failed: {err.strip() or f'exit {rc}'}"
    if not on:
        return True, "Recording only while you're logged in, from the next boot."
    text = "Recording from boot, before you log in and after you log out."
    if system.which("systemctl") is not None:
        rc, out, err = system.run(["systemctl", "--user", "is-enabled", UNIT])
        available, enabled, _reason = parse_enabled(rc, out, err)
        if available and not enabled:
            text += (f"\nThe recorder itself is off: `systemctl --user enable --now {UNIT}` "
                     "turns it on.")
    return True, text


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
