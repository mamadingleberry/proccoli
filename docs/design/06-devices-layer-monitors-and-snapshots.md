# 6. Devices layer: monitors and snapshots

Every sidebar entry except Apps and Processes is a **device**. A device has
an immutable `DeviceInfo`, discovered once, and a `Monitor` that produces a
`Snapshot` on every tick.

```mermaid
classDiagram
    direction TB
    class DeviceKind {
        <<enumeration>>
        CPU
        MEMORY
        GPU
        DRIVE
        NETWORK
        BATTERY
    }
    class DeviceInfo {
        <<dataclass, frozen>>
        +id: str
        +kind: DeviceKind
        +name: str
        +description: str
        +icon_name: str
        +properties: dict~str,str~
    }
    class Snapshot {
        <<dataclass>>
        +time: float
        +usage: float|None
        +usage_text: str
        +detail_text: str
    }
    class Monitor {
        <<abstract, GObject>>
        +info: DeviceInfo
        +history: History
        +latest: Snapshot|None
        +refresh(now)*
        +start()
        +stop()
        +describe(encode) dict
        +reading(encode) dict|None
        +signal updated(snapshot)
        #sample(now)* Snapshot
    }
    class CpuMonitor {
        -prev_jiffies: list
        +sample(now) CpuSnapshot
    }
    class MemoryMonitor {
        +sample(now) MemorySnapshot
        +load_modules(elevated) list~MemoryModule~
    }
    class DriveMonitor {
        -prev_stats: DiskStats
        +sample(now) DriveSnapshot
    }
    class NetworkMonitor {
        -prev_bytes: tuple
        +sample(now) NetworkSnapshot
    }
    class BatteryMonitor {
        +sample(now) BatterySnapshot
    }
    class CpuSnapshot {
        +total: float
        +per_thread: list~float~
        +frequency_hz: float
        +temperature_c: float|None
    }
    class MemorySnapshot {
        +used, total, available: int
        +swap_used, swap_total: int
    }
    class DriveSnapshot {
        +busy: float
        +read_bps, write_bps: float
        +total_read, total_written: int
    }
    class NetworkSnapshot {
        +rx_bps, tx_bps: float
        +total_rx, total_tx: int
    }
    class BatterySnapshot {
        +charge: float
        +power_w: float
        +state: str
    }
    class DeviceSource {
        <<abstract, GObject>>
        +remote: bool
        +connected: bool
        +status: str
        +monitors(kind) list~Monitor~
        +monitor(id) Monitor
        +start(ticker)*
        +stop()*
        +refresh(now)*
        +rescan()*
        +retry(id)* bool
        +reconnect()
        +signal device_added(monitor)
        +signal device_removed(id)
        +signal connection_changed()
    }
    class DeviceManager {
        -sysroot: SysRoot
        -discoverers: list~Discoverer~
        +register(discoverer)
    }
    DeviceSource <|-- DeviceManager : reads devices itself
    DeviceSource <|-- RemoteDeviceManager : the recorder's, over D-Bus
    class Discoverer {
        <<interface>>
        +kind: DeviceKind
        +rescan: bool
        +settings_keys: tuple
        +discover(sysroot, settings) list~DeviceInfo~
        +create_monitor(info, sysroot, settings) Monitor
    }
    Monitor <|-- CpuMonitor
    Monitor <|-- MemoryMonitor
    Monitor <|-- DriveMonitor
    Monitor <|-- NetworkMonitor
    Monitor <|-- BatteryMonitor
    Monitor <|-- GpuController : GPU devices are monitors too
    Snapshot <|-- CpuSnapshot
    Snapshot <|-- MemorySnapshot
    Snapshot <|-- DriveSnapshot
    Snapshot <|-- NetworkSnapshot
    Snapshot <|-- BatterySnapshot
    Monitor o-- DeviceInfo
    DeviceManager o-- "many" Monitor
    DeviceManager o-- "many" Discoverer
    Discoverer ..> Monitor : creates
```

**Data sources per device** (all through `SysRoot`, so every one can be
tested with fixtures):

| Device | Discovery | Per-tick data | Properties |
|---|---|---|---|
| CPU | `/proc/cpuinfo` | `/proc/stat` deltas, `/sys/devices/system/cpu/cpu*/cpufreq` | `/proc/cpuinfo`, `lscpu`-style topology from `/sys/devices/system/cpu`, `/proc/uptime`; temperature from hwmon `coretemp` / `k10temp` |
| Memory | always; description "16.0 GB DDR4 @ 2667 MT/s" (`memory_description`: one decimal, the slowest module's speed) | `/proc/meminfo` | udev's SMBIOS record `/run/udev/data/+dmi:id` (`MEMORY_DEVICE_<n>_*`, readable by any user): slots, type, speed, form factor. Only without it: `dmidecode -t 17` through the helper (banner + Authenticate) |
| Drive | `/sys/block/*` (skip loop/ram; virtual drives optional) | `/sys/block/X/stat` deltas | size, `removable`, `ro`, rotational → HDD/SSD/NVMe, `device/model` |
| Network | `/sys/class/net/*` (skip `lo`; virtual optional: no `device` link) | `/sys/class/net/X/statistics/{rx,tx}_bytes` | MAC address, driver (`device/driver`), speed; SSID and type from NetworkManager over D-Bus; wireless if `X/wireless` exists |
| Battery | `/sys/class/power_supply/*` with `type=Battery` | `capacity`, `power_now` or `current_now × voltage_now` | `energy_full_design`, `cycle_count`, `technology`, `manufacturer`, `model_name` |
| GPU | see [§7](07-the-gpu-carve-out.md) | see [§7](07-the-gpu-carve-out.md) | see [§7](07-the-gpu-carve-out.md) |

**A device that can't be set up (v0.2.0)** still appears. If its
`Discoverer.create_monitor()` or the monitor's `start()` raises,
`DeviceManager._build` logs it and keeps a `FailedMonitor` in its place:
a monitor that records nothing and carries `message` (in words) and
`details` (the traceback). Its page is an error page ([§9.7](09.7-error-pages.md));
`DeviceManager.retry(id)` builds it again. A discoverer that fails as a
whole is still only logged (there's no device to show).

**Sidebar naming** mirrors Resources: the Processor's description is its
model and Memory's its size, DDR type and speed; drives are
labelled "Drive" with the model as the description, and network interfaces are "Ethernet Connection",
"Wi-Fi Connection" or "VPN" with the interface name as the description.
These names come from `DeviceInfo.name` and `DeviceInfo.description`.
