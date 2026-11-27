"""Screenshot harness: renders the main window in several layouts to PNGs.

Run it on the private headless display (``make ui-test`` does this):

    tests/run-headless.sh python3 tests/ui/shoot.py [OUTDIR [SCENE...]] [--real]

Writes OUTDIR/<scene>.png (default OUTDIR: tests/ui/out); with SCENE
names, only those. Demo scenes use
synthetic data. ``--real`` adds scenes of this machine's own devices and
processes; those images show your hardware and process names, so they're
not for sharing. Broadway's screen is 1024×768, the largest scene size.
"""

from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Graphene", "1.0")
from gi.repository import Adw, Gdk, Gio, GLib, Graphene, Gtk  # noqa: E402

from proccoli.context import build_context  # noqa: E402
from proccoli.core.profile import Profile, profile_settings  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.ui.style import ThemeCss, add_source_icons, install_css  # noqa: E402
from proccoli.ui.theme import Theme  # noqa: E402
from proccoli.ui.window import MainWindow  # noqa: E402

# name: (width, height, page (ID prefix), settings overrides,
# True to open the overlaid sidebar, or a dialog to show)
SCENES = {
    "wide-demo": (1024, 768, "demo", {}, False),
    "wide-overview": (1024, 768, "overview", {}, False),
    "wide-sidebar-hidden": (1024, 768, "demo", {"sidebar-shown": False}, False),
    "wide-sidebar-icons": (1024, 768, "demo", {"sidebar-style": "icons"}, False),
    "narrow-sidebar-icons": (700, 600, "demo", {"sidebar-style": "icons"}, True),
    "portrait-overview": (480, 768, "overview", {}, False),
    # Lightweight Mode's Overview (small charts) and icons-only sidebar.
    "lightweight-overview": (1024, 768, "overview", {"_lightweight": True}, False),
    "wide-progress-meters": (1024, 768, "demo",
                             {"sidebar-meter-type": "progress-bar", "show-graph-grids": True},
                             False),
    "wide-placeholder": (1024, 768, "cpu", {}, False),
    # the graph toolbar with every item, wide and narrow (it scrolls).
    "toolbar-all-items": (1024, 768, "demo", {"show-graph-grids": True}, False),
    "narrow-toolbar": (500, 600, "demo", {}, False),
    # a custom 3-day range (axes in days; the toolbar names it).
    "custom-range-3-days": (1024, 768, "demo", {"graph-time-range": "custom",
                                                "graph-time-range-custom": 3 * 86400,
                                                "show-graph-grids": True}, False),
    # Graph Grid reaches every chart: the Overview cards and sidebar meters too.
    "overview-grids": (1024, 768, "overview", {"show-graph-grids": True}, False),
    "demo-gpu-overview": (1024, 768, "gpu", {"gpu-view": "overview"}, False),
    "demo-gpu-details": (1024, 768, "gpu", {"gpu-view": "details"}, False),
    "demo-gpu-processes": (1024, 768, "gpu", {"gpu-view": "processes"}, False),
    # the demo AMD APU (the second GPU), its Details and Overview tabs.
    "demo-amd-details": (1024, 768, "gpu", {"gpu-view": "details", "_pick": "last"}, False),
    "demo-amd-overview": (1024, 768, "gpu", {"gpu-view": "overview", "_pick": "last"}, False),
    "demo-gpu-details-off": (1024, 768, "gpu", {"gpu-view": "details",
                                                "gpu-details-disabled": ["0000:00:02.0"]},
                             False),
    "narrow-gpu-details": (500, 600, "gpu", {"gpu-view": "details"}, False),
    "narrow-demo": (700, 600, "demo", {}, False),
    "narrow-sidebar-open": (700, 600, "demo", {}, True),
    "minimum": (360, 300, "demo", {}, False),
    # Portrait: graphs capped by width, pairs stacked.
    "portrait-demo": (480, 768, "demo", {}, False),
    "portrait-gpu-details": (480, 768, "gpu", {"gpu-view": "details"}, False),
    "dialog-preferences": (1024, 768, "demo", {}, "preferences"),
    # Each page of Preferences.
    **{f"preferences-{page}": (1024, 768, "demo", {}, f"preferences:{page}")
       for page in ("appearance", "sidebar", "tables", "recording", "devices", "system")},
    "dialog-about": (1024, 768, "demo", {}, "about"),
    # Lightweight Mode's Preferences: the notice, padlocks on fixed settings.
    "lightweight-preferences": (1024, 768, "overview", {"_lightweight": True}, "preferences"),
    "palette-tango-light": (1024, 768, "gpu", {"palette": "tango", "color-scheme": "light",
                                              "gpu-view": "details"}, False),
    "style-nord-okabe-ito": (1024, 768, "demo", {"color-scheme": "nord",
                                                 "palette": "okabe-ito"}, False),
    "style-high-contrast-light": (1024, 768, "demo", {"color-scheme": "high-contrast-light",
                                                      "palette": "tol-bright"}, False),
    "style-gruvbox-dark": (1024, 768, "demo", {"color-scheme": "gruvbox-dark",
                                               "palette": "gruvbox"}, False),
    "palette-solarized-dark": (1024, 768, "demo", {"palette": "solarized",
                                                   "color-scheme": "dark"}, False),
    # a stretch the history filled in for a time Proccoli wasn't running.
    "offline-light": (1024, 768, "demo", {"_offline": True, "color-scheme": "light"}, False),
    "offline-dark": (1024, 768, "demo", {"_offline": True, "color-scheme": "dark"}, False),
    "offline-nord-dark": (1024, 768, "demo", {"_offline": True, "palette": "nord",
                                              "color-scheme": "dark"}, False),
    "palette-nord-dark-prefs": (1024, 768, "demo", {"palette": "nord", "color-scheme": "dark"},
                                "preferences"),
}
REAL_SCENES = {
    f"real-{page}": (1024, 768, page, {"show-logical-cpus": page == "cpu",
                                       "auth-at-launch": False}, False)
    for page in ("overview", "apps", "processes", "cpu", "memory", "drive", "net", "gpu")
}
# The Processor's total chart: the same area as real-cpu's per-CPU chart.
REAL_SCENES["real-cpu-total"] = (1024, 768, "cpu", {"auth-at-launch": False}, False)
# The last GPU (on a hybrid laptop, the discrete one: NVIDIA's tabs).
REAL_SCENES["real-gpu-last-details"] = (1024, 768, "gpu", {"auth-at-launch": False,
                                                           "_pick": "last",
                                                           "gpu-view": "details"}, False)
REAL_SCENES["real-gpu-last-overview"] = (1024, 768, "gpu", {"auth-at-launch": False,
                                                            "_pick": "last"}, False)
REAL_SCENES["real-lightweight-overview"] = (1024, 768, "overview",
                                            {"auth-at-launch": False, "_lightweight": True},
                                            False)
REAL_SCENES["real-overview-tables"] = (1024, 768, "overview",
                                       {"auth-at-launch": False, "_scroll": "end"}, False)
REAL_SCENES["real-overview-portrait"] = (480, 768, "overview",
                                         {"auth-at-launch": False, "_scroll": "end",
                                          "overview-top-by": "memory"}, False)


def pump(seconds: float) -> None:
    ctx = GLib.MainContext.default()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while ctx.pending():
            ctx.iteration(False)
        time.sleep(0.01)


def snapshot(win: Gtk.Window, path: str, widget=None) -> bool:
    """Render the window (or ``widget``, e.g. a dialog) to a PNG. The whole
    window, not just its content: the window draws the page background,
    which a dark style needs."""
    widget = widget or win
    # Headless frames are slow: right after a page switch the widget may
    # have nothing painted yet. Wait for it (up to 3 s) instead of failing.
    node = None
    for _attempt in range(12):
        w, h = widget.get_width(), widget.get_height()
        if w > 0 and h > 0:
            snap = Gtk.Snapshot()
            Gtk.WidgetPaintable(widget=widget).snapshot(snap, w, h)
            node = snap.to_node()
            if node is not None:
                break
        pump(0.25)
    if node is None:
        return False
    rect = Graphene.Rect()
    rect.init(0, 0, w, h)
    win.get_renderer().render_texture(node, rect).save_to_png(path)
    return True


def add_earlier_run(ctx) -> None:
    """What the history database would put in front of the demo's graphs:
    an earlier run, then a stretch Proccoli wasn't running."""
    import math
    for monitor in ctx.devices.monitors():
        h = monitor.history
        room = h.room()
        if room < 10 or not h.times:
            continue
        step = h.step_s or 1.0
        times = [h.times[0] - step * k for k in range(room, 0, -1)]
        recorded = room * 2 // 5
        values = {name: [40 + 25 * math.sin(i / 4) if i < recorded else None
                         for i in range(room)] for name, _unit in h.keys()}
        h.backfill(times, values, [i >= recorded for i in range(room)])


def shoot(app: Adw.Application, name: str, scene, outdir: str, real: bool = False) -> bool:
    width, height, page, overrides, sidebar_open = scene
    overrides = dict(overrides)
    scroll_end = overrides.pop("_scroll", None) == "end"   # shoot the bottom of the page
    pick_last = overrides.pop("_pick", None) == "last"     # e.g. a second GPU
    offline = overrides.pop("_offline", False)             # an earlier run, then a gap
    lightweight = overrides.pop("_lightweight", False)     # Lightweight Mode's profile
    if offline:
        overrides.setdefault("graph-time-range", "2-minutes")
    settings = Settings.for_tests({"graph-time-range": "30-seconds", **overrides})
    if lightweight:
        settings = profile_settings(settings, Profile.lightweight())
    # Demo scenes never touch the system; --real ones use the real services,
    # minus the privileged helper (nothing here should prompt).
    ctx = build_context(settings, demo=not real, helper_command=None)
    ctx.theme = Theme(settings, Adw.StyleManager.get_default())   # as Application does
    theme_css = ThemeCss(ctx.theme)
    ctx.start()
    ticker = ctx.ticker
    if not real:
        # Demo scenes tick 4 times a second so a stretch of graph draws in
        # a few seconds (faster than any Update Interval; screenshots only).
        # Real processes need 1 s samples: at 250 ms most use under a tick.
        ticker.set_interval(250)
    win = MainWindow(app, ctx)
    win.set_default_size(width, height)
    matches = [i for i in win.sidebar.order() if i.startswith(page)]
    win.select_page(matches[-1] if pick_last else matches[0])
    win.present()
    ticker.start()
    pump(6.0)                       # let the demo draw a stretch of graph
    if offline:
        add_earlier_run(ctx)
    if sidebar_open is True:
        win.split_view.set_show_sidebar(True)
        pump(0.6)                   # overlay animation
    elif sidebar_open:              # a dialog's name
        from proccoli.devices.base import DeviceKind
        from proccoli.ui.dialogs.about import about_dialog
        from proccoli.ui.dialogs.preferences import PreferencesDialog
        kind, _, prefs_page = sidebar_open.partition(":")
        dialog = (PreferencesDialog(settings, ctx.devices.monitors(DeviceKind.GPU), ctx.theme)
                  if kind == "preferences" else about_dialog())
        if prefs_page:
            dialog.set_visible_page(dialog.pages[prefs_page])
        dialog.present(win)
        pump(0.8)
    shown = dialog if sidebar_open not in (True, False) else None
    # Headless Broadway produces about one frame per second (no browser is
    # connected), and list views re-bind their rows only during a frame's
    # layout, so table rows in these images can lag behind the data (the
    # Processes scene often shows its first sort). Graphs are drawn at
    # snapshot time and are current. test_ui_tables checks the real wiring.
    if scroll_end:
        visible = win.page(win.visible_page_id())
        adj = visible.scroller.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())
    win.get_frame_clock().request_phase(Gdk.FrameClockPhase.LAYOUT)
    pump(1.5)
    # Broadway sometimes hands back an empty render node (seemingly when the
    # snapshot races a frame); retrying for a few seconds always gets one.
    ok = False
    for _ in range(25):
        ok = snapshot(win, os.path.join(outdir, f"{name}.png"), shown)
        if ok:
            break
        pump(0.3)
    size = f"{win.get_width()}×{win.get_height()}"
    ctx.stop()
    win.close()
    win.destroy()
    theme_css.shutdown()
    ctx.theme.shutdown()
    print(f"{'ok  ' if ok else 'FAIL'} {name} ({size})", flush=True)
    return ok


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--real"]
    real = "--real" in sys.argv
    outdir = args[0] if args else os.path.join(HERE, "out")
    os.makedirs(outdir, exist_ok=True)
    Adw.init()
    install_css()
    add_source_icons()
    app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.register(None)
    app.hold()
    for name in ("about", "preferences", "shortcuts"):   # as Application has them
        app.add_action(Gio.SimpleAction.new(name, None))
    only = set(args[1:])
    results = [shoot(app, name, scene, outdir) for name, scene in SCENES.items()
               if not only or name in only]
    if real:
        results += [shoot(app, name, scene, outdir, real=True)
                    for name, scene in REAL_SCENES.items() if not only or name in only]
    print(f"screenshots in {outdir}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
