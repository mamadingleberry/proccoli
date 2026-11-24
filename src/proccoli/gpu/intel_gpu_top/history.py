"""Group-aware history of intel_gpu_top samples (ported from intel_gpu_top_gui)."""

from __future__ import annotations

import csv
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable, Optional

# Top-level keys that are not plotted as metric groups.
_SKIP_GROUPS = {"period", "clients", "engines"}


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
        unit = str(data.get("unit", ""))
        series = {}
        for name, v in data.items():
            if name == "unit":
                continue
            fv = to_float(v)
            if fv is not None:
                series[name] = fv
        if series:
            groups[key] = (unit, series)
    return groups


@dataclass
class Series:
    group: str
    name: str
    unit: str
    values: deque  # aligned with History.times; None = no data


@dataclass
class History:
    max_points: int = 600
    times: deque = field(default_factory=deque)
    series: dict[tuple[str, str], Series] = field(default_factory=dict)
    group_order: list[str] = field(default_factory=list)
    latest_sample: Optional[dict] = None

    def __post_init__(self) -> None:
        self.times = deque(maxlen=self.max_points)

    def set_max_points(self, n: int) -> None:
        if n == self.max_points:
            return
        self.max_points = n
        self.times = deque(self.times, maxlen=n)
        for s in self.series.values():
            s.values = deque(s.values, maxlen=n)

    def clear(self) -> None:
        self.times.clear()
        for s in self.series.values():
            s.values.clear()
        self.latest_sample = None

    def add(self, sample: dict, timestamp: Optional[float] = None) -> None:
        ts = time.time() if timestamp is None else timestamp
        groups = flatten_sample(sample)
        self.latest_sample = sample
        self.times.append(ts)
        seen = set()
        for group, (unit, values) in groups.items():
            if group not in self.group_order:
                self.group_order.append(group)
            for name, v in values.items():
                key = (group, name)
                s = self.series.get(key)
                if s is None:
                    # Back-fill so that the deque stays aligned with times.
                    s = Series(group, name, unit, deque(maxlen=self.max_points))
                    s.values.extend([None] * (len(self.times) - 1))
                    self.series[key] = s
                s.unit = unit
                s.values.append(v)
                seen.add(key)
        for key, s in self.series.items():
            if key not in seen:
                s.values.append(None)

    def add_gap(self, timestamp: Optional[float] = None) -> None:
        """Insert an empty sample so that lines break (e.g. after a pause)."""
        if not self.times:
            return
        self.times.append(time.time() if timestamp is None else timestamp)
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
