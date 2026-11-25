"""Group-aware history of intel_gpu_top samples (ported from intel_gpu_top_gui)."""

from __future__ import annotations

import csv
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable, Optional

from ...core.history import Averager, regroup
from ...core.history import Series as CoreSeries

# Top-level keys that are not plotted as metric groups.
_SKIP_GROUPS = {"period", "clients", "engines"}

# intel_gpu_top's units -> (factor, base unit): readings are kept in base
# units, so charts format them in the user's units like every other (Idea 4).
BASE_UNITS = {"MiB/s": (1024.0 * 1024.0, "B/s"), "MHz": (1e6, "Hz")}


def to_base_unit(unit: str, value: float) -> tuple[str, float]:
    factor, base = BASE_UNITS.get(unit, (1.0, unit))
    return base, value * factor


def to_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def flatten_sample(sample: dict) -> dict[str, tuple[str, dict[str, float]]]:
    """Return ``{group: (unit, {series_name: value})}`` for one sample.

    ``engines`` becomes the group ``"engines"`` with one series per engine
    (its ``busy`` value).  Every other top-level object with numeric members
    (frequency, power, rc6, interrupts, imc-bandwidth, and whatever future
    versions of intel_gpu_top add) becomes a group of its own.
    """
    groups: dict[str, tuple[str, dict[str, float]]] = {}

    engines = sample.get("engines")
    if isinstance(engines, dict):
        series = {}
        for name, data in engines.items():
            if isinstance(data, dict):
                v = to_float(data.get("busy"))
                if v is not None:
                    series[name] = v
        if series:
            groups["engines"] = ("%", series)

    for key, data in sample.items():
        if key in _SKIP_GROUPS or not isinstance(data, dict):
            continue
        raw_unit = str(data.get("unit", ""))
        unit = to_base_unit(raw_unit, 0.0)[0]
        series = {}
        for name, v in data.items():
            if name == "unit":
                continue
            fv = to_float(v)
            if fv is not None:
                series[name] = to_base_unit(raw_unit, fv)[1]
        if series:
            groups[key] = (unit, series)
    return groups


class Series(CoreSeries):
    """The shared graph series (``core.history.Series``: what ``Graph``
    draws) with the metric group it belongs to. Values are aligned with
    ``History.times``; None = no data."""

    def __init__(self, group: str, name: str, unit: str, capacity: int) -> None:
        super().__init__(name, unit, capacity)
        self.group = group


@dataclass
class History:
    """Every series of every group, aligned with ``times`` (wall-clock
    seconds). With ``set_plan(points, every, step_s)`` each point averages
    ``every`` samples (long *Graph Time Range*s). It can be filled from the
    history database (``room``, ``keys``, ``backfill``: series keys are
    ``"group/name"``)."""

    max_points: int = 600
    times: deque = field(default_factory=deque)
    offline: deque = field(default_factory=deque)
    series: dict[tuple[str, str], Series] = field(default_factory=dict)
    group_order: list[str] = field(default_factory=list)
    latest_sample: Optional[dict] = None
    step_s: Optional[float] = None

    WALL_TIMES = True

    def __post_init__(self) -> None:
        self.times = deque(maxlen=self.max_points)
        self.offline = deque(maxlen=self.max_points)
        self._averager = Averager(1)
        self._units: dict[tuple[str, str], str] = {}

    def set_plan(self, points: int, every: int = 1, step_s: Optional[float] = None) -> None:
        """As ``core.history.History.set_plan``: a new step regroups the
        points held (a longer one) or drops them (a shorter one)."""
        old_step = self.step_s
        self.set_max_points(points)
        if max(1, every) != self._averager.every:
            self._averager = Averager(every)
        self.step_s = step_s
        if old_step and step_s and step_s != old_step and self.times:
            if step_s < old_step:
                self.clear()
            else:
                self._regroup(step_s)

    def _regroup(self, step: float) -> None:
        series = list(self.series.values())
        times, columns, offline = regroup(list(self.times), [list(s.values) for s in series],
                                          list(self.offline), step, self.max_points)
        self.times = deque(times, maxlen=self.max_points)
        self.offline = deque(offline, maxlen=self.max_points)
        for s, column in zip(series, columns):
            s.values = deque(column, maxlen=self.max_points)
            s.offline = self.offline

    def room(self) -> int:
        return self.max_points - len(self.times)

    def keys(self) -> list[tuple[str, str]]:
        return [(f"{g}/{n}", s.unit) for (g, n), s in self.series.items()]

    def readings(self) -> tuple[dict, dict]:
        """The latest sample as ``({"group/name": value}, {key: unit})``."""
        if self.latest_sample is None:
            return {}, {}
        values, units = {}, {}
        for group, (unit, items) in flatten_sample(self.latest_sample).items():
            for name, v in items.items():
                values[f"{group}/{name}"] = v
                units[f"{group}/{name}"] = unit
        return values, units

    def backfill(self, times, values, offline=None) -> int:
        """Older points in front (as ``core.history.History.backfill``)."""
        oldest = self.times[0] if self.times else float("inf")
        room = self.room()
        keep = [i for i, t in enumerate(times) if t < oldest][-room:] if room > 0 else []
        if not keep:
            return 0
        self.times.extendleft(times[i] for i in reversed(keep))
        self.offline.extendleft(bool(offline[i]) if offline else False for i in reversed(keep))
        for (g, n), s in self.series.items():
            column = values.get(f"{g}/{n}")
            s.values.extendleft(None if column is None else column[i] for i in reversed(keep))
        return len(keep)

    def set_max_points(self, n: int) -> None:
        if n == self.max_points:
            return
        self.max_points = n
        self.times = deque(self.times, maxlen=n)
        self.offline = deque(self.offline, maxlen=n)
        for s in self.series.values():
            s.values = deque(s.values, maxlen=n)
            s.offline = self.offline

    def clear(self) -> None:
        self._averager.reset()
        self.times.clear()
        self.offline.clear()
        for s in self.series.values():
            s.values.clear()
        self.latest_sample = None

    def add(self, sample: dict, timestamp: Optional[float] = None) -> None:
        ts = time.time() if timestamp is None else timestamp
        groups = flatten_sample(sample)
        self.latest_sample = sample
        flat = {}
        for group, (unit, values) in groups.items():
            if group not in self.group_order:
                self.group_order.append(group)
            for name, v in values.items():
                key = (group, name)
                if key not in self.series:
                    # Back-fill so that the deque stays aligned with times.
                    s = self.series[key] = Series(group, name, unit, self.max_points)
                    s.values.extend([None] * len(self.times))
                    s.offline = self.offline
                self.series[key].unit = unit
                flat[key] = v
        point = self._averager.push(flat)
        if point is None:
            return
        self.times.append(ts)
        self.offline.append(False)
        for key, s in self.series.items():
            s.values.append(point.get(key))

    def add_gap(self, timestamp: Optional[float] = None) -> None:
        """Insert an empty sample so that lines break (e.g. after a pause)."""
        self._averager.reset()
        if not self.times:
            return
        self.times.append(time.time() if timestamp is None else timestamp)
        self.offline.append(False)
        for s in self.series.values():
            s.values.append(None)

    def group_series(self, group: str) -> list[Series]:
        return [s for (g, _), s in self.series.items() if g == group]

    def write_csv(self, path: str) -> None:
        keys = list(self.series.keys())
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(
                ["timestamp"]
                + [f"{g}/{n} ({self.series[(g, n)].unit})" for g, n in keys]
            )
            cols: list[Iterable] = [self.series[k].values for k in keys]
            for i, ts in enumerate(self.times):
                row = [f"{ts:.3f}"]
                for c in cols:
                    v = c[i] if i < len(c) else None
                    row.append("" if v is None else f"{v:.3f}")
                w.writerow(row)
