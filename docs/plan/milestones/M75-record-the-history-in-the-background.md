# Milestone 75: Record the history in the background

*✅ Done.* Was Idea 13. `proccoli-metrics`, a systemd user service without Gtk, writes the history while the window is closed; `history.lock` makes one process the writer, the other reads and takes over within 10 s; Preferences turns it on (and *Start at Boot*) and says who's recording. Fixes Bug 6 (fdinfo read twice per update). 15.6 MiB private memory, 1.1 % of one core on the Ryzen 3 4300U

Was Idea 13 (its full design is kept below). Steps I13.1–I13.8 as
designed, with the deviations and findings listed after the table.

| Step | Create / change | Test |
|---|---|---|
| 75.1 | `System.try_lock` / `release_lock` (`flock`, 0600); `core/history_lock.py`; `HistoryStore(lock, program, graphs)`: writer or reader, retry and take over at each commit, `meta` `writer`, `session_start()`, a deleted file restarts, a newer schema (`HistoryDb.NewerSchema`) never writes | Unit: only the holder writes; the reader fills graphs; takeover after the writer stops (2 sessions); a reader exports the writer's run; *Delete History…* from a reader; schema 99 refused and the lock let go; the real `flock` |
| 75.2 | `Profile.metrics()` (`gpu_elevate=False`, no pins); `profile_settings` carries any non-full profile; `context.MetricsContext` and `build_metrics_context`; `GpuController`: sources that need a password stay off without asking | Unit: what's built; the Intel GPU's details off with "need administrator rights" and no `pkexec`; the Renoir APU's AMD details running; the ticker started by `start()` |
| 75.3 | `proccoli/metrics.py`: `Collector`, `run` (SIGTERM / SIGINT), `--once`, `--status`, `--version`; its log `proccoli-metrics.log` | Unit: a run on a fake loop writes every reading, `meta` `writer`, a closed session, the lock freed; `--once` and `--status`; a fresh interpreter building and refreshing the collector loads no Gtk, Gdk, Adw or `proccoli.ui` |
| 75.4 | Settings follow-through: nothing new needed (the store, the ticker and the device manager already follow their keys; the collector's store skips graph keys) | Covered by 75.1–75.3 |
| 75.5 | `data/proccoli-metrics.service`; `install.sh` installs it and `bin/proccoli-metrics` (and removes them, disabling the unit globally); `build-deb.sh` through `install.sh` | `test_packaging`: paths for `/usr` and `/usr/local`, the unit's `ExecStart`, the deb's contents; `systemd-analyze --user verify` reports only the staged `ExecStart` path |
| 75.6 | `core/background.py` (`systemctl --user`, `loginctl` through `System.run_async`); Preferences → *History*: *Record in the Background*, *Start at Boot*, *Recording*; `Application` passes it (not in `--demo`); the window's store takes the lock | Unit: parsing, the commands, without systemctl or the unit, the status lines; UI: the switches run the commands and follow the answers; greyed out without the unit |
| 75.7 | Measured (below) | Run |
| 75.8 | README (*Recording in the background*, *Preferences*, *Files*, *Uninstalling*); [DESIGN §4.1](../../design/04-architecture-overview.md), [§4.2](../../design/04-architecture-overview.md), [Idea 13's design](../../design/ideas/idea-13-record-the-history-in-the-background.md) as built, [Bug 6's design](../../design/bugs/bug-06-an-amd-gpu-s-fdinfo-was.md) | – |

**Decisions on Idea 13's open questions** (the design's leanings):
(1) log-in by default; *Start at Boot* is a second switch; (2) no process
list; (3) the window keeps its own live readings; (4) Intel details
aren't recorded in the background; (5) a collector started while the
window writes waits for the window to quit.

**Deviations from Idea 13, and why:**
- **The "not running" hover text stays "Proccoli wasn't running":** the
  collector is part of Proccoli, so it's still true; a second wording
  added nothing.
- **No `mem.py --metrics` / `perf.py --metrics`:** the collector was
  measured directly (RssAnon and `/proc/<pid>/stat` over two minutes,
  twice), which is simpler and what those options would have done.
- **The deb has no maintainer scripts yet:** removing the package leaves
  an enabled user's `default.target.wants` link pointing at nothing
  (harmless: systemd skips it). Idea 15's packaging adds the scripts.

**Measured** on the Ryzen 3 4300U laptop, 7 devices including the AMD
APU's Details source, 1 s update interval, two runs of two minutes:
private memory (RssAnon) **15.6 MiB** (the window's full profile: 78–90
MiB at start, M66), flat over the run; processor time **1.33 %** of one
core before Bug 6's fix, **1.08–1.09 %** after. **The 0.5 % target is
missed:** about half of each update is the GPU's per-process `fdinfo`
reads (every process's GPU clients, needed for the AMD engine charts and
per-app GPU use), the rest sysfs reads and the commit. Reading `fdinfo`
less often in the collector (every few updates) would halve it, at the
cost of coarser engine history; left as a choice for the user.

*Found while doing 75:*
- **Bug 6** (below): each update read every process's `fdinfo` twice
  for an AMD GPU, once for its summary and once for its Details tab, in
  the window too. Fixed here.
- **The first real run recorded nothing:** `MetricsContext.start()`
  didn't start the ticker (the window starts its own when it shows), and
  the unit test had driven `refresh()` itself. Fixed, with a test where
  only the ticker reads.
- **Export as a reader:** a reader has no session of its own, so
  *Export Statistics…* would have said "Nothing has been recorded yet";
  it now exports the run the writer is recording (`session_start`).
- **The no-Gtk check under the headless runner:** `tests/helpers.py`
  installs the UI's CSS when `PROCCOLI_UI_TESTS=1`, so the check runs
  its interpreter without that variable.
