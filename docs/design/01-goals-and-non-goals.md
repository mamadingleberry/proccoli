# 1. Goals and non-goals

**Goals**

1. **A system service that records, and a window that shows.** The
   recorder (`proccoli`, a systemd user service with no GUI) reads every
   device, keeps the history in SQLite and serves every reading over
   D-Bus. The window (`proccoli-gui`) reads nothing itself, apart from the
   process tables: it subscribes to the recorder and draws. The two
   install separately, so the recorder runs on a machine without a screen
   ([§4](04-architecture-overview.md),
   [DESIGN_UML.md](DESIGN_UML.md), [DESIGN_DB.md](DESIGN_DB.md)).
2. **A history that keeps going:** readings from before the window
   opened, from boot when asked, summarised as they age and capped in
   size; graphs show any range from seconds to weeks, and exports take
   any of it.
3. **Mirror the Resources experience, then go further:** a sidebar of
   devices, a page per device, Apps and Processes tables and Preferences,
   as in Resources, plus an Overview page, sidebar groups (GPUs, Drives,
   Network, Batteries), back and forward, and a graph toolbar.
4. **Pluggable GPU details:** each GPU's page is chosen at runtime from
   registered backends: a summary source for every GPU, and a vendor
   detail source where one exists (Intel's `intel_gpu_top`, NVIDIA's tools,
   AMD's `amdgpu` statistics). A new vendor is one package and a
   registration line ([§7](07-the-gpu-carve-out.md)).
5. **Highly customisable, and accessible:** styles and palettes (with
   color-blind-safe ones and high contrast), each sidebar entry's parts,
   order, graph type and grouping, the toolbar's buttons, units, and
   Lightweight Mode for small machines.
6. **Light on the machine:** no work for what isn't on screen; the
   window's tables, graphs and pages pause when hidden; the recorder
   stays small.
7. **Testable without real hardware or a display:** every OS access goes
   through injectable seams (`SysRoot`, `System`, clocks), logic lives in
   display-free modules, and UI code has smoke tests on a headless
   display.
8. **Ships in small steps:** work is tracked as Features and Bugs and
   shipped in Releases ([§13](13-features-bugs-and-releases.md)); every
   step ends with a runnable, tested app.

**Directions, not yet planned**

- **A Web UI** served by the recorder on the local machine
  ([Feature 16](features/feature-16-a-web-gui-hosted-locally.md)), then for
  several machines on the local network
  ([Feature 17](features/feature-17-the-web-gui-for-machines-on.md)): the
  recorder already serves every reading, so a browser view is one more
  client.
- **Monitoring Debian machines on the same network:** recorders on each,
  one window or Web UI reading them all, and a machine-wide recorder
  ([Feature 25](features/feature-25-a-recorder-for-the-whole-machine.md))
  for servers.

**Non-goals (for now)**

- NPU pages. Resources has them, but they are out of scope.
- Distributions other than Debian and Ubuntu, and packaging other than
  `.deb` and `install.sh` (Flatpak or Snap would need a sandboxed way to
  read `/proc`, `/sys` and the GPU tools).
- Sending anything off the machine: no telemetry, no cloud. Network
  monitoring, when it comes, stays on the local network.
- Translations, until asked for (the strings are plain, so they can be
  added later).
- Copying Resources' code, icons or name. Proccoli re-implements the UX from
  scratch, because Resources is GPL and Proccoli is 0BSD (see
  [§11](11-cross-cutting-concerns.md), Licensing).
