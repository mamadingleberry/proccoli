"""Device pages. Headless display only (``make ui-test``)."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from helpers import FIXTURES, LAPTOP, FakeRoot, FakeSystem, make_context, resize_or_skip  # noqa: E402

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from proccoli.core import pciids  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.ticker import history_points  # noqa: E402
from proccoli.core.sysroot import SysRoot  # noqa: E402

HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()
if HAVE_DISPLAY:
    Adw.init()
    from proccoli.ui.pages.factory import standard_page_factory
    from proccoli.ui.window import MainWindow

PCI = pciids.load(os.path.join(FIXTURES, "pci", "pci.ids"))


class _RealStreams(FakeSystem):
    """Fake OS, but real (threaded) stream readers: the demo GPU's generator."""

    def stream_reader(self):
        from proccoli.core.runner import StreamReader
        return StreamReader()


def pump(until=lambda: False, timeout=2.0):
    ctx = GLib.MainContext.default()
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        while ctx.pending():
            ctx.iteration(False)
        if until():
            return True
        time.sleep(0.01)
    return until()


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class LaptopPagesTest(unittest.TestCase):
    """Pages built from the laptop fixture, ticked twice so deltas exist."""

    def setUp(self):
        self.settings = Settings.for_tests()
        ctx = make_context(self, settings=self.settings, sysroot=SysRoot(LAPTOP))
        self.devices = ctx.devices
        self.devices.start()
        factory = standard_page_factory(ctx)
        self.pages = {m.info.id: factory.create(m) for m in self.devices.monitors()}
        self.devices.refresh(1.0)
        self.devices.refresh(2.0)   # fixture files don't change: zero rates

    def test_all_pages_built(self):
        self.assertEqual(set(self.pages), {"cpu", "memory", "gpu-0000:00:02.0", "drive-sda",
                                           "net-eno1", "net-wlp43s0"})

    def test_every_device_page_has_a_sidebar_chart(self):
        for page_id, page in self.pages.items():
            summary = page.sidebar_summary()
            self.assertTrue(summary.series, page_id)
            for series in summary.series:
                self.assertTrue(series.values, page_id)              # filled by the ticks
        net = self.pages["net-eno1"].sidebar_summary()
        self.assertEqual([s.name for s in net.series], ["rx", "tx"])  # receive and send
        self.assertIsNone(net.max_value)                              # auto-scaled
        self.assertEqual(self.pages["cpu"].sidebar_summary().max_value, 100.0)

    def test_cpu_page(self):
        page = self.pages["cpu"]
        self.assertEqual(page.title, "Processor")
        self.assertEqual(page.description, "12th Gen Intel(R) Core(TM) i5-12450H")
        # One chart, a line and a legend item per logical CPU.
        self.assertEqual(len(page.threads.graph.series), 12)
        self.assertEqual([i.name for i in page.legend.items], [f"CPU {i}" for i in range(12)])
        self.assertFalse(page.threads.graph.fill)
        page.update_labels(page.monitor.latest)           # normally on each tick
        colors = {page.threads.graph.color_for(i) for i in range(12)}
        self.assertEqual(len(colors), 12)                 # every line its own color
        # Unchanging fixture files: no busiest CPU yet, but the count shows.
        self.assertEqual(page.threads.pane.info_label.get_label(), "12 logical CPUs")
        from proccoli.core.units import NO_DATA
        self.assertEqual({i.value_label.get_label() for i in page.legend.items}, {NO_DATA})
        self.assertTrue(page.sensors.get_visible())        # coretemp present
        self.assertEqual(page.property_rows["Physical Cores"].get_value(), "8")
        self.settings.set("show-logical-cpus", True)
        self.assertEqual(page.usage_stack.get_visible_child_name(), "logical")
        self.assertTrue(page.logical_switch.get_active())
        # The toolbar has the switch; the page's own row shows only without it.
        self.assertFalse(page.options.get_visible())
        self.settings.set("show-toolbar", False)
        self.assertTrue(page.options.get_visible())
        self.settings.set("show-toolbar", True)
        self.assertFalse(page.options.get_visible())
        self.settings.set("temperature-unit", "fahrenheit")
        self.assertTrue(page.temperature.pane.info_label.get_label().endswith("°F"))

    def test_processor_and_gpu_cards_get_their_readings(self):
        # the Overview cards' readings line comes from the summary.
        cpu = self.pages["cpu"].sidebar_summary()
        self.assertEqual(len(cpu.facts), 1)
        self.assertRegex(cpu.facts[0], r"^Temperature \d+ °C$")       # coretemp
        self.settings.set("temperature-unit", "kelvin")
        self.assertRegex(self.pages["cpu"].sidebar_summary().facts[0], r" K$")
        # This laptop's Intel iGPU reports neither temperature nor memory.
        self.assertEqual(self.pages["gpu-0000:00:02.0"].sidebar_summary().facts, [])
        self.assertEqual(self.pages["memory"].sidebar_summary().facts, [])

    def test_memory_page_shows_udev_properties_without_a_password(self):
        page = self.pages["memory"]
        self.assertIn(" of ", page.memory.pane.info_label.get_label())
        self.assertFalse(page.banner.get_revealed())
        self.assertTrue(page.properties.get_visible())
        self.assertEqual(page.property_rows["Type"].get_value(), "DDR4")
        self.assertTrue(page.description.endswith("DDR4 @ 2667 MT/s"))

    def test_memory_page_without_udev_offers_authentication(self):
        from proccoli.ui.pages.memory import MemoryPage
        monitor = self.devices.monitor("memory")
        monitor.modules = None
        page = MemoryPage(monitor, self.settings)
        self.addCleanup(page.shutdown)
        self.assertTrue(page.banner.get_revealed())
        self.assertFalse(page.properties.get_visible())

    def test_drive_and_network_pages(self):
        drive = self.pages["drive-sda"]
        self.assertEqual(drive.read.pane.info_label.get_label(), "0 B/s")
        self.assertEqual(drive.property_rows["Capacity"].get_value(), "512.1 GB")
        wifi = self.pages["net-wlp43s0"]
        self.assertEqual(wifi.title, "Wi-Fi Connection")
        self.settings.set("network-bits", True)
        self.assertEqual(wifi.receiving.pane.info_label.get_label(), "0 bit/s")
        summary = wifi.sidebar_summary()
        self.assertIsNone(summary.usage)
        self.assertIsNone(summary.max_value)

    def test_sort_order(self):
        pages = sorted(self.pages.values(), key=lambda p: p.sort_key())
        self.assertEqual([p.page_id for p in pages],
                         ["cpu", "memory", "gpu-0000:00:02.0", "drive-sda", "net-eno1",
                          "net-wlp43s0"])


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class GpuPagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    def setUp(self):
        self.settings = Settings.for_tests()
        ctx = make_context(self, demo=True, settings=self.settings, system=_RealStreams())
        ctx.ticker.set_interval(250)          # faster than any Update Interval: tests only
        ctx.start()
        self.ticker = ctx.ticker
        self.devices = ctx.devices
        self.win = MainWindow(self.app, ctx)
        self.addCleanup(self.win.destroy)
        self.controller = self.devices.monitor("gpu-demo")

    def test_detailed_tabs_fill_from_the_stream(self):
        from proccoli.gpu.intel_gpu_top.views import IntelClientsView, IntelGraphsView
        from proccoli.ui.pages.gpu import GpuPage
        page = self.win.page("gpu-demo")
        self.assertIsInstance(page, GpuPage)
        self.assertEqual(list(page.hosts), ["details", "processes"])
        container = self.win.containers["gpu-demo"]
        self.assertIs(container.header.get_title_widget(), page.switcher)
        self.win.select_page("gpu-demo")
        self.win.present()
        self.assertTrue(pump(lambda: page.hosts["details"].view is not None, timeout=3))
        graphs = page.hosts["details"].view.widget
        self.assertIsInstance(graphs, IntelGraphsView)
        self.assertIsInstance(page.hosts["processes"].view.widget, IntelClientsView)
        self.assertFalse(page.detail_header.get_visible())     # Overview tab
        page.show_tab("details")
        self.assertEqual(self.settings.get("gpu-view"), "details")
        self.assertTrue(page.detail_header.get_visible())
        tips = [w.get_tooltip_text() for w in page.detail_header]
        self.assertEqual(tips, ["Pause Graphs", "Detailed Statistics Menu"])   # shared once
        self.assertTrue(pump(lambda: "engines" in graphs.sections, timeout=3))

    def test_details_charts_are_the_shared_legend_charts(self):
        # every group is a LegendChart with the app's palette,
        # legend rules, hover, axes and Graph Time Range.
        from proccoli.ui.widgets.legend_chart import LegendChart
        self.settings.set("show-graph-axes", True)
        self.settings.set("graph-time-range", "2-minutes")
        page = self.win.page("gpu-demo")
        self.win.select_page("gpu-demo")
        self.win.present()
        page.show_tab("details")
        self.assertTrue(pump(lambda: page.hosts["details"].view is not None, timeout=3))
        graphs = page.hosts["details"].view.widget
        self.assertTrue(pump(lambda: {"engines", "frequency", "power"} <= set(graphs.sections)
                             and graphs.sections["engines"].chart.legend.items, timeout=5))
        engines = graphs.sections["engines"]
        self.assertIsInstance(engines.chart, LegendChart)
        graph = engines.graph
        self.assertTrue(graph.hover and graph.has_axes())
        self.assertEqual(graph.time_span_s, 120)
        self.assertEqual(self.controller.detail_backend.history.max_points,
                         history_points(120, self.controller.detail_backend.interval_ms))
        self.assertEqual(engines.chart.legend.items[0].name, "Render/3D")
        freq = graphs.sections["frequency"]
        self.assertIsNone(freq.graph.max_value)                  # scaled to the data
        self.assertTrue(freq.graph.has_axes())                   # value axis in MHz
        self.assertIs(freq.graph.axis_gutter, graph.axis_gutter)  # plots line up
        # Legend rules: right-click shows only that line, never nothing.
        legend = engines.chart.legend
        legend.solo(0)
        self.assertEqual(legend.shown().count(True), 1)
        legend.toggle(0)
        self.assertTrue(all(legend.shown()))
        # Compact layout: legend values move to the hover text.
        graphs.set_compact(True)
        self.assertTrue(legend.compact)
        graphs.set_compact(False)
        self.assertFalse(legend.compact)
        # The menu no longer has its own History Length.
        labels = [m.get_item_attribute_value(i, "label").get_string()
                  for m in [page.detail_header.get_last_child().get_menu_model()
                            .get_item_link(0, "section")]
                  for i in range(m.get_n_items())]
        self.assertEqual(labels, ["Update Interval"])

    def test_palette_change_recolors_the_details_tab(self):
        page = self.win.page("gpu-demo")
        self.win.select_page("gpu-demo")
        self.win.present()
        page.show_tab("details")
        self.assertTrue(pump(lambda: page.hosts["details"].view is not None
                             and "engines" in page.hosts["details"].view.widget.sections,
                             timeout=5))
        graph = page.hosts["details"].view.widget.sections["engines"].graph
        before = graph.color_for(0)
        self.settings.set("palette", "tango")
        self.assertNotEqual(graph.color_for(0), before)

    def test_gpu_processes_tab_gets_app_icons(self):
        ctx_icons = self.win.ctx.app_icons
        page = self.win.page("gpu-demo")
        self.assertEqual(page.services.app_icon, ctx_icons.icon_for_pid)
        self.assertTrue(pump(lambda: page.hosts["processes"].view is not None, timeout=3))
        clients = page.hosts["processes"].view.widget
        self.assertEqual(clients.table.app_icon, ctx_icons.icon_for_pid)
        self.assertIsNone(clients.table.app_icon(2190))   # demo PIDs: puzzle piece

    def test_turning_details_off_keeps_the_page_and_tabs(self):
        from proccoli.gpu.controller import DetailState
        self.win.select_page("gpu-demo")
        page = self.win.page("gpu-demo")
        self.assertTrue(pump(lambda: page.hosts["details"].view is not None, timeout=3))
        page.show_tab("details")
        self.controller.set_details_enabled(False)
        self.assertIs(self.win.page("gpu-demo"), page)           # never replaced
        host = page.hosts["details"]
        self.assertIsNone(host.view)
        self.assertEqual(host.get_visible_child_name(), "status")
        self.assertEqual(host.button.get_label(), "Turn On")
        self.assertFalse(page.detail_header.get_visible())
        self.assertEqual(len(page.view_connections), 0)          # views disconnected
        host.button.emit("clicked")
        self.assertEqual(self.controller.detail_state, DetailState.STARTING)
        self.assertTrue(pump(lambda: host.view is not None, timeout=3))

    def test_failure_shows_retry_and_overview_keeps_working(self):
        self.win.select_page("gpu-demo")
        page = self.win.page("gpu-demo")
        self.controller.detail_backend.emit("failed", "no counters", True)
        host = page.hosts["processes"]
        self.assertEqual(host.status.get_description(), "no counters")
        self.assertEqual(host.button.get_label(), "Try Again")
        self.assertEqual(page.details_row.get_subtitle(), "no counters")
        self.controller.refresh(5.0)
        self.assertNotEqual(page.usage.pane.info_label.get_label(), "")
        host.button.emit("clicked")
        self.assertIsNotNone(self.controller.detail_backend)
        self.assertTrue(self.controller.detail_backend.elevated)    # can_elevate was set

    def test_last_tab_is_restored(self):
        self.settings.set("gpu-view", "processes")
        from proccoli.ui.pages.gpu import GpuPage
        page = GpuPage(self.controller, self.settings)
        self.addCleanup(page.shutdown)
        self.assertEqual(page.current_tab(), "processes")
        self.settings.set("gpu-view", "no-such-tab")
        other = GpuPage(self.controller, self.settings)
        self.addCleanup(other.shutdown)
        self.assertEqual(other.current_tab(), "overview")

    def test_sidebar_follows_the_gpu_summary(self):
        self.win.select_page("gpu-demo")
        self.win.present()
        item = self.win.sidebar.items["gpu-demo"]
        self.ticker.start()
        self.assertTrue(pump(lambda: "%" in item.usage_label.get_label(), timeout=3))
        self.ticker.stop()


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class GraphsFillThePageTest(unittest.TestCase):
    """graphs resize with the window, both ways."""

    @classmethod
    def setUpClass(cls):
        cls.app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    def window(self, page_id, demo=False, **settings):
        self.settings = Settings.for_tests(settings)
        ctx = make_context(self, demo=demo, settings=self.settings, system=_RealStreams())
        ctx.start()
        ctx.devices.refresh(1.0)
        ctx.devices.refresh(2.0)          # two samples: CPU deltas exist
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        win.set_default_size(1024, 768)
        win.select_page(page_id)
        win.present()
        pump(timeout=1.5)
        return win, win.page(page_id)

    def resize(self, win, w, h):
        resize_or_skip(self, win, w, h)
        pump(timeout=1.5)

    def test_page_graphs_share_the_height(self):
        win, page = self.window("memory")
        tall = [g.get_content_height() for g in page.graphs]
        self.assertGreater(tall[0], 120)
        self.assertEqual(len(set(tall)), 1)                   # rows share it equally
        self.resize(win, 1024, 450)
        short = page.graphs[0].get_content_height()
        self.assertLess(short, tall[0])
        self.assertGreaterEqual(short, 120)                   # never below the minimum
        self.resize(win, 1024, 768)
        self.assertEqual(page.graphs[0].get_content_height(), tall[0])

    def test_axes_follow_settings(self):
        win, page = self.window("memory")
        g = page.memory.graph
        self.assertTrue(g.has_axes())                            # on by default
        self.assertEqual(g.time_span_s, 60.0)
        self.settings.set("update-interval", "2-seconds")
        self.assertEqual(g.time_span_s, 60.0)          # the time range holds
        self.settings.set("graph-time-range", "2-minutes")
        self.assertEqual(g.time_span_s, 120.0)
        self.settings.set("show-graph-axes", False)
        self.assertFalse(g.has_axes())
        cpu_chart = win.sidebar.items["cpu"].meter.graph
        self.assertFalse(cpu_chart.show_axes)
        self.settings.set("show-graph-axes", True)
        self.assertTrue(cpu_chart.has_axes())
        # speeds get a value axis too, in the user's units.
        net = win.page("net-eno1").receiving.graph
        self.assertTrue(net.has_axes())
        self.assertEqual(net.axis_format(2e6), "2 MB/s")
        self.settings.set("network-bits", True)
        self.assertEqual(net.axis_format(2e6), "16 Mb/s")
        self.settings.set("base", "binary")
        self.assertEqual(net.axis_format(2**20), "8 Mib/s")
        self.settings.set("show-graph-axes", False)
        self.assertFalse(net.has_axes())

    def test_column_uses_the_width(self):
        win, page = self.window("memory")
        margins = page.box.get_margin_start() + page.box.get_margin_end()
        self.assertEqual(page.box.get_width(), page.scroller.get_width() - margins)
        self.assertGreaterEqual(page.clamp.get_maximum_size(), 1600)   # was 800

    def test_per_cpu_chart_fills_the_page_like_the_others(self):
        win, page = self.window("cpu", **{"show-logical-cpus": True})
        page.update_labels(page.monitor.latest)
        pump(timeout=1.0)
        graph = page.threads.graph
        self.assertTrue(graph.get_mapped())
        # Sized like any page graph, sharing its area with the legend.
        from proccoli.ui.layout import MIN_GRAPH_IN_AREA
        self.assertGreaterEqual(graph.get_height(), MIN_GRAPH_IN_AREA)
        self.assertGreater(page.legend.get_height(), 0)
        # The legend sits below the chart and spreads over several columns.
        items = page.legend.items
        self.assertGreater(items[1].compute_bounds(page.box)[1].get_x(),
                           items[0].compute_bounds(page.box)[1].get_x())

    def test_per_cpu_chart_and_legend_take_the_total_charts_area(self):
        # switching between the total and the per-CPU chart keeps the
        # area; the legend is part of it, inside the chart's card.
        from proccoli.ui.widgets.graph_box import GraphBox
        win, page = self.window("cpu")
        page.update_labels(page.monitor.latest)
        self.assertIs(page.legend.get_ancestor(GraphBox), page.threads)

        def settled():
            return pump(lambda: not page._fit_source
                        and page.fit_key() == page._fitted_for, timeout=3)
        settled()
        total_area = page.total.get_height()
        total_graph = page.total.graph.get_content_height()
        self.settings.set("show-logical-cpus", True)
        pump(lambda: page.threads.get_height() > 0, timeout=3)    # headless frames are slow
        settled()
        pump(lambda: abs(page.threads.get_height() - total_area) <= 3, timeout=3)
        self.assertAlmostEqual(page.threads.get_height(), total_area, delta=3)
        legend = page.legend.get_height()
        self.assertGreater(legend, 0)
        self.assertAlmostEqual(page.threads.graph.get_content_height(),
                               total_graph - legend - page.threads.pane.get_spacing(),
                               delta=3)
        self.settings.set("show-logical-cpus", False)
        pump(lambda: page.total.get_height() > 0, timeout=3)
        settled()
        pump(lambda: abs(page.total.get_height() - total_area) <= 3, timeout=3)
        self.assertAlmostEqual(page.total.get_height(), total_area, delta=3)

    def test_legend_drops_values_when_the_chart_would_be_cramped(self):
        # values move to the hover text so the chart keeps its room.
        win, page = self.window("cpu", **{"show-logical-cpus": True})
        page.update_labels(page.monitor.latest)
        pump(lambda: page.threads.graph.get_mapped() and page.threads.graph.get_width() > 0,
             timeout=3)
        item = page.legend.items[0]
        page.threads.comfort = 0                          # plenty of room: values shown
        page.threads.fit_legend()
        self.assertFalse(page.legend.compact)
        self.assertTrue(item.value_label.get_visible())
        self.assertEqual(item.get_tooltip_text().split("\n")[0], "CPU 0")
        self.assertFalse(page.threads.fit_legend())             # settled: no flip-flop
        page.threads.comfort = 10_000                     # the chart would be cramped
        self.assertTrue(page.threads.fit_legend())
        self.assertTrue(page.legend.compact)
        self.assertFalse(item.value_label.get_visible())
        self.assertTrue(item.get_tooltip_text().startswith("CPU 0: "))
        self.assertFalse(page.threads.fit_legend())

    def test_right_click_shows_only_that_core(self):
        # left-click hides or shows a core; right-click shows only it.
        win, page = self.window("cpu", **{"show-logical-cpus": True})
        graph, legend = page.threads.graph, page.legend
        n = len(legend.items)
        legend.items[3].solo()                            # what a right-click does
        self.assertEqual([graph.series_shown(i) for i in range(n)],
                         [i == 3 for i in range(n)])
        self.assertEqual(legend.shown(), [i == 3 for i in range(n)])
        legend.items[3].solo()                            # again: every core
        self.assertTrue(all(graph.series_shown(i) for i in range(n)))
        legend.items[5].emit("clicked")                   # a left-click toggles
        self.assertFalse(graph.series_shown(5))
        # one core selected, then deselected: every core again.
        legend.items[3].solo()
        legend.items[3].emit("clicked")
        self.assertTrue(all(graph.series_shown(i) for i in range(n)))
        self.assertEqual(legend.shown(), [True] * n)
        # Hiding them one by one: the last one brings them all back.
        for i in range(n):
            legend.items[i].emit("clicked")
        self.assertEqual(legend.shown(), [True] * n)
        self.assertIn("Right-click", legend.items[0].get_tooltip_text())

    def test_legend_toggles_hide_their_line(self):
        win, page = self.window("cpu", **{"show-logical-cpus": True})
        item = page.legend.items[3]
        self.assertTrue(item.get_active())
        item.set_active(False)
        self.assertFalse(page.threads.graph.series_shown(3))
        self.assertTrue(page.threads.graph.series_shown(2))
        item.set_active(True)
        self.assertTrue(page.threads.graph.series_shown(3))

    def test_portrait_window_caps_graphs_by_width(self):
        # a portrait monitor makes the window tall and narrow;
        # graphs stop at half their width instead of growing into towers.
        win, page = self.window("memory")
        self.resize(win, 700, 1800)
        for g in page.graphs:
            self.assertLessEqual(g.get_content_height(), g.get_width() * 0.5 + 1)
            self.assertGreater(g.get_content_height(), 120)
        self.resize(win, 1024, 768)
        self.assertGreater(page.graphs[0].get_content_height(), 120)

    def test_pairs_stack_on_portrait_and_narrow_windows(self):
        win, page = self.window("demo", demo=True)
        pair = page.io
        self.assertFalse(pair.stacked)                         # landscape: side by side
        start, end = (g.compute_bounds(page.box)[1] for g in pair.graphs)
        self.assertEqual(start.get_y(), end.get_y())
        self.resize(win, 800, 1600)
        self.assertTrue(pump(lambda: pair.stacked, timeout=2))
        pump(timeout=1.0)
        start, end = (g.compute_bounds(page.box)[1] for g in pair.graphs)
        self.assertLess(start.get_y(), end.get_y())            # one above the other
        self.assertAlmostEqual(start.get_width(), page.graphs[0].get_width(), delta=2)
        self.resize(win, 1024, 768)
        self.assertTrue(pump(lambda: not pair.stacked, timeout=2))

    def test_gpu_details_fill_the_height(self):
        self.settings = Settings.for_tests({"gpu-view": "details"})
        ctx = make_context(self, demo=True, settings=self.settings, system=_RealStreams())
        ctx.ticker.set_interval(250)          # faster than any Update Interval: tests only
        ctx.start()
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        win.set_default_size(1024, 768)
        win.select_page("gpu-demo")
        win.present()
        page = win.page("gpu-demo")
        self.assertTrue(pump(lambda: page.hosts["details"].view is not None
                             and page.hosts["details"].view.widget.grid.get_visible(),
                             timeout=3))
        grid = page.hosts["details"].view.widget.grid
        self.assertTrue(pump(lambda: grid.get_height() > 0, timeout=3))   # ~1 frame/s
        tall = grid.get_height()
        resize_or_skip(self, win, 1024, 500)
        self.assertTrue(pump(lambda: 0 < grid.get_height() < tall, timeout=3))
        # Portrait: one tall column, graphs capped by width.
        from proccoli.ui.layout import graph_cap
        resize_or_skip(self, win, 700, 1800)
        pump(timeout=2.0)
        for section in grid.sections:
            if section.get_visible():
                self.assertLessEqual(section.graph.get_height(),
                                     graph_cap(section.get_width()) + 1)

    def test_intel_details_are_the_chart_family(self):
        # user units, the legend rule, live preferences, entry color.
        self.settings = Settings.for_tests({"gpu-view": "details"})
        ctx = make_context(self, demo=True, settings=self.settings, system=_RealStreams())
        ctx.ticker.set_interval(250)          # faster than any Update Interval: tests only
        ctx.start()
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        win.set_default_size(1024, 768)
        win.select_page("gpu-demo")
        win.present()
        page = win.page("gpu-demo")
        self.assertTrue(pump(lambda: page.hosts["details"].view is not None
                             and "imc-bandwidth" in page.hosts["details"].view.widget.sections,
                             timeout=4))
        view = page.hosts["details"].view.widget
        pump(lambda: view.sections["imc-bandwidth"].info != "", timeout=2)
        bandwidth = view.sections["imc-bandwidth"].graph
        self.assertEqual(bandwidth.series[0].unit, "B/s")
        self.assertEqual(bandwidth.axis_format(2 * 2**30), "2.15 GB/s")
        self.settings.set("base", "binary")
        self.assertEqual(bandwidth.axis_format(2 * 2**30), "2 GiB/s")
        self.assertTrue(view.sections["engines"].legend.get_visible())
        self.assertFalse(view.sections["rc6"].legend.get_visible())       # one line
        self.assertTrue(view.sections["rc6"].info.endswith("%"))          # its value
        self.settings.set("show-graph-axes", False)                       # at once
        self.assertFalse(view.sections["engines"].graph.has_axes())
        self.settings.set("show-graph-grids", True)
        self.assertTrue(view.sections["engines"].graph.show_grid)
        # The Details tab starts at the GPU entry's color, like its Overview.
        self.assertIsNotNone(page.entry_index)
        self.assertEqual(view.sections["engines"].graph.entry_base, page.entry_index)
        self.assertEqual(page.usage.graph.entry_base, page.entry_index)


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class GenericGpuPageTest(unittest.TestCase):
    def test_amd_style_values(self):
        from proccoli.devices.base import DeviceInfo, DeviceKind
        from proccoli.gpu.controller import GpuController
        from proccoli.gpu.generic_drm import GenericDrmBackend
        from proccoli.gpu.info import GpuInfo, GpuVendor
        from proccoli.gpu.registry import GpuBackendRegistry
        dev = "/sys/class/drm/card0/device"
        root = FakeRoot(self, {
            f"{dev}/gpu_busy_percent": "37\n", f"{dev}/mem_info_vram_used": "1073741824\n",
            f"{dev}/mem_info_vram_total": "8589934592\n",
            f"{dev}/hwmon/hwmon5/power1_average": "45000000\n",
            f"{dev}/hwmon/hwmon5/power1_cap": "200000000\n",
            f"{dev}/hwmon/hwmon5/temp1_input": "61000\n"})
        from proccoli.gpu.backend import GpuDeps
        gpu = GpuInfo("card0", "0000:03:00.0", GpuVendor.AMD, 0x1002, 0x744c, "amdgpu",
                      "AMD Radeon", False, None, {"PCI Slot": "0000:03:00.0"})
        registry = GpuBackendRegistry((GenericDrmBackend,))
        settings = Settings.for_tests()
        c = GpuController(DeviceInfo("gpu-0000:03:00.0", DeviceKind.GPU, "GPU", "AMD Radeon"),
                          gpu, registry, GpuDeps(root.sysroot, settings, FakeSystem()))
        c.start()
        from proccoli.ui.pages.gpu import GpuPage
        page = GpuPage(c, settings)
        c.refresh(1.0)
        self.assertEqual(page.usage.pane.info_label.get_label(), "37 %")
        self.assertTrue(page.video.get_visible())            # separate enc/dec engines
        self.assertFalse(page.video_combined.get_visible())
        self.assertTrue(page.vram.get_visible())
        self.assertEqual(page.power.get_value(), "45.0 W / 200 W")
        self.assertTrue(page.sensors.get_visible())
        self.assertEqual(page.property_rows["Max Power Cap"].get_value(), "200 W")
        self.assertEqual(page.header_widgets(), [])           # no detail source:
        self.assertIsNone(page.title_widget())                # no tabs either
        self.assertEqual(page.hosts, {})
        self.assertIsNone(page.details_row)
        self.assertEqual(page.vram.get_title(), "Video Memory")
        self.assertEqual(page.power.get_title(), "Power Usage")

    def test_apu_labels_its_shared_memory_and_package_power(self):
        """An APU's honest readings, on this Ryzen 3 4300U's files."""
        from helpers import RENOIR
        from proccoli.core import pciids
        from proccoli.core.sysroot import SysRoot
        from proccoli.devices.base import DeviceInfo, DeviceKind
        from proccoli.gpu.backend import GpuDeps
        from proccoli.gpu.controller import GpuController
        from proccoli.gpu.generic_drm import GenericDrmBackend
        from proccoli.gpu.info import discover_gpus
        from proccoli.gpu.registry import GpuBackendRegistry
        from proccoli.ui.pages.gpu import GpuPage
        sysroot = SysRoot(RENOIR)
        [gpu] = discover_gpus(sysroot, pciids.PciIds({}, {}))
        settings = Settings.for_tests()
        c = GpuController(DeviceInfo("gpu-0000:03:00.0", DeviceKind.GPU, "GPU", gpu.name),
                          gpu, GpuBackendRegistry((GenericDrmBackend,)),
                          GpuDeps(sysroot, settings, FakeSystem()))
        c.start()
        page = GpuPage(c, settings)
        c.refresh(1.0)
        self.assertEqual(page.vram.get_title(), "Graphics Memory")
        self.assertTrue(page.vram.pane.info_label.get_label().endswith("of 8.9 GB"))
        self.assertEqual(page.power.get_title(), "Processor Package Power")
        self.assertEqual(page.power.get_value(), "12.0 W")


if __name__ == "__main__":
    unittest.main()
