# Idea 19: The window reads nothing: `proccoli-metrics` serves every reading

Design note: [design/ideas/idea-19-the-window-reads-nothing-proccoli-serves.md](../../design/ideas/idea-19-the-window-reads-nothing-proccoli-serves.md)

**Status: in three parts, each approved before the next** (asked for:
"break it up into incremental sub-Ideas that I can periodically approve"):

| Part | What | Status |
|---|---|---|
| **19a** | The collector serves every reading over D-Bus (steps I19.1–I19.2, and `--watch`); the window unchanged | Done as Milestone 78 |
| **19b** | The window switches: `RemoteDeviceManager`, history read-only, the collector started on demand and always on (packaging), the "Not receiving readings" banner (I19.3–I19.5, I19.6's packaging); open question 1 | Done as Milestone 79 |
| **19c** | The features that need administrator rights (open questions 2 and 3), Preferences' rows, the `strace` check and measurements (I19.6's Preferences, I19.7–I19.8) | After 19b |

*Designed as one idea, first:* asked for after M77:
"The GUI must not collect/write metrics, it should rely on
proccoli-metrics to provide those", with two answers: **no device reads
at all in the window**, and **`proccoli-metrics` always on** (the window
starts it if it's stopped). This changes parts of M75 (marked below).

**Goal:** one process, `proccoli-metrics`, reads every device and writes
the history. The window only shows: live readings arrive from the
collector, older ones come from the history database (read-only, as M75's
reader already does).

**Why:** today two processes read the same files every second while the
window is open (M75 measured the collector alone at about 1 % of a core;
the window costs about as much again), and the window's role (writer or
reader) changes with what else is running. With one reader there's one
set of numbers, one cost, and one role each.

## 1. What moves where

| | Today | After |
|---|---|---|
| Device readings (processor, memory, GPUs, drives, network, batteries), GPU Details sources (AMD, NVIDIA) | read by the window, and by the collector when it runs | **collector only**; sent to the window each update |
| The history database | written by whoever holds the lock | **collector only**; the window opens it read-only (graphs fill from it, exports read it) |
| Device list and details (`DeviceInfo`, properties) | discovered by the window | discovered by the collector; sent on connect and when devices come and go |
| Settings (dconf) | both read | both read: the window changes them, the collector follows them (as now) |
| Per-process GPU use (fdinfo) | GPU controllers in the window | collector, sent with the GPU's readings |
| The process list (Apps, Processes) | window | **open question 1** (leaning: stays in the window) |
| Intel GPU Details (`intel_gpu_top`, needs root) | window, through `pkexec` | **open question 2** |
| Memory module details (`dmidecode`, needs root when udev lacks them) | window, through the helper | **open question 3** |
| `--demo` | window, made-up devices | window, made-up devices (not real readings; no collector needed) |

## 2. How the window gets readings: D-Bus

The session bus, with Gio (already a dependency; no new packages), name
`io.github.mamadingleberry.Proccoli.Metrics`, object
`/io/github/mamadingleberry/Proccoli/Metrics`:

| Member | Kind | Carries |
|---|---|---|
| `Devices()` → `aa{sv}` | method | every device: id, kind, name, description, icon, properties, sort name, and its snapshot type |
| `DeviceAdded(a{sv})`, `DeviceRemoved(s)` | signals | as the device manager's signals |
| `Readings(x time_ms, d mono, a{sa{sv}} snapshots)` | signal, each update | every device's snapshot as a dictionary (below), and the update's time on both clocks |
| `Subscribe()`, `Unsubscribe()` | methods | the window asks for `Readings`; the collector watches each subscriber's bus name and forgets it when it goes |
| `Status()` → `a{sv}` | method | version, schema, update interval, whether it's writing the history, since when |
| `Detail(s device)` → `a{sv}` | method | a GPU's Details state (running, off, why), for the tab's banner |

- **Snapshots on the wire:** every `Snapshot` subclass is a dataclass
  (`CpuSnapshot`, `GpuSnapshot` with its `GpuSummary`, …). A small codec
  (`core/snapshot_codec.py`, display-free) turns one into `{type: "cpu",
  fields: {…}}` and back into the same class, so pages keep using
  `CpuSnapshot` exactly as today. Detail samples (`AmdgpuSample`, the
  NVIDIA sample) travel the same way inside the GPU's snapshot.
- **Size and cost:** one signal a second of a few kilobytes (this laptop:
  7 devices, about 300 values); D-Bus delivers it in well under a
  millisecond. D-Bus doesn't tell a sender who listens, so the window
  calls `Subscribe()` and the collector watches that caller's bus name:
  with no window subscribed, nothing is encoded or sent.
- **Why D-Bus, not a socket:** it starts the collector on demand (D-Bus
  activation, section 4), it's already how desktop services talk, the
  session bus only lets the same user in, and Gio has both sides.

## 3. The window's side

- **`RemoteDeviceManager`** (`devices/remote.py`): the same interface as
  `DeviceManager` (`monitors()`, `monitor(id)`, `device-added`,
  `device-removed`, `start`, `stop`), filled from `Devices()` and the
  signals. Its **`RemoteMonitor`**s have the same interface as
  `Monitor` (`info`, `history`, `latest`, the `updated` signal,
  `described_properties()`), so pages, the sidebar, the Overview and the
  toolbar don't change: each `Readings` signal is decoded and fed to each
  monitor's `refresh`, which records it in its `History` and emits
  `updated`, as a local monitor does after sampling.
- **GPUs:** a `RemoteGpuController` keeps the controller's interface for
  the GPU page (`detail_state`, `detail_message`, `process_usage()`,
  `detail_history()`, the Details views' `backend.sample`), fed from the
  GPU's snapshot; the views (`DetailChartsView`) don't change.
- **History:** the window's `HistoryStore` becomes **read-only for good**
  (no lock, no writer role, no takeover: those parts of M75 go); it
  fills graphs and serves exports as M75's reader does. The window's
  clock offset for backfill comes from the `Readings` times.
- **When the collector isn't there:** the window asks D-Bus to start it
  (activation); while waiting, and if it can't (not installed, crashed
  repeatedly), each page shows a banner, "Not receiving readings", with
  the reason from systemd and a *Try Again* button; the history still
  shows. It reconnects by itself when the name appears again (`Gio`
  name watching).
- **Live points line up with history points** because both come from the
  same readings at the same times.

## 4. Always on

- **Enabled for everyone on install:** the package ships the unit
  enabled for all users (`systemctl --global enable`, in `postinst`; a
  preset file `90-proccoli.preset` for systems that apply presets), so it
  starts at every log-in.
- **Started on demand:** a D-Bus service file
  (`/usr/share/dbus-1/services/io.github.mamadingleberry.Proccoli.Metrics.service`
  with `SystemdService=proccoli-metrics.service`) means the window's
  first call starts it if it's stopped (for example after `systemctl
  --user stop`).
- **Preferences:** *Record in the Background* goes (it's always on);
  *Start at Boot* stays (lingering); *Recording* stays (status). *Keep
  History* still turns the history off: the collector then sends live
  readings and writes nothing.
- **`install.sh`** does the same for `/usr/local` (global enable,
  D-Bus service file under `$PREFIX/share/dbus-1/services`).

## 5. What it costs and saves

- **Saves:** the window's own device reads (about 1 % of a core at 1 s on
  the laptop, measured for the collector in M75) and its GPU detail
  sources; the window's memory drops by its device code's share.
- **Costs:** the collector runs whenever the user is logged in (15.6
  MiB, ~1 % of a core); a D-Bus signal per update while the window is
  open.
- **Latency:** a reading reaches the window a few milliseconds after
  it's taken; the charts move at the same cadence as now.

## 6. Testing

- **Codec:** every snapshot type round-trips (unit, no display).
- **D-Bus:** the service and `RemoteDeviceManager` on a private bus
  (`Gio.TestDBus`), with the collector built on fixture machines: the
  window side sees the same devices, the same snapshots, additions and
  removals, and a `Readings` signal per tick.
- **The window without the collector:** the banner and *Try Again*;
  reconnecting when the name returns.
- **Pages unchanged:** the existing UI tests run against
  `RemoteDeviceManager` fed by a local collector on a test bus (a
  `make_context(remote=True)` helper), so every page is exercised the new
  way.
- **Static:** nothing in the window's composition (`build_context` for a
  non-demo window) builds a `DeviceManager`, a discoverer or a
  `HistoryStore` that can write.
- **Packaging:** the D-Bus service file and preset installed; `postinst`
  enables globally.

| Step | Create / change | Test |
|---|---|---|
| I19.1 | `core/snapshot_codec.py`: snapshots (and detail samples) to and from `a{sv}`-ready dictionaries | Unit: every type round-trips; unknown fields ignored (a newer collector) |
| I19.2 | `metrics_service.py` (collector side): the D-Bus object, `Devices`, `Subscribe`/`Unsubscribe` (with name watching), `Readings`, `DeviceAdded/Removed`, `Status`, `Detail`; readings only while someone is subscribed | Unit on `Gio.TestDBus`: a subscribed client sees devices and a signal per tick; none once it leaves the bus |
| I19.3 | `devices/remote.py`: `RemoteDeviceManager`, `RemoteMonitor`, `RemoteGpuController`; name watching, activation, the "not receiving" state | Unit on a test bus: same monitors and snapshots as local; device added and removed; the collector going away and coming back |
| I19.4 | `context.build_context`: a remote device manager for the window (local only for `--demo`); `HistoryStore` read-only in the window (M75's writer role and takeover removed from the window) | Static: the window builds no `DeviceManager` or writing store; UI: every existing page test against the remote manager |
| I19.5 | The pages' "Not receiving readings" banner and *Try Again* | UI: with no collector on the test bus, the banner; it clears when one appears |
| I19.6 | Packaging: D-Bus service file, preset, `postinst` global enable (`prerm` unchanged), `install.sh` the same; Preferences: *Record in the Background* removed, *Start at Boot* and *Recording* kept | `test_packaging`; UI: Preferences rows |
| I19.7 | Open questions 1–3, as answered | – |
| I19.8 | Measure the window's processor and memory before and after; README (*Installing*, *Recording in the background* → *How Proccoli records*), [DESIGN §4.2](../../design/04-architecture-overview.md), [Idea 13's design](../../design/ideas/idea-13-record-the-history-in-the-background.md), [Idea 19's design](../../design/ideas/idea-19-the-window-reads-nothing-proccoli-serves.md) as built | Run |

**Done when:** with the window open, only `proccoli-metrics` reads
`/proc` and `/sys` device files (checked with `strace -f -e trace=openat`
on the window: no device files), every page shows what it shows today,
the window opening starts a stopped collector, and closing or killing the
collector shows the banner and recovers when it's back.

**Open questions for the user:**
1. **The process list** (Apps, Processes, the Overview's busiest apps):
   keep it in the window (leaning: it's a view of running programs, not
   a recorded metric; the window needs the processes locally anyway to
   end, pause or reprioritise them; and it costs nothing while those
   pages aren't shown), or move it to the collector too (strictly "no
   reads" in the window, but the collector would read every process
   every second even when nobody looks)?
2. **Intel GPU Details** need administrator rights (`intel_gpu_top`
   through `pkexec`), and the collector can't ask for a password. Drop
   them, keep that one exception in the window (it runs
   `intel_gpu_top` and shows its readings, not recorded), or let an
   administrator grant the collector the capability once (installed
   rule)?
3. **Memory module details** (`dmidecode`, the same kind of exception,
   once per run): same three choices.
