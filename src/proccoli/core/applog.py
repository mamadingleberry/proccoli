"""The diagnostics log: a size-capped file for debugging.

- ``FileLog`` keeps a rotating log file of Proccoli's own messages, set up
  from the preferences: ``log-level`` (off, error, warning, info, debug;
  debug, i.e. everything, by default) and ``log-max-size`` (KiB). One
  previous file is kept, so the log never takes more than twice that on
  disk. Times are UTC, in ISO 8601 (``2026-11-23T21:41:25.154Z``), so logs
  from different machines and time zones line up.
- ``PerformanceLog`` writes how Proccoli itself is doing every
  ``log-performance-interval`` minutes: its CPU use, memory, threads, and
  how long its slowest refresh took.

The file lives where the XDG spec puts state and logs:
``$XDG_STATE_HOME/proccoli/proccoli-gui.log`` (``~/.local/state/...``).
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional

from .. import WINDOW
from .connections import Connections

LOGGER = "proccoli"          # the package's logger; GTK's own warnings stay out
BACKUPS = 1                 # previous files kept
LEVELS = {"off": None, "error": logging.ERROR, "warning": logging.WARNING,
          "info": logging.INFO, "debug": logging.DEBUG}
FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
DEFAULT_LEVEL = logging.DEBUG    # the schema's default too: record everything


class UtcFormatter(logging.Formatter):
    """``FORMAT`` with UTC times in ISO 8601, to the millisecond:
    ``2026-11-23T21:41:25.154Z``."""

    converter = time.gmtime

    def __init__(self, fmt: str = FORMAT) -> None:
        super().__init__(fmt)

    def formatTime(self, record, datefmt=None) -> str:   # noqa: N802 (logging's name)
        from .units import iso_utc
        return iso_utc(record.created)


def log_path(env: Mapping[str, str] = os.environ, home: Optional[Path] = None) -> Path:
    """``$XDG_STATE_HOME/proccoli/proccoli-gui.log``, defaulting to ~/.local/state."""
    state = env.get("XDG_STATE_HOME") or str((home or Path.home()) / ".local" / "state")
    return Path(state) / "proccoli" / f"{WINDOW}.log"


def disk_budget(max_kib: int) -> int:
    """The most the log can take on disk, in bytes."""
    return max_kib * 1024 * (BACKUPS + 1)


class PrivateRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Log files only the user can read (they can name processes and
    devices): created 0600, including every file a rollover starts."""

    def _open(self):
        fd = os.open(self.baseFilename, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        os.fchmod(fd, 0o600)          # also a file left from an older version
        return os.fdopen(fd, "a", encoding=self.encoding, errors=self.errors)


class FileLog:
    """Keeps a rotating file handler on the ``proccoli`` logger, following
    the preferences live."""

    def __init__(self, settings, path: Path,
                 logger: Optional[logging.Logger] = None) -> None:
        self.settings = settings
        self.path = Path(path)
        self.logger = logger or logging.getLogger(LOGGER)
        self.handler: Optional[logging.Handler] = None
        self.connections = Connections()
        self.connections.watch(settings, ("log-level", "log-max-size"), lambda *_: self.apply())
        self.apply()

    @property
    def level(self) -> Optional[int]:
        return LEVELS.get(self.settings.get("log-level"), DEFAULT_LEVEL)

    def apply(self) -> None:
        self._close()
        level = self.level
        if level is None:
            return
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            handler = PrivateRotatingFileHandler(
                self.path, maxBytes=self.settings.get("log-max-size") * 1024,
                backupCount=BACKUPS, encoding="utf-8")
        except OSError as exc:
            logging.getLogger(__name__).warning("can't write the log %s: %s", self.path, exc)
            return
        handler.setLevel(level)
        handler.setFormatter(UtcFormatter())
        self.handler = handler
        self.logger.addHandler(handler)
        # Let records at the file's level through, even if the console
        # (root logger) shows less.
        if self.logger.getEffectiveLevel() > level or self.logger.level == logging.NOTSET:
            self.logger.setLevel(min(level, logging.getLogger().getEffectiveLevel()))

    def _close(self) -> None:
        if self.handler is not None:
            self.logger.removeHandler(self.handler)
            self.handler.close()
            self.handler = None

    def shutdown(self) -> None:
        self.connections.disconnect_all()
        self._close()


@dataclass
class PerfSample:
    cpu_ticks: int          # utime + stime
    rss_bytes: int
    threads: int


def read_own_stats(sysroot) -> Optional[PerfSample]:
    """Proccoli's own CPU time, memory and threads from /proc/self."""
    stat = sysroot.read_text("/proc/self/stat")
    status = sysroot.read_text("/proc/self/status")
    if not stat or not status:
        return None
    try:
        fields = stat[stat.rindex(")") + 2:].split()
        ticks = int(fields[11]) + int(fields[12])      # utime, stime (fields 14, 15)
    except (ValueError, IndexError):
        return None
    values = {}
    for line in status.splitlines():
        key, _, rest = line.partition(":")
        if key in ("VmRSS", "Threads"):
            values[key] = int(rest.split()[0])
    return PerfSample(ticks, values.get("VmRSS", 0) * 1024, values.get("Threads", 0))


class PerformanceLog:
    """Every ``log-performance-interval`` minutes (0: never), logs Proccoli's
    CPU %, memory, threads, refreshes and its slowest refresh, measured
    around the ticker's ``tick`` (first handler to last)."""

    def __init__(self, sysroot, clk_tck: int, ticker, settings,
                 clock: Callable[[], float] = time.monotonic,
                 logger: Optional[logging.Logger] = None) -> None:
        self.sysroot = sysroot
        self.clk_tck = clk_tck or 100
        self.settings = settings
        self.clock = clock
        self.logger = logger or logging.getLogger(LOGGER + ".performance")
        self.ticks = 0
        self.slowest_s = 0.0
        self._tick_start: Optional[float] = None
        self._last: Optional[tuple[float, PerfSample]] = None
        self._next_report: Optional[float] = None
        self.ticker = ticker
        self.connections = Connections()
        self.connections.connect(ticker, "tick", self._on_tick_start)
        self.connections.add(ticker, ticker.connect_after("tick", self._on_tick_end))

    @property
    def interval_s(self) -> float:
        return self.settings.get("log-performance-interval") * 60.0

    def _on_tick_start(self, *_a) -> None:
        self._tick_start = self.clock()

    def _on_tick_end(self, *_a) -> None:
        now = self.clock()
        if self._tick_start is not None:
            self.slowest_s = max(self.slowest_s, now - self._tick_start)
        self.ticks += 1
        if self.interval_s <= 0:
            return
        if self._next_report is None:
            self._baseline(now)
        elif now >= self._next_report:
            self.report(now)

    def _baseline(self, now: float) -> None:
        sample = read_own_stats(self.sysroot)
        if sample is not None:
            self._last = (now, sample)
        self._next_report = now + self.interval_s

    def report(self, now: Optional[float] = None) -> Optional[str]:
        """Log one line (and return it); start the next period."""
        now = self.clock() if now is None else now
        sample = read_own_stats(self.sysroot)
        line = None
        if sample is not None and self._last is not None and now > self._last[0]:
            then, prev = self._last
            cpu = 100.0 * (sample.cpu_ticks - prev.cpu_ticks) / self.clk_tck / (now - then)
            line = (f"cpu {cpu:.1f} %, memory {sample.rss_bytes / 2 ** 20:.1f} MiB, "
                    f"threads {sample.threads}, refreshes {self.ticks}, "
                    f"slowest refresh {self.slowest_s * 1000:.0f} ms")
            self.logger.info(line)
        if sample is not None:
            self._last = (now, sample)
        self.ticks = 0
        self.slowest_s = 0.0
        self._next_report = now + max(self.interval_s, 60.0)
        return line

    def shutdown(self) -> None:
        self.connections.disconnect_all()
