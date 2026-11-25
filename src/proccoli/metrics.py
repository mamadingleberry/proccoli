"""``proccoli``: record the history in the background.

A process without a window, started by the user's systemd
(``proccoli.service``): it reads every device at the *Update
Interval* and writes the history database, holding ``history.lock`` so it
is the only writer (the window reads, and takes over when it stops). It
follows the saved preferences live (dconf tells it of changes), never
asks for a password, and never imports Gtk.

    proccoli run (what the unit runs)
    proccoli --once read every device once, print it, write nothing
    proccoli --status who's recording, since when, and the database
    proccoli --watch print each update the running collector sends
    proccoli --version

Everything that touches the system is injected (``run(..., context=,
loop=, signals=)``), so tests drive it without a display or a real clock.
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Callable, Optional, Sequence

from . import COLLECTOR, __version__

log = logging.getLogger("proccoli.metrics")

PROGRAM = COLLECTOR
LOG_NAME = f"{COLLECTOR}.log"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=PROGRAM, description="Record Proccoli's history in the background.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    what = parser.add_mutually_exclusive_group()
    what.add_argument("--once", action="store_true",
                      help="read every device once, print it, and write nothing")
    what.add_argument("--status", action="store_true",
                      help="say who's recording, since when, and how big the history is")
    what.add_argument("--watch", action="store_true",
                      help="print each update the running collector sends (Ctrl+C stops)")
    parser.add_argument("--debug", action="store_true", help="log debugging to stderr")
    return parser.parse_args(argv)


def metrics_settings(settings=None):
    """The user's real settings (dconf) under ``Profile.metrics()``."""
    from .core.profile import Profile, profile_settings
    from .core.settings import Settings
    return profile_settings(settings or Settings.load(), Profile.metrics())


# -- --once ---------------------------------------------------------------------------


def read_once(context, sleep: Callable[[float], None] = time.sleep,
              clock: Callable[[], float] = time.monotonic) -> dict:
    """Every device's readings: two samples an update interval apart (rates
    need two). ``{device id: {"name", "readings": {name: [value, unit]}}}``."""
    from .core.ticker import update_interval_ms
    devices = context.devices
    devices.start()                       # discover, without the ticker
    devices.refresh(clock())
    sleep(update_interval_ms(context.settings) / 1000)
    devices.refresh(clock())
    out = {}
    for monitor in devices.monitors():
        snap = monitor.latest
        if snap is None:
            continue
        units = snap.stats_units()
        out[monitor.info.id] = {
            "name": monitor.info.name,
            "readings": {k: [v, units.get(k, "")] for k, v in snap.stats_values().items()
                         if v is not None}}
    return out


# -- --status ---------------------------------------------------------------------------


def status(history_path: Path, system, now_s: Optional[float] = None) -> tuple[int, str]:
    """``(exit code, text)``: 0 when something is recording."""
    from .core.history_db import HistoryDb, files_size
    from .core.history_lock import HistoryLock, lock_path
    from .core.units import iso_utc
    now_s = time.time() if now_s is None else now_s
    lock = HistoryLock(system, lock_path(history_path))
    recording = not lock.acquire()
    lock.release()
    lines = [f"History: {history_path}"]
    if not history_path.exists():
        lines.append("Nothing recorded yet.")
        return (0 if recording else 1), "\n".join(lines)
    db = HistoryDb(history_path, readonly=True)
    try:
        writer = json.loads(db.meta("writer") or "null")
        sessions = db.sessions()
        oldest = min((s for s, _ in sessions), default=None)
    finally:
        db.close()
    if recording and writer:
        lines.append(f"Recording: by {writer.get('program', '?')} {writer.get('version', '')} "
                     f"(process {writer.get('pid', '?')}) since "
                     f"{iso_utc(writer.get('since', 0) / 1000)}")
    elif recording:
        lines.append("Recording.")
    else:
        lines.append("Not recording: neither proccoli nor the window is running.")
    from .core.units import Base, format_bytes
    lines.append(f"Size on disk: {format_bytes(files_size(history_path), Base.BINARY)}")
    if oldest is not None:
        lines.append(f"Oldest recording: {iso_utc(oldest / 1000)}")
    day_ago = (now_s - 86400) * 1000
    lines.append(f"Runs in the last day: {sum(1 for _, end in sessions if end >= day_ago)}")
    return (0 if recording else 1), "\n".join(lines)


# -- running ------------------------------------------------------------------------------


class Collector:
    """The running collector: the devices, the history store and the loop.
    ``start`` begins recording, ``stop`` writes everything out."""

    def __init__(self, context, history_path: Path, *, wall_clock=time.time,
                 idle=None, bus=None, import_dir=None) -> None:
        """``bus``: a ``Gio.DBusConnection`` to serve readings on (tests);
        None: the session bus; False: don't serve. ``import_dir``: Milestone
        58's statistics files, imported once by the writer."""
        from .core.history_lock import HistoryLock, lock_path
        from .core.history_store import HistoryStore
        self.context = context
        self.lock = HistoryLock(context.system, lock_path(history_path))
        self.store = HistoryStore(context.devices, context.settings, history_path,
                                  __version__, wall_clock=wall_clock, idle=idle,
                                  lock=self.lock, program=PROGRAM, graphs=False,
                                  import_dir=import_dir)
        self.bus = bus
        self.service = None

    def start(self) -> None:
        self.context.start()
        devices = [m.info.id for m in self.context.devices.monitors()]
        log.info("%s %s started: %d devices (%s)", PROGRAM, __version__, len(devices),
                 ", ".join(devices))
        self.store.open()
        log.info("recording: %s", "writing the history" if self.store.writer
                 else "another process writes it; waiting to take over")
        if self.bus is not False:
            # Every reading, for the window.
            from .metrics_service import MetricsService
            self.service = MetricsService(self.context.devices, self.context.ticker,
                                          self.store, self.context.settings)
            self.service.start(self.bus)

    def stop(self) -> None:
        if self.service is not None:
            self.service.stop()
        self.store.shutdown()                 # commits, ends the session, frees the lock
        self.context.stop()
        log.info("%s stopped", PROGRAM)


def run(context=None, history_path: Optional[Path] = None, loop=None,
        signals: Optional[Callable] = None, file_log=None, bus=None) -> int:
    """Record until SIGTERM or SIGINT. Everything is injectable."""
    from gi.repository import GLib
    from .context import build_metrics_context
    from .core.history_store import history_path as default_history_path, old_stats_dir
    if context is None:
        context = build_metrics_context(metrics_settings())
    collector = Collector(context, history_path or default_history_path(),
                          idle=GLib.idle_add, bus=bus,
                          import_dir=None if history_path else old_stats_dir())
    loop = loop or GLib.MainLoop()

    def quit_loop(*_a) -> bool:
        log.info("stopping on a signal")
        loop.quit()
        return False

    add_signal = signals or (lambda sig, cb: GLib.unix_signal_add(
        GLib.PRIORITY_DEFAULT, sig, cb))
    for sig in (signal.SIGTERM, signal.SIGINT):
        add_signal(sig, quit_loop)
    collector.start()
    try:
        loop.run()
    finally:
        collector.stop()
        if file_log is not None:
            file_log.shutdown()
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    level = logging.DEBUG if args.debug else logging.INFO
    # stderr goes to the journal under systemd.
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    # stderr keeps this level even when the log file records more.
    for handler in logging.getLogger().handlers:
        handler.setLevel(level)
    from .core.history_store import history_path
    from .core.system import System
    if args.status:
        code, text = status(history_path(), System())
        print(text)
        return code
    if args.watch:
        from .metrics_service import watch
        try:
            return 0 if watch(lambda line: print(line, flush=True)) else 1
        except KeyboardInterrupt:
            return 0
    from .context import build_metrics_context
    context = build_metrics_context(metrics_settings())
    if args.once:
        for device_id, info in read_once(context).items():
            print(f"{device_id} ({info['name']})")
            for name, (value, unit) in sorted(info["readings"].items()):
                print(f"  {name}: {value:g} {unit}".rstrip())
        context.stop()
        return 0
    from .core.applog import FileLog, log_path
    file_log = FileLog(context.settings, log_path().with_name(LOG_NAME))
    return run(context, file_log=file_log)


if __name__ == "__main__":
    sys.exit(main())
