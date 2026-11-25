"""Human-readable formatting of measured values.

Every function accepts ``None`` and returns an en dash for "no data", so
callers can pass sensor readings straight through.
"""

from __future__ import annotations

import math
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


def iso_utc(epoch_s: float) -> str:
    """ISO 8601 in UTC, to the millisecond: ``2026-11-23T21:41:25.154Z``
    (the diagnostics log and the old statistics files)."""
    import time
    whole = int(epoch_s)
    ms = int(round((epoch_s - whole) * 1000))
    if ms == 1000:
        whole, ms = whole + 1, 0
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(whole)) + f".{ms:03d}Z"


def parse_iso_utc(text: str) -> float:
    """The reverse of ``iso_utc``: epoch seconds (ValueError if malformed)."""
    import calendar
    import time
    whole, _, frac = text.rstrip("Z").partition(".")
    seconds = calendar.timegm(time.strptime(whole, "%Y-%m-%dT%H:%M:%S"))
    return seconds + (int(frac) / 10 ** len(frac) if frac else 0.0)


def format_used_total(used: Optional[float], total: Optional[float],
                      base: Base = Base.DECIMAL) -> str:
    """"598.7 MB / 8.5 GB": each with its own unit."""
    return f"{format_bytes(used, base)} / {format_bytes(total, base)}"


def device_facts(temperature_c: Optional[float] = None,
                 unit: TemperatureUnit = TemperatureUnit.CELSIUS,
                 memory_used: Optional[float] = None, memory_total: Optional[float] = None,
                 base: Base = Base.DECIMAL) -> list[str]:
    """The current readings an Overview card shows under its name:
    "Temperature 48 °C", "Memory 598.7 MB / 8.5 GB". A reading the device
    doesn't have is left out."""
    facts = []
    if temperature_c is not None:
        facts.append(f"Temperature {format_temperature(temperature_c, unit)}")
    if memory_used is not None and memory_total:
        facts.append(f"Memory {format_used_total(memory_used, memory_total, base)}")
    return facts


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


def nice_ceiling(v: float) -> float:
    """Round up to 1, 2, 2.5 or 5 times a power of ten (an axis maximum;
    moved here from the graph widget so domain code can use it)."""
    if v <= 0:
        return 1.0
    exp = math.floor(math.log10(v))
    base = 10 ** exp
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * base * (1 + 1e-9):
            return m * base
    return 10 * base


def format_reading(value: Optional[float], unit: str, base: Base = Base.DECIMAL,
                   bits: bool = False,
                   temperature: TemperatureUnit = TemperatureUnit.CELSIUS) -> str:
    """A graph series' value by its unit ("%", "B/s", "W", "°C", "Hz";
    anything else as a short number and the unit), with the user's unit
    preferences: the hover box's default text."""
    if value is None:
        return NO_DATA
    if unit == "%":
        return format_percent(value)
    if unit == "B/s":
        return format_rate(value, base, bits)
    if unit == "W":
        return format_power(value)
    if unit == "°C":
        return format_temperature(value, temperature)
    if unit == "Hz":
        return format_frequency(value)
    number = f"{value:.0f}" if abs(value) >= 100 else f"{value:.3g}"
    return f"{number} {unit}".strip()


def _short_number(v: float) -> str:
    """At most three significant figures, no trailing zeros: 2, 1.5, 250."""
    if abs(v) < 10:
        text = f"{v:.2f}"
    elif abs(v) < 100:
        text = f"{v:.1f}"
    else:
        return f"{v:.0f}"
    return text.rstrip("0").rstrip(".")


_SI_PREFIXES = ["", "k", "M", "G", "T"]


def _si(value: float) -> tuple[float, str]:
    """Powers of 1000 with SI prefixes (hertz, counts)."""
    v, i = float(value), 0
    while abs(v) >= 1000 and i < len(_SI_PREFIXES) - 1:
        v /= 1000
        i += 1
    return v, _SI_PREFIXES[i]


def format_axis_label(value: float, unit: str, base: Base = Base.DECIMAL,
                      bits: bool = False,
                      temperature: TemperatureUnit = TemperatureUnit.CELSIUS) -> str:
    """``format_reading``'s short form, for value-axis labels: "2 GB/s",
    "1.5 GHz", "60 °C", "15 W"."""
    if unit == "%":
        return f"{value:.0f} %"
    if unit == "B/s":
        v, p = _scaled(value * 8 if bits else value, base)
        word = ("b/s" if p else "bit/s") if bits else "B/s"
        return f"{_short_number(v)} {p}{word}"
    if unit == "B":
        v, p = _scaled(value, base)
        return f"{_short_number(v)} {p}B"
    if unit == "Hz":
        v, p = _si(value)
        return f"{_short_number(v)} {p}Hz"
    if unit == "W":
        if 0 < abs(value) < 1:
            return f"{_short_number(value * 1000)} mW"
        return f"{_short_number(value)} W"
    if unit == "°C":
        return format_temperature(value, temperature)
    v, p = _si(value)
    return f"{_short_number(v)}{p} {unit}".strip()


def nice_max_in_units(peak: float, unit: str, base: Base = Base.DECIMAL,
                      bits: bool = False) -> float:
    """An automatic axis maximum rounded in the unit it's shown in, so a
    binary axis reads "5 GiB/s", not "4.88 GiB/s" (was the Intel
    tab's bandwidth rule)."""
    if peak <= 0:
        return nice_ceiling(peak)
    if unit in ("B/s", "B"):
        factor = 8.0 if bits and unit == "B/s" else 1.0
        shown = peak * factor
        step = 1024 if base == Base.BINARY else 1000
        v, p = _scaled(shown, base)
        prefixes = _BINARY_PREFIXES if base == Base.BINARY else _DECIMAL_PREFIXES
        return nice_ceiling(v) * step ** prefixes.index(p) / factor
    if unit == "Hz" or unit not in ("%", "W", "°C", ""):
        v, p = _si(peak)
        return nice_ceiling(v) * 1000 ** _SI_PREFIXES.index(p)
    return nice_ceiling(peak)
