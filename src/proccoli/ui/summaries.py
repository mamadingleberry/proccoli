"""What a device's sidebar entry and Overview card show, from its monitor
alone: so an entry works before its page is built, which
Lightweight Mode relies on (pages built on first visit). Device pages
answer ``sidebar_summary()`` from here too, so both always agree.
"""

from __future__ import annotations

from typing import Optional

from ..core.units import Base, TemperatureUnit, device_facts, format_rate
from ..devices.base import DeviceKind
from .page import SidebarSummary


def sort_name_for(monitor) -> str:
    """Where a device sorts within its sidebar group (``Monitor.sort_name()``:
    a local monitor knows it, a remote one was told by the collector)."""
    return monitor.sort_name()


def summary_for(monitor, settings) -> Optional[SidebarSummary]:
    """Usage, detail line, chart series and facts of ``monitor``'s entry."""
    snap = monitor.latest
    history = monitor.history
    kind = monitor.info.kind
    base = Base(settings.get("base"))
    temperature = TemperatureUnit(settings.get("temperature-unit"))
    if kind == DeviceKind.NETWORK:
        series = [history.series("rx"), history.series("tx")]      # receive, send
        if snap is None:
            return SidebarSummary(series=series, max_value=None)
        bits = settings.get("network-bits")
        return SidebarSummary(None, f"↓ {format_rate(snap.rx_bps, base, bits)}",
                              f"↑ {format_rate(snap.tx_bps, base, bits)}",
                              series, max_value=None)
    series = [history.series("usage")]
    if snap is None:
        return SidebarSummary(series=series)
    summary = SidebarSummary(snap.usage, snap.usage_text, snap.detail_text, series)
    if kind == DeviceKind.CPU:
        summary.facts = device_facts(getattr(snap, "temperature_c", None), temperature)
    elif kind == DeviceKind.GPU and getattr(snap, "summary", None) is not None:
        s = snap.summary
        summary.facts = device_facts(s.temperature_c, temperature, s.memory_used,
                                     s.memory_total, base)
    return summary
