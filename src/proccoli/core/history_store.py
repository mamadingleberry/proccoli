"""Keeps the metrics history: follows every
device's ``updated`` signal and writes the readings to the history
database (``core/history_db.py``), tidies it as it ages, fills graphs from
it, and imports older versions' statistics files once.

- **Writing:** rows are buffered and committed every ``COMMIT_EVERY_S``
  seconds (one transaction), and on quit or when *Keep History* is turned
  off. Each commit also moves the session's end forward, so a crash loses
  at most those seconds, and notes each device's description and
  properties when they've changed (``device_info``).
- **Housekeeping** every ``HOUSEKEEPING_EVERY_S``, so it works without ever
  quitting: roll detail up into minutes and minutes into hours, delete
  detail older than ``history-detail-hours`` and minutes older than
  ``MINUTES_KEPT_DAYS``, keep the whole under ``history-max-size`` MiB, and
  give the space back.
- **Graphs from history:** on a device's first reading of a run its
  ``History`` is filled from the database in front of what it holds
  (``backfill``): one device per idle call. When the graphs' time range
  or update interval changes, the history is emptied and filled again
  completely at the new step, so no point is drawn at a spacing
  it wasn't taken at. Slots outside every recorded session are marked
  offline (``offline_slots``): Proccoli wasn't running then.

**One writer**: with a ``lock`` (``core/history_lock.py``), the
store writes only while it holds it; otherwise it's a *reader*: it opens
the database read-only, still fills graphs from it, records nothing, and
tries the lock again at every commit, so it takes over within
``COMMIT_EVERY_S`` of the writer stopping. The writer notes who it is in
``meta`` ``writer``. Without a lock (tests, older callers) it always
writes, as before. A writer that finds the database deleted (*Delete
History…* from a reader) starts a new one; one that finds a newer schema
never writes.

Both timers run off the readings themselves (no timers of their own), and
the wall clock, the idle scheduler, the path and the old files' folder are
injected, so tests drive it at fixed times in a temporary folder. Errors
are logged, never raised into the main loop: the history is a nice-to-have.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Callable, Mapping, Optional

from .. import WINDOW
from .connections import Connections
from .history import DETAIL_PREFIX
from .history_db import (DAY_MS, HOUR_MS, HistoryDb, NewerSchema, column_name, delete_files,
                         files_size, from_fixed, table_name, to_fixed, unit_of_column)
from .ticker import PLAN_KEYS, update_interval_ms
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
    """Where older versions kept their statistics files."""
    return state_dir(env, home) / "stats"


def ms(epoch_s: float) -> int:
    return int(round(epoch_s * 1000))


def offline_slots(starts_ms: list[int], width_ms: int,
                  sessions: list[tuple[int, int]]) -> list[bool]:
    """For each slot ``[start, start + width)`` (ascending), whether no
    recorded session (``(start, end)`` in ms, ascending) touches it:
    Proccoli wasn't running then. A slot a session only partly covers is
    online. One pass over both lists."""
    out: list[bool] = []
    j = 0
    for start in starts_ms:
        end = start + width_ms
        while j < len(sessions) and sessions[j][1] < start:
            j += 1                       # sessions that ended before this slot
        out.append(not (j < len(sessions) and sessions[j][0] < end))
    return out


def open_run(sessions: list[tuple[int, int]], now_ms: int,
             width_ms: int) -> list[tuple[int, int]]:
    """``sessions`` with the newest one running until ``now_ms`` when it's
    still being recorded: its end, moved forward at each commit, is at most
    ``COMMIT_EVERY_S`` (and a slot) old. Those seconds were recorded, just
    not written yet, so they're never shown as time Proccoli wasn't
    running."""
    if not sessions:
        return sessions
    start, end = sessions[-1]
    if 0 <= now_ms - end <= COMMIT_EVERY_S * 1000 + 2 * width_ms:
        return sessions[:-1] + [(start, now_ms)]
    return sessions


class HistoryStore:
    """Records every device's readings while ``history`` is on."""

    def __init__(self, devices, settings, path: Path, version: str = "",
                 wall_clock: Callable[[], float] = time.time,
                 idle: Optional[Callable] = None, import_dir: Optional[Path] = None,
                 lock=None, program: str = WINDOW, graphs: bool = True,
                 read_only: bool = False) -> None:
        """``idle(callback)`` runs ``callback`` later until it returns False
        (``GLib.idle_add``; None: at once). ``import_dir`` holds older versions'
        statistics files to import once. ``lock`` (a ``HistoryLock``)
        decides whether this store writes; ``program`` is who it says it
        is in ``meta`` ``writer``; ``graphs=False`` (the collector) skips
        filling graphs. ``read_only`` (the window): never
        write, never take over; fill graphs and serve exports only."""
        self.devices = devices
        self.settings = settings
        self.path = Path(path)
        self.version = version
        self.wall_clock = wall_clock
        self.idle = idle
        self.import_dir = import_dir
        self.lock = lock
        self.program = program
        self.graphs = graphs
        self._never_write = read_only            # the window, or a newer schema
        self.db: Optional[HistoryDb] = None
        self.session: Optional[int] = None        # this run's start (UTC ms)
        self._buffer: list[tuple] = []           # (monitor, time_ms, values, units)
        self._last_commit = wall_clock()
        self._last_housekeeping = wall_clock()
        self._offsets: dict[str, float] = {}     # device -> wall minus monitor clock
        self._clock: dict[str, float] = {}       # device -> its clock at the last reading
        self._detail_filled: set = set()         # (device, id(detail history)) filled
        self._refill: set[str] = set()           # devices to empty and fill again
        self._backfill_queue: list = []
        self._failed = False
        self._following: dict[str, Connections] = {}       # per device
        self.connections = Connections()
        self.connections.connect(devices, "device-added", lambda _d, m: self._follow(m))
        self.connections.connect(devices, "device-removed", lambda _d, i: self._forget(i))
        self.connections.watch(settings, "history", lambda *_: self._apply())
        self.connections.watch(settings, ("history-max-size", "history-detail-hours"),
                               lambda *_: self._tidy_soon())
        if graphs:
            self.connections.watch(settings, PLAN_KEYS, lambda *_: self.backfill_all())
        for monitor in devices.monitors():
            self._follow(monitor)

    @property
    def writer(self) -> bool:
        """Whether this store writes (holds the lock, or has none)."""
        return (self.lock is None or self.lock.held) and not self._never_write

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
        following = self._following.setdefault(monitor.info.id, Connections())
        following.connect(monitor, "updated", lambda m, snap: self.record(m, snap))

    def _forget(self, device_id: str) -> None:
        following = self._following.pop(device_id, None)
        if following is not None:
            following.disconnect_all()
        self._offsets.pop(device_id, None)

    # -- the database ------------------------------------------------------------------

    def open(self) -> Optional[HistoryDb]:
        """The database, opened on first use: read-write with a session
        when this store gets the lock, else read-only (a reader)."""
        if self.db is None and not self._failed:
            if self._never_write or (self.lock is not None and not self.lock.acquire()):
                return self._open_reader()
            try:
                self.db = HistoryDb(self.path)
                start = ms(self.wall_clock())
                with self.db.transaction():
                    self.session = self.db.start_session(start, self.version)
                    self.db.set_meta("writer", json.dumps({
                        "program": self.program, "pid": os.getpid(),
                        "version": self.version, "since": start}))
                log.info("history: writing %s", self.path)
            except NewerSchema as exc:
                log.warning("history: %s; reading it only", exc)
                self._never_write = True
                if self.lock is not None:
                    self.lock.release()
                return self._open_reader()
            except ERRORS as exc:
                self._fail("can't open the history at %s: %s", self.path, exc)
                return None
            self._start_import()
        return self.db

    def _open_reader(self) -> Optional[HistoryDb]:
        """Read-only, for graphs and exports; nothing until the writer has
        made the file."""
        if not self.path.exists():
            return None
        try:
            self.db = HistoryDb(self.path, readonly=True)
        except ERRORS as exc:
            log.warning("can't read the history at %s: %s", self.path, exc)
            return None
        self.session = None
        log.info("history: reading %s (another process writes it)", self.path)
        return self.db

    def _take_over(self) -> None:
        """A reader: try the lock; with it, reopen as the writer."""
        if self._never_write or self.lock is None or not self.enabled:
            return
        if self.lock.acquire():
            log.info("history: the writer stopped; writing from now on")
            if self.db is not None:
                self.db.close()
                self.db = None
            self.open()

    def session_start(self) -> Optional[int]:
        """The start of the run being recorded (UTC ms): this store's own
        session, or a reader's view of the writer's (its latest)."""
        if self.session is not None:
            return self.session
        if self.open() is None:
            return None
        try:
            sessions = self.db.sessions()
        except ERRORS:
            return None
        return sessions[-1][0] if sessions else None

    def writer_info(self) -> Optional[dict]:
        """Who writes the history (``meta`` ``writer``), or None."""
        if self.open() is None:
            return None
        try:
            text = self.db.meta("writer")
        except ERRORS:
            return None
        try:
            return json.loads(text) if text else None
        except ValueError:
            return None

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
        """Write out what's buffered, end the session, close the file,
        and let another process write."""
        if self.db is not None:
            self.commit()
        if self.db is not None:
            if self.writer:
                try:
                    self.db.checkpoint()
                except ERRORS:
                    pass
            self.db.close()
            self.db = None
            self.session = None
        if self.lock is not None:
            self.lock.release()

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
        if self.db is None:
            self.open()                          # decides: writer or reader
        if self.writer:
            self._buffer.append((monitor, ms(now), snapshot.stats_values(),
                                 dict(snapshot.stats_units())))
        if self.graphs and first:
            self.backfill_soon(monitor)
        elif self.graphs:
            target = monitor.detail_history()      # a Details tab that started since
            if target is not None and (device_id, id(target)) not in self._detail_filled \
                    and monitor not in self._backfill_queue:
                self.backfill_soon(monitor)
        if now - self._last_commit >= COMMIT_EVERY_S:
            self.commit()
        if now - self._last_housekeeping >= HOUSEKEEPING_EVERY_S:
            self.housekeeping()

    def commit(self) -> None:
        """Write the buffered rows in one transaction (a reader: try to
        take over instead)."""
        self._last_commit = self.wall_clock()
        rows, self._buffer = self._buffer, []
        if not self.writer:
            self._take_over()
            return
        if self.db is not None and not self.path.exists():
            # Deleted by someone else (Delete History… from a reader).
            log.info("history: the file was deleted; starting a new one")
            self.db.close()
            self.db, self.session = None, None
        if not rows or self.open() is None:
            return
        try:
            with self.db.transaction():
                described = set()
                for monitor, time_ms, values, units in rows:
                    info = monitor.info
                    tbl = self.db.ensure_device(info.id, info.name,
                                                getattr(info.kind, "value", str(info.kind)))
                    if tbl not in described:        # what it is, when that changes
                        described.add(tbl)
                        self.db.record_info(tbl, time_ms, info.description,
                                            monitor.described_properties())
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
        if self.db is None or not self.writer:
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
        for device_id in list(self._following):
            self._forget(device_id)
        self.connections.disconnect_all()

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
        """After the range or speed changed: every device, one at a time,
        emptied and filled again at the new step, once whoever records the
        history has written out its last seconds (``devices.flush``)."""
        self.commit()                       # when this process records
        self.devices.flush(self._backfill_all_now)

    def _backfill_all_now(self) -> None:
        self._detail_filled.clear()
        for monitor in self.devices.monitors():
            if monitor.info.id in self._offsets:
                self._refill.add(monitor.info.id)
                if monitor not in self._backfill_queue:
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
        target = monitor.detail_history()
        refill = device_id in self._refill
        if refill:
            # Its points may be from another step: the database
            # has them all, at whatever step is asked for.
            self._refill.discard(device_id)
            monitor.history.clear()
            if target is not None:
                target.clear()
        tbl = table_name(device_id)
        added = self._fill(monitor.history, tbl, offset, self._clock.get(device_id, 0.0),
                           through_now=refill)
        if target is not None:
            self._detail_filled.add((device_id, id(target)))
            wall = self.wall_clock()
            added += self._fill(target, tbl, 0.0 if target.WALL_TIMES else offset,
                                wall if target.WALL_TIMES else wall - offset, DETAIL_PREFIX,
                                through_now=refill)
        if added:
            log.debug("history: %d older points for %s", added, device_id)
        return added

    def _fill(self, history, tbl: str, offset: float, now: float, prefix: str = "",
              through_now: bool = False) -> int:
        """Put the database's points from before ``history``'s oldest (or
        before ``now``, if it has none yet) in front of it: one per point
        slot (``history.step_s`` apart), each the average of the rows in
        its slot, with gaps where nothing was recorded, and offline where
        no session was. ``through_now``: an emptied history's slots end at
        ``now``, since the newest reading is only in the database.
        ``offset`` turns the history's clock into the wall clock."""
        room = history.room()
        if room <= 0:
            return 0
        if not history.times:
            self.commit()                    # this run's first rows, too
            if self.open() is None:          # (a reader opens it read-only)
                return 0
        step = history.step_s or update_interval_ms(self.settings) / 1000
        oldest = history.times[0] if history.times else now + (step if through_now else 0)
        slots = [oldest - step * k for k in range(room, 0, -1)]
        cols = {key: column_name(prefix + key, unit) for key, unit in history.keys()}
        try:
            known = {r["col"]: r["scale"] for r in self.db.readings(tbl)}
            wanted = [k for k in cols if cols[k] in known]
            if not wanted:
                return 0
            origin = ms(slots[0] + offset - step / 2)
            width = max(1, ms(step))
            points = self.db.buckets(tbl, [cols[k] for k in wanted], origin, room, width)
            sessions = open_run(self.db.sessions(), ms(self.wall_clock()), width)
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
        offline = offline_slots([origin + i * width for i in range(first, room)], width,
                                sessions)
        return history.backfill(slots[first:], values, offline)

    # -- older versions' statistics files -------------------------------------------------------

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
    """One old statistics file (``cpu.csv``, ``gpu-0000-02-00.0.csv.1``)
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

