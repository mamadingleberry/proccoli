"""Running statistics files (DESIGN.md §11, Milestone 58): every reading
Proccoli shows, kept on disk, size-capped.

One CSV file per device in ``$XDG_STATE_HOME/proccoli/stats/``
(``~/.local/state/proccoli/stats/cpu.csv``, ``gpu-0000-02-00.0.csv`` …),
following common standards:

- RFC 4180 CSV, UTF-8, one header row; ``\\r\\n`` line ends as the RFC says.
- ``time_utc`` first: ISO 8601 in UTC with milliseconds
  (``2026-11-24T04:19:54.594Z``).
- Then one column per reading, snake case with its unit spelled out
  (``usage_percent``, ``read_bytes_per_second``, ``temperature_celsius``):
  SI units, bytes for sizes; an empty field for "no reading".
- Each file is capped at ``stats-log-max-size`` KiB; when full it becomes
  ``<name>.csv.1`` (replacing the older one) and a new file starts, so a
  device never takes more than twice the cap. A device whose columns change
  (its per-CPU readings appear after the first sample) also starts a new
  file, so every file has one valid header.
- Files are private (0600) in a private folder (0700), like the log.

Recording follows the monitors' ``updated`` signal (one row per refresh
and device) and the settings live: ``stats-log`` turns it on or off,
``stats-log-max-size`` sets the cap. Rows are buffered and flushed every
``FLUSH_EVERY`` rows per file, and on stop. The wall clock and the folder
are injected, so tests write to a temporary folder at fixed times.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import re
import time
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence

from .units import iso_utc

log = logging.getLogger(__name__)

BACKUPS = 1          # older files kept per device
FLUSH_EVERY = 10     # rows buffered per file before they're written out

UNIT_WORDS = {"%": "percent", "B/s": "bytes_per_second", "B": "bytes", "°C": "celsius",
              "W": "watts", "Hz": "hertz", "MHz": "megahertz", "": ""}


def stats_dir(env: Mapping[str, str] = os.environ, home: Optional[Path] = None) -> Path:
    """``$XDG_STATE_HOME/proccoli/stats``, defaulting to ~/.local/state."""
    state = env.get("XDG_STATE_HOME") or str((home or Path.home()) / ".local" / "state")
    return Path(state) / "proccoli" / "stats"


def column_name(name: str, unit: str) -> str:
    """``("read", "B/s")`` -> ``read_bytes_per_second``."""
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    word = UNIT_WORDS.get(unit, re.sub(r"[^a-z0-9]+", "_", unit.lower()).strip("_"))
    return f"{base}_{word}" if word else base


def file_name(device_id: str) -> str:
    """A safe file name for a device ID (``gpu-0000:02:00.0`` ->
    ``gpu-0000-02-00.0.csv``)."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", device_id) + ".csv"


def format_value(value: Optional[float]) -> str:
    """Plain decimal (no exponent), at most 3 decimals; empty for none."""
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def csv_line(fields: Sequence[str]) -> str:
    out = io.StringIO()
    csv.writer(out, lineterminator="\r\n").writerow(fields)
    return out.getvalue()


class RotatingCsv:
    """One device's file: a header, then rows; rolls over by size or when
    the header changes."""

    def __init__(self, path: Path, max_bytes: int) -> None:
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.header: Optional[list[str]] = None
        self._pending: list[str] = []
        self._size = 0

    def write(self, header: list[str], row: list[str]) -> None:
        line = csv_line(row)
        if self.header is None:
            self._adopt(header)
        if header != self.header:
            self.flush()
            self._roll(header)
        elif self._size + len(line.encode()) > self.max_bytes:
            self.flush()
            self._roll(header)
        self._pending.append(line)
        self._size += len(line.encode())
        if len(self._pending) >= FLUSH_EVERY:
            self.flush()

    def _adopt(self, header: list[str]) -> None:
        """Continue the file from an earlier run if its header matches,
        else start a new one."""
        existing = self._read_header()
        if existing == header and self.path.stat().st_size < self.max_bytes:
            self.header = header
            self._size = self.path.stat().st_size
        else:
            self._roll(header, keep_old=existing is not None)

    def _read_header(self) -> Optional[list[str]]:
        try:
            with open(self.path, newline="", encoding="utf-8") as f:
                return next(csv.reader(f), None)
        except OSError:
            return None

    def _roll(self, header: list[str], keep_old: bool = True) -> None:
        if keep_old and self.path.exists():
            os.replace(self.path, self.path.with_name(self.path.name + ".1"))
        self.header = header
        text = csv_line(header)
        self._write_text(text, truncate=True)
        self._size = len(text.encode())

    def flush(self) -> None:
        if self._pending:
            self._write_text("".join(self._pending))
            self._pending = []

    def _write_text(self, text: str, truncate: bool = False) -> None:
        flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if truncate else os.O_APPEND)
        fd = os.open(self.path, flags, 0o600)
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, text.encode())
        finally:
            os.close(fd)


class StatsLog:
    """Records every device's readings while ``stats-log`` is on."""

    def __init__(self, devices, settings, directory: Path,
                 wall_clock: Callable[[], float] = time.time) -> None:
        self.devices = devices
        self.settings = settings
        self.directory = Path(directory)
        self.wall_clock = wall_clock
        self.files: dict[str, RotatingCsv] = {}
        self._monitor_handlers: dict[str, tuple[object, int]] = {}
        self._handlers = [
            (devices, devices.connect("device-added", lambda _d, m: self._follow(m))),
            (devices, devices.connect("device-removed", lambda _d, i: self._forget(i))),
            (settings, settings.connect_changed("stats-log", lambda *_: self._apply())),
            (settings, settings.connect_changed("stats-log-max-size",
                                                lambda *_: self._apply_size())),
        ]
        for monitor in devices.monitors():
            self._follow(monitor)

    @property
    def enabled(self) -> bool:
        return bool(self.settings.get("stats-log"))

    @property
    def max_bytes(self) -> int:
        return self.settings.get("stats-log-max-size") * 1024

    def _follow(self, monitor) -> None:
        handler = monitor.connect("updated", lambda m, snap: self.record(m.info.id, snap))
        self._monitor_handlers[monitor.info.id] = (monitor, handler)

    def _forget(self, device_id: str) -> None:
        monitor, handler = self._monitor_handlers.pop(device_id, (None, 0))
        if monitor is not None:
            monitor.disconnect(handler)
        f = self.files.pop(device_id, None)
        if f is not None:
            f.flush()

    def record(self, device_id: str, snapshot) -> None:
        """One row: the time, then every reading of ``snapshot``."""
        if not self.enabled:
            return
        values, units = snapshot.stats_values(), snapshot.stats_units()
        names = list(values)
        header = ["time_utc"] + [column_name(n, units.get(n, "")) for n in names]
        row = [iso_utc(self.wall_clock())] + [format_value(values[n]) for n in names]
        try:
            self._file(device_id).write(header, row)
        except OSError as exc:
            log.warning("can't write statistics for %s: %s", device_id, exc)

    def _file(self, device_id: str) -> RotatingCsv:
        f = self.files.get(device_id)
        if f is None:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(self.directory, 0o700)
            f = RotatingCsv(self.directory / file_name(device_id), self.max_bytes)
            self.files[device_id] = f
        return f

    def _apply(self) -> None:
        if not self.enabled:
            self.flush()

    def _apply_size(self) -> None:
        for f in self.files.values():
            f.max_bytes = self.max_bytes

    def flush(self) -> None:
        for f in self.files.values():
            try:
                f.flush()
            except OSError as exc:
                log.warning("can't write statistics to %s: %s", f.path, exc)

    def shutdown(self) -> None:
        self.flush()
        for device_id in list(self._monitor_handlers):
            self._forget(device_id)
        for source, handler in self._handlers:
            source.disconnect(handler)
        self._handlers = []
