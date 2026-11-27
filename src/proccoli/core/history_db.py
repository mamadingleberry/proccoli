"""The metrics history database: every reading
Proccoli shows, in one SQLite file, summarised as it ages so it never grows
without bound.

Layout (all times are UTC epoch **milliseconds**):

- ``device``: one row per device table: its ID, name and kind, and how far
  its detail has been rolled up into minutes (``minutes_done``) and its
  minutes into hours (``hours_done``).
- ``reading``: what each column of a device table holds: the reading's
  name, unit and fixed-point ``scale`` (value = stored integer / scale).
- ``session``: each run's start and end.
- ``device_info`` (schema 2): what each device was: its description
  and properties (JSON, what its page lists under *Properties*), a row
  from ``time`` on, written only when they change (``record_info``).
- Per device ``d_<id>``: ``time`` (primary key) and one integer column per
  reading, named like the old CSV files' columns (``usage_percent``,
  ``read_bytes_per_second``). A new reading is an ``ALTER TABLE … ADD
  COLUMN``, which SQLite does without rewriting the table.
- Per device ``d_<id>_m`` (minutes) and ``d_<id>_h`` (hours): ``time`` (the
  start of the minute or hour), ``n`` (detail rows summarised), and
  ``<column>_avg``, ``_min``, ``_max``.

Readings are stored as scaled integers (hundredths of a percent and of a
degree, milliwatts, bytes, hertz), which SQLite packs into 1 to 8 bytes.

``HistoryDb`` is the SQL only: no GObject, no timers, no settings. The
``HistoryStore`` (core/history_store.py) decides when to write and tidy.
Both the database and its folder are private (0600 / 0700).
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

MINUTE_MS = 60_000
HOUR_MS = 3_600_000
DAY_MS = 24 * HOUR_MS
SCHEMA_VERSION = "2"          # 2: device_info
CACHE_KIB = 512

# Fixed-point scale per unit: stored integer = round(value * scale).
SCALES = {"%": 100, "°C": 100, "W": 1000, "MHz": 1000, "Hz": 1, "B/s": 1, "B": 1}
DEFAULT_SCALE = 1000

# Unit words in column names (the old CSV files' columns, kept for export).
UNIT_WORDS = {"%": "percent", "B/s": "bytes_per_second", "B": "bytes", "°C": "celsius",
              "W": "watts", "Hz": "hertz", "MHz": "megahertz", "": ""}
LEVELS = ("", "_m", "_h")            # detail, minutes, hours: table suffixes


def scale_for(unit: str) -> int:
    return SCALES.get(unit, DEFAULT_SCALE)


def to_fixed(value: Optional[float], scale: int) -> Optional[int]:
    """``value`` as a scaled integer; None for none, NaN or infinity."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    return int(round(v * scale))


def from_fixed(stored: Optional[float], scale: int) -> Optional[float]:
    return None if stored is None else stored / scale


def _snake(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def column_name(name: str, unit: str) -> str:
    """``("read", "B/s")`` -> ``read_bytes_per_second``."""
    base = _snake(name)
    word = UNIT_WORDS.get(unit, _snake(unit))
    return f"{base}_{word}" if word else base


def unit_of_column(column: str) -> tuple[str, str]:
    """The reverse of ``column_name`` as far as it goes: ``(name, unit)``
    from ``read_bytes_per_second`` (for importing the old statistics files). An
    unknown unit word stays in the name."""
    for unit, word in sorted(UNIT_WORDS.items(), key=lambda kv: -len(kv[1])):
        if word and column.endswith("_" + word):
            return column[: -len(word) - 1], unit
    return column, ""


def table_name(device_id: str) -> str:
    """A safe table name for a device ID (``gpu-0000:02:00.0`` ->
    ``d_gpu_0000_02_00_0``). The old statistics file name of a device
    (``gpu-0000-02-00.0``) gives the same table."""
    return "d_" + (_snake(device_id) or "device")


def q(identifier: str) -> str:
    """A quoted SQL identifier (names come from ``_snake``, but quote anyway)."""
    return '"' + identifier.replace('"', '""') + '"'


def private_file(path: Path) -> None:
    """Create ``path`` (and its folder) private before SQLite opens it."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)


class NewerSchema(Exception):
    """The database was written by a newer Proccoli: don't write to it."""


class HistoryDb:
    """One connection to the history database at ``path``."""

    def __init__(self, path, readonly: bool = False) -> None:
        self.path = Path(path)
        if readonly:
            self.conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True,
                                        isolation_level=None, check_same_thread=False)
        else:
            private_file(self.path)
            self.conn = sqlite3.connect(str(self.path), isolation_level=None)
            # Before any table exists, so the file can shrink later.
            self.conn.execute("PRAGMA auto_vacuum = INCREMENTAL")
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute(f"PRAGMA cache_size = -{CACHE_KIB}")
        self.conn.execute("PRAGMA busy_timeout = 2000")
        self._columns: dict[str, set[str]] = {}       # table -> its reading columns
        self._named: dict[str, tuple] = {}            # table -> (id, name, kind) written
        self._described: dict[str, dict] = {}         # table -> {reading: (column, scale)}
        self._info: dict[str, tuple] = {}             # table -> (description, properties) last
        if not readonly:
            self._check_schema()
            self._create()

    def _check_schema(self) -> None:
        """Refuse to write a schema newer than this code knows (a newer
        Proccoli wrote it, then a downgrade): raises ``NewerSchema``."""
        try:
            row = self.conn.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
        except sqlite3.OperationalError:            # a new file: no tables yet
            return
        if row and row[0].isdigit() and int(row[0]) > int(SCHEMA_VERSION):
            self.conn.close()
            raise NewerSchema(f"schema {row[0]} is newer than {SCHEMA_VERSION}")

    def _create(self) -> None:
        with self.transaction():
            self.conn.execute("CREATE TABLE IF NOT EXISTS meta "
                              "(key TEXT PRIMARY KEY, value TEXT)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS device (tbl TEXT PRIMARY KEY, "
                              "id TEXT, name TEXT, kind TEXT, "
                              "minutes_done INTEGER NOT NULL DEFAULT 0, "
                              "hours_done INTEGER NOT NULL DEFAULT 0)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS reading (tbl TEXT, col TEXT, "
                              "name TEXT, unit TEXT, scale INTEGER, "
                              "PRIMARY KEY (tbl, col)) WITHOUT ROWID")
            self.conn.execute("CREATE TABLE IF NOT EXISTS session "
                              "(start INTEGER PRIMARY KEY, end INTEGER, version TEXT)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS device_info (tbl TEXT, "
                              "time INTEGER, description TEXT, properties TEXT, "
                              "PRIMARY KEY (tbl, time)) WITHOUT ROWID")
            # An older database gains the new tables above; nothing to migrate.
            self.conn.execute("INSERT OR REPLACE INTO meta VALUES ('schema', ?)",
                              (SCHEMA_VERSION,))

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def transaction(self):
        self.conn.execute("BEGIN")
        try:
            yield
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        self.conn.execute("COMMIT")

    # -- meta ------------------------------------------------------------------------

    def meta(self, key: str) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))

    # -- devices and readings -------------------------------------------------------

    def ensure_device(self, device_id: str, name: str = "", kind: str = "",
                      table: Optional[str] = None) -> str:
        """The table for ``device_id`` (created if new); its name and kind
        are updated when given."""
        tbl = table or table_name(device_id)
        if tbl not in self._columns:
            self.conn.execute("INSERT OR IGNORE INTO device (tbl, id, name, kind) "
                              "VALUES (?, ?, ?, ?)", (tbl, device_id, name or device_id, kind))
            self.conn.execute(f"CREATE TABLE IF NOT EXISTS {q(tbl)} "
                              "(time INTEGER PRIMARY KEY)")
            for suffix in LEVELS[1:]:
                self.conn.execute(f"CREATE TABLE IF NOT EXISTS {q(tbl + suffix)} "
                                  "(time INTEGER PRIMARY KEY, n INTEGER)")
            self._columns[tbl] = {r[1] for r in self.conn.execute(
                f"PRAGMA table_info({q(tbl)})")} - {"time"}
        if name and self._named.get(tbl) != (device_id, name, kind):
            self.conn.execute("UPDATE device SET id = ?, name = ?, kind = ? WHERE tbl = ?",
                              (device_id, name, kind, tbl))
            self._named[tbl] = (device_id, name, kind)
        return tbl

    def ensure_columns(self, tbl: str, readings: Mapping[str, str]) -> dict[str, tuple[str, int]]:
        """Columns for ``readings`` (``{name: unit}``), added where new:
        ``{name: (column, scale)}``."""
        known = self._columns[tbl]
        described = self._described.setdefault(tbl, {})
        out = {}
        for name, unit in readings.items():
            col, scale = column_name(name, unit), scale_for(unit)
            if described.get(name) == (col, scale):
                out[name] = (col, scale)
                continue
            if col not in known:
                self.conn.execute(f"ALTER TABLE {q(tbl)} ADD COLUMN {q(col)} INTEGER")
                for suffix in LEVELS[1:]:
                    for part in ("avg", "min", "max"):
                        self.conn.execute(f"ALTER TABLE {q(tbl + suffix)} "
                                          f"ADD COLUMN {q(col + '_' + part)} INTEGER")
                known.add(col)
            self.conn.execute("INSERT OR REPLACE INTO reading VALUES (?, ?, ?, ?, ?)",
                              (tbl, col, name, unit, scale))
            described[name] = out[name] = (col, scale)
        return out

    def record_info(self, tbl: str, time_ms: int, description: str,
                    properties: Mapping[str, str]) -> bool:
        """Note what the device is from ``time_ms`` on, unless that's what
        the last row already says; True when a row was written."""
        props = json.dumps(dict(properties), ensure_ascii=False, sort_keys=True)
        current = (description or "", props)
        if tbl not in self._info:
            row = self.conn.execute("SELECT description, properties FROM device_info "
                                    "WHERE tbl = ? ORDER BY time DESC LIMIT 1", (tbl,)).fetchone()
            self._info[tbl] = tuple(row) if row else None
        if self._info[tbl] == current:
            return False
        self.conn.execute("INSERT OR REPLACE INTO device_info VALUES (?, ?, ?, ?)",
                          (tbl, time_ms, *current))
        self._info[tbl] = current
        return True

    def device_info(self, tbl: str, start_ms: int, end_ms: int) -> list[dict]:
        """What the device was over ``start_ms``..``end_ms``: the row in
        effect at the start (if any), then every change before the end.
        Empty for a database older than schema 2."""
        try:
            before = self.conn.execute(
                "SELECT time, description, properties FROM device_info "
                "WHERE tbl = ? AND time <= ? ORDER BY time DESC LIMIT 1",
                (tbl, start_ms)).fetchall()
            during = self.conn.execute(
                "SELECT time, description, properties FROM device_info "
                "WHERE tbl = ? AND time > ? AND time <= ? ORDER BY time",
                (tbl, start_ms, end_ms)).fetchall()
        except sqlite3.OperationalError:          # no such table
            return []
        return [{"time": r[0], "description": r[1], "properties": json.loads(r[2] or "{}")}
                for r in before + during]

    def devices(self) -> list[dict]:
        rows = self.conn.execute("SELECT tbl, id, name, kind FROM device ORDER BY tbl")
        return [dict(zip(("table", "id", "name", "kind"), r)) for r in rows]

    def readings(self, tbl: str) -> list[dict]:
        """A table's columns in the order they were added."""
        info = {r["col"]: r for r in (
            dict(zip(("col", "name", "unit", "scale"), row)) for row in self.conn.execute(
                "SELECT col, name, unit, scale FROM reading WHERE tbl = ?", (tbl,)))}
        order = [r[1] for r in self.conn.execute(f"PRAGMA table_info({q(tbl)})")]
        return [info[c] for c in order if c in info]

    # -- writing ------------------------------------------------------------------------

    def insert(self, tbl: str, time_ms: int, values: Mapping[str, Optional[int]]) -> None:
        """One detail row (``{column: stored integer}``); a row at the same
        time (a clock set back) is replaced."""
        cols = list(values)
        names = ", ".join(["time"] + [q(c) for c in cols])
        marks = ", ".join("?" * (len(cols) + 1))
        self.conn.execute(f"INSERT OR REPLACE INTO {q(tbl)} ({names}) VALUES ({marks})",
                          [time_ms] + [values[c] for c in cols])

    def start_session(self, start_ms: int, version: str) -> int:
        self.conn.execute("INSERT OR REPLACE INTO session VALUES (?, ?, ?)",
                          (start_ms, start_ms, version))
        return start_ms

    def end_session(self, start_ms: int, end_ms: int) -> None:
        self.conn.execute("UPDATE session SET end = ? WHERE start = ?", (end_ms, start_ms))

    def sessions(self) -> list[tuple[int, int]]:
        return [tuple(r) for r in self.conn.execute(
            "SELECT start, end FROM session ORDER BY start")]

    # -- housekeeping --------------------------------------------------------------------

    def roll_up(self, now_ms: int) -> None:
        """Summarise finished minutes from detail and finished hours from
        minutes. Each level starts where it stopped last time (or earlier,
        if the clock was set back), so it's cheap and idempotent."""
        for tbl, minutes_done, hours_done in self.conn.execute(
                "SELECT tbl, minutes_done, hours_done FROM device").fetchall():
            cols = sorted(self._table_columns(tbl))
            minute_end = now_ms - now_ms % MINUTE_MS
            self._roll(tbl, tbl + "_m", cols, min(minutes_done, minute_end), minute_end,
                       MINUTE_MS, from_detail=True)
            hour_end = now_ms - now_ms % HOUR_MS
            self._roll(tbl + "_m", tbl + "_h", cols, min(hours_done, hour_end), hour_end,
                       HOUR_MS, from_detail=False)
            self.conn.execute("UPDATE device SET minutes_done = ?, hours_done = ? "
                              "WHERE tbl = ?", (minute_end, hour_end, tbl))

    def _table_columns(self, tbl: str) -> set[str]:
        if tbl not in self._columns:
            self._columns[tbl] = {r[1] for r in self.conn.execute(
                f"PRAGMA table_info({q(tbl)})")} - {"time"}
        return self._columns[tbl]

    def _roll(self, source: str, target: str, cols: Sequence[str], start: int, end: int,
              bucket: int, from_detail: bool) -> None:
        if start >= end:
            return
        names, exprs = ["time", "n"], [f"time - time % {bucket} AS b",
                                       "count(*)" if from_detail else "sum(n)"]
        for c in cols:
            names += [q(c + "_avg"), q(c + "_min"), q(c + "_max")]
            if from_detail:
                exprs += [f"CAST(round(avg({q(c)})) AS INTEGER)", f"min({q(c)})", f"max({q(c)})"]
            else:
                avg, weight = q(c + "_avg"), f"CASE WHEN {q(c + '_avg')} IS NULL THEN 0 ELSE n END"
                exprs += [f"CAST(round(sum({avg} * n) * 1.0 / nullif(sum({weight}), 0)) "
                          "AS INTEGER)", f"min({q(c + '_min')})", f"max({q(c + '_max')})"]
        self.conn.execute(f"INSERT OR REPLACE INTO {q(target)} ({', '.join(names)}) "
                          f"SELECT {', '.join(exprs)} FROM {q(source)} "
                          "WHERE time >= ? AND time < ? GROUP BY b", (start, end))

    def expire(self, now_ms: int, detail_ms: int, minutes_ms: int) -> None:
        """Delete detail older than ``detail_ms`` and minutes older than
        ``minutes_ms`` (never what hasn't been summarised yet)."""
        for tbl, minutes_done, hours_done in self.conn.execute(
                "SELECT tbl, minutes_done, hours_done FROM device").fetchall():
            self.conn.execute(f"DELETE FROM {q(tbl)} WHERE time < ?",
                              (min(now_ms - detail_ms, minutes_done),))
            self.conn.execute(f"DELETE FROM {q(tbl + '_m')} WHERE time < ?",
                              (min(now_ms - minutes_ms, hours_done),))

    def size_bytes(self) -> int:
        """The data the database holds (free pages not counted)."""
        pages = self.conn.execute("PRAGMA page_count").fetchone()[0]
        free = self.conn.execute("PRAGMA freelist_count").fetchone()[0]
        size = self.conn.execute("PRAGMA page_size").fetchone()[0]
        return (pages - free) * size

    def vacuum(self) -> None:
        """Give free pages back to the file system."""
        self.conn.execute("PRAGMA incremental_vacuum")

    def checkpoint(self) -> None:
        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def enforce_cap(self, max_bytes: int, now_ms: int, min_detail_ms: int = HOUR_MS) -> bool:
        """Delete the oldest data until the database holds ``max_bytes`` or
        less: hours a month at a time, then minutes a day at a time, then
        detail an hour at a time, never detail newer than
        ``min_detail_ms``. True if anything was deleted."""
        deleted = False
        steps = (("_h", 30 * DAY_MS, None), ("_m", DAY_MS, None),
                 ("", HOUR_MS, now_ms - min_detail_ms))
        for suffix, chunk, floor in steps:
            while self.size_bytes() > max_bytes:
                oldest = self._oldest(suffix)
                if oldest is None or (floor is not None and oldest >= floor):
                    break
                cut = oldest + chunk if floor is None else min(oldest + chunk, floor)
                for tbl in self._tables():
                    self.conn.execute(f"DELETE FROM {q(tbl + suffix)} WHERE time < ?", (cut,))
                deleted = True
        return deleted

    def _tables(self) -> list[str]:
        return [r[0] for r in self.conn.execute("SELECT tbl FROM device")]

    def _oldest(self, suffix: str) -> Optional[int]:
        times = [self.conn.execute(f"SELECT min(time) FROM {q(tbl + suffix)}").fetchone()[0]
                 for tbl in self._tables()]
        times = [t for t in times if t is not None]
        return min(times) if times else None

    # -- reading back -------------------------------------------------------------------

    def rows(self, tbl: str, columns: Iterable[str], start_ms: int, end_ms: int,
             level: str = "") -> list[tuple]:
        """``(time, value, ...)`` rows of a level (``""`` detail, ``"_m"``,
        ``"_h"``) in ``[start_ms, end_ms)``. Summary levels give their
        averages unless ``columns`` name ``_min``/``_max`` themselves."""
        cols = list(columns)
        names = ", ".join(["time"] + [q(c) for c in cols])
        return self.conn.execute(f"SELECT {names} FROM {q(tbl + level)} "
                                 "WHERE time >= ? AND time < ? ORDER BY time",
                                 (start_ms, end_ms)).fetchall()

    def oldest(self, tbl: str, level: str = "") -> Optional[int]:
        return self.conn.execute(f"SELECT min(time) FROM {q(tbl + level)}").fetchone()[0]

    def count(self, tbl: str, level: str = "") -> int:
        return self.conn.execute(f"SELECT count(*) FROM {q(tbl + level)}").fetchone()[0]

    def series(self, tbl: str, columns: Sequence[str], start_ms: int,
               end_ms: int) -> list[tuple]:
        """Rows for a graph: detail where it's kept, minute averages before
        that (``(time, value, ...)``, oldest first)."""
        first = self.oldest(tbl)
        out: list[tuple] = []
        if first is None or start_ms < first:
            out = self.rows(tbl, [c + "_avg" for c in columns], start_ms,
                            end_ms if first is None else min(first, end_ms), "_m")
        return out + self.rows(tbl, columns, start_ms, end_ms)


    def buckets(self, tbl: str, columns: Sequence[str], origin_ms: int, count: int,
                bucket_ms: int) -> dict[int, tuple]:
        """Averages per graph point: ``{i: (avg, ...)}`` for the ``count``
        buckets ``[origin + i·bucket, origin + (i+1)·bucket)``, from detail
        where it's kept and minute averages before that; buckets with no
        rows are left out (gaps). One indexed, grouped query per level,
        so a day of detail is quick."""
        if bucket_ms <= 0 or count <= 0:
            return {}
        end = origin_ms + count * bucket_ms
        first = self.oldest(tbl)
        out: dict[int, tuple] = {}

        def grouped(table: str, cols: Sequence[str], lo: int, hi: int) -> None:
            if lo >= hi:
                return
            exprs = ", ".join(f"avg({q(c)})" for c in cols)
            for row in self.conn.execute(
                    f"SELECT (time - ?) / ? AS i, {exprs} FROM {q(table)} "
                    "WHERE time >= ? AND time < ? GROUP BY i", (origin_ms, bucket_ms, lo, hi)):
                out[int(row[0])] = tuple(row[1:])

        minutes_end = end if first is None else min(first, end)
        grouped(tbl + "_m", [c + "_avg" for c in columns], origin_ms, minutes_end)
        if first is not None and max(origin_ms, first) < end:
            exprs = ", ".join(f"avg({q(c)})" for c in columns)
            detail = {int(row[0]): (row[1], row[2], tuple(row[3:])) for row in self.conn.execute(
                f"SELECT (time - ?) / ? AS i, min(time), max(time), {exprs} FROM {q(tbl)} "
                "WHERE time >= ? AND time < ? GROUP BY i",
                (origin_ms, bucket_ms, max(origin_ms, first), end))}
            out.update(mend_drift(detail, origin_ms, bucket_ms))
        return out


# Readings this close together (in steps) are one run of the recorder even
# when they straddle an empty slot.
DRIFT_TOLERANCE = 1.5


def mend_drift(slots: dict[int, tuple], origin_ms: int, bucket_ms: int) -> dict[int, tuple]:
    """``{i: values}`` from ``{i: (first_ms, last_ms, values)}`` (slot
    ``i`` is ``[origin + i·bucket, origin + (i+1)·bucket)``), with one-slot
    holes filled where the readings either side of the hole are less than
    ``DRIFT_TOLERANCE`` steps apart. A recorder's ticks are never exactly
    one interval apart, so now and then a reading lands in the next slot
    and leaves one empty: that's not a gap. The hole takes the values of
    the neighbor whose reading is nearer to it. A recorder that really
    stopped leaves readings further apart than that, and the gap stays."""
    out = {i: values for i, (_first, _last, values) in slots.items()}
    for i, (_first, last, values) in slots.items():
        after = slots.get(i + 2)
        if i + 1 in slots or after is None or after[0] - last >= DRIFT_TOLERANCE * bucket_ms:
            continue
        hole_start = origin_ms + (i + 1) * bucket_ms
        hole_end = hole_start + bucket_ms
        out[i + 1] = values if hole_start - last <= after[0] - hole_end else after[2]
    return out

def delete_files(path: Path) -> None:
    """Remove the database and its WAL and shared-memory files."""
    for p in (path, path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm")):
        try:
            p.unlink()
        except FileNotFoundError:
            pass


def files_size(path: Path) -> int:
    """Bytes the database takes on disk, with its WAL file."""
    total = 0
    for p in (path, path.with_name(path.name + "-wal")):
        try:
            total += p.stat().st_size
        except OSError:
            pass
    return total
