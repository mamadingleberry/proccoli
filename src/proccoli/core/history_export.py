"""*Export Statistics…* (DESIGN.md §13.2, Idea 2): the running session's
readings, from the history database, as files in a folder the user picks.

``export_session`` writes into a new folder inside the chosen one
(``proccoli-statistics-20261124T101530Z``, never over existing files):

- one CSV file per device (RFC 4180, UTF-8, ``\\r\\n`` line ends):
  ``time_utc`` (ISO 8601 UTC with milliseconds), then ``<reading>_<unit>``
  columns in their real units (``usage_percent``, ``read_bytes_per_second``),
  empty for no reading;
- when the session is longer than the detail kept, the older part as
  ``<device>-minutes.csv`` with ``_avg``/``_min``/``_max`` columns;
- ``export.json``: Proccoli's version, the session's start and end (UTC),
  and each file's device, kind, level and columns with units.

It opens its own read-only connection, so it can run on a worker thread
while the main loop keeps recording. ``progress(done, total)`` is called
after each device.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .. import APP_NAME
from .history_db import HistoryDb, from_fixed
from .units import iso_utc

CHUNK_MS = 3_600_000            # rows read an hour at a time


def format_value(value: Optional[float]) -> str:
    """Plain decimal (no exponent), at most 3 decimals; empty for none."""
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def file_stem(device_id: str) -> str:
    """A safe file name for a device ID (``gpu-0000:02:00.0`` ->
    ``gpu-0000-02-00.0``)."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", device_id).strip(".") or "device"


def folder_name(now_s: float) -> str:
    stamp = iso_utc(now_s)[:19].replace("-", "").replace(":", "")
    return f"{APP_NAME.lower()}-statistics-{stamp}Z"


def new_folder(parent: Path, now_s: float) -> Path:
    """A folder that doesn't exist yet (``… (2)`` if it does)."""
    base = parent / folder_name(now_s)
    path, n = base, 1
    while path.exists():
        n += 1
        path = base.with_name(f"{base.name} ({n})")
    path.mkdir(parents=True)
    return path


@dataclass
class ExportResult:
    folder: Path
    files: list[str] = field(default_factory=list)
    rows: int = 0


def _csv_line(fields) -> str:
    out = io.StringIO()
    csv.writer(out, lineterminator="\r\n").writerow(fields)
    return out.getvalue()


def export_session(db_path: Path, parent: Path, start_ms: int, end_ms: int,
                   version: str = "", now_s: Optional[float] = None,
                   progress: Optional[Callable[[int, int], None]] = None) -> ExportResult:
    """Write the readings from ``start_ms`` to ``end_ms`` (UTC ms) into a
    new folder in ``parent``."""
    import time
    db = HistoryDb(db_path, readonly=True)
    try:
        result = ExportResult(new_folder(Path(parent), time.time() if now_s is None else now_s))
        manifest = {"application": APP_NAME, "version": version,
                    "session": {"start_utc": iso_utc(start_ms / 1000),
                                "end_utc": iso_utc(end_ms / 1000)},
                    "files": []}
        devices = db.devices()
        for done, device in enumerate(devices, 1):
            _export_device(db, device, result, manifest, start_ms, end_ms)
            if progress is not None:
                progress(done, len(devices))
        _write(result.folder / "export.json", json.dumps(manifest, indent=2) + "\n")
        result.files.append("export.json")
        return result
    finally:
        db.close()


def _export_device(db: HistoryDb, device: dict, result: ExportResult, manifest: dict,
                   start_ms: int, end_ms: int) -> None:
    tbl, stem = device["table"], file_stem(device["id"])
    readings = db.readings(tbl)
    if not readings:
        return
    first_detail = db.oldest(tbl)
    # The part of the session the detail no longer holds: minutes.
    minutes_end = end_ms if first_detail is None else min(max(first_detail, start_ms), end_ms)
    if start_ms < minutes_end:
        cols = [f"{r['col']}_{part}" for r in readings for part in ("avg", "min", "max")]
        scales = [r["scale"] for r in readings for _ in range(3)]
        n = _write_level(db, tbl, "_m", result.folder / f"{stem}-minutes.csv", cols, scales,
                         start_ms, minutes_end)
        if n:
            result.rows += n
            result.files.append(f"{stem}-minutes.csv")
            manifest["files"].append(_describe(f"{stem}-minutes.csv", device, "minutes",
                                               readings, ("avg", "min", "max")))
    detail_start = max(start_ms, minutes_end) if first_detail is not None else end_ms
    if detail_start < end_ms:
        n = _write_level(db, tbl, "", result.folder / f"{stem}.csv",
                         [r["col"] for r in readings], [r["scale"] for r in readings],
                         detail_start, end_ms)
        if n:
            result.rows += n
            result.files.append(f"{stem}.csv")
            manifest["files"].append(_describe(f"{stem}.csv", device, "detail", readings))


def _describe(name: str, device: dict, level: str, readings, parts=()) -> dict:
    columns = [{"column": "time_utc", "unit": "ISO 8601 UTC"}]
    for r in readings:
        for col in ([f"{r['col']}_{p}" for p in parts] or [r["col"]]):
            columns.append({"column": col, "reading": r["name"], "unit": r["unit"]})
    return {"file": name, "device": device["id"], "name": device["name"],
            "kind": device["kind"], "level": level, "columns": columns}


def _write_level(db: HistoryDb, tbl: str, level: str, path: Path, cols, scales,
                 start_ms: int, end_ms: int) -> int:
    count = 0
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(_csv_line(["time_utc"] + cols))
        t = start_ms
        while t < end_ms:
            chunk_end = min(t + CHUNK_MS, end_ms)
            for row in db.rows(tbl, cols, t, chunk_end, level):
                f.write(_csv_line([iso_utc(row[0] / 1000)] + [
                    format_value(from_fixed(v, s)) for v, s in zip(row[1:], scales)]))
                count += 1
            t = chunk_end
    if not count:
        path.unlink()
    return count


def _write(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
