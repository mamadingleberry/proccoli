"""Measures the history database on this machine.

Reads every device once for real (to get this machine's readings), then
simulates an hour at 1 s per refresh into a temporary database, with
values wandering the way real ones do, and reports:

- bytes per second, per day and per year of detail;
- what an hour of minutes and of hours adds;
- how long a commit (10 rows per device), a housekeeping run and reading
  back the last 10 minutes of three devices take.

    PYTHONPATH=src python3 tests/ui/history_size.py [--hours 1]
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from proccoli.context import build_context  # noqa: E402
from proccoli.core.history_db import HOUR_MS, MINUTE_MS, HistoryDb, to_fixed  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402


def real_readings():
    """Every device's readings and units, sampled for real."""
    ctx = build_context(Settings.for_tests(), connection_name=None)
    ctx.devices.start()
    for _ in range(3):                         # delta-based readings need two samples
        ctx.devices.refresh(time.monotonic())
        time.sleep(1.0)
    out = []
    for m in ctx.devices.monitors():
        if m.latest is not None:
            out.append((m.info, m.latest.stats_values(), dict(m.latest.stats_units())))
    ctx.devices.stop()
    return out


def wander(value, rnd):
    if value is None:
        return None
    return max(0.0, value * (1 + rnd.gauss(0, 0.02)) + rnd.gauss(0, 0.5))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=1.0)
    args = parser.parse_args()
    devices = real_readings()
    readings = sum(len(v) for _, v, _ in devices)
    print(f"{len(devices)} devices, {readings} readings per refresh")
    rnd = random.Random(1)
    seconds = int(args.hours * 3600)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "history.sqlite3"
        db = HistoryDb(path)
        tables = {}
        with db.transaction():
            for info, values, units in devices:
                tbl = db.ensure_device(info.id, info.name, info.kind.value)
                tables[info.id] = (tbl, db.ensure_columns(tbl, {n: units.get(n, "")
                                                                for n in values}))
        state = {info.id: dict(values) for info, values, _ in devices}
        start = 1_795_000_000_000
        commits = []
        for s in range(0, seconds, 10):
            began = time.perf_counter()
            with db.transaction():
                for k in range(10):
                    for info, _v, _u in devices:
                        tbl, cols = tables[info.id]
                        vals = state[info.id]
                        for n in vals:
                            vals[n] = wander(vals[n], rnd)
                        db.insert(tbl, start + (s + k) * 1000,
                                  {cols[n][0]: to_fixed(v, cols[n][1]) for n, v in vals.items()})
            commits.append(time.perf_counter() - began)
        db.checkpoint()
        detail = db.size_bytes()
        began = time.perf_counter()
        with db.transaction():
            db.roll_up(start + seconds * 1000 + HOUR_MS)
        housekeeping = time.perf_counter() - began
        with_summaries = db.size_bytes()
        began = time.perf_counter()
        end = start + seconds * 1000
        for info, values, _ in devices[:3]:
            tbl, cols = tables[info.id]
            db.series(tbl, [c for c, _s in cols.values()], end - 10 * MINUTE_MS, end)
        read_back = time.perf_counter() - began
        db.close()
    per_s = detail / seconds
    summaries = (with_summaries - detail) / args.hours
    print(f"detail:     {per_s:.0f} bytes/s, {per_s * 86400 / 2**20:.1f} MiB/day, "
          f"{per_s * 86400 * 365 / 2**30:.1f} GiB/year if all kept")
    print(f"summaries:  {summaries / 1024:.1f} KiB per hour of minutes and hours "
          f"({summaries * 24 / 2**20:.2f} MiB/day)")
    print(f"commit:     {sum(commits) / len(commits) * 1000:.1f} ms per 10 s")
    print(f"roll-up:    {housekeeping * 1000:.0f} ms for {args.hours:g} h")
    print(f"read back:  {read_back * 1000:.1f} ms for 10 minutes of 3 devices")
    hours_per_day = summaries * 24 / 61          # one hour row per 60 minute rows
    print(f"steady state (24 h detail + 30 days of minutes): about "
          f"{(per_s * 86400 + summaries * 24 * 30) / 2**20:.0f} MiB, plus about "
          f"{hours_per_day * 365 / 2**20:.0f} MiB of hours a year")
    return 0


if __name__ == "__main__":
    sys.exit(main())
