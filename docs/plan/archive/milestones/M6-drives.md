# Milestone 6: Drives

*✅ Done.* Hotplug by 5 s rescans

*Goal: the first **dynamic, multi-instance** device type.*

| # | Create | Test |
|---|---|---|
| 6.1 | `devices/drive.py`: `DriveDiscoverer` (`/sys/block/*`; skip `loop`, `ram`, `zram`; virtual (dm, md, zd) only with *Show Virtual Drives*) | Fixtures: NVMe + USB stick + dm-crypt; the setting toggles the dm device |
| 6.2 | Drive type detection: NVMe, SSD (`rotational=0`), HDD, removable/flash, optical; capacity from `size × 512`; writable, removable; model and link | Fixture table |
| 6.3 | `DriveMonitor.sample()`: busy % from the `io_ticks` delta, read/write B/s from sector deltas, totals | Fixture pair → known speeds |
| 6.4 | `DeviceManager.rescan()` every 5 s: emits `device-added` and `device-removed` | Unit: swap fixture dirs between scans → one added, one removed |
| 6.5 | `ui/pages/drive.py`: `DrivePage` (busy, read and write graphs; totals; properties) | Smoke |
| 6.6 | Window handles `device-removed`: removes the page and sidebar item, and selects a neighbour if it was visible | UI test with a fake manager |

**Done:** plugging in a USB stick adds a "Drive" entry within 5 s, and
unplugging removes it.
