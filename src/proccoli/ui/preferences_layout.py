"""Where each preference goes: the Preferences pages, their groups and the
rows in each, in order.

Display-free, so a test can check that every setting is in Preferences
exactly once, or is set somewhere else on purpose. A row is either a
settings key or one of the ``SPECIAL`` items: rows built from a service
(the history store, the background unit, the GPUs, the sidebar) or that
hold several keys at once. Within a page, actions and status rows sit in
their own group at the end, so a page reads as settings first.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Group:
    id: str
    title: str
    items: tuple[str, ...]
    description: str = ""


@dataclass(frozen=True)
class Page:
    id: str
    title: str
    icon: str
    groups: tuple[Group, ...]


APP_COLUMNS = [("memory", "Memory"), ("cpu", "Processor"), ("drive-read-speed", "Drive Read"),
               ("drive-read-total", "Drive Read Total"), ("drive-write-speed", "Drive Write"),
               ("drive-write-total", "Drive Write Total"), ("gpu", "GPU"),
               ("gpu-memory", "Video Memory"), ("encoder", "Video Encoder"),
               ("decoder", "Video Decoder"), ("swap", "Swap"),
               ("combined-memory", "Combined Memory")]
PROCESS_COLUMNS = [("id", "Process ID"), ("user", "User")] + APP_COLUMNS + [
    ("total-cpu-time", "Total CPU Time"), ("user-cpu-time", "User CPU Time"),
    ("system-cpu-time", "System CPU Time"), ("priority", "Priority"),
    ("commandline", "Commandline")]

# Rows that aren't one settings key, and the keys each one sets.
SPECIAL: dict[str, tuple[str, ...]] = {
    "custom-range": ("graph-time-range-custom",),        # shown with Custom…
    "sidebar-entries": ("sidebar-order", "sidebar-minimized", "sidebar-hidden-fields",
                        "sidebar-graph-types"),
    "apps-columns": tuple(f"apps-show-{k}" for k, _ in APP_COLUMNS),
    "processes-columns": tuple(f"processes-show-{k}" for k, _ in PROCESS_COLUMNS),
    "background": (),            # Record in the Background, Start at Boot (systemd)
    "recording": (),             # who records, since when
    "history-size": (),          # Size on Disk, Delete History…
    "export": (),                # Export…
    "gpu-sources": ("gpu-details-disabled",),            # a switch per GPU
    "window-switching": (),      # the GNOME Shell extension
    "log-file": (),              # Open Folder
}

# Settings set somewhere other than Preferences, and where.
ELSEWHERE: dict[str, str] = {
    "window-width": "the window's size",
    "window-height": "the window's size",
    "is-maximized": "the window's size",
    "refresh-speed": "replaced by update-interval; read once to migrate",
    "show-toolbar": "the main menu",
    "toolbar-items": "the graph toolbar's ⋮ menu",
    "sidebar-shown": "the main menu",
    "sidebar-collapsed-groups": "a sidebar group's arrow",
    "overview-top-by": "the Overview's busiest apps and processes",
    "show-logical-cpus": "the Processor page's toolbar",
    "apps-sort-by": "the Apps table's column headers",
    "apps-sort-by-ascending": "the Apps table's column headers",
    "processes-sort-by": "the Processes table's column headers",
    "processes-sort-by-ascending": "the Processes table's column headers",
    "gpu-view": "the GPU page's tabs",
    "linger-offered": "the one-time Record from Boot? question (the choice is "
                      "Start at Boot, on Recording)",
}

PAGES: tuple[Page, ...] = (
    Page("appearance", "Appearance", "applications-graphics-symbolic", (
        Group("style", "Style", ("color-scheme", "palette")),
        Group("graphs", "Graphs", ("show-graph-axes", "show-graph-grids", "graph-time-range",
                                   "custom-range")),
        Group("units", "Units", ("base", "network-bits", "temperature-unit")),
    )),
    Page("sidebar", "Sidebar", "sidebar-show-symbolic", (
        Group("all-entries", "All Entries", ("sidebar-style", "sidebar-details",
                                             "sidebar-description", "sidebar-meter-type")),
        Group("entries", "Entries", ("sidebar-entries",),
              "Apps and Processes always stay at the top"),
    )),
    Page("tables", "Tables", "view-list-bullet-symbolic", (
        Group("options", "Options", ("normalize-cpu-usage", "detailed-priority")),
        Group("columns", "Information Columns", ("apps-columns", "processes-columns")),
    )),
    Page("recording", "Recording", "document-open-recent-symbolic", (
        Group("history", "History", ("history", "history-detail-hours", "history-max-size"),
              "Every reading, with times in UTC. Graphs show it at once, "
              "even from earlier runs"),
        Group("background", "In the Background", ("background",)),
        Group("exports", "Exports", ("export-hardware-addresses",)),
        Group("status", "Status and Actions", ("recording", "history-size", "export")),
    )),
    Page("devices", "Devices", "computer-symbolic", (
        Group("drives", "Drives", ("show-virtual-drives",)),
        Group("networks", "Network Interfaces", ("show-virtual-network-interfaces",)),
        Group("gpus", "GPU Detailed Statistics", ("gpu-sources",),
              "Each GPU always shows an overview. Where a vendor tool "
              "such as intel_gpu_top is installed, it adds detailed tabs"),
        Group("gpu-options", "GPU Detailed Statistics Options",
              ("gpu-elevate", "intel-gpu-top-interval")),
    )),
    Page("system", "System", "preferences-system-symbolic", (
        Group("memory-use", "Memory Use", ("lightweight",)),
        Group("readings", "Readings", ("update-interval",)),
        Group("administrator", "Administrator Rights", ("auth-at-launch",)),
        Group("window-switching", "Window Switching", ("window-switching",),
              "GNOME lets an app bring only its own windows to the front. "
              "A small GNOME Shell extension lets Apps → Switch To bring "
              "any app's window forward. It can only list windows and "
              "activate one"),
        Group("diagnostics", "Diagnostics", ("log-level", "log-max-size",
                                             "log-performance-interval", "log-file"),
              "A small log of Proccoli's messages and performance, for reporting problems"),
    )),
)

# A page longer than this many rows wants splitting (column lists count
# as one row each: they open in place).
MAX_ROWS = 12


def items() -> list[str]:
    """Every row, in order, pages first."""
    return [item for page in PAGES for group in page.groups for item in group.items]


def placed_keys() -> list[str]:
    """Every settings key Preferences sets, with repeats (there should be
    none)."""
    out: list[str] = []
    for item in items():
        out.extend(SPECIAL[item] if item in SPECIAL else (item,))
    return out


def page_of(item: str) -> str:
    """The id of the page an item (or the key a special item sets) is on."""
    for page in PAGES:
        for group in page.groups:
            for it in group.items:
                if it == item or item in SPECIAL.get(it, ()):
                    return page.id
    raise KeyError(item)
