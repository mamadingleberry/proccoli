import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.units import (  # noqa: E402
    NO_DATA, Base, TemperatureUnit, convert_temperature, format_bytes,
    format_duration, format_frequency, format_percent, format_power,
    format_rate, format_temperature)

B, D = Base.BINARY, Base.DECIMAL


class UnitsTest(unittest.TestCase):
    def check(self, fn, cases):
        for args, expected in cases:
            args = args if isinstance(args, tuple) else (args,)
            self.assertEqual(fn(*args), expected, args)

    def test_none_is_no_data_everywhere(self):
        for fn in (format_bytes, format_rate, format_percent, format_frequency,
                   format_power, format_temperature, format_duration):
            self.assertEqual(fn(None), NO_DATA, fn.__name__)

    def test_bytes(self):
        self.check(format_bytes, [
            (0, "0 B"), (999, "999 B"), (1000, "1.0 kB"), (1536, "1.5 kB"),
            ((1536, B), "1.5 KiB"), (16 * 10 ** 9, "16.0 GB"),
            ((16 * 2 ** 30, B), "16.0 GiB"), ((1023, B), "1023 B"),
            (999_960, "1.0 MB"),          # rounding carries into the next unit
            (2 * 10 ** 21, "2000.0 EB"),  # beyond the largest prefix
        ])

    def test_rate_bytes_and_bits(self):
        self.check(format_rate, [
            (0, "0 B/s"), (1_250_000, "1.2 MB/s"), ((1_250_000, B), "1.2 MiB/s"),
            ((1_250_000, D, True), "10.0 Mb/s"), ((100, D, True), "800 bit/s"),
        ])

    def test_percent(self):
        self.check(format_percent, [(0, "0.0 %"), (5.25, "5.2 %"), (12.6, "13 %"),
                                    (100, "100 %")])

    def test_frequency(self):
        self.check(format_frequency, [(800e6, "800 MHz"), (1.2e9, "1.20 GHz"),
                                      (4.7e9, "4.70 GHz"), (32e3, "32 kHz"), (50, "50 Hz")])

    def test_power(self):
        self.check(format_power, [(0.25, "250 mW"), (5.21, "5.2 W"), (12.82, "12.8 W"),
                                  (250.4, "250 W")])

    def test_temperature(self):
        self.check(format_temperature, [
            (45, "45 °C"), ((45, TemperatureUnit.FAHRENHEIT), "113 °F"),
            ((45, TemperatureUnit.KELVIN), "318 K"),
        ])
        self.assertAlmostEqual(convert_temperature(-40, TemperatureUnit.FAHRENHEIT), -40)

    def test_enums_accept_settings_strings(self):
        self.assertIs(Base("binary"), Base.BINARY)
        self.assertIs(TemperatureUnit("kelvin"), TemperatureUnit.KELVIN)

    def test_duration(self):
        self.check(format_duration, [
            (0, "0 s"), (45.9, "45 s"), (200, "3 min 20 s"), (7500, "2 h 05 min"),
            (3 * 86400 + 4 * 3600 + 59, "3 d 4 h"), (-5, "0 s"),
        ])


class FactsTest(unittest.TestCase):
    """The Overview cards' readings line (M57)."""

    def test_used_total_each_with_its_unit(self):
        from proccoli.core.units import Base, format_used_total
        self.assertEqual(format_used_total(571 * 2**20, 8151 * 2**20), "598.7 MB / 8.5 GB")
        self.assertEqual(format_used_total(571 * 2**20, 8151 * 2**20, Base.BINARY),
                         "571.0 MiB / 8.0 GiB")

    def test_facts(self):
        from proccoli.core.units import Base, TemperatureUnit, device_facts
        self.assertEqual(device_facts(48.0), ["Temperature 48 °C"])
        self.assertEqual(device_facts(39.0, TemperatureUnit.FAHRENHEIT, 571 * 2**20,
                                      8151 * 2**20, Base.DECIMAL),
                         ["Temperature 102 °F", "Memory 598.7 MB / 8.5 GB"])
        self.assertEqual(device_facts(None, memory_used=1, memory_total=None), [])
        self.assertEqual(device_facts(), [])


if __name__ == "__main__":
    unittest.main()
