"""AMD detail source: decoding gpu_metrics, reading amdgpu's
sysfs files, the backend's probe and readings; and the Details tab (UI
tests, on the headless display), against a Ryzen 3 4300U's own files."""

import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from helpers import FIXTURES, RENOIR, FakeRoot, FakeSystem  # noqa: E402

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from proccoli.core import pciids  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.sysroot import SysRoot  # noqa: E402
from proccoli.devices.base import DeviceInfo, DeviceKind  # noqa: E402
from proccoli.gpu.amdgpu import metrics  # noqa: E402
from proccoli.gpu.amdgpu.backend import AmdgpuBackend  # noqa: E402
from proccoli.gpu.amdgpu.sensors import (HISTORY_UNITS, AmdgpuSample, engine_classes,  # noqa: E402
                                        read_sample)
from proccoli.gpu.backend import GpuDeps, SupportLevel  # noqa: E402
from proccoli.gpu.controller import DetailState, GpuController  # noqa: E402
from proccoli.gpu.detect import plan_gpu  # noqa: E402
from proccoli.gpu.info import GpuInfo, GpuVendor, discover_gpus  # noqa: E402
from proccoli.gpu.registry import standard_registry  # noqa: E402

HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()
if HAVE_DISPLAY:
    Adw.init()
PCI = pciids.load(os.path.join(FIXTURES, "pci", "pci.ids"))
DEV = "/sys/class/drm/card1/device"
DGPU = GpuInfo("card0", "0000:03:00.0", GpuVendor.AMD, 0x1002, 0x744c, "amdgpu",
               "AMD Radeon RX 7900 XTX", False, "renderD128")


def table(name: str) -> bytes:
    with open(os.path.join(RENOIR, f"gpu_metrics-{name}.bin"), "rb") as fh:
        return fh.read()


def apu() -> GpuInfo:
    [gpu] = discover_gpus(SysRoot(RENOIR), PCI)
    return gpu


def deps(sysroot=None, settings=None) -> GpuDeps:
    return GpuDeps(sysroot or SysRoot(RENOIR), settings or Settings.for_tests(), FakeSystem())


class MetricsTest(unittest.TestCase):
    def test_renoir_idle(self):
        m = metrics.parse_gpu_metrics(table("idle"))
        self.assertEqual(m.version, (2, 2))
        self.assertEqual((m.gfx_temperature_c, m.soc_temperature_c), (33.0, 34.25))
        # A 4-core part fills 4 of the 8 core slots (the ones with a clock).
        self.assertEqual(m.core_temperatures_c, [35.75, 36.25, 37.25, 35.5])
        self.assertEqual(m.hottest_core_c, 37.25)
        self.assertEqual(m.socket_power_w, 15.0)               # whole watts on Renoir
        self.assertAlmostEqual(m.cpu_power_w, 11.672)
        self.assertAlmostEqual(m.soc_power_w, 1.708)
        self.assertIsNone(m.gfx_power_w)                       # 0xFFFF: not reported
        self.assertEqual((m.gfx_clock_hz, m.fabric_clock_hz), (400e6, 1200e6))
        self.assertIsNone(m.memory_clock_hz)                   # a level number, not a clock
        self.assertEqual(m.throttle, [])

    def test_renoir_under_load(self):
        m = metrics.parse_gpu_metrics(table("load"))
        self.assertEqual(m.socket_power_w, 32.0)
        self.assertAlmostEqual(m.cpu_power_w, 28.941)
        self.assertEqual(m.hottest_core_c, 56.25)
        self.assertEqual(m.throttle, ["Fast power limit"])

    def test_socket_power_units(self):
        self.assertEqual(metrics.socket_power_w(15, 11672), 15.0)       # watts (Renoir)
        self.assertEqual(metrics.socket_power_w(15000, 11672), 15.0)    # milliwatts
        self.assertEqual(metrics.socket_power_w(9000, 0xFFFF), 9.0)
        self.assertIsNone(metrics.socket_power_w(0xFFFF, 11672))

    def test_throttle_reasons(self):
        self.assertEqual(metrics.throttle_reasons(0), [])
        self.assertEqual(metrics.throttle_reasons(1 << 5 | 1 << 33),
                         ["Fast power limit", "Core temperature"])
        # Two bits with one name are named once.
        self.assertEqual(metrics.throttle_reasons(1 << 44 | 1 << 45), ["Regulator hot"])

    def test_layouts_it_does_not_know(self):
        self.assertIsNone(metrics.parse_gpu_metrics(None))
        self.assertIsNone(metrics.parse_gpu_metrics(b"\x80\x00"))
        self.assertIsNone(metrics.parse_gpu_metrics(table("idle")[:60]))     # truncated
        dgpu = b"\x60\x00\x01\x03" + bytes(92)                               # revision 1
        self.assertIsNone(metrics.parse_gpu_metrics(dgpu))
        self.assertFalse(metrics.is_apu_table(dgpu))
        self.assertTrue(metrics.is_apu_table(table("idle")))

    def test_v2_0_reports_whole_degrees(self):
        data = bytearray(table("idle"))
        data[3] = 0                                            # content revision 0
        struct.pack_into("<H", data, 4, 45)                    # gfx: 45 °C
        m = metrics.parse_gpu_metrics(bytes(data))
        self.assertEqual(m.gfx_temperature_c, 45.0)
        self.assertEqual(m.throttle, [])                       # no indep status before 2.2


class SensorsTest(unittest.TestCase):
    def test_apu(self):
        s = read_sample(SysRoot(RENOIR), DEV, True, {"gfx": 3.0, "compute": 0.0})
        self.assertEqual((s.usage, s.video, s.memory_controller), (6.0, 0.0, None))
        self.assertEqual(s.engines, {"gfx": 3.0, "compute": 0.0})
        self.assertEqual((s.clock_hz, s.memory_clock_hz, s.fabric_clock_hz, s.soc_clock_hz),
                         (400e6, 1333e6, 1333e6, 400e6))
        self.assertEqual(s.temperature_c, 32.0)                # hwmon's edge
        self.assertEqual((s.soc_temperature_c, s.cpu_temperature_c), (34.25, 37.25))
        self.assertIsNone(s.power_w)                           # the GPU's own: not reported
        self.assertEqual(s.package_power_w, 15.0)
        self.assertEqual((s.gfx_voltage_v, s.nb_voltage_v), (1.156, 0.793))
        self.assertIsNone(s.fan)
        values = s.history_values()
        self.assertEqual(set(values), set(HISTORY_UNITS))
        self.assertGreater(values["vram"], 80)                 # the carve-out
        self.assertLess(values["gtt"], 5)

    def test_apu_summary_is_honest(self):
        summary = read_sample(SysRoot(RENOIR), DEV, True).to_summary()
        self.assertTrue(summary.shared_memory and summary.power_is_package)
        self.assertEqual(summary.power_w, 15.0)
        self.assertLess(summary.memory_usage, 20)

    def test_discrete_gpu_from_hwmon(self):
        dev = DGPU.device_path
        h = f"{dev}/hwmon/hwmon3"
        root = FakeRoot(self, {
            f"{dev}/gpu_busy_percent": "88\n", f"{dev}/mem_busy_percent": "41\n",
            f"{dev}/mem_info_vram_used": "4294967296\n",
            f"{dev}/mem_info_vram_total": "25769803776\n",
            f"{dev}/pp_dpm_sclk": "0: 500Mhz\n1: 2500Mhz *\n",
            f"{dev}/pp_dpm_mclk": "0: 96Mhz\n3: 1250Mhz *\n",
            f"{h}/temp1_input": "61000\n", f"{h}/temp1_label": "edge\n",
            f"{h}/temp2_input": "78000\n", f"{h}/temp2_label": "junction\n",
            f"{h}/temp3_input": "70000\n", f"{h}/temp3_label": "mem\n",
            f"{h}/power1_average": "301000000\n", f"{h}/power1_cap": "355000000\n",
            f"{h}/pwm1": "102\n", f"{h}/in0_input": "1050\n", f"{h}/in0_label": "vddgfx\n"})
        s = read_sample(root.sysroot, dev, False)
        self.assertEqual((s.usage, s.memory_controller), (88.0, 41.0))
        self.assertEqual((s.temperature_c, s.junction_c, s.memory_temperature_c),
                         (61.0, 78.0, 70.0))
        self.assertEqual((s.power_w, s.power_cap_w, s.package_power_w), (301.0, 355.0, None))
        self.assertAlmostEqual(s.fan, 40.0)
        self.assertEqual(s.gfx_voltage_v, 1.05)
        self.assertIsNone(s.soc_temperature_c)
        summary = s.to_summary()
        self.assertFalse(summary.shared_memory or summary.power_is_package)
        self.assertAlmostEqual(summary.memory_usage, 100 / 6)

    def test_engine_classes(self):
        self.assertEqual(engine_classes({"gfx": 10.0, "dma": 2.0, "dec": 5.0, "jpeg": 9.0,
                                         "enc": 1.0, "enc_1": 4.0}),
                         {"gfx": 10.0, "dma": 2.0, "dec": 9.0, "enc": 4.0})
        self.assertEqual(engine_classes({}), {})

    def test_an_empty_sample(self):
        s = AmdgpuSample()
        self.assertTrue(all(v is None for v in s.history_values().values()))
        self.assertIsNone(s.to_summary().power_w)


class BackendTest(unittest.TestCase):
    def test_probe_matrix(self):
        nvidia = GpuInfo("card1", "0000:02:00.0", GpuVendor.NVIDIA, 0x10de, 0x2d59, "nvidia",
                         "NVIDIA", False)
        radeon = GpuInfo("card0", "0000:01:00.0", GpuVendor.AMD, 0x1002, 0x6779, "radeon",
                         "AMD Radeon HD 6450", False)
        empty = FakeRoot(self)
        for gpu, sysroot, level, reason in (
                (apu(), SysRoot(RENOIR), SupportLevel.PREFERRED, "amdgpu's statistics files"),
                (nvidia, SysRoot(RENOIR), SupportLevel.UNSUPPORTED, "not an AMD GPU"),
                (radeon, SysRoot(RENOIR), SupportLevel.UNSUPPORTED,
                 "driver radeon; detailed statistics need amdgpu"),
                (DGPU, empty.sysroot, SupportLevel.UNSUPPORTED,
                 "amdgpu doesn't report this GPU's usage")):
            with self.subTest(gpu=gpu.name):
                probe = AmdgpuBackend.probe(gpu, deps(sysroot))
                self.assertEqual((probe.level, probe.reason), (level, reason))
                self.assertFalse(probe.needs_elevation)

    def test_readings_history_and_processes(self):
        root = FakeRoot(self)
        dev = f"{RENOIR}{DEV}"
        for name in os.listdir(dev):
            if os.path.isfile(os.path.join(dev, name)):
                with open(os.path.join(dev, name), "rb") as fh:
                    root.write_bytes(f"{DEV}/{name}", fh.read())
        root.link("/proc/40/fd/9", "/dev/dri/renderD128")
        fdinfo = ("drm-driver:\tamdgpu\ndrm-client-id:\t3\ndrm-pdev:\t0000:03:00.0\n"
                  "drm-total-vram:\t1024 KiB\ndrm-total-gtt:\t2048 KiB\n"
                  "drm-engine-gfx:\t{gfx} ns\n")
        root.write("/proc/40/fdinfo/9", fdinfo.format(gfx=0))
        b = AmdgpuBackend(apu(), deps(root.sysroot))
        updates = []
        b.connect("updated", lambda _b: updates.append(1))
        b.refresh(1.0)                                          # not started: nothing
        self.assertFalse(b.has_data())
        b.start()
        self.assertFalse(b.elevated)
        b.refresh(1.0)
        root.write("/proc/40/fdinfo/9", fdinfo.format(gfx=250_000_000))
        b.refresh(2.0)
        self.assertEqual(len(updates), 2)
        self.assertTrue(b.has_data())
        self.assertAlmostEqual(b.sample.engines["gfx"], 25.0)
        self.assertEqual(b.process_usage()[40].vram, 3 << 20)   # GTT counts on an APU
        self.assertEqual(b.history.series("package-power").values[-1], 15.0)
        readings, units = b.history_readings()
        self.assertEqual(readings["gfx"], 25.0)
        self.assertEqual(units["gfx-voltage"], "V")
        self.assertIs(b.history_target(), b.history)
        self.assertTrue(b.summary().power_is_package)
        b.stop()
        b.refresh(3.0)
        self.assertEqual(len(updates), 2)

    def test_graph_time_range_follows_the_preference(self):
        settings = Settings.for_tests()
        b = AmdgpuBackend(apu(), deps(settings=settings))
        b.start()
        before = b.history.step_s
        settings.set("graph-time-range", "1-day")
        self.assertGreater(b.history.step_s, before)
        b.stop()
        settings.set("graph-time-range", "1-minute")
        self.assertGreater(b.history.step_s, before)            # no longer listening

    def test_this_apu_gets_the_amd_tabs(self):
        plan = plan_gpu(apu(), standard_registry(), deps())
        self.assertEqual(plan.detail.backend.id, "amdgpu")
        self.assertEqual(plan.summary.backend.id, "generic")
        self.assertEqual(plan.detail_text(), "AMD (amdgpu's statistics files)")

    def test_controller_runs_it_without_a_password(self):
        info = DeviceInfo("gpu-0000:03:00.0", DeviceKind.GPU, "GPU", "AMD")
        with self.assertLogs("proccoli.gpu", "INFO"):
            c = GpuController(info, apu(), standard_registry(), deps())
            c.start()
        c.refresh(1.0)
        self.assertEqual(c.detail_state, DetailState.RUNNING)
        s = c.summary()
        self.assertTrue(s.shared_memory and s.power_is_package)
        self.assertEqual(c.latest.usage, 6.0)
        self.assertIn("detail/package-power", c.latest.stats_values())
        c.stop()


class SharedFdinfoTest(unittest.TestCase):
    """the summary and AMD backends of one GPU read /proc/*/fdinfo
    once per update, not once each."""

    def test_one_reader_one_read_per_update(self):
        from proccoli.gpu.amdgpu.backend import AmdgpuBackend
        from proccoli.gpu.generic_drm import GenericDrmBackend
        d = deps()
        summary, detail = GenericDrmBackend(apu(), d), AmdgpuBackend(apu(), d)
        self.assertIs(summary.fdinfo, detail.fdinfo)
        reader = summary.fdinfo
        detail.start()
        self.addCleanup(detail.stop)
        for now in (1.0, 2.0):
            summary.refresh(now)
            detail.refresh(now)
        self.assertEqual(reader._reads, 2)                 # not 4

    def test_other_gpus_get_their_own(self):
        from proccoli.gpu.fdinfo import shared_reader
        d = deps()
        self.assertIsNot(shared_reader(d, "0000:03:00.0"), shared_reader(d, "0000:04:00.0"))
        self.assertIsNot(shared_reader(deps(), "0000:03:00.0"),
                         shared_reader(d, "0000:03:00.0"))


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class AmdgpuDetailsViewTest(unittest.TestCase):
    def view(self, gpu=None, sysroot=None):
        from proccoli.gpu.amdgpu.views import AmdgpuDetailsView
        from proccoli.ui.chart_settings import ChartSettings
        settings = Settings.for_tests()
        b = AmdgpuBackend(gpu or apu(), deps(sysroot, settings))
        view = AmdgpuDetailsView(b, ChartSettings(settings))
        return b, view

    def test_before_the_first_reading_every_card_shows(self):
        _b, view = self.view()
        self.assertTrue(all(card.get_visible() for card in view.groups.values()))

    def test_apu_cards_and_lines(self):
        b, view = self.view()
        b.start()
        b.refresh(1.0)
        view.refresh()
        shown = {t for t, card in view.groups.items() if card.get_visible()}
        # No fan on a laptop APU, and fdinfo has no engines yet (one reading).
        self.assertEqual(shown, {"GPU Utilization", "Memory", "Clocks", "Temperature",
                                 "Power", "Voltage"})
        self.assertIn("Ryzen", view.caption_line())
        self.assertIn("integrated", view.caption_line())
        self.assertEqual(view.info("Power"), "Package 15.0 W")
        self.assertEqual(view.legends["Temperature"].available, [True, False, False, True, True])
        self.assertTrue(view.info("Memory").endswith("of 8.9 GB"))

    def test_throttling_is_named(self):
        b, view = self.view()
        b.start()
        b.refresh(1.0)
        b.sample.throttle = ["Fast power limit"]
        self.assertEqual(view.info("Power"), "Package 15.0 W · limited by fast power limit")

    def test_create_views_follows_updates(self):
        from proccoli.gpu.amdgpu.views import create_views
        from proccoli.gpu.backend import DetailServices
        b, _ = self.view()
        views = create_views(b, None, DetailServices(Settings.for_tests()))
        [view] = views.views
        self.assertEqual(view.name, "details")
        b.start()
        b.refresh(1.0)
        self.assertFalse(view.widget.groups["Fan"].get_visible())
        for h in views.handlers:
            b.disconnect(h)


if __name__ == "__main__":
    unittest.main()
