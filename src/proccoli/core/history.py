"""Fixed-length time series for graphs.

A ``History`` holds the sample times and one ``Series`` per measured value,
all kept aligned: every ``add()`` appends exactly one entry to ``times`` and
to every series (``None`` where a value is missing), so index ``i`` means
the same moment everywhere. When full, the oldest entries drop off.

Ported from intel_gpu_top_gui's history module, generalised from
intel_gpu_top samples to plain ``{name: value}`` dictionaries.

Two things keep a graph honest about time:

- **Regrouping.** A graph draws its points evenly, ``step_s`` apart.
  When the time range or update interval changes the step, the points
  held are put into the new step's slots by their own times
  (``regroup``), so old points are never drawn at the new spacing.
- **Offline flags.** ``History.offline`` has one flag per point: True
  where the point was filled from the history database for a time when
  Proccoli wasn't running. Every series of a history shares it
  (``Series.offline``), so a ``Graph`` can shade those stretches.
"""

from __future__ import annotations

import csv
import math
from collections import deque
from typing import Iterable, Iterator, Mapping, Optional, Sequence


# Readings of a GPU's Details tab are recorded as "detail/<key>" (history
# follow-ups), so they can fill that tab again.
DETAIL_PREFIX = "detail/"


class Series:
    def __init__(self, name: str, unit: str = "", capacity: int = 60) -> None:
        self.name = name
        self.unit = unit
        self.values: deque[Optional[float]] = deque(maxlen=capacity)
        # The owning history's offline flags (aligned with ``values``), or
        # None for a series outside a history.
        self.offline: Optional[deque[bool]] = None

    def __repr__(self) -> str:
        return f"Series({self.name!r}, {self.unit!r}, {len(self.values)}/{self.capacity})"

    @property
    def capacity(self) -> int:
        return self.values.maxlen or 0

    def latest(self) -> Optional[float]:
        return self.values[-1] if self.values else None

    def peak(self) -> Optional[float]:
        """Largest value currently held (for auto-scaling graphs)."""
        present = [v for v in self.values if v is not None]
        return max(present) if present else None


class Averager:
    """Averages every ``every`` samples into one point (long *Graph Time
    Range*s: ``ticker.history_plan()``). ``push(values)`` returns the
    averages (``{key: mean of the non-None values, or None}``) when a
    point is complete, else None."""

    def __init__(self, every: int = 1) -> None:
        self.every = max(1, every)
        self.reset()

    def reset(self) -> None:
        self.count = 0
        self._sums: dict = {}
        self._counts: dict = {}

    def push(self, values: Mapping) -> Optional[dict]:
        if self.every == 1:
            return dict(values)
        self.count += 1
        for key, v in values.items():
            self._sums.setdefault(key, 0.0)
            self._counts.setdefault(key, 0)
            if v is not None:
                self._sums[key] += v
                self._counts[key] += 1
        if self.count < self.every:
            return None
        out = {k: (self._sums[k] / self._counts[k] if self._counts[k] else None)
               for k in self._sums}
        self.reset()
        return out


def regroup(times: Sequence[float], columns: Sequence[Sequence[Optional[float]]],
            offline: Sequence[bool], step: float, max_points: int
            ) -> tuple[list[float], list[list[Optional[float]]], list[bool]]:
    """Points ``times`` (oldest first), with their ``columns`` and
    ``offline`` flags, put into slots ``step`` apart counted back from the
    newest: each slot the mean of its points' values (None if none had
    one), offline only if all its points were, and empty slots between
    them gaps (None, not offline). At most the newest ``max_points``."""
    if not times or step <= 0:
        return [], [[] for _ in columns], []
    newest = times[-1]
    slots: dict[int, list[int]] = {}
    for i, t in enumerate(times):
        k = max(0, math.floor((newest - t) / step + 0.5))   # halves go back, evenly
        slots.setdefault(k, []).append(i)
    oldest_k = min(max(slots), max_points - 1)
    out_times: list[float] = []
    out_cols: list[list[Optional[float]]] = [[] for _ in columns]
    out_offline: list[bool] = []
    for k in range(oldest_k, -1, -1):
        members = slots.get(k, [])
        out_times.append(newest - k * step)
        out_offline.append(bool(members) and all(offline[i] for i in members))
        for col, out in zip(columns, out_cols):
            present = [col[i] for i in members if col[i] is not None]
            out.append(sum(present) / len(present) if present else None)
    return out_times, out_cols, out_offline


def offline_runs(flags: Iterable[bool]) -> list[tuple[int, int]]:
    """``(first, last)`` index of each run of True flags, oldest first."""
    runs: list[tuple[int, int]] = []
    start = None
    i = -1
    for i, flag in enumerate(flags):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, i))
    return runs


class History:
    """Aligned series of samples (or, with ``every`` > 1, of averages of
    ``every`` samples; ``step_s`` is the time between points)."""

    # Times are the monitors' (monotonic) clock, not the wall clock.
    WALL_TIMES = False

    def __init__(self, max_points: int = 60) -> None:
        if max_points < 2:
            raise ValueError("a history needs at least two points")
        self.max_points = max_points
        self.times: deque[float] = deque(maxlen=max_points)
        self.offline: deque[bool] = deque(maxlen=max_points)
        self._series: dict[str, Series] = {}
        self.step_s: Optional[float] = None
        self._averager = Averager(1)

    @property
    def every(self) -> int:
        return self._averager.every

    def set_plan(self, points: int, every: int = 1, step_s: Optional[float] = None) -> None:
        """Hold ``points`` points of ``every`` samples each (a new
        averaging step drops a half-made point). A new step regroups the
        points held (``regroup``): a longer one averages them into its
        slots; a shorter one drops them, since what's between them is
        gone (the history database fills them in again, if it's on)."""
        old_step = self.step_s
        self.set_max_points(points)
        if max(1, every) != self.every:
            self._averager = Averager(every)
        self.step_s = step_s
        if old_step and step_s and step_s != old_step and self.times:
            if step_s < old_step:
                self.clear()
            else:
                self._regroup(step_s)

    def _regroup(self, step: float) -> None:
        series = list(self._series.values())
        times, columns, offline = regroup(list(self.times), [list(s.values) for s in series],
                                          list(self.offline), step, self.max_points)
        self.times = deque(times, maxlen=self.max_points)
        self.offline = deque(offline, maxlen=self.max_points)
        for s, column in zip(series, columns):
            s.values = deque(column, maxlen=self.max_points)
            s.offline = self.offline

    def keys(self) -> list[tuple[str, str]]:
        """``(name, unit)`` of every series (for ``backfill``)."""
        return [(s.name, s.unit) for s in self._series.values()]

    # -- series ---------------------------------------------------------------

    def define(self, name: str, unit: str = "") -> Series:
        """Create a series up front (so a graph can show it before data
        arrives), or return the existing one."""
        s = self._series.get(name)
        if s is None:
            s = Series(name, unit, self.max_points)
            s.values.extend([None] * len(self.times))  # stay aligned
            s.offline = self.offline
            self._series[name] = s
        elif unit:
            s.unit = unit
        return s

    def series(self, name: str) -> Optional[Series]:
        return self._series.get(name)

    def names(self) -> list[str]:
        return list(self._series)

    def __iter__(self) -> Iterator[Series]:
        return iter(self._series.values())

    def __len__(self) -> int:
        return len(self.times)

    # -- recording --------------------------------------------------------------

    def add(self, now: float, values: Mapping[str, Optional[float]],
            units: Optional[Mapping[str, str]] = None) -> None:
        """Record one sample. Unknown names become new series (back-filled
        with ``None``); known series missing from ``values`` get ``None``."""
        for name in values:
            if name not in self._series:
                self.define(name, (units or {}).get(name, ""))
        point = self._averager.push(values)
        if point is not None:
            self._append(now, point)

    def _append(self, now: float, values: Mapping[str, Optional[float]]) -> None:
        self.times.append(now)
        self.offline.append(False)
        for name, s in self._series.items():
            s.values.append(values.get(name))

    def add_gap(self, now: float) -> None:
        """Record "no data" for every series, so plotted lines break (after
        a pause, or a monitor failing for a while)."""
        self._averager.reset()
        if not self.times:
            return
        self._append(now, {})

    def set_max_points(self, n: int) -> None:
        """Change capacity, keeping the newest entries."""
        if n < 2:
            raise ValueError("a history needs at least two points")
        if n == self.max_points:
            return
        self.max_points = n
        self.times = deque(self.times, maxlen=n)
        self.offline = deque(self.offline, maxlen=n)
        for s in self._series.values():
            s.values = deque(s.values, maxlen=n)
            s.offline = self.offline

    def room(self) -> int:
        """How many older samples would still fit (for ``backfill``)."""
        return self.max_points - len(self.times)

    def backfill(self, times: Sequence[float],
                 values: Mapping[str, Sequence[Optional[float]]],
                 offline: Optional[Sequence[bool]] = None) -> int:
        """Put older samples in front (oldest first; ``values[name][i]`` at
        ``times[i]``): the history of an earlier run, read back from the
        database. Only times before the oldest held, only known
        series (the others get ``None``), and only what fits. ``offline[i]``
        marks a time Proccoli wasn't running. Returns how many were added."""
        oldest = self.times[0] if self.times else float("inf")
        keep = [i for i, t in enumerate(times) if t < oldest][-self.room():] \
            if self.room() > 0 else []
        if not keep:
            return 0
        self.times.extendleft(times[i] for i in reversed(keep))
        self.offline.extendleft(bool(offline[i]) if offline else False for i in reversed(keep))
        for name, s in self._series.items():
            column = values.get(name)
            s.values.extendleft(None if column is None else column[i]
                                for i in reversed(keep))
        return len(keep)

    def clear(self) -> None:
        self._averager.reset()
        self.times.clear()
        self.offline.clear()
        for s in self._series.values():
            s.values.clear()

    # -- export -------------------------------------------------------------------

    def write_csv(self, path: str) -> None:
        series = list(self._series.values())
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["timestamp"] + [
                f"{s.name} ({s.unit})" if s.unit else s.name for s in series])
            for i, ts in enumerate(self.times):
                row = [f"{ts:.3f}"]
                for s in series:
                    v = s.values[i]
                    row.append("" if v is None else f"{v:.3f}")
                w.writerow(row)
