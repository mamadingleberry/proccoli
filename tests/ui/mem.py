"""How much private memory Proccoli uses, in the full and the lightweight
profile (Lightweight Mode, Idea 1, steps L.1 and L.11). Each profile runs
in a fresh process with the real services on the headless display:

    tests/run-headless.sh python3 tests/ui/mem.py [--after SECONDS]

Reports RssAnon (anonymous resident memory: Python's and GTK's own, not
the shared libraries) after start, after visiting every page, and after
waiting (long enough for lightweight pages to be dropped again).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))


def rss_anon_mib() -> float:
    with open("/proc/self/status", encoding="ascii") as f:
        for line in f:
            if line.startswith("RssAnon:"):
                return int(line.split()[1]) / 1024
    return 0.0


def run_for(seconds: float) -> None:
    from gi.repository import GLib
    ctx = GLib.MainContext.default()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        ctx.iteration(False) or time.sleep(0.01)


def measure(profile_name: str, after: float, drop_s: int) -> None:
    import dataclasses
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gio
    from proccoli.context import build_context
    from proccoli.core.profile import Profile, profile_settings
    from proccoli.core.settings import Settings
    from proccoli.ui.window import MainWindow

    Adw.init()
    app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.register(None)
    app.hold()
    profile = Profile.lightweight() if profile_name == "lightweight" else Profile.full()
    profile = dataclasses.replace(profile, page_drop_s=drop_s)
    settings = profile_settings(Settings.for_tests(), profile)
    ctx = build_context(settings, helper_command=None)
    ctx.start()
    win = MainWindow(app, ctx)
    win.set_default_size(1024, 768)
    win.present()
    ctx.ticker.start()
    run_for(5.0)
    rows = [("started", rss_anon_mib())]
    for page_id in win.sidebar.order():
        win.select_page(page_id)
        run_for(2.0)
        if os.environ.get("MEM_PER_PAGE"):
            print(f"# {profile_name} {page_id} {rss_anon_mib():.1f}", file=sys.stderr)
    win.show_overview()
    run_for(2.0)
    rows.append(("every page visited", rss_anon_mib()))
    run_for(after)
    rows.append((f"{after:.0f} s later", rss_anon_mib()))
    import ctypes
    import gc
    gc.collect()
    ctypes.CDLL("libc.so.6").malloc_trim(0)
    run_for(1.0)
    rows.append(("after gc + malloc_trim", rss_anon_mib()))
    ctx.stop()
    for label, mib in rows:
        print(f"{profile_name}\t{label}\t{mib:.1f}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--after", type=float, default=30.0)
    parser.add_argument("--drop", type=int, default=10,
                        help="seconds before lightweight drops a page (60 in the app)")
    parser.add_argument("--profile", choices=("full", "lightweight"))
    args = parser.parse_args()
    if args.profile:
        measure(args.profile, args.after, args.drop)
        return 0
    results = {}
    for name in ("full", "lightweight"):
        out = subprocess.run([sys.executable, __file__, "--profile", name,
                              "--after", str(args.after), "--drop", str(args.drop)],
                             capture_output=True, text=True, check=True).stdout
        for line in out.splitlines():
            if line.count("\t") == 2:
                profile, label, mib = line.split("\t")
                results.setdefault(label, {})[profile] = float(mib)
    print(f"{'RssAnon (MiB)':<22}{'full':>8}{'lightweight':>13}{'saved':>8}")
    for label, by in results.items():
        full, light = by.get("full", 0), by.get("lightweight", 0)
        saved = 100 * (full - light) / full if full else 0
        print(f"{label:<22}{full:>8.1f}{light:>13.1f}{saved:>7.0f} %")
    return 0


if __name__ == "__main__":
    sys.exit(main())
