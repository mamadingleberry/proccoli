import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.units import (  # noqa: E402
    NO_DATA, Base, TemperatureUnit, convert_temperature, format_bytes,
    format_duration, format_frequency, format_percent, format_power,
    format_rate, format_reading, format_temperature)

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
    """The Overview cards' readings line."""

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


class FormatReadingTest(unittest.TestCase):
    def test_by_unit(self):
        self.assertEqual(format_reading(None, "%"), NO_DATA)
        self.assertEqual(format_reading(42.0, "%"), format_percent(42.0))
        self.assertEqual(format_reading(1.5e6, "B/s"), format_rate(1.5e6))
        self.assertEqual(format_reading(1.5e6, "B/s", B, True), format_rate(1.5e6, B, True))
        self.assertEqual(format_reading(12.5, "W"), format_power(12.5))
        self.assertEqual(format_reading(50, "°C", temperature=TemperatureUnit.FAHRENHEIT),
                         "122 °F")
        self.assertEqual(format_reading(2.4e9, "Hz"), format_frequency(2.4e9))

    def test_other_units_are_short_numbers(self):
        self.assertEqual(format_reading(1234567.0, "rpm"), "1234567 rpm")
        self.assertEqual(format_reading(3.14159, ""), "3.14")


class AxisLabelTest(unittest.TestCase):
    """format_axis_label: format_reading's short form."""

    def test_units(self):
        from proccoli.core.units import format_axis_label
        B, D = Base.BINARY, Base.DECIMAL
        cases = [
            ((50, "%"), "50 %"),
            ((2 * 2**30, "B/s", B), "2 GiB/s"),
            ((2e9, "B/s", D), "2 GB/s"),
            ((1.25e6, "B/s", D, True), "10 Mb/s"),
            ((0, "B/s", D), "0 B/s"),
            ((1.5e9, "Hz"), "1.5 GHz"),
            ((2.5, "W"), "2.5 W"),
            ((0.5, "W"), "500 mW"),
            ((1500, "irq/s"), "1.5k irq/s"),
            ((250, "irq/s"), "250 irq/s"),
            ((4 * 2**30, "B", B), "4 GiB"),
        ]
        for args, expected in cases:
            self.assertEqual(format_axis_label(*args), expected, args)
        self.assertEqual(format_axis_label(100, "°C", temperature=TemperatureUnit.FAHRENHEIT),
                         "212 °F")


class NiceMaxInUnitsTest(unittest.TestCase):
    def test_rounds_in_the_shown_unit(self):
        from proccoli.core.units import nice_max_in_units
        self.assertEqual(nice_max_in_units(4.1 * 2**30, "B/s", Base.BINARY), 5 * 2**30)
        self.assertEqual(nice_max_in_units(4.1e9, "B/s", Base.DECIMAL), 5e9)
        self.assertEqual(nice_max_in_units(800 * 2**20, "B/s", Base.BINARY), 1000 * 2**20)
        self.assertAlmostEqual(nice_max_in_units(1.3e6 / 8, "B/s", Base.DECIMAL, True),
                               2e6 / 8)
        self.assertAlmostEqual(nice_max_in_units(1.3e9, "Hz"), 2e9)
        self.assertEqual(nice_max_in_units(42, "W"), 50)
        self.assertEqual(nice_max_in_units(0, "W"), 1.0)


if __name__ == "__main__":
    unittest.main()
