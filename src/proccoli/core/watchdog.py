"""Stall watchdog for the diagnostics log (DESIGN.md §11, Milestone 44).

A frozen window leaves nothing in a log: the main loop that would write
it is the thing that's stuck. So the main loop beats a heartbeat every
``BEAT_MS`` and a separate thread watches it. When it stops for
``timeout_s``, the thread logs an error with a few samples of every
thread's Python stack, spaced apart so a loop shows its repeating frames.
When the heartbeat comes back, it logs how long the stall lasted.

PyGObject releases the GIL while GTK runs C code, so the thread runs even
when the main thread is stuck inside GTK. Then the main thread's stack
ends at the call into GTK (``app.run``, or one of our virtual functions
GTK keeps calling), which is still the clue that's needed.

Clock, sleeping, stack capture and scheduling are injectable for tests.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
import traceback
from typing import Callable, Optional

BEAT_MS = 250
TIMEOUT_S = 3.0
SAMPLES = 3
SAMPLE_GAP_S = 0.3


def format_stacks(frames: Optional[dict] = None) -> str:
    """Every thread's Python stack, main thread first."""
    frames = frames if frames is not None else sys._current_frames()
    names = {t.ident: t.name for t in threading.enumerate()}
    main = threading.main_thread().ident
    out = []
    for ident in sorted(frames, key=lambda i: i != main):
        out.append(f"Thread {names.get(ident, ident)}:\n"
                   + "".join(traceback.format_stack(frames[ident])))
    return "\n".join(out)


class StallWatchdog:
    def __init__(self, logger: Optional[logging.Logger] = None, timeout_s: float = TIMEOUT_S,
                 clock: Callable[[], float] = time.monotonic,
                 stacks: Callable[[], str] = format_stacks,
                 sleep: Callable[[float], None] = time.sleep,
                 schedule: Optional[Callable] = None) -> None:
        self.logger = logger or logging.getLogger("proccoli.watchdog")
        self.timeout_s = timeout_s
        self.clock = clock
        self.stacks = stacks
        self.sleep = sleep
        self.schedule = schedule        # (ms, callback) -> source id; GLib by default
        self.last_beat = clock()
        self.stalled_since: Optional[float] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._source = 0

    # -- main loop side ---------------------------------------------------------

    def beat(self) -> bool:
        self.last_beat = self.clock()
        return True                     # keep the GLib timeout

    # -- watcher side -------------------------------------------------------------

    def check(self) -> Optional[str]:
        """One look: ``"stalled"`` when a stall starts (and was logged),
        ``"recovered"`` when it ends, else None."""
        now = self.clock()
        age = now - self.last_beat
        if self.stalled_since is None and age >= self.timeout_s:
            self.stalled_since = self.last_beat
            samples = []
            for i in range(SAMPLES):
                if i:
                    self.sleep(SAMPLE_GAP_S)
                samples.append(f"--- sample {i + 1} ---\n{self.stacks()}")
            self.logger.error("main loop stalled for %.1f s; stacks:\n%s", age,
                              "\n".join(samples))
            return "stalled"
        if self.stalled_since is not None and age < self.timeout_s:
            self.logger.warning("main loop responsive again after %.1f s",
                                self.last_beat - self.stalled_since)
            self.stalled_since = None
            return "recovered"
        return None

    def _run(self) -> None:
        while not self._stop.wait(BEAT_MS / 1000):
            self.check()

    def start(self) -> None:
        if self.schedule is None:
            from gi.repository import GLib
            self.schedule = GLib.timeout_add
        self.last_beat = self.clock()
        self._source = self.schedule(BEAT_MS, self.beat)
        self._thread = threading.Thread(target=self._run, name="stall-watchdog", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._source:
            from gi.repository import GLib
            GLib.source_remove(self._source)
            self._source = 0
