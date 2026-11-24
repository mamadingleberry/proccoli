"""Names of intel_gpu_top's measures in legends (kept from the graph code
ported from intel_gpu_top_gui in Milestone 9). Their numbers are formatted
by ``core.units`` in the user's units, like every other chart (Idea 4).
Pure, so it's unit-tested without a display."""

from __future__ import annotations

DISPLAY_NAMES = {
    "value": "Residency", "count": "Rate", "requested": "Requested",
    "actual": "Actual", "reads": "Reads", "writes": "Writes",
}


def display_name(name: str) -> str:
    """A series' legend name: intel_gpu_top's key, or a friendlier word."""
    return DISPLAY_NAMES.get(name, name)
