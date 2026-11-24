import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from helpers import FIXTURES, LAPTOP, FakeRoot  # noqa: E402

from proccoli.core import pciids  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.sysroot import SysRoot  # noqa: E402
from proccoli.devices.network import (  # noqa: E402
    NetType, NetworkDiscoverer, NetworkMonitor, net_type)

PCI = pciids.load(os.path.join(FIXTURES, "pci", "pci.ids"))


class PciIdsTest(unittest.TestCase):
    def test_lookup(self):
        self.assertEqual(PCI.vendor(0x8086), "Intel Corporation")
        self.assertEqual(PCI.device(0x8086, 0x46a3), "Alder Lake-P GT1 [UHD Graphics]")
        self.assertIsNone(PCI.device(0x8086, 0xffff))
        self.assertIsNone(PCI.vendor(None))
        self.assertNotIn(0x00, PCI.vendors)          # class section not parsed

    def test_missing_database_is_empty(self):
        self.assertEqual(pciids.load("/nonexistent/pci.ids").vendors, {})


class DiscoveryTest(unittest.TestCase):
    def test_laptop_interfaces(self):
        found = {i.id: i for i in NetworkDiscoverer(PCI).discover(
            SysRoot(LAPTOP), Settings.for_tests())}
        self.assertEqual(set(found), {"net-eno1", "net-wlp43s0"})   # lo skipped
        wifi, eth = found["net-wlp43s0"], found["net-eno1"]
        self.assertEqual((wifi.name, wifi.description), ("Wi-Fi Connection", "wlp43s0"))
        self.assertEqual(eth.name, "Ethernet Connection")
        self.assertEqual(wifi.properties["Manufacturer"], "Realtek Semiconductor Co., Ltd.")
        self.assertEqual(wifi.properties["Driver Used"], "rtw88_8821ce")
        self.assertEqual(eth.properties["Driver Used"], "e1000e")
        self.assertRegex(eth.properties["Hardware Address"], r"^02:00:00:00:00:")

    def test_virtual_interfaces_need_the_setting(self):
        root = FakeRoot(self, {"/sys/class/net/docker0/type": "1\n",
                               "/sys/class/net/wg0/type": "65534\n",
                               "/sys/class/net/wg0/uevent": "DEVTYPE=wireguard\n"},
                        dirs=["/sys/class/net/docker0/bridge"])
        settings = Settings.for_tests()
        self.assertEqual(NetworkDiscoverer(PCI).discover(root.sysroot, settings), [])
        settings.set("show-virtual-network-interfaces", True)
        found = {i.id: i for i in NetworkDiscoverer(PCI).discover(root.sysroot, settings)}
        self.assertEqual(found["net-docker0"].name, "Network Bridge")
        self.assertEqual(found["net-wg0"].name, "VPN")

    def test_types(self):
        root = SysRoot(LAPTOP)
        self.assertIs(net_type(root, "wlp43s0"), NetType.WIFI)
        self.assertIs(net_type(root, "eno1"), NetType.ETHERNET)


class MonitorTest(unittest.TestCase):
    def test_rates_and_connection_name(self):
        root = FakeRoot(self, {"/sys/class/net/wlan0/statistics/rx_bytes": "1000\n",
                               "/sys/class/net/wlan0/statistics/tx_bytes": "500\n",
                               "/sys/class/net/wlan0/speed": "-1\n"},
                        dirs=["/sys/class/net/wlan0/wireless"])
        [info] = NetworkDiscoverer(PCI).discover(
            root.sysroot, Settings.for_tests({"show-virtual-network-interfaces": True}))
        lookups = []
        m = NetworkMonitor(info, root.sysroot,
                           connection_name=lambda i: lookups.append(i) or "HomeNet")
        m.refresh(1.0)
        root.write("/sys/class/net/wlan0/statistics/rx_bytes", "5000\n")
        root.write("/sys/class/net/wlan0/statistics/tx_bytes", "1500\n")
        m.refresh(3.0)
        s = m.latest
        self.assertEqual((s.rx_bps, s.tx_bps), (2000.0, 500.0))
        self.assertEqual((s.total_rx, s.total_tx), (5000, 1500))
        self.assertIsNone(s.usage)
        self.assertIsNone(s.link_speed_mbps)     # -1 = link down / unknown
        self.assertEqual(s.network_name, "HomeNet")
        self.assertEqual(lookups, ["wlan0"])     # not looked up on every tick
        self.assertEqual(m.sort_order(), NetType.WIFI.order)


if __name__ == "__main__":
    unittest.main()
