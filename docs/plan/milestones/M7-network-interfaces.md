# Milestone 7: Network interfaces

*✅ Done.*

| # | Create | Test |
|---|---|---|
| 7.1 | `devices/network.py`: `NetworkDiscoverer` (`/sys/class/net/*`, skip `lo`, virtual only with the setting); type = Wi-Fi if `wireless/` exists, Ethernet if `type=1` with a `device` link, otherwise Other | Fixtures: `eno1` and `wlp43s0` (this laptop), plus `docker0`, `tun0` |
| 7.2 | Names like Resources: "Ethernet Connection" or "Wi-Fi Connection", with the interface as the description | Unit |
| 7.3 | `NetworkMonitor.sample()`: rx/tx B/s from deltas, totals | Fixture pair |
| 7.4 | `devices/nm.py`: `NetworkManagerClient` over `Gio.DBusProxy`: SSID and link speed for an interface. Optional; `None` when NM is absent. | Unit with a fake proxy object |
| 7.5 | `ui/pages/network.py`: receiving and sending graphs, totals, properties (manufacturer, driver, interface, MAC, network name, link, speed); *Show Network Speeds in Bits* | Smoke |

**Done:** the sidebar matches Resources on this laptop: Ethernet Connection
and Wi-Fi Connection, with live speeds.
