"""Optional authentication at launch.

Pages that can show more with administrator rights offer it as an
``ElevationOffer``; the launch dialog (and the main menu's *Show All
Details…*) runs the ones the user picks with an ``ElevationRunner``.
Declining changes nothing: each page keeps its own button.

No widgets here, so it's unit-tested without a display.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Optional

# run(done): start the privileged action; call done(ok) once it worked or failed.
Done = Callable[[bool], None]


@dataclass
class ElevationOffer:
    id: str              # the offering page's ID
    title: str           # what it unlocks, e.g. "Detailed GPU statistics"
    subtitle: str        # where, e.g. "Intel UHD Graphics"
    run: Callable[[Done], None]


def collect_offers(pages: Iterable) -> list[ElevationOffer]:
    """The offers of ``pages`` (``ResourcePage.elevation_offer()``), in order."""
    return [o for o in (p.elevation_offer() for p in pages) if o is not None]


class ElevationRunner:
    """Runs offers **one after another**: each may show a polkit password
    prompt, and two at once would compete. A failure or a cancelled prompt
    doesn't stop the rest. ``finished(results)`` gets ``{offer id: ok}``."""

    def __init__(self, offers: Iterable[ElevationOffer],
                 finished: Optional[Callable[[dict[str, bool]], None]] = None) -> None:
        self.queue = list(offers)
        self.finished = finished
        self.results: dict[str, bool] = {}
        self.current: Optional[ElevationOffer] = None

    @property
    def done(self) -> bool:
        return self.current is None and not self.queue

    def start(self) -> None:
        self._next()

    def _next(self) -> None:
        if not self.queue:
            self.current = None
            if self.finished is not None:
                self.finished(dict(self.results))
            return
        offer = self.current = self.queue.pop(0)
        called = False

        def done(ok: bool) -> None:
            nonlocal called
            if called:                  # an action may report twice; count once
                return
            called = True
            self.results[offer.id] = bool(ok)
            self._next()
        try:
            offer.run(done)
        except Exception:               # a broken offer mustn't stop the rest
            done(False)
