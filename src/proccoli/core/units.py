"""Human-readable formatting of measured values.

Every function accepts ``None`` and returns an en dash for "no data", so
callers can pass sensor readings straight through.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

NO_DATA = "–"


class Base(str, Enum):
    """Data unit prefixes (the *Data Unit Prefix* preference)."""
    DECIMAL = "decimal"   # kB, MB, GB (powers of 1000)
    BINARY = "binary"     # KiB, MiB, GiB (powers of 1024)


class TemperatureUnit(str, Enum):
    CELSIUS = "celsius"
    FAHRENHEIT = "fahrenheit"
    KELVIN = "kelvin"


_DECIMAL_PREFIXES = ["", "k", "M", "G", "T", "P", "E"]
_BINARY_PREFIXES = ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei"]


def _scaled(value: float, base: Base) -> tuple[float, str]:
    step = 1024.0 if base == Base.BINARY else 1000.0
    prefixes = _BINARY_PREFIXES if base == Base.BINARY else _DECIMAL_PREFIXES
    i = 0
    v = float(value)
    while abs(v) >= step and i < len(prefixes) - 1:
        v /= step
        i += 1
    # Rounding can carry into the next unit (999.96 kB -> "1000.0 kB").
    if i < len(prefixes) - 1 and abs(round(v, 1)) >= step:
        v /= step
        i += 1
    return v, prefixes[i]


def _number(v: float, prefix: str) -> str:
    if not prefix:            # plain bytes/bits are whole numbers
        return f"{v:.0f}"
    return f"{v:.1f}"


def format_bytes(n: Optional[float], base: Base = Base.DECIMAL) -> str:
    if n is None:
        return NO_DATA
    v, p = _scaled(n, base)
    return f"{_number(v, p)} {p}B"


def format_bytes_fixed(n: float, base: Base = Base.DECIMAL, decimals: int = 1) -> str:
    """Bytes with a fixed number of decimals ("16.0 GB"), for labels whose
    format is fixed."""
    v, p = _scaled(n, base)
    return f"{v:.{decimals}f} {p}B"


def format_rate(bytes_per_s: Optional[float], base: Base = Base.DECIMAL,
                bits: bool = False) -> str:
    """Transfer speed, in bytes per second or (``bits=True``) bits per
    second, as the *Show Network Speeds in Bits* preference chooses."""
    if bytes_per_s is None:
        return NO_DATA
    value = bytes_per_s * 8 if bits else bytes_per_s
    v, p = _scaled(value, base)
    unit = "bit/s" if bits else "B/s"
    if bits and p:
        unit = "b/s"
    return f"{_number(v, p)} {p}{unit}"


def format_percent(v: Optional[float]) -> str:
    if v is None:
        return NO_DATA
    if abs(v) < 10:
        return f"{v:.1f} %"
    return f"{v:.0f} %"


def format_frequency(hz: Optional[float]) -> str:
    if hz is None:
        return NO_DATA
    if abs(hz) >= 1e9:
        return f"{hz / 1e9:.2f} GHz"
    if abs(hz) >= 1e6:
        return f"{hz / 1e6:.0f} MHz"
    if abs(hz) >= 1e3:
        return f"{hz / 1e3:.0f} kHz"
    return f"{hz:.0f} Hz"


def format_power(watts: Optional[float]) -> str:
    if watts is None:
        return NO_DATA
    if abs(watts) < 1:
        return f"{watts * 1000:.0f} mW"
    if abs(watts) < 100:
        return f"{watts:.1f} W"
    return f"{watts:.0f} W"


def convert_temperature(celsius: float, unit: TemperatureUnit) -> float:
    if unit == TemperatureUnit.FAHRENHEIT:
        return celsius * 9 / 5 + 32
    if unit == TemperatureUnit.KELVIN:
        return celsius + 273.15
    return celsius


def format_temperature(celsius: Optional[float],
                       unit: TemperatureUnit = TemperatureUnit.CELSIUS) -> str:
    if celsius is None:
        return NO_DATA
    v = convert_temperature(celsius, unit)
    symbol = {TemperatureUnit.CELSIUS: "°C", TemperatureUnit.FAHRENHEIT: "°F",
              TemperatureUnit.KELVIN: "K"}[unit]
    return f"{v:.0f} {symbol}"


def format_duration(seconds: Optional[float]) -> str:
    """Compact duration: "45 s", "3 min 20 s", "2 h 05 min", "3 d 4 h"."""
    if seconds is None:
        return NO_DATA
    s = max(0, int(seconds))
    days, s = divmod(s, 86400)
    hours, s = divmod(s, 3600)
    minutes, s = divmod(s, 60)
    if days:
        return f"{days} d {hours} h"
    if hours:
        return f"{hours} h {minutes:02d} min"
    if minutes:
        return f"{minutes} min {s} s"
    return f"{s} s"
