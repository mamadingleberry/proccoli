# Idea 13: Record the history in the background (`proccoli-metrics`)

Design note: [design/ideas/idea-13-record-the-history-in-the-background.md](../../design/ideas/idea-13-record-the-history-in-the-background.md)

*Done as Milestone 75* (its decisions, deviations and measurements are
listed there).

**Status (at design time): designed in full, awaiting review.** This replaces
the first sketch of this idea (same goal; every part is now decided or
listed as an open question). [Idea 13's design](../../design/ideas/idea-13-record-the-history-in-the-background.md) has the diagrams.

**Goal:** the history keeps recording whether or not the window is
open. `proccoli-metrics`, a small process without a window, starts with
the user's session (or at boot), and is then the **only writer** of the
history database. It follows the saved preferences the moment they
change in Preferences. The window keeps working exactly as today when
the collector isn't running.

**Why:** a 1-day or 30-day graph (M74) only has data for the hours the
window was open; the rest is the "not running" bar (M68). People open
Proccoli *after* something went wrong and want to see what happened.

## 1. Scope

| In | Out (for now) |
|---|---|
| Every device reading the window records today (`stats_values`), including GPU detail readings from sources that need no password (AMD, NVIDIA) | The process list (not in the history today; would need a new table and is the biggest cost: *open question 2*) |
| Housekeeping: roll-ups, expiry, the size cap (`HistoryStore` as is) | Intel `intel_gpu_top` details: they need administrator rights, which a background process can't ask for |
| Following *Keep History*, *Maximum Size*, *Keep Every Reading For*, *Update Interval*, the log settings, the device list settings | Serving data to the window or a browser (Idea 16) |
| Turning it on and off from Preferences | A system-wide (root) service |

## 2. How it runs

- **Command:** `proccoli-metrics` (`/usr/bin`), which runs
  `python3 -m proccoli.metrics`: Python, PyGObject and GLib only. It
  **never imports Gtk, Gdk or Adw** (a static test checks the whole
  import graph from `proccoli.metrics`), so it runs with no display.
- **Started by systemd, as the user:** a **user unit**,
  `proccoli-metrics.service`, installed by the package and
  `install.sh` but **disabled** until the user turns it on. The history
  (`~/.local/state/proccoli/`) and the settings (dconf) are per user, so
  a system service running as root couldn't use them.

  ```ini
  [Unit]
  Description=Proccoli: record the history of every reading

  [Service]
  Type=exec
  ExecStart=/usr/bin/proccoli-metrics
  Restart=on-failure
  RestartSec=10
  Nice=10
  IOSchedulingClass=idle

  [Install]
  WantedBy=default.target
  ```

  `default.target` of the user's systemd starts at log-in. **"At boot"**
  is the same unit plus `loginctl enable-linger`, which starts the
  user's systemd (and so the unit) at boot, before anyone logs in, and
  keeps it after they log out.
- **The main loop:** `GLib.MainLoop`; the `Ticker` (already GLib-based)
  drives the `DeviceManager` at the update interval, and the
  `HistoryStore` records each `updated`, as in the window. SIGTERM and
  SIGINT (`GLib.unix_signal_add`) commit what's buffered, end the
  session and quit; `systemctl --user stop` therefore loses nothing.

## 3. What it builds (the composition root)

`context.build_metrics_context(settings, system, sysroot)`: the same
discoverers as the window (`standard_discoverers`), a `DeviceManager`, a
`Ticker`, and a `HistoryStore`. **Not** built: the process monitor, app
icons, the window switcher, the privileged helper (`helper=None`), the
performance log's per-tick timing (it keeps its log lines). A new
profile, `Profile.metrics()`, says so for the parts that read the
profile:

| Flag | Window (full) | Collector |
|---|---|---|
| `gpu_details` | on | on, **never elevated**: a source that needs a password is reported as "needs administrator rights" in the log and skipped (the `gpu-elevate` setting is ignored: there's no one to ask) |
| `app_icons`, `theme_css`, `lazy_pages`, `graph_toolbar` | per profile | off (no UI) |
| `pins` | Lightweight Mode's, if on | **none**: Lightweight Mode is a window profile; the collector always uses the user's real settings |
| `pci_on_demand` | per profile | on (look names up as needed; a long-running process shouldn't keep pci.ids parsed) |

## 4. One writer: the lock

Two processes recording the same readings would double every row and
fight over housekeeping. So exactly one writes, decided by a lock:

- **The lock:** `~/.local/state/proccoli/history.lock`, an exclusive,
  non-blocking `fcntl.flock` (through `System.try_lock(path)`, faked in
  tests). The kernel releases it when its holder exits or crashes, so a
  stale lock can't happen.
- **Whoever holds it writes** (`HistoryStore(role=WRITER)`); everyone
  else is a **reader** (`role=READER`): it opens the database read-only
  (`HistoryDb(readonly=True)`, M62), still **fills graphs from it**
  (backfill, refills on range changes), and records nothing (its
  `record` only remembers clock offsets for backfill).
- **Taking over:** a reader tries the lock again every
  `COMMIT_EVERY_S` (10 s; one system call). When it gets it, it becomes
  the writer: opens the database read-write and starts a session. So
  when the collector stops, the window takes over within 10 s, and when
  the window quits, a waiting collector takes over within 10 s.
- **Who goes first:** whoever starts first. If the window is already
  writing when the collector starts, the collector waits as a reader
  (it has no graphs to fill, so it just retries) until the window quits.
  Nothing is lost: the window records meanwhile. *Open question 5* asks
  whether the window should hand over at once instead.
- **Saying who writes:** the writer stores `meta` `writer` =
  `{"program": "proccoli-metrics" | "proccoli", "pid", "version",
  "since"}` on taking the lock. Preferences reads it to say
  "Recording in the background since 08:12" or "Recording while
  Proccoli is open".
- **Sessions:** only the writer starts and ends sessions. With the
  collector on, the "not running" bar (M68) now means "nothing was
  recording": the machine was off or suspended, or the collector was
  stopped. The hover text changes to "Nothing was recording" when the
  collector is enabled (else it stays "Proccoli wasn't running").

## 5. Following the saved preferences

Both processes read the same dconf keys through `Settings.load()`;
GSettings delivers change notifications to every process that reads a
key, over the session bus, so a change in Preferences reaches the
collector with nothing extra. What each key does there:

| Key | In the collector |
|---|---|
| `history` (*Keep History*) | off: commit, end the session, close the database, keep running idle (so turning it on again resumes at once) |
| `history-max-size`, `history-detail-hours` | applied at the next housekeeping (`_tidy_soon`, as in the window) |
| `update-interval` | the `Ticker` follows it (as in the window) |
| `graph-time-range`, `graph-time-range-custom` | ignored: no graphs (the backfill listeners aren't connected) |
| `log-level`, `log-max-size` | its own log follows them |
| `gpu-details-disabled`, `show-virtual-drives`, `show-virtual-network-interfaces` | the `DeviceManager` and GPU controllers follow them, as in the window |
| `lightweight` and every window-only key | ignored |

At start the collector checks that the installed schema has the keys it
needs (`schema_covers`, as the window does) and exits with a clear log
line if not (an old schema left by a downgrade).

## 6. The window's side

- **`HistoryStore(role)`:** the window starts as today and simply tries
  the lock first; with the collector running it's a reader. Everything
  the user sees stays the same: graphs fill from the history at start
  and on range changes; live points come from the window's own readings
  (both read the same files, so they agree).
- **Export** (*Export Statistics…*) works in both roles: it already
  opens its own read-only connection; a reader skips its own `commit()`
  (the writer commits every 10 s, so an export is at most 10 s behind).
- **Delete History…** in reader mode asks the collector to stop writing
  first: it turns *Keep History* off (the collector closes the database),
  deletes the files, and turns it back on if it was.
- **Preferences → General → *History*:**
  - *Record in the Background* (switch): `systemctl --user enable --now
    proccoli-metrics.service`, or `disable --now`, through
    `System.run_async`; its state comes from `systemctl --user
    is-enabled` and `is-active`, so a change made with `systemctl` shows
    too. Greyed out with a reason when the unit isn't installed or
    there's no user systemd.
  - *Start at Boot* (switch, under it): `loginctl enable-linger` /
    `disable-linger` for the user; state from `loginctl show-user $USER
    --property=Linger`. Its subtitle says it also keeps recording after
    log-out.
  - *Status* (row): who's writing and since when (from `meta`
    `writer`), or why nothing is ("Keep History is off").
- **No settings key** for "record in the background": the unit's
  enabled state is the truth, so there's nothing to get out of sync.

## 7. Command line

| Command | Does |
|---|---|
| `proccoli-metrics` | run (what the unit runs); logs to its own file and the journal |
| `proccoli-metrics --once` | take one reading of every device, print it, write nothing (a quick check that it can read this machine) |
| `proccoli-metrics --status` | who's writing and since when, the database's size and oldest reading, today's sessions; exit code 0 if something is recording |
| `proccoli-metrics --version` | the version |

## 8. Logging

`~/.local/state/proccoli/proccoli-metrics.log` (its own file, so two
processes never rotate one file), same rotation and level as the
window's (`FileLog` with a different name), plus stderr, which systemd
puts in the journal (`journalctl --user -u proccoli-metrics`). One line
on start (version, devices found, role), on each role change, on every
setting it applies, and on stop.

## 9. When things go wrong

| Situation | What happens |
|---|---|
| The database can't be opened or written (disk full, permissions) | logged once; recording stops; it retries at the next housekeeping (10 min) rather than exiting, so systemd doesn't restart-loop |
| A newer schema than it knows (a newer Proccoli wrote it, then a downgrade) | it becomes a reader that never writes, and logs why |
| The collector crashes | the kernel frees the lock; systemd restarts it after 10 s (`Restart=on-failure`); an open window takes over meanwhile if one is running |
| Suspend and resume | a gap in the readings, as today; the session's end stops at the last commit, so the time asleep shows as not recording |
| The clock is set back | as today (`INSERT OR REPLACE` at the same times; roll-ups redo those minutes) |
| A device appears or goes (USB drive, dock) | the `DeviceManager` handles it as in the window |
| The user logs out (no linger) | systemd stops the unit: SIGTERM, commit, session ends |
| No session bus (a broken setup) | settings fall back to defaults with a warning (as `Settings.load` does); it still records, without following changes |

## 10. Cost, and how it's measured

Two processes reading the same devices while the window is open costs a
second set of reads (a few milliseconds per update interval). The
collector alone should be well under the window's memory, since it
loads no GTK. Targets, measured before the milestone is called done
(`tests/ui/mem.py --metrics` and `tests/ui/perf.py --metrics`, new):

- private memory (RssAnon) under a third of the window's (full profile)
  after an hour;
- processor time under 0.5 % of one core at a 1 s update interval on the
  development laptop;
- no growth over a day (`malloc_trim`ed RssAnon flat within 2 MiB).

## 11. Security and privacy

It runs as the user, never as root, reads only what the window reads
without a password, and writes only the user's own 0600 history. It
listens on nothing (Idea 16 would add that, off by default). Turning it
on is the user's choice; the README says plainly that it records while
the window is closed, and how to stop it.

## 12. How it's tested

- **Display-free unit tests** for everything: the lock (two stores on
  one temporary database with a fake `System.try_lock`: only the holder
  writes; the reader backfills; takeover when the holder stops; `meta`
  `writer`), the collector's composition (`build_metrics_context` with
  `FakeSystem` and a fixture `SysRoot`: devices found, no process
  monitor, no helper, detail sources never elevated), the settings
  table above (each key on a shared `Settings.for_tests()` store), the
  command line (`--once` on a fixture root, `--status` on a temporary
  database), signals (a fake `unix_signal_add`).
- **A static test:** nothing reachable from `proccoli.metrics` imports
  Gtk, Gdk, Adw or `proccoli.ui`.
- **An end-to-end run without a display:** `proccoli-metrics` on the
  fixture root for a few seconds with a fake clock, then the window's
  `HistoryStore` as a reader on the same file sees its rows.
- **Packaging:** the unit file is installed where systemd looks
  (`/usr/lib/systemd/user/`, `$PREFIX/lib/systemd/user/`) and passes
  `systemd-analyze --user verify` when that's available.
- **By hand, once:** enable it, close the window, wait an hour, open a
  1-hour graph: no "not running" bar.

| Step | Create / change | Test |
|---|---|---|
| I13.1 | `System.try_lock` / `release_lock`; `core/history_lock.py`; `HistoryStore(role)`: reader mode (read-only, backfill only, retry every 10 s, take over), `meta` `writer` | Unit: the lock cases above; the window as it is today when it gets the lock |
| I13.2 | `Profile.metrics()`; `context.build_metrics_context`; GPU controllers never elevate in it | Unit: what's built and what isn't; an Intel GPU's details reported as needing rights, AMD's started |
| I13.3 | `proccoli/metrics.py`: main loop, signals, `--once`, `--status`, `--version`; its `FileLog` | Unit: start, ticks on a fake clock, SIGTERM: rows written, session closed; `--once` output; `--status` output and exit codes; static: no Gtk reachable |
| I13.4 | Settings follow-through (table in 5); `history` off closes and on resumes; schema check | Unit: each key's effect without a restart |
| I13.5 | `data/proccoli-metrics.service`; `install.sh` and `build-deb.sh` install it and `bin/proccoli-metrics`; README | `test_packaging`: installed paths, unit contents; `systemd-analyze verify` when available |
| I13.6 | Preferences: *Record in the Background*, *Start at Boot*, *Status*; *Delete History…* in reader mode; the hover's "Nothing was recording" | UI: the switches run the right commands (faked) and show the unit's state; greyed out without the unit |
| I13.7 | Measure (section 10): `mem.py --metrics`, `perf.py --metrics` | Run; figures in PLAN |
| I13.8 | [DESIGN §4.1](../../design/04-architecture-overview.md), [§4.2](../../design/04-architecture-overview.md), [§11](../../design/11-cross-cutting-concerns.md), [Idea 13's design](../../design/ideas/idea-13-record-the-history-in-the-background.md) as built; README *Files Proccoli keeps*, *History*, *Uninstalling* (stop the unit) | – |

**Done when:** with *Record in the Background* on, closing the window
and opening it an hour later shows that hour on a 1-hour graph with no
"not running" bar; a change to *Keep History*, *Maximum Size* or *Update
Interval* in Preferences takes effect in the collector without a
restart; only one process ever writes (tested); and the collector meets
the targets in section 10.

**Open questions for the user:**
1. Start at log-in (*Record in the Background* only) or truly at boot
   by default (*Start at Boot* on too)? Boot also records while nobody is
   logged in, and after log-out, which some people won't expect.
2. Should the collector also record the busiest processes ("what was
   using the processor at 3 am")? It's a new table, the largest cost,
   and process names are personal; today only device readings are kept.
3. Should the window take its live readings from the collector (over
   D-Bus) instead of reading the devices too? It saves the second set of
   reads while both run, at the cost of a D-Bus interface and the window
   depending on the collector. *Leaning: not now.*
4. Intel GPU details can't be recorded in the background (they need
   administrator rights). Accept that, or offer an opt-in that grants
   the collector the one capability `intel_gpu_top` needs (a polkit rule
   or `setcap`, installed by an administrator)?
5. When the window is writing and the collector starts, should the
   window hand over at once (a lock request over D-Bus) rather than the
   collector waiting until the window quits? Waiting loses nothing, it
   just means the collector's session starts later.
