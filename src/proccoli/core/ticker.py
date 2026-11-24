"""The app-wide refresh clock.

One ``Ticker`` drives every monitor, so all graphs sample at the same moments
and line up. Its interval follows the *Update Interval* preference
(``update-interval``; it replaced *Refresh Speed*, Idea 6).
"""

from __future__ import annotations

import math
import time
from typing import Callable, Optional

from gi.repository import GLib, GObject

# Update-interval nicks (settings schema) -> milliseconds. Nothing faster
# than once a second (Idea 6).
UPDATE_INTERVALS_MS = {
    "1-second": 1000,
    "2-seconds": 2000,
    "3-seconds": 3000,
    "5-seconds": 5000,
    "10-seconds": 10000,
}
DEFAULT_INTERVAL = "1-second"

# The old *Refresh Speed* nicks -> the update interval that replaces them
# (settings.migrate; also how an old Intel tab interval is read).
REFRESH_SPEED_TO_INTERVAL = {
    "very-slow": "5-seconds",      # was 4 s
    "slow": "2-seconds",
    "normal": "1-second",
    "fast": "1-second",            # was 0.5 s: too fast
    "very-fast": "1-second",       # was 0.25 s: too fast
}


def interval_for(nick: str) -> int:
    """Milliseconds for an update-interval nick (or an old refresh-speed
    one); unknown: 1 second."""
    nick = REFRESH_SPEED_TO_INTERVAL.get(nick, nick)
    return UPDATE_INTERVALS_MS.get(nick, UPDATE_INTERVALS_MS[DEFAULT_INTERVAL])


def update_interval_ms(settings) -> int:
    return interval_for(settings.get("update-interval"))


# Graph time-range nicks (settings schema) -> seconds (M58). Graphs show
# this much time whatever the update interval; the number of points follows.
TIME_RANGES_S = {
    "30-seconds": 30,
    "1-minute": 60,
    "2-minutes": 120,
    "5-minutes": 300,
    "10-minutes": 600,
    "30-minutes": 1800,         # the longer ranges average samples (below)
    "1-hour": 3600,
    "6-hours": 21600,
    "1-day": 86400,
}

# A graph keeps at most this many points; a longer range averages several
# samples into each point, so a day costs no more memory or drawing than
# ten minutes (history follow-ups).
MAX_GRAPH_POINTS = 1200


def time_range_s(nick: str) -> int:
    return TIME_RANGES_S.get(nick, TIME_RANGES_S["1-minute"])


def history_points(span_s: float, interval_ms: int) -> int:
    """Samples needed to cover ``span_s`` seconds at ``interval_ms``: one
    per interval, plus the one at the start."""
    return max(2, int(span_s * 1000 / interval_ms) + 1)


def history_plan(span_s: float, interval_ms: int,
                 max_points: int = MAX_GRAPH_POINTS) -> tuple[int, int]:
    """``(points, every)``: a history of ``points`` covering ``span_s``,
    each point the average of ``every`` samples taken ``interval_ms``
    apart (1 for ranges that fit: 10 minutes at 1 s is 601 points of one
    sample; a day at 1 s is 1200 points of 72)."""
    raw = history_points(span_s, interval_ms)
    every = max(1, math.ceil((raw - 1) / (max_points - 1)))
    return history_points(span_s, interval_ms * every), every


def graph_plan(settings) -> tuple[int, int, float]:
    """``(points, every, step_s)`` for the graphs' time range at the
    update interval; ``step_s`` is the time between points."""
    interval = update_interval_ms(settings)
    points, every = history_plan(time_range_s(settings.get("graph-time-range")), interval)
    return points, every, interval * every / 1000


def graph_points(settings) -> int:
    """How many points a graph keeps: its time range at the update
    interval (1 minute at 1 s: 61; at 2 s: 31; never more than
    ``MAX_GRAPH_POINTS``)."""
    return graph_plan(settings)[0]


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
        """Keep the interval in sync with the ``update-interval`` setting."""
        self.set_interval(update_interval_ms(settings))
        self._settings_handler = settings.connect_changed(
            "update-interval", lambda _k, v: self.set_interval(interval_for(v)))

    def _arm(self) -> None:
        self._source = self._timeout_add(self._interval_ms, self._on_timeout)

    def _on_timeout(self) -> bool:
        self.tick_now()
        return True  # keep the GLib source alive
