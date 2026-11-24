"""How much CPU Proccoli itself uses (PLAN.md step 15.4: under 2 % when idle
at a 1 s refresh). Runs the real services on the headless display:

    tests/run-headless.sh python3 tests/ui/perf.py [SECONDS]

Prints this process's CPU use, as a share of one CPU, per visible page.
"""

from __future__ import annotations

import os
import resource
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib  # noqa: E402

from proccoli.context import build_context  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.ui.window import MainWindow  # noqa: E402


def cpu_seconds() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF)
    return r.ru_utime + r.ru_stime


def run_for(seconds: float) -> None:
    ctx = GLib.MainContext.default()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        ctx.iteration(True)


def main() -> int:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    Adw.init()
    app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.register(None)
    app.hold()
    ctx = build_context(Settings.for_tests({"refresh-speed": "normal"}),
                        helper_command=None)
    ctx.start()
    win = MainWindow(app, ctx)
    win.set_default_size(1024, 768)
    win.present()
    ctx.ticker.start()
    results = {}
    # Proccoli's own sampling, without drawing anything: the window hidden,
    # but the process scan running as if the Processes page were open.
    win.set_visible(False)
    ctx.processes.acquire()
    run_for(2.0)
    t0, c0 = time.monotonic(), cpu_seconds()
    run_for(seconds)
    results["no drawing"] = 100 * (cpu_seconds() - c0) / (time.monotonic() - t0)
    ctx.processes.release()
    win.set_visible(True)
    for page in ("cpu", "processes", "gpu"):
        win.select_page(next(i for i in win.sidebar.order() if i.startswith(page)))
        run_for(2.0)                                  # settle
        t0, c0 = time.monotonic(), cpu_seconds()
        run_for(seconds)
        results[page] = 100 * (cpu_seconds() - c0) / (time.monotonic() - t0)
    ctx.stop()
    for page, pct in results.items():
        print(f"{page:>11}: {pct:5.1f} % of one CPU")
    return 0


if __name__ == "__main__":
    sys.exit(main())
