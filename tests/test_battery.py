import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from helpers import FakeRoot  # noqa: E402

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.devices.battery import (  # noqa: E402
    BatteryDiscoverer, BatteryMonitor, energy_wh, power_watts)

BAT = "/sys/class/power_supply/BAT0"


def battery(root, name="BAT0", **attrs):
    defaults = {"type": "Battery", "status": "Discharging", "capacity": "80",
                "present": "1"}
    defaults.update(attrs)
    for k, v in defaults.items():
        root.write(f"/sys/class/power_supply/{name}/{k}", f"{v}\n")


class BatteryTest(unittest.TestCase):
    def discover(self, root):
        return BatteryDiscoverer().discover(root.sysroot, Settings.for_tests())

    def test_energy_reporting_battery(self):
        root = FakeRoot(self)
        battery(root, energy_full="45000000", energy_full_design="50000000",
                energy_now="36000000", power_now="7500000", cycle_count="123",
                technology="Li-ion", manufacturer="ACME", model_name="BAT-5000")
        [info] = self.discover(root)
        self.assertEqual((info.id, info.name, info.description),
                         ("battery-BAT0", "Battery", "BAT-5000"))
        p = info.properties
        self.assertEqual((p["Battery Health"], p["Design Capacity"], p["Charge Cycles"]),
                         ("90 %", "50.0 Wh", "123"))
        self.assertEqual(p["Technology"], "Li-ion")
        m = BatteryMonitor(info, root.sysroot)
        m.refresh(1.0)
        self.assertEqual((m.latest.charge, m.latest.power_w, m.latest.state),
                         (80.0, 7.5, "Discharging"))
        self.assertEqual(m.latest.detail_text, "Discharging · 7.5 W")
        self.assertEqual(m.history.series("power").latest(), 7.5)

    def test_charge_reporting_battery(self):
        root = FakeRoot(self)
        battery(root, charge_full="4000000", charge_full_design="5000000",
                voltage_min_design="11000000", voltage_now="12000000",
                current_now="-500000")
        self.assertAlmostEqual(energy_wh(root.sysroot, "BAT0", "full_design"), 55.0)
        self.assertAlmostEqual(power_watts(root.sysroot, "BAT0"), 6.0)   # |I| * V
        [info] = self.discover(root)
        self.assertEqual(info.properties["Battery Health"], "80 %")

    def test_capacity_falls_back_to_energy(self):
        root = FakeRoot(self)
        battery(root, energy_full="40000000", energy_now="10000000")
        root.remove(f"{BAT}/capacity")
        [info] = self.discover(root)
        m = BatteryMonitor(info, root.sysroot)
        m.refresh(1.0)
        self.assertEqual(m.latest.charge, 25.0)

    def test_full_battery_shows_no_power(self):
        root = FakeRoot(self)
        battery(root, status="Full", power_now="0")
        [info] = self.discover(root)
        m = BatteryMonitor(info, root.sysroot)
        m.refresh(1.0)
        self.assertEqual(m.latest.detail_text, "Full")

    def test_what_is_not_a_system_battery(self):
        root = FakeRoot(self)
        battery(root, "hidpp_battery_0", scope="Device")     # a mouse
        battery(root, "BAT1", present="0")                   # empty bay
        root.write("/sys/class/power_supply/AC/type", "Mains\n")
        self.assertEqual(self.discover(root), [])

    def test_no_charge_at_all_is_a_gap(self):
        root = FakeRoot(self)
        battery(root)
        root.remove(f"{BAT}/capacity")
        [info] = self.discover(root)
        m = BatteryMonitor(info, root.sysroot)
        with self.assertLogs("proccoli.devices.base"):
            m.refresh(1.0)
        self.assertIsNone(m.latest)

    def test_laptop_fixture_has_no_battery(self):
        from helpers import LAPTOP
        from proccoli.core.sysroot import SysRoot
        self.assertEqual(BatteryDiscoverer().discover(SysRoot(LAPTOP), Settings.for_tests()),
                         [])


if __name__ == "__main__":
    unittest.main()
