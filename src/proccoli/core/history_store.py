"""Keeps the metrics history (DESIGN.md §13.2, Idea 2): follows every
device's ``updated`` signal and writes the readings to the history
database (``core/history_db.py``), tidies it as it ages, fills graphs from
it, and imports the statistics files of Milestone 58 once.

- **Writing:** rows are buffered and committed every ``COMMIT_EVERY_S``
  seconds (one transaction), and on quit or when *Keep History* is turned
  off. Each commit also moves the session's end forward, so a crash loses
  at most those seconds.
- **Housekeeping** every ``HOUSEKEEPING_EVERY_S``, so it works without ever
  quitting: roll detail up into minutes and minutes into hours, delete
  detail older than ``history-detail-hours`` and minutes older than
  ``MINUTES_KEPT_DAYS``, keep the whole under ``history-max-size`` MiB, and
  give the space back.
- **Graphs from history:** on a device's first reading of a run, and when
  the graphs' time range or refresh speed changes, its ``History`` is
  filled from the database (``backfill``): one device per idle call.

Both timers run off the readings themselves (no timers of their own), and
the wall clock, the idle scheduler, the path and the old files' folder are
injected, so tests drive it at fixed times in a temporary folder. Errors
are logged, never raised into the main loop: the history is a nice-to-have.
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Callable, Mapping, Optional

from .history import DETAIL_PREFIX
from .history_db import (DAY_MS, HOUR_MS, HistoryDb, column_name, delete_files, files_size,
                         from_fixed, table_name, to_fixed, unit_of_column)
from .ticker import update_interval_ms
from .units import parse_iso_utc

log = logging.getLogger(__name__)

COMMIT_EVERY_S = 10
HOUSEKEEPING_EVERY_S = 600
MINUTES_KEPT_DAYS = 30
MIN_DETAIL_MS = HOUR_MS          # the size cap never cuts detail below this
IMPORT_BATCH = 5000              # rows per transaction when importing old files

ERRORS = (OSError, ValueError, sqlite3.Error)


def state_dir(env: Mapping[str, str] = os.environ, home: Optional[Path] = None) -> Path:
    """``$XDG_STATE_HOME/proccoli``, defaulting to ~/.local/state."""
    state = env.get("XDG_STATE_HOME") or str((home or Path.home()) / ".local" / "state")
    return Path(state) / "proccoli"


def history_path(env: Mapping[str, str] = os.environ, home: Optional[Path] = None) -> Path:
    return state_dir(env, home) / "history.sqlite3"


def old_stats_dir(env: Mapping[str, str] = os.environ, home: Optional[Path] = None) -> Path:
    """Where Milestone 58 kept its statistics files."""
    return state_dir(env, home) / "stats"


def ms(epoch_s: float) -> int:
    return int(round(epoch_s * 1000))


class HistoryStore:
    """Records every device's readings while ``history`` is on."""

    def __init__(self, devices, settings, path: Path, version: str = "",
                 wall_clock: Callable[[], float] = time.time,
                 idle: Optional[Callable] = None, import_dir: Optional[Path] = None) -> None:
        """``idle(callback)`` runs ``callback`` later until it returns False
        (``GLib.idle_add``; None: at once). ``import_dir`` holds M58
        statistics files to import once."""
        self.devices = devices
        self.settings = settings
        self.path = Path(path)
        self.version = version
        self.wall_clock = wall_clock
        self.idle = idle
        self.import_dir = import_dir
        self.db: Optional[HistoryDb] = None
        self.session: Optional[int] = None        # this run's start (UTC ms)
        self._buffer: list[tuple] = []           # (monitor, time_ms, values, units)
        self._last_commit = wall_clock()
        self._last_housekeeping = wall_clock()
        self._offsets: dict[str, float] = {}     # device -> wall minus monitor clock
        self._clock: dict[str, float] = {}       # device -> its clock at the last reading
        self._detail_filled: set = set()         # (device, id(detail history)) filled
        self._backfill_queue: list = []
        self._failed = False
        self._monitor_handlers: dict[str, tuple[object, int]] = {}
        self._handlers = [
            (devices, devices.connect("device-added", lambda _d, m: self._follow(m))),
            (devices, devices.connect("device-removed", lambda _d, i: self._forget(i))),
            (settings, settings.connect_changed("history", lambda *_: self._apply())),
            (settings, settings.connect_changed("history-max-size",
                                                lambda *_: self._tidy_soon())),
            (settings, settings.connect_changed("history-detail-hours",
                                                lambda *_: self._tidy_soon())),
        ]
        for key in ("graph-time-range", "update-interval"):
            self._handlers.append((settings, settings.connect_changed(
                key, lambda *_: self.backfill_all())))
        for monitor in devices.monitors():
            self._follow(monitor)

    @property
    def enabled(self) -> bool:
        return bool(self.settings.get("history"))

    @property
    def max_bytes(self) -> int:
        return self.settings.get("history-max-size") * 1024 * 1024

    @property
    def detail_ms(self) -> int:
        return self.settings.get("history-detail-hours") * HOUR_MS

    # -- following the devices ------------------------------------------------------

    def _follow(self, monitor) -> None:
        handler = monitor.connect("updated", lambda m, snap: self.record(m, snap))
        self._monitor_handlers[monitor.info.id] = (monitor, handler)

    def _forget(self, device_id: str) -> None:
        monitor, handler = self._monitor_handlers.pop(device_id, (None, 0))
        if monitor is not None:
            monitor.disconnect(handler)
        self._offsets.pop(device_id, None)

    # -- the database ------------------------------------------------------------------

    def open(self) -> Optional[HistoryDb]:
        """The database, opened (and the session started) on first use."""
        if self.db is None and not self._failed:
            try:
                self.db = HistoryDb(self.path)
                start = ms(self.wall_clock())
                with self.db.transaction():
                    self.session = self.db.start_session(start, self.version)
                log.info("history: %s", self.path)
            except ERRORS as exc:
                self._fail("can't open the history at %s: %s", self.path, exc)
                return None
            self._start_import()
        return self.db

    def _fail(self, message: str, *args) -> None:
        log.warning(message, *args)
        self._failed = True
        self._buffer = []
        if self.db is not None:
            try:
                self.db.close()
            except ERRORS:
                pass
            self.db = None

    def close(self) -> None:
        """Write out what's buffered, end the session, close the file."""
        if self.db is None:
            return
        self.commit()
        if self.db is None:
            return
        try:
            self.db.checkpoint()
        except ERRORS:
            pass
        self.db.close()
        self.db = None
        self.session = None

    def delete(self) -> None:
        """*Delete History*: everything goes, a new session starts with the
        next reading (if still on)."""
        self._buffer = []
        self._last_commit = self.wall_clock()
        if self.db is not None:
            self.db.close()
            self.db = None
            self.session = None
        delete_files(self.path)
        self._failed = False
        log.info("history deleted")

    def size_on_disk(self) -> int:
        return files_size(self.path)

    # -- recording ------------------------------------------------------------------------

    def record(self, monitor, snapshot) -> None:
        """Buffer one row; commit and tidy when it's time."""
        if not self.enabled or self._failed:
            return
        now = self.wall_clock()
        device_id = monitor.info.id
        first = device_id not in self._offsets
        self._offsets[device_id] = now - snapshot.time
        self._clock[device_id] = snapshot.time
        self._buffer.append((monitor, ms(now), snapshot.stats_values(),
                             dict(snapshot.stats_units())))
        if first:
            self.backfill_soon(monitor)
        else:
            target = monitor.detail_history()      # a Details tab that started since
            if target is not None and (device_id, id(target)) not in self._detail_filled \
                    and monitor not in self._backfill_queue:
                self.backfill_soon(monitor)
        if now - self._last_commit >= COMMIT_EVERY_S:
            self.commit()
        if now - self._last_housekeeping >= HOUSEKEEPING_EVERY_S:
            self.housekeeping()

    def commit(self) -> None:
        """Write the buffered rows in one transaction."""
        self._last_commit = self.wall_clock()
        rows, self._buffer = self._buffer, []
        if not rows or self.open() is None:
            return
        try:
            with self.db.transaction():
                for monitor, time_ms, values, units in rows:
                    info = monitor.info
                    tbl = self.db.ensure_device(info.id, info.name,
                                                getattr(info.kind, "value", str(info.kind)))
                    cols = self.db.ensure_columns(tbl, {n: units.get(n, "") for n in values})
                    self.db.insert(tbl, time_ms, {cols[n][0]: to_fixed(v, cols[n][1])
                                                  for n, v in values.items()})
                self.db.end_session(self.session, ms(self.wall_clock()))
        except ERRORS as exc:
            self._fail("can't write the history: %s", exc)

    def housekeeping(self) -> None:
        """Summarise, expire, keep under the cap, give space back."""
        self._last_housekeeping = self.wall_clock()
        self.commit()
        if self.db is None:
            return
        now = ms(self.wall_clock())
        started = time.monotonic()
        try:
            with self.db.transaction():
                self.db.roll_up(now)
                self.db.expire(now, self.detail_ms, MINUTES_KEPT_DAYS * DAY_MS)
                if self.db.enforce_cap(self.max_bytes, now, MIN_DETAIL_MS):
                    log.info("history: oldest data removed to stay under %d MiB",
                             self.max_bytes // 2**20)
            self.db.vacuum()
        except ERRORS as exc:
            self._fail("can't tidy the history: %s", exc)
            return
        log.debug("history housekeeping took %.0f ms", (time.monotonic() - started) * 1000)

    def _tidy_soon(self) -> None:
        self._last_housekeeping = float("-inf")    # at the next reading

    def _apply(self) -> None:
        if not self.enabled:
            self.close()
            self._offsets.clear()

    def shutdown(self) -> None:
        self.close()
        for device_id in list(self._monitor_handlers):
            self._forget(device_id)
        for source, handler in self._handlers:
            source.disconnect(handler)
        self._handlers = []

    # -- graphs from history -------------------------------------------------------------

    def _later(self, callback: Callable[[], bool]) -> None:
        if self.idle is None:
            while callback():
                pass
        else:
            self.idle(callback)

    def backfill_soon(self, monitor) -> None:
        self._backfill_queue.append(monitor)
        if len(self._backfill_queue) == 1:
            self._later(self._backfill_next)

    def backfill_all(self) -> None:
        """After the range or speed changed: every device, one at a time."""
        self._detail_filled.clear()
        for monitor in self.devices.monitors():
            if monitor.info.id in self._offsets and monitor not in self._backfill_queue:
                self.backfill_soon(monitor)

    def _backfill_next(self) -> bool:
        if not self._backfill_queue:
            return False
        self.backfill(self._backfill_queue.pop(0))
        return bool(self._backfill_queue)

    def backfill(self, monitor) -> int:
        """Fill ``monitor``'s graphs, and its Details tab's if it has one
        running (``monitor.detail_history()``), from the database. Returns
        the points added."""
        device_id = monitor.info.id
        offset = self._offsets.get(device_id)
        if offset is None or not self.enabled or self.open() is None:
            return 0
        tbl = table_name(device_id)
        added = self._fill(monitor.history, tbl, offset, self._clock.get(device_id, 0.0))
        target = monitor.detail_history()
        if target is not None:
            self._detail_filled.add((device_id, id(target)))
            wall = self.wall_clock()
            added += self._fill(target, tbl, 0.0 if target.WALL_TIMES else offset,
                                wall if target.WALL_TIMES else wall - offset, DETAIL_PREFIX)
        if added:
            log.debug("history: %d older points for %s", added, device_id)
        return added

    def _fill(self, history, tbl: str, offset: float, now: float, prefix: str = "") -> int:
        """Put the database's points from before ``history``'s oldest (or
        before ``now``, if it has none yet) in front of it: one per point
        slot (``history.step_s`` apart), each the average of the rows in
        its slot, with gaps where nothing was recorded. ``offset`` turns
        the history's clock into the wall clock."""
        room = history.room()
        if room <= 0:
            return 0
        if not history.times:
            self.commit()                    # this run's first rows, too
            if self.db is None:
                return 0
        step = history.step_s or update_interval_ms(self.settings) / 1000
        oldest = history.times[0] if history.times else now
        slots = [oldest - step * k for k in range(room, 0, -1)]
        cols = {key: column_name(prefix + key, unit) for key, unit in history.keys()}
        try:
            known = {r["col"]: r["scale"] for r in self.db.readings(tbl)}
            wanted = [k for k in cols if cols[k] in known]
            if not wanted:
                return 0
            points = self.db.buckets(tbl, [cols[k] for k in wanted],
                                     ms(slots[0] + offset - step / 2), room,
                                     max(1, ms(step)))
        except ERRORS as exc:
            log.warning("can't read the history of %s: %s", tbl, exc)
            return 0
        if not points:
            return 0
        first = min(points)                  # the graph starts where data does
        values = {}
        for j, key in enumerate(wanted):
            scale = known[cols[key]]
            values[key] = [None if i not in points else from_fixed(points[i][j], scale)
                           for i in range(first, room)]
        return history.backfill(slots[first:], values)

    # -- the statistics files of Milestone 58 ------------------------------------------------

    def _start_import(self) -> None:
        folder = self.import_dir
        if folder is None or not folder.is_dir():
            return
        files = sorted(folder.glob("*.csv.1")) + sorted(folder.glob("*.csv"))
        state = {"rows": 0, "files": list(files)}

        def step() -> bool:
            if self.db is None:
                return False
            if state["files"]:
                path = state["files"].pop(0)
                try:
                    state["rows"] += import_csv(self.db, path)
                except ERRORS as exc:
                    log.warning("can't import %s: %s", path, exc)
                return True
            shutil.rmtree(folder, ignore_errors=True)
            log.info("history: imported %d rows from %d statistics files in %s "
                     "(the folder is removed)", state["rows"], len(files), folder)
            return False

        self._later(step)


def import_csv(db: HistoryDb, path: Path) -> int:
    """One M58 statistics file (``cpu.csv``, ``gpu-0000-02-00.0.csv.1``)
    into its device's detail table; the next housekeeping sums up and
    expires what's old. Returns the rows imported."""
    import csv
    stem = path.name.split(".csv")[0]
    count = [0]
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header or header[0] != "time_utc":
            return 0
        readings = dict(unit_of_column(c) for c in header[1:])
        names = [unit_of_column(c)[0] for c in header[1:]]
        batch: list[list[str]] = []

        def flush() -> None:
            with db.transaction():
                tbl = db.ensure_device(stem, table=table_name(stem))
                cols = db.ensure_columns(tbl, readings)
                for row in batch:
                    try:
                        when = ms(parse_iso_utc(row[0]))
                        values = {cols[n][0]: to_fixed(float(v), cols[n][1]) if v else None
                                  for n, v in zip(names, row[1:])}
                    except (ValueError, IndexError):
                        continue
                    db.insert(tbl, when, values)
                    count[0] += 1

        for row in reader:
            batch.append(row)
            if len(batch) >= IMPORT_BATCH:
                flush()
                batch = []
        if batch:
            flush()
    return count[0]

