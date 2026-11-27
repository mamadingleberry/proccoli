# Milestone 23: Memory type (DDR) without a password

*✅ Done.* udev has the module data, so no password is needed at all here

systemd's udev database (`/run/udev/data/+dmi:id`, readable by any user)
holds the SMBIOS memory devices (`MEMORY_DEVICE_<n>_TYPE=DDR4`, size,
speed, form factor, locator). So the module properties don't need
`dmidecode` and a password.

| Step | Create / change | Test |
|---|---|---|
| 23.1 | `devices/memory.py`: `parse_udev_memory(text)` → `list[MemoryModule]` (empty slots included), read through `SysRoot` | Unit on a fixture copied from this laptop, plus empty/absent files |
| 23.2 | `memory_type(modules)` ("DDR4", or "DDR4, DDR5" if mixed); the sidebar description becomes "16.0 GB DDR4", like the Processor's model | Unit |
| 23.3 | `MemoryMonitor.modules` is filled from udev at discovery; the page shows Properties at once and hides the Authenticate banner. `dmidecode` through the helper stays as the fallback when udev has no data. | UI test both ways |
