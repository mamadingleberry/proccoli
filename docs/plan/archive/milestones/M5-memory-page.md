# Milestone 5: Memory page

*✅ Done.* Authenticate reads modules through the helper (M12)

| # | Create | Test |
|---|---|---|
| 5.1 | `devices/memory.py`: `MemoryMonitor` from `/proc/meminfo` (used = total − available, swap) | Fixture |
| 5.2 | `ui/pages/memory.py`: Usage group (memory and swap graphs, info "X of Y") | Smoke |
| 5.3 | Properties group, hidden behind an `AdwBanner` ("You need to authenticate to see memory properties") | Smoke: banner visible and properties hidden by default |
| 5.4 | Parser for `dmidecode -t 17` output → `MemoryModule` list (slots used, speed, form factor, type, type detail) | Unit with captured dmidecode text fixtures |
| 5.5 | *(Deferred to Milestone 12)* The banner button runs the helper. For now it shows a toast saying it's not available yet. | – |

**Done:** the Memory page shows live RAM and swap use.
