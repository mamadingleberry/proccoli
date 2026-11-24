"""The app-wide refresh clock.

One ``Ticker`` drives every monitor, so all graphs sample at the same moments
and line up. Its interval follows the *Refresh Speed* preference.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from gi.repository import GLib, GObject

# Refresh-speed nicks (settings schema) -> milliseconds.
REFRESH_INTERVALS_MS = {
    "very-slow": 4000,
    "slow": 2000,
    "normal": 1000,
    "fast": 500,
    "very-fast": 250,
}


def interval_for(speed: str) -> int:
    return REFRESH_INTERVALS_MS.get(speed, REFRESH_INTERVALS_MS["normal"])


# Graph time-range nicks (settings schema) -> seconds (M58). Graphs show
# this much time whatever the refresh speed; the number of points follows.
TIME_RANGES_S = {
    "30-seconds": 30,
    "1-minute": 60,
    "2-minutes": 120,
    "5-minutes": 300,
    "10-minutes": 600,
}


def time_range_s(nick: str) -> int:
    return TIME_RANGES_S.get(nick, TIME_RANGES_S["1-minute"])


def history_points(span_s: float, interval_ms: int) -> int:
    """Samples needed to cover ``span_s`` seconds at ``interval_ms``: one
    per interval, plus the one at the start."""
    return max(2, int(span_s * 1000 / interval_ms) + 1)


def graph_points(settings) -> int:
    """How many samples a graph keeps: its time range at the refresh speed
    (1 minute at 1 s: 61; at 0.25 s: 241)."""
    return history_points(time_range_s(settings.get("graph-time-range")),
                          interval_for(settings.get("refresh-speed")))


class Ticker(GObject.Object):
    """Emits ``tick(now)`` every ``interval_ms`` while running.

    ``now`` is a monotonic timestamp in seconds. The timer functions are
    injectable for tests.
    """

    __gsignals__ = {
        "tick": (GObject.SignalFlags.RUN_FIRST, None, (float,)),
    }

    def __init__(self, interval_ms: int = 1000, *,
                 timeout_add: Callable = GLib.timeout_add,
                 source_remove: Callable = GLib.source_remove,
                 clock: Callable[[], float] = time.monotonic) -> None:
        super().__init__()
        if interval_ms <= 0:
            raise ValueError("interval must be positive")
        self._interval_ms = interval_ms
        self._timeout_add = timeout_add
        self._source_remove = source_remove
        self._clock = clock
        self._source: Optional[int] = None
        self._settings_handler: Optional[int] = None

    @property
    def interval_ms(self) -> int:
        return self._interval_ms

    @property
    def running(self) -> bool:
        return self._source is not None

    def start(self) -> None:
        """Start ticking. The first tick fires immediately, so pages fill
        without waiting a whole interval."""
        if self.running:
            return
        self._arm()
        self.tick_now()

    def stop(self) -> None:
        if self._source is not None:
            self._source_remove(self._source)
            self._source = None

    def set_interval(self, interval_ms: int) -> None:
        if interval_ms <= 0:
            raise ValueError("interval must be positive")
        if interval_ms == self._interval_ms:
            return
        self._interval_ms = interval_ms
        if self.running:  # re-arm so the new interval applies right away
            self._source_remove(self._source)
            self._arm()

    def tick_now(self) -> None:
        self.emit("tick", self._clock())

    def follow(self, settings) -> None:
        """Keep the interval in sync with the ``refresh-speed`` setting."""
        self.set_interval(interval_for(settings.get("refresh-speed")))
        self._settings_handler = settings.connect_changed(
            "refresh-speed", lambda _k, v: self.set_interval(interval_for(v)))

    def _arm(self) -> None:
        self._source = self._timeout_add(self._interval_ms, self._on_timeout)

    def _on_timeout(self) -> bool:
        self.tick_now()
        return True  # keep the GLib source alive
