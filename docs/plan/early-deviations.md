# Deviations from the original plan (Milestones 0–15)

What changed from the first plan while building the first milestones,
and why. Two refactors done between milestones are here too:
*dependency injection* (before M12) and *GPU tabs* (after M15).


- **2.6:** there's no need for `make run` to set `GSETTINGS_SCHEMA_DIR`.
  `Settings.load()` compiles the source checkout's schema into
  `build/schemas/` by itself, so `python3 -m proccoli` works without make.
- **2.8, 3.7:** these depend on Milestone 1's pages and sidebar, which were
  skipped for now. The parts that don't are done. The rest moved to steps
  1.8 and 1.9.
- **1.7:** `tests/run-headless.sh` (a private Broadway display with in-memory
  settings and no D-Bus) was built early, for the M3 widget tests. The
  screenshot harness uses 1024×768 instead of 1280×800, because that's the
  largest screen Broadway offers.
- **1.4:** the primary menu's Preferences, Keyboard Shortcuts and About
  entries are present but greyed out until Milestones 13 and 15 add their
  actions.
- **1.6:** Adwaita has no CPU or memory icons, and Resources' icons are GPL.
  Processor uses `computer-symbolic` and Memory uses `media-flash-symbolic`
  until our own icons arrive in Milestone 15.
- **Added:** a page lifecycle (`ResourcePage.track()` / `shutdown()`, see
  [DESIGN §9](../design/09-ui-layer.md)), so swapped or removed pages disconnect cleanly.
- **4–9, added:** a shared `DevicePage` base (`ui/pages/device.py`) for
  every device page: graph and unit preferences, redraw only while visible,
  sidebar summary, Properties group and an optional banner. `DeviceManager`
  and the demo device move the demo out of the window.
- **6:** the sidebar title of a drive is its type ("Solid State Drive",
  "NVMe Drive", ...), with the model as the description. The generic SCSI
  vendor "ATA" is dropped from model names.
- **7:** manufacturer names come from the system's `pci.ids` (`core/pciids.py`,
  also used for GPU names). Network interfaces have no percentage, so the
  sidebar shows no progress bar for them; the graph meter auto-scales to the
  receive rate (`SidebarSummary.max_value`).
- **8:** on this laptop `perf_event_paranoid` is 4, so intel_gpu_top needs
  administrator rights. As designed, the GPU page doesn't ask for a password
  at start-up: its Details and Processes tabs offer "Show Detailed
  Statistics" instead (originally a banner on a swapped-in summary page,
  see the GPU tabs refactor). The generic backend can only count the user's own
  processes on Intel iGPUs (no `gpu_busy_percent`), and says so on the page.
- **9:** `--demo` adds a synthetic Intel GPU with both data sources (the
  summary one also synthetic), so the detail tabs and their states can be
  seen and tested anywhere. The demo never reads the real system: its GPU uses an
  empty filesystem root (a test guards this).
- **10:** scanning /proc runs only while Apps or Processes is on screen
  (pages `acquire()`/`release()` the `ProcessMonitor`); a full scan of ~330
  processes takes about 20 ms here.
- **Refactor (before M12):** dependency injection by hand.
  - `core/system.py` (`System`) holds every OS call.
  - `context.py` (`build_context` → `AppContext`) is the only place
    services are created.
  - `PageFactory` replaced the `if`-chain.
  - GPU backends receive `GpuDeps`, and `probe(gpu, deps)` replaced
    `probe(gpu, sysroot, which)`.
  - `MainWindow(app, ctx)`, and `Application(context_factory=...)`.
  - `tests/test_static.py` enforces it.
  - DESIGN.md's diagrams were brought back in line with the code ([§4.2](../design/04-architecture-overview.md), [§5](../design/05-core-layer.md),
    [§7](../design/07-the-gpu-carve-out.md), [§8](../design/08-processes-and-apps.md), [§9](../design/09-ui-layer.md)). The planned `ProcessSource`/`HelperSource` split became
    `ProcessMonitor.use_elevated_io()`.
- **12:**
  - The helper refuses PID 1 and its own PID.
  - The polkit policy has one action per subcommand (`exec.argv1`), plus
    `auth_admin` without caching for `intel_gpu_top`, which can write files.
  - From a source checkout, pkexec runs the helper through Python and shows
    its generic prompt.
- **12/13:** the dialogs need libadwaita 1.5 (`Adw.Dialog`), which raises
  the minimum from 1.4. Ubuntu 24.04 ships 1.5.
- **15.1:** our own app icon and Processor and Memory symbolic icons
  replace the stand-ins. `desktop-file-validate` and `appstreamcli` (pedantic)
  pass.
- **15.2:** the `.deb` builds and its contents are checked by tests.
  Installing it in a clean container wasn't possible here.
- **15.4:** measured with `tests/ui/perf.py` (1 s refresh, headless):
  - Processor page: 2.4–3 % of one CPU
  - GPU page: 2.5–2.8 %
  - Processes page: 5–6 %
  - Sampling alone, nothing drawn: about 1 % (2.9 % with the process scan)

  The rest is GTK rendering under Broadway's software renderer. On a real
  desktop it should be lower, but that wasn't measured, so the 2 % target
  is **not confirmed**. Two hot spots were fixed: `SysRoot` built a pathlib
  `Path` per read, and the `fdinfo` fd scan ran twice as often as needed.
- **15.5:** graphs and sidebar rows have accessible labels and
  descriptions. An Orca walkthrough wasn't possible here.
- **Refactor: GPU tabs (after M15).** Swapping the whole GPU page between
  backends lost the overview whenever the detail tool stopped, and hid the
  vendor view behind a menu. Now ([DESIGN §7](../design/07-the-gpu-carve-out.md)):
  - Backends have a role. The SUMMARY source (sysfs/fdinfo) always runs;
    the DETAIL source (intel_gpu_top) is optional, with its own lifecycle
    (`DetailState`: unavailable, off, needs-auth, starting, running,
    failed).
  - One `GpuPage` per GPU, never replaced: an Overview tab plus the detail
    class's `TABS` (Details, Processes), switched from the header (a bottom
    bar below 550sp). Until the source runs, each tab shows a status page
    with Show Detailed Statistics / Try Again / Turn On.
  - `DetailBackend.create_views()` returns `DetailViews` (views plus the
    backend connections feeding them), so the page disconnects stale views
    when the source restarts.
  - Settings: `gpu-backend` became `gpu-details-disabled`, plus `gpu-view`
    and `intel-gpu-top-history`. Preferences has a per-GPU switch.
  - `build_context(gpu_registry=...)` makes the backends injectable.
  - `tests/run-headless.sh` now checks the Broadway daemon really started
    (a stale daemon holding the port made every UI test fail) and removes
    its socket when interrupted.
  - `Settings` rejects a string for an array key (it was stored as a list
    of characters), found by the property tests.
- **11:** this system's cgroups differ from the forms assumed in [DESIGN §8](../design/08-processes-and-apps.md).
  GNOME 49 puts apps in `app-<id>.slice`. Snaps use
  `snap.<name>.<app>-<uuid>.scope`. All forms are handled (see
  `processes/apps.py`). `GioUnix.DesktopAppInfo` is used where available.

---
