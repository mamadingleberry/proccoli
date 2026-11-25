"""Snapshots on the wire: every reading the
collector sends the window.

Snapshots and the detail samples inside them are dataclasses; ``encode``
turns one into JSON-ready data (``{"__type__": "CpuSnapshot", ...}``,
nested dataclasses, lists and dictionaries as they are) and ``decode``
builds the same class back, so the window's pages keep using
``CpuSnapshot`` and friends unchanged.

Only the types in ``TYPES`` are ever built: anything else decodes as
plain data, so a message can't make the window instantiate arbitrary
classes. Fields the window doesn't know (a newer collector) are dropped;
fields it knows but didn't get (an older one) keep their defaults.
Display-free.
"""

from __future__ import annotations

import dataclasses
import enum
import json
from typing import Any

from ..gpu.amdgpu.sensors import AmdgpuSample
from ..gpu.backend import GpuProcessUsage, GpuSummary
from ..gpu.controller import GpuSnapshot
from ..gpu.info import GpuInfo, GpuVendor
from ..gpu.nvidia.query import NvidiaSample
from .base import Snapshot
from .battery import BatterySnapshot
from .cpu import CpuSnapshot
from .demo import DemoSnapshot
from .drive import DriveSnapshot
from .memory import MemoryModule, MemorySnapshot
from .network import NetworkSnapshot

TYPE = "__type__"
ENUM = "__enum__"
TYPES: dict[str, type] = {cls.__name__: cls for cls in (
    Snapshot, CpuSnapshot, MemorySnapshot, DriveSnapshot, NetworkSnapshot, BatterySnapshot,
    DemoSnapshot, GpuSnapshot, GpuSummary, GpuProcessUsage, AmdgpuSample, NvidiaSample,
    GpuInfo, MemoryModule)}
ENUMS: dict[str, type] = {cls.__name__: cls for cls in (GpuVendor,)}


def encode(value: Any) -> Any:
    """JSON-ready data for a snapshot (or anything inside one)."""
    if isinstance(value, enum.Enum):
        return {ENUM: type(value).__name__, "name": value.name}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        out = {TYPE: type(value).__name__}
        for f in dataclasses.fields(value):
            out[f.name] = encode(getattr(value, f.name))
        return out
    if isinstance(value, dict):
        return {str(k): encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(v) for v in value]
    if isinstance(value, float) and value != value:      # NaN isn't JSON
        return None
    return value


def decode(data: Any) -> Any:
    """The object ``encode`` made ``data`` from (known types only)."""
    if isinstance(data, dict) and ENUM in data:
        cls = ENUMS.get(data[ENUM])
        return cls[data["name"]] if cls is not None and data.get("name") in cls.__members__ \
            else data.get("name")
    if isinstance(data, dict):
        cls = TYPES.get(data.get(TYPE)) if TYPE in data else None
        if cls is None:
            return {k: decode(v) for k, v in data.items() if k != TYPE}
        known = {f.name for f in dataclasses.fields(cls) if f.init}
        return cls(**{k: decode(v) for k, v in data.items() if k in known})
    if isinstance(data, list):
        return [decode(v) for v in data]
    return data


def dumps(value: Any) -> str:
    return json.dumps(encode(value), separators=(",", ":"), allow_nan=False)


def loads(text: str) -> Any:
    return decode(json.loads(text))
