"""Fixed-length time series for graphs.

A ``History`` holds the sample times and one ``Series`` per measured value,
all kept aligned: every ``add()`` appends exactly one entry to ``times`` and
to every series (``None`` where a value is missing), so index ``i`` means
the same moment everywhere. When full, the oldest entries drop off.

Ported from intel_gpu_top_gui's history module, generalised from
intel_gpu_top samples to plain ``{name: value}`` dictionaries.
"""

from __future__ import annotations

import csv
from collections import deque
from typing import Iterator, Mapping, Optional, Sequence


# Readings of a GPU's Details tab are recorded as "detail/<key>" (history
# follow-ups), so they can fill that tab again.
DETAIL_PREFIX = "detail/"


class Series:
    def __init__(self, name: str, unit: str = "", capacity: int = 60) -> None:
        self.name = name
        self.unit = unit
        self.values: deque[Optional[float]] = deque(maxlen=capacity)

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
    Range*s: ``ticker.history_plan``). ``push(values)`` returns the
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
        self._series: dict[str, Series] = {}
        self.step_s: Optional[float] = None
        self._averager = Averager(1)

    @property
    def every(self) -> int:
        return self._averager.every

    def set_plan(self, points: int, every: int = 1, step_s: Optional[float] = None) -> None:
        """Hold ``points`` points of ``every`` samples each (a new
        averaging step drops a half-made point)."""
        self.set_max_points(points)
        if max(1, every) != self.every:
            self._averager = Averager(every)
        self.step_s = step_s

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
        for s in self._series.values():
            s.values = deque(s.values, maxlen=n)

    def room(self) -> int:
        """How many older samples would still fit (for ``backfill``)."""
        return self.max_points - len(self.times)

    def backfill(self, times: Sequence[float],
                 values: Mapping[str, Sequence[Optional[float]]]) -> int:
        """Put older samples in front (oldest first; ``values[name][i]`` at
        ``times[i]``): the history of an earlier run, read back from the
        database (Idea 2). Only times before the oldest held, only known
        series (the others get ``None``), and only what fits. Returns how
        many were added."""
        oldest = self.times[0] if self.times else float("inf")
        keep = [i for i, t in enumerate(times) if t < oldest][-self.room():] \
            if self.room() > 0 else []
        if not keep:
            return 0
        self.times.extendleft(times[i] for i in reversed(keep))
        for name, s in self._series.items():
            column = values.get(name)
            s.values.extendleft(None if column is None else column[i]
                                for i in reversed(keep))
        return len(keep)

    def clear(self) -> None:
        self._averager.reset()
        self.times.clear()
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
