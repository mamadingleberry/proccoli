"""The busiest apps and processes, for the Overview's tables (DESIGN.md
§9.6, Milestone 41). Pure functions, unit-tested without a display.

Ranked by processor use or by memory (``overview-top-by``); ties go to the
other measure, then the name, so rows don't swap places on equal values.
"System Processes" (everything that isn't an app) is left out of the top
apps: it would nearly always be first, and its processes appear in the
top processes anyway.
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Protocol, TypeVar

from .apps import SYSTEM_ID, App
from .model import ProcessInfo

TOP_COUNT = 10


class TopMetric(str, Enum):
    CPU = "cpu"           # settings nicks
    MEMORY = "memory"


class _Ranked(Protocol):
    name: str
    cpu: float
    memory: int


T = TypeVar("T", bound=_Ranked)


def rank_key(item: _Ranked, metric: TopMetric) -> tuple:
    """Sort key, busiest first."""
    if TopMetric(metric) == TopMetric.MEMORY:
        return (-item.memory, -item.cpu, item.name.lower())
    return (-item.cpu, -item.memory, item.name.lower())


def top(items: Iterable[T], metric: TopMetric, count: int = TOP_COUNT) -> list[T]:
    return sorted(items, key=lambda i: rank_key(i, metric))[:max(0, count)]


def top_processes(processes: Iterable[ProcessInfo], metric: TopMetric,
                  count: int = TOP_COUNT) -> list[ProcessInfo]:
    return top(processes, metric, count)


def top_apps(apps: Iterable[App], metric: TopMetric, count: int = TOP_COUNT) -> list[App]:
    return top((a for a in apps if a.id != SYSTEM_ID), metric, count)
