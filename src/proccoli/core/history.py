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
from typing import Iterator, Mapping, Optional


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


class History:
    def __init__(self, max_points: int = 60) -> None:
        if max_points < 2:
            raise ValueError("a history needs at least two points")
        self.max_points = max_points
        self.times: deque[float] = deque(maxlen=max_points)
        self._series: dict[str, Series] = {}

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
        self.times.append(now)
        for name, s in self._series.items():
            s.values.append(values.get(name))

    def add_gap(self, now: float) -> None:
        """Record "no data" for every series, so plotted lines break (after
        a pause, or a monitor failing for a while)."""
        if not self.times:
            return
        self.add(now, {})

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

    def clear(self) -> None:
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
