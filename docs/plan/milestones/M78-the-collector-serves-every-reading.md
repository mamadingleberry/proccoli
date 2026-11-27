# Milestone 78: The collector serves every reading (Idea 19a)

*✅ Done.* `proccoli-metrics` owns `<app ID>.Metrics` on the session bus: `Devices`, `Subscribe` / `Unsubscribe` (name-watched), `Status`, and a `Readings` signal each update while someone's subscribed; snapshots as JSON by `devices/snapshot_codec` (known types only); `proccoli-metrics --watch`. The window doesn't use it yet. Serving costs nothing measurable (1.12 % of a core with a subscriber, 1.22 % without)

The first of Idea 19's three parts (kept below with the whole design):
`proccoli-metrics` serves what it reads; the window doesn't use it yet,
so nothing changes for it.

| Step | Create / change | Test |
|---|---|---|
| 78.1 | `devices/snapshot_codec.py`: `encode` / `decode` (and `dumps` / `loads`), every snapshot type and the detail samples (`GpuSummary`, `GpuProcessUsage`, `AmdgpuSample`, `NvidiaSample`) | Unit: every snapshot of two fixture machines round-trips equal; a detail sample; `None` and NaN; an unknown type decodes as plain data; a newer and an older collector's fields |
| 78.2 | `metrics_service.py`: `MetricsService` (the D-Bus object, name owning, subscribers watched by bus name, `Readings` after each update while anyone's subscribed, `DeviceAdded` / `DeviceRemoved`, `Status`); `Collector` starts it (`bus=False` for tests); `watch()` and `proccoli-metrics --watch` | Unit on a private `dbus-daemon`: devices with properties; readings only while subscribed, and none once the client unsubscribes; a client that leaves is forgotten; status; `watch` prints a line per update. By hand: the collector and `--watch` as two processes on the real session bus |

**Deviations from the design, and why:**
- **JSON strings, not `a{sv}`:** GVariant has no null, and snapshots are
  full of `None` (a reading a device doesn't have); JSON round-trips them
  exactly, nested dataclasses and lists included, at a few kilobytes a
  second.
- **No `Detail()` method:** a GPU's Details state, message, source,
  sample and per-process use travel in each reading (`"gpu"`), so the
  window gets them at the same moment as the snapshot.

*Found while doing 78:*
- **Synchronous D-Bus calls deadlock in one process:** a client's
  `call_sync` blocks the main loop the service answers from. The window
  and `--watch` are other processes, but `watch()` and the tests call
  asynchronously anyway.
- **`Gio.TestDBus` changes the whole test run's session bus:** every
  later test registering a GTK application failed. The service tests run
  their own `dbus-daemon`, reached by address.

**Measured** (the real collector on the laptop, 60 s each): 1.22 % of a
core with nobody subscribed, 1.12 % with `--watch` subscribed: serving
is within the noise.
