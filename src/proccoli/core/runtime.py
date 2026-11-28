"""Diagnostics that both programs start the same way: the console log, the
log file, the stall watchdog and a hook that logs uncaught exceptions.

The window (``app.py``) and the recorder (``metrics.py``) each used to set
these up themselves, and only the window had the watchdog. ``Runtime``
gives the recorder the same diagnostics: a stuck main loop in the
recorder is logged with its stacks, like the window's.

Everything is injectable (the file log, the watchdog, ``sys``), so tests
start and stop it without touching the real log or the real hook.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Callable, Optional

CONSOLE_FORMAT = "%(levelname)s %(name)s: %(message)s"

log = logging.getLogger(__name__)


def console_logging(level: int, configure: Callable = logging.basicConfig) -> None:
    """Log to stderr at ``level`` (the journal, under systemd). stderr keeps
    that level even when the log file records more."""
    configure(level=level, format=CONSOLE_FORMAT)
    for handler in logging.getLogger().handlers:
        handler.setLevel(level)


class Runtime:
    """The log file, the stall watchdog and the exception hook, for one
    program's lifetime: ``start()`` once it has its settings, ``shutdown()``
    as it ends."""

    def __init__(self, settings, path: Path, file_log_factory=None,
                 watchdog_factory=None, system_module=sys) -> None:
        self.settings = settings
        self.path = Path(path)
        self._file_log_factory = file_log_factory
        self._watchdog_factory = watchdog_factory
        self._sys = system_module
        self.file_log = None
        self.watchdog = None
        self._previous_hook = None

    def start(self) -> "Runtime":
        if self._file_log_factory is None:
            from .applog import FileLog
            self._file_log_factory = FileLog
        if self._watchdog_factory is None:
            from .watchdog import StallWatchdog
            self._watchdog_factory = StallWatchdog
        self.file_log = self._file_log_factory(self.settings, self.path)
        self.watchdog = self._watchdog_factory()       # logs stalls with stacks
        self.watchdog.start()
        self._previous_hook = self._sys.excepthook
        self._sys.excepthook = self._log_uncaught
        return self

    def _log_uncaught(self, kind, value, tb) -> None:
        """An exception nothing caught: in the log file too, then as before."""
        if not issubclass(kind, KeyboardInterrupt):
            log.critical("uncaught exception", exc_info=(kind, value, tb))
        if self._previous_hook is not None:
            self._previous_hook(kind, value, tb)

    def shutdown(self) -> None:
        if self.watchdog is not None:
            self.watchdog.stop()
            self.watchdog = None
        if self._previous_hook is not None:
            self._sys.excepthook = self._previous_hook
            self._previous_hook = None
        if self.file_log is not None:
            self.file_log.shutdown()
            self.file_log = None
