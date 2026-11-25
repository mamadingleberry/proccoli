"""Who writes the history.

Exactly one process writes the history database: the one holding an
exclusive lock on ``history.lock`` beside it (``System.try_lock()``, an
``flock`` the kernel frees when the holder exits). Everyone else reads.
``HistoryStore`` takes a ``HistoryLock`` and asks it; the background
collector (``proccoli``) and the window use the same rule, so
whoever starts first writes and the other takes over when it stops.
"""

from __future__ import annotations

from pathlib import Path


def lock_path(history_path) -> Path:
    """The lock file for a history database: beside it."""
    return Path(history_path).with_name("history.lock")


class HistoryLock:
    def __init__(self, system, path) -> None:
        self.system = system
        self.path = Path(path)
        self._handle = None

    @property
    def held(self) -> bool:
        return self._handle is not None

    def acquire(self) -> bool:
        """True when this process holds it (now or already)."""
        if self._handle is None:
            self._handle = self.system.try_lock(self.path)
        return self._handle is not None

    def release(self) -> None:
        if self._handle is not None:
            self.system.release_lock(self._handle)
            self._handle = None
