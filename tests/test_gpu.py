import dataclasses
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from helpers import FIXTURES, LAPTOP, RENOIR, FakeRoot, FakeSystem  # noqa: E402

from gi.repository import GLib  # noqa: E402

from proccoli.core import pciids  # noqa: E402
from proccoli.core.jsonstream import JsonStreamParser  # noqa: E402
from proccoli.core.runner import StreamReader  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.sysroot import SysRoot  # noqa: E402
from proccoli.devices.base import DeviceInfo, DeviceKind  # noqa: E402
from proccoli.gpu.backend import (BackendRole, DetailBackend, GpuBackend, GpuDeps,  # noqa: E402
                                 GpuProcessUsage, GpuSummary, Probe, SupportLevel, TabSpec,
                                 frequency_text)
from proccoli.gpu.controller import (DetailState, GpuController, GpuDiscoverer,  # noqa: E402
                                    merge_summaries)
from proccoli.gpu.fdinfo import FdinfoReader, parse_fdinfo  # noqa: E402
from proccoli.gpu.generic_drm import GenericDrmBackend, Residency, active_dpm_hz  # noqa: E402
from proccoli.gpu.info import GpuInfo, GpuVendor, discover_gpus, pretty_name  # noqa: E402
from proccoli.gpu.intel_gpu_top import backend as igt  # noqa: E402
from proccoli.gpu.registry import GpuBackendRegistry, standard_registry  # noqa: E402

PCI = pciids.load(os.path.join(FIXTURES, "pci", "pci.ids"))
INTEL = GpuInfo("card1", "0000:00:02.0", GpuVendor.INTEL, 0x8086, 0x46a3, "i915",
                "Intel UHD Graphics", True, "renderD128")
AMD = GpuInfo("card0", "0000:03:00.0", GpuVendor.AMD, 0x1002, 0x744c, "amdgpu",
              "AMD Radeon", False, "renderD128")


def deps(sysroot=None, settings=None, **system):
    return GpuDeps(sysroot or SysRoot("/nonexistent"), settings or Settings.for_tests(),
                   FakeSystem(**system))


def pump(until, timeout=3.0):
    ctx = GLib.MainContext.default()
    end = time.monotonic() + timeout
    while time.monotonic() < end and not until():
        while ctx.pending():
            ctx.iteration(False)
        time.sleep(0.01)
    return until()


FDINFO = """pos:\t0
flags:\t02100002
drm-driver:\ti915
drm-client-id:\t{cid}
drm-pdev:\t{pdev}
drm-total-system0:\t438700 KiB
drm-total-local0:\t{local} KiB
drm-engine-render:\t{render} ns
drm-engine-copy:\t0 ns
drm-engine-video:\t{video} ns
drm-engine-video-enhance:\t0 ns
"""


class InfoTest(unittest.TestCase):
    def test_laptop(self):
        [gpu] = discover_gpus(SysRoot(LAPTOP), PCI)
        self.assertEqual((gpu.card, gpu.pci_slot, gpu.driver), ("card1", "0000:00:02.0", "i915"))
        self.assertEqual(gpu.name, "Intel UHD Graphics")
        self.assertIs(gpu.vendor, GpuVendor.INTEL)
        self.assertTrue(gpu.integrated)
        self.assertEqual(gpu.render_node, "renderD128")
        self.assertEqual(gpu.properties["Manufacturer"], "Intel Corporation")

    def test_pretty_names(self):
        self.assertEqual(pretty_name(GpuVendor.NVIDIA, "NVIDIA Corporation",
                                     "AD102 [GeForce RTX 4090]"), "NVIDIA GeForce RTX 4090")
        self.assertEqual(pretty_name(GpuVendor.AMD, None, None), "AMD GPU")
        self.assertEqual(pretty_name(GpuVendor.OTHER, "Matrox Electronics", "G200eR2"),
                         "Matrox G200eR2")


class FdinfoTest(unittest.TestCase):
    def test_parse(self):
        cid, c = parse_fdinfo(FDINFO.format(cid=9, pdev="0000:00:02.0", local=1024,
                                            render=5, video=7), 42)
        self.assertEqual((cid, c.pid, c.pdev), ("9", 42, "0000:00:02.0"))
        self.assertEqual(c.engines_ns, {"render": 5, "copy": 0, "video": 7,
                                        "video-enhance": 0})
        self.assertEqual(c.vram, 1024 * 1024)          # system memory isn't VRAM
        self.assertIsNone(parse_fdinfo("pos:\t0\nflags:\t0\n", 1))

    def test_reader_deltas_and_dedup(self):
        root = FakeRoot(self)

        def client(pid, fd, cid, render, video, pdev="0000:00:02.0"):
            root.link(f"/proc/{pid}/fd/{fd}", "/dev/dri/renderD128")
            root.write(f"/proc/{pid}/fdinfo/{fd}", FDINFO.format(
                cid=cid, pdev=pdev, local=0, render=render, video=video))
        client(100, 5, 1, 0, 0)
        client(100, 6, 1, 0, 0)          # same client via a second fd
        client(200, 3, 2, 0, 0)
        client(300, 4, 3, 0, 0, pdev="0000:03:00.0")   # another GPU
        root.link("/proc/100/fd/1", "/dev/pts/0")      # not DRM
        reader = FdinfoReader(root.sysroot, "0000:00:02.0")
        reader.read(10.0)
        self.assertEqual(set(reader.processes), {100, 200})
        self.assertEqual(reader.engines, {})
        # One second later: pid 100 rendered 0.5 s, pid 200 decoded 0.25 s.
        client(100, 5, 1, 500_000_000, 0)
        client(100, 6, 1, 500_000_000, 0)
        client(200, 3, 2, 0, 250_000_000)
        reader.read(11.0)
        self.assertAlmostEqual(reader.processes[100].usage, 50.0)
        self.assertAlmostEqual(reader.processes[200].decode, 25.0)
        self.assertAlmostEqual(reader.processes[200].encode, 25.0)   # i915: one video engine
        self.assertAlmostEqual(reader.engines["render"], 50.0)


class GenericBackendTest(unittest.TestCase):
    def test_dpm_table(self):
        self.assertEqual(active_dpm_hz("0: 500Mhz\n1: 2100Mhz *\n"), 2.1e9)
        self.assertIsNone(active_dpm_hz("0: 500Mhz\n"))

    def test_intel_igpu(self):
        root = FakeRoot(self, {"/sys/class/drm/card1/gt_act_freq_mhz": "850\n"})
        b = GenericDrmBackend(INTEL, deps(root.sysroot))
        b.refresh(1.0)
        s = b.summary()
        self.assertEqual(s.frequency_hz, 850e6)
        self.assertTrue(s.combined_video)
        self.assertIsNone(s.vram_total)
        self.assertIsNone(s.temperature_c)

    def test_residency_gives_busy(self):
        r = Residency()
        self.assertIsNone(r.sample(10.0, 5000))              # nothing to compare yet
        self.assertEqual(r.sample(11.0, 6000), 0.0)          # asleep the whole second
        self.assertEqual(r.sample(12.0, 6250), 75.0)
        self.assertIsNone(r.sample(13.0, 100))               # went backwards: a reset
        self.assertEqual(r.sample(14.0, 600), 50.0)          # and on from there
        self.assertEqual(r.sample(15.0, 1700), 0.0)          # rounding past Δt clamps
        self.assertIsNone(r.sample(16.0, None))
        self.assertIsNone(r.sample(17.0, 2000))              # starts over after a gap

    def idle_intel(self, xe=False):
        """An Intel GPU nothing has open: its GTs asleep, 0 MHz."""
        if xe:
            gt = "/sys/class/drm/card1/device/tile0/gt{n}/gtidle/idle_residency_ms"
            files = {"/sys/class/drm/card1/device/tile0/gt0/freq0/act_freq": "0\n"}
            info = dataclasses.replace(INTEL, driver="xe")
        else:
            gt = "/sys/class/drm/card1/gt/gt{n}/rc6_residency_ms"
            files = {"/sys/class/drm/card1/gt_act_freq_mhz": "0\n",
                     "/sys/class/drm/card1/gt_cur_freq_mhz": "300\n"}
            info = INTEL
        files.update({gt.format(n=0): "1000\n", gt.format(n=1): "2000\n"})
        root = FakeRoot(self, files)
        return root, gt, GenericDrmBackend(info, deps(root.sysroot))

    def test_an_idle_intel_gpu_reads_zero(self):
        for xe in (False, True):
            with self.subTest(xe=xe):
                root, gt, b = self.idle_intel(xe)
                b.refresh(1.0)
                self.assertIsNone(b.summary().usage)
                root.write(gt.format(n=0), "2000\n")          # asleep all second
                root.write(gt.format(n=1), "2900\n")          # media GT 10 % busy
                b.refresh(2.0)
                s = b.summary()
                self.assertEqual(s.usage, 0.0)
                self.assertAlmostEqual(s.decode, 10.0)
                self.assertEqual(s.frequency_hz, 0.0)        # a reading, not a gap
                self.assertEqual(frequency_text(s.frequency_hz), "Idle")

    def test_fdinfo_engines_come_first(self):
        root, gt, b = self.idle_intel()

        class Clients:
            engines = {"render": 40.0, "video": 20.0}
            processes = {}

            def read(self, _now):
                pass
        b.fdinfo = Clients()
        b.refresh(1.0)
        root.write(gt.format(n=0), "2000\n")
        b.refresh(2.0)
        s = b.summary()
        self.assertEqual(s.usage, 40.0)
        self.assertEqual(s.decode, 20.0)                     # not the media GT's figure

    def test_older_intel_gpus_without_residency_are_unchanged(self):
        root = FakeRoot(self, {"/sys/class/drm/card1/gt_act_freq_mhz": "850\n"})
        b = GenericDrmBackend(INTEL, deps(root.sysroot))
        b.refresh(1.0)
        b.refresh(2.0)
        self.assertIsNone(b.summary().usage)
        self.assertIsNone(b.summary().decode)

    def test_frequency_text(self):
        self.assertIsNone(frequency_text(None))
        self.assertEqual(frequency_text(0), "Idle")
        self.assertEqual(frequency_text(850e6), "850 MHz")

    def test_amd_dgpu(self):
        dev = "/sys/class/drm/card0/device"
        root = FakeRoot(self, {
            f"{dev}/gpu_busy_percent": "37\n", f"{dev}/mem_info_vram_used": "1073741824\n",
            f"{dev}/mem_info_vram_total": "8589934592\n",
            f"{dev}/pp_dpm_sclk": "0: 500Mhz\n1: 2400Mhz *\n",
            f"{dev}/pp_dpm_mclk": "0: 96Mhz\n3: 1000Mhz *\n",
            f"{dev}/hwmon/hwmon5/power1_average": "45000000\n",
            f"{dev}/hwmon/hwmon5/power1_cap": "200000000\n",
            f"{dev}/hwmon/hwmon5/temp1_input": "61000\n"})
        b = GenericDrmBackend(AMD, deps(root.sysroot))
        b.refresh(1.0)
        s = b.summary()
        self.assertEqual((s.usage, s.frequency_hz, s.vram_frequency_hz), (37.0, 2.4e9, 1e9))
        self.assertAlmostEqual(s.memory_usage, 12.5)
        self.assertEqual((s.power_w, s.power_cap_w, s.temperature_c), (45.0, 200.0, 61.0))
        self.assertFalse(s.combined_video)


AMDGPU_FDINFO = """drm-driver:\tamdgpu
drm-client-id:\t{cid}
drm-pdev:\t0000:03:00.0
drm-total-gtt:\t39240 KiB
drm-resident-gtt:\t67272 KiB
drm-total-vram:\t415160 KiB
drm-resident-vram:\t387128 KiB
drm-memory-vram:\t387128 KiB
drm-memory-gtt: \t67272 KiB
drm-engine-gfx:\t{gfx} ns
drm-engine-compute:\t0 ns
"""


class AmdApuBugsTest(unittest.TestCase):
    """The generic source's readings on an AMD APU (3 and 4),
    against this Ryzen 3 4300U's own files."""

    def apu(self):
        [gpu] = discover_gpus(SysRoot(RENOIR), PCI)
        return gpu

    def test_the_apu_is_found_as_integrated(self):
        gpu = self.apu()
        self.assertEqual((gpu.card, gpu.pci_slot, gpu.driver), ("card1", "0000:03:00.0",
                                                                "amdgpu"))
        self.assertEqual(gpu.name, "AMD Radeon RX Vega 6 (Ryzen 4000/5000 Mobile Series)")
        self.assertTrue(gpu.integrated)

    def test_integrated_is_decided_by_the_metrics_table(self):
        dev = "/sys/class/drm/card0/device"
        base = {f"{dev}/vendor": "0x1002\n", f"{dev}/device": "0x1636\n",
                f"{dev}/uevent": "DRIVER=amdgpu\nPCI_SLOT_NAME=0000:03:00.0\n"}
        for table, vram, integrated in ((b"\x80\x00\x02\x02", 4 << 30, True),  # 4 GiB UMA
                                        (b"\x60\x00\x01\x03", 1 << 29, False),  # dGPU
                                        (None, 1 << 29, True), (None, 8 << 30, False)):
            root = FakeRoot(self, {**base, f"{dev}/mem_info_vram_total": f"{vram}\n"})
            if table:
                root.write_bytes(f"{dev}/gpu_metrics", table)
            with self.subTest(table=table, vram=vram):
                [gpu] = discover_gpus(root.sysroot, PCI)
                self.assertIs(gpu.integrated, integrated)

    def test_graphics_memory_includes_gtt(self):
        """the carve-out alone read 85 % used; the GPU mostly uses GTT."""
        b = GenericDrmBackend(self.apu(), deps(SysRoot(RENOIR)))
        b.refresh(1.0)
        s = b.summary()
        self.assertTrue(s.shared_memory)
        self.assertEqual(s.vram_total, 1073741824)
        self.assertEqual(s.gtt_total, 7822807040)
        self.assertEqual(s.memory_total, 1073741824 + 7822807040)
        self.assertEqual(s.memory_used, s.vram_used + s.gtt_used)
        self.assertLess(s.memory_usage, 20)
        self.assertGreater(100 * s.vram_used / s.vram_total, 80)

    def test_power_is_the_packages(self):
        """hwmon's PPT on an APU is the whole package, cores included."""
        b = GenericDrmBackend(self.apu(), deps(SysRoot(RENOIR)))
        b.refresh(1.0)
        s = b.summary()
        self.assertEqual(s.power_w, 12.0)
        self.assertTrue(s.power_is_package)
        self.assertEqual(s.temperature_c, 32.0)

    def test_a_discrete_gpu_is_unchanged(self):
        dev = "/sys/class/drm/card0/device"
        root = FakeRoot(self, {f"{dev}/mem_info_vram_used": "1073741824\n",
                               f"{dev}/mem_info_vram_total": "8589934592\n",
                               f"{dev}/mem_info_gtt_used": "4294967296\n",
                               f"{dev}/mem_info_gtt_total": "8589934592\n",
                               f"{dev}/hwmon/hwmon5/power1_average": "45000000\n"})
        b = GenericDrmBackend(AMD, deps(root.sysroot))
        b.refresh(1.0)
        s = b.summary()
        self.assertFalse(s.shared_memory or s.power_is_package)
        self.assertEqual((s.memory_used, s.memory_total), (1 << 30, 8 << 30))
        self.assertEqual(s.gtt_used, 4 << 30)                  # kept, not counted

    def test_amdgpu_process_memory_counts_each_region_once(self):
        """drm-memory-vram repeats drm-total-vram's region (as resident)."""
        _cid, c = parse_fdinfo(AMDGPU_FDINFO.format(cid=1, gfx=0), 7)
        self.assertEqual(c.vram, 415160 * 1024)
        _cid, c = parse_fdinfo(AMDGPU_FDINFO.format(cid=1, gfx=0), 7,
                               ("vram", "local", "gtt"))
        self.assertEqual(c.vram, (415160 + 39240) * 1024)
        # An older kernel with only drm-memory-*: those count.
        _cid, c = parse_fdinfo("drm-driver:\tamdgpu\ndrm-client-id:\t2\n"
                               "drm-memory-vram:\t1024 KiB\n", 7)
        self.assertEqual(c.vram, 1 << 20)

    def test_apu_processes_count_gtt(self):
        root = FakeRoot(self)
        root.link("/proc/50/fd/3", "/dev/dri/renderD128")
        root.write("/proc/50/fdinfo/3", AMDGPU_FDINFO.format(cid=4, gfx=0))
        for shared, expected in ((False, 415160), (True, 415160 + 39240)):
            reader = FdinfoReader(root.sysroot, "0000:03:00.0", shared_memory=shared)
            reader.read(1.0)
            self.assertEqual(reader.processes[50].vram, expected * 1024)


class FakeSummary(GpuBackend):
    id = "summary"
    display_name = "Summary"
    started = []

    @classmethod
    def probe(cls, gpu, deps):
        return Probe(SupportLevel.FALLBACK)

    def start(self, elevate=False):
        super().start(elevate)
        FakeSummary.started.append((self.id, elevate))

    def summary(self):
        return GpuSummary(usage=12.0, frequency_hz=1e9, temperature_c=50.0)

    def process_usage(self):
        return {1: GpuProcessUsage(1, usage=12.0)}


class FakeDetail(DetailBackend):
    """A vendor tool: has data only after ``deliver()``."""
    id = "detailed"
    display_name = "Detailed"
    elevation = False
    TABS = (TabSpec("details", "Details", "x-symbolic"),)

    def __init__(self, gpu, deps):
        super().__init__(gpu, deps)
        self.data = False
        self.stopped = False

    @classmethod
    def probe(cls, gpu, deps):
        return Probe(SupportLevel.PREFERRED, needs_elevation=cls.elevation)

    def start(self, elevate=False):
        super().start(elevate)
        FakeSummary.started.append((self.id, elevate))

    def stop(self):
        self.stopped = True

    def deliver(self):
        self.data = True
        self.emit("updated")

    def has_data(self):
        return self.data

    def summary(self):
        return GpuSummary(usage=80.0)

    def create_views(self, controller, services):
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk
        from proccoli.gpu.backend import DetailView, DetailViews
        return DetailViews([DetailView("details", Gtk.Label(label="details"))])

    def process_usage(self):
        return {2: GpuProcessUsage(2, usage=80.0)}


class Never(GpuBackend):
    id = "never"

    @classmethod
    def probe(cls, gpu, deps):
        return Probe(SupportLevel.UNSUPPORTED)


class RegistryAndControllerTest(unittest.TestCase):
    def setUp(self):
        FakeSummary.started = []
        FakeDetail.elevation = False
        self.registry = GpuBackendRegistry((FakeSummary, Never, FakeDetail))
        self.settings = Settings.for_tests()
        self.deps = deps(settings=self.settings)

    def controller(self, registry=None):
        info = DeviceInfo("gpu-0000:00:02.0", DeviceKind.GPU, "GPU", "Intel")
        c = GpuController(info, INTEL, registry or self.registry, self.deps)
        self.states = []
        c.connect("detail-changed", lambda _c, state: self.states.append(state))
        return c

    def test_candidates_best_first_without_unsupported(self):
        ids = [c.id for c, _ in self.registry.candidates(INTEL, self.deps)]
        self.assertEqual(ids, ["detailed", "summary"])

    def test_best_per_role(self):
        self.assertIs(self.registry.best(INTEL, self.deps, BackendRole.SUMMARY)[0],
                      FakeSummary)
        self.assertIs(self.registry.best(INTEL, self.deps, BackendRole.DETAIL)[0], FakeDetail)

    def test_summary_always_runs_and_details_start_without_rights(self):
        c = self.controller()
        c.start()
        self.assertEqual(FakeSummary.started, [("summary", False), ("detailed", False)])
        self.assertEqual(c.detail_state, DetailState.STARTING)
        c.refresh(1.0)
        self.assertEqual(c.latest.usage, 12.0)          # no detail data yet
        c.detail_backend.deliver()
        self.assertEqual(c.detail_state, DetailState.RUNNING)
        self.assertEqual(self.states, ["starting", "running"])
        c.refresh(2.0)
        self.assertEqual(c.latest.usage, 80.0)          # the detail source feeds it
        self.assertEqual(c.summary().temperature_c, 50.0)   # gaps filled from sysfs
        self.assertEqual(set(c.process_usage()), {2})

    def test_elevation_is_offered_not_forced(self):
        FakeDetail.elevation = True
        c = self.controller()
        c.start()
        self.assertEqual(c.detail_state, DetailState.NEEDS_AUTH)
        self.assertIsNone(c.detail_backend)
        self.assertEqual(FakeSummary.started, [("summary", False)])
        c.start_details(elevate=True)
        self.assertEqual(FakeSummary.started[-1], ("detailed", True))
        self.assertEqual(c.detail_state, DetailState.STARTING)

    def test_auto_elevate_setting(self):
        FakeDetail.elevation = True
        self.settings.set("gpu-elevate", True)
        c = self.controller()
        c.start()
        self.assertEqual(FakeSummary.started[-1], ("detailed", True))

    def test_turning_details_off_and_on_is_remembered_per_gpu(self):
        c = self.controller()
        c.start()
        backend = c.detail_backend
        c.set_details_enabled(False)
        self.assertTrue(backend.stopped)
        self.assertEqual(c.detail_state, DetailState.OFF)
        self.assertEqual(self.settings.get("gpu-details-disabled"), ["0000:00:02.0"])
        c2 = self.controller()
        c2.start()
        self.assertEqual(c2.detail_state, DetailState.OFF)
        c2.set_details_enabled(True)
        self.assertEqual(c2.detail_state, DetailState.STARTING)
        self.assertEqual(self.settings.get("gpu-details-disabled"), [])

    def test_failure_keeps_the_summary_and_offers_a_retry(self):
        c = self.controller()
        c.start()
        backend = c.detail_backend
        backend.deliver()
        backend.emit("failed", "no counters", True)
        self.assertEqual(c.detail_state, DetailState.FAILED)
        self.assertEqual((c.detail_message, c.detail_can_elevate), ("no counters", True))
        self.assertIsNone(c.detail_backend)
        self.assertTrue(backend.stopped)
        c.refresh(1.0)
        self.assertEqual(c.latest.usage, 12.0)

    def test_signals_from_a_replaced_backend_are_ignored(self):
        c = self.controller()
        c.start()
        old = c.detail_backend
        c.start_details()
        old.emit("failed", "late", False)
        self.assertEqual(c.detail_state, DetailState.STARTING)

    def test_without_a_detail_tool(self):
        c = self.controller(GpuBackendRegistry((FakeSummary,)))
        c.start()
        self.assertEqual(c.detail_state, DetailState.UNAVAILABLE)
        self.assertIsNone(c.detail_class)
        with self.assertRaises(RuntimeError):
            c.start_details()

    def test_a_gpu_needs_a_summary_source(self):
        with self.assertRaises(RuntimeError):
            self.controller(GpuBackendRegistry((FakeDetail,)))

    def test_stop_stops_both(self):
        c = self.controller()
        c.start()
        backend = c.detail_backend
        c.stop()
        self.assertTrue(backend.stopped)
        self.assertIsNone(c.detail_backend)

    def test_merge_summaries(self):
        merged = merge_summaries(GpuSummary(usage=5.0), GpuSummary(usage=1.0, power_w=3.0))
        self.assertEqual((merged.usage, merged.power_w), (5.0, 3.0))

    def test_standard_registry_prefers_detail(self):
        reg = standard_registry()
        self.assertEqual([c.id for c in reg.classes()], ["intel_gpu_top", "nvidia", "amdgpu",
                                                         "generic"])
        ids = [c.id for c, _ in reg.candidates(
            INTEL, deps(programs={"intel_gpu_top": "/usr/bin/intel_gpu_top"}))]
        self.assertEqual(ids, ["intel_gpu_top", "generic"])
        self.assertEqual([c.id for c, _ in reg.candidates(AMD, deps())], ["generic"])

    def test_discoverer_on_laptop(self):
        d = GpuDiscoverer(self.registry, PCI, FakeSystem())
        [info] = d.discover(SysRoot(LAPTOP), self.settings)
        self.assertEqual((info.id, info.name, info.description),
                         ("gpu-0000:00:02.0", "GPU", "Intel UHD Graphics"))
        self.assertIsInstance(d.create_monitor(info, SysRoot(LAPTOP), self.settings),
                              GpuController)


class IntelGpuTopTest(unittest.TestCase):
    def test_probe_matrix(self):
        root = FakeRoot(self, {"/proc/sys/kernel/perf_event_paranoid": "2\n"})
        have = {"intel_gpu_top": "/usr/bin/intel_gpu_top"}

        def probe(gpu=INTEL, **system):
            return igt.IntelGpuTopBackend.probe(gpu, deps(root.sysroot, **system))
        self.assertEqual(probe(AMD, programs=have).level, SupportLevel.UNSUPPORTED)
        self.assertEqual(probe(programs={}).level, SupportLevel.UNSUPPORTED)
        p = probe(programs=have)
        self.assertEqual((p.level, p.needs_elevation), (SupportLevel.PREFERRED, True))
        self.assertFalse(probe(programs=have, euid=0).needs_elevation)        # root
        self.assertFalse(probe(programs=have, capabilities=True).needs_elevation)
        root.write("/proc/sys/kernel/perf_event_paranoid", "0\n")
        self.assertFalse(probe(programs=have).needs_elevation)
        xe = GpuInfo("card0", "0000:03:00.0", GpuVendor.INTEL, 0x8086, 0x56a0, "xe",
                     "Intel Arc", False)
        self.assertEqual(probe(xe, programs=have).level, SupportLevel.PREFERRED)

    def backend(self, **system):
        return igt.IntelGpuTopBackend(INTEL, deps(**system))

    def test_command(self):
        b = self.backend()
        self.assertEqual(b.command("igt"), ["igt", "-J", "-s", "1000", "-d", "drm:/dev/dri/card1"])
        b.settings.set("intel-gpu-top-interval", "2-seconds")
        self.assertIn("2000", b.command("igt"))
        b.settings.set("intel-gpu-top-interval", "fast")          # an old nick: 1 s now
        self.assertIn("1000", b.command("igt"))

    def test_summary_and_processes_from_records(self):
        b = self.backend()
        samples = igt.demo_samples(1000)
        for _ in range(3):
            b._on_record(None, next(samples))
        s = b.summary()
        latest = b.latest
        self.assertAlmostEqual(s.usage, max(latest["engines"]["Render/3D"]["busy"],
                                            latest["engines"]["Blitter"]["busy"]))
        self.assertEqual(s.encode, latest["engines"]["Video"]["busy"])
        self.assertAlmostEqual(s.frequency_hz, latest["frequency"]["actual"] * 1e6)
        self.assertEqual(s.power_w, latest["power"]["GPU"])
        procs = b.process_usage()
        self.assertEqual(set(procs), {2190, 4410, 9120})
        self.assertIn("engines", b.history.group_order)
        self.assertEqual(len(b.history.times), 3)

    def test_engine_instances_collapse_to_classes(self):
        b = self.backend()
        b._on_record(None, {"engines": {"Render/3D/0": {"busy": 10}, "Render/3D/1": {"busy": 30},
                                        "Video/0": {"busy": 5}}})
        self.assertEqual(b.summary().usage, 30)
        self.assertEqual(b.summary().decode, 5)

    def test_elevated_runs_only_a_root_owned_copy(self):
        # PATH might find ~/.local/bin/intel_gpu_top first.
        b = self.backend(programs={"intel_gpu_top": "/home/u/.local/bin/intel_gpu_top"})
        self.assertEqual(b.executable(False), "/home/u/.local/bin/intel_gpu_top")
        self.assertEqual(b.executable(True), "/usr/bin/intel_gpu_top")
        b.deps.system.trusted = {"/usr/local/bin/intel_gpu_top"}
        self.assertEqual(b.executable(True), "/usr/local/bin/intel_gpu_top")
        b.deps.system.trusted = set()
        self.assertIsNone(b.executable(True))

    def with_helper(self, protocol):
        import dataclasses
        from proccoli.core.privileged import PrivilegedHelper
        d = deps(programs={"intel_gpu_top": "/usr/bin/intel_gpu_top"})
        helper = PrivilegedHelper(d.system, ["/usr/libexec/proccoli/proccoli-helper"],
                                  protocol)
        return igt.IntelGpuTopBackend(INTEL, dataclasses.replace(d, helper=helper))

    def test_elevated_goes_through_the_helper(self):
        # the helper stops intel_gpu_top when Proccoli stops reading.
        b = self.with_helper(3)
        b.start(elevate=True)
        self.assertEqual(b.reader.started, (["/usr/libexec/proccoli/proccoli-helper",
                                             "gpu-top", "1000", "card1"], True))
        b.start(elevate=False)                             # unelevated: run it directly
        self.assertEqual(b.reader.started, (b.command("/usr/bin/intel_gpu_top"), False))
        b.stop()

    def test_older_helper_falls_back_to_running_it_directly(self):
        b = self.with_helper(2)
        with self.assertLogs("proccoli.gpu.intel_gpu_top.backend", "WARNING"):
            b.start(elevate=True)
        self.assertEqual(b.reader.started, (b.command("/usr/bin/intel_gpu_top"), True))
        b.stop()

    def test_no_trusted_copy_fails_without_running_anything(self):
        from gi.repository import GLib
        b = self.backend(programs={"intel_gpu_top": "/opt/igt/intel_gpu_top"})
        b.deps.system.trusted = set()
        failures = []
        b.connect("failed", lambda _b, reason, can: failures.append((reason, can)))
        b.start(elevate=True)
        self.assertEqual(failures, [])                       # not during start()
        ctx = GLib.MainContext.default()
        while ctx.pending():
            ctx.iteration(False)
        self.assertEqual(failures, [(igt.UNTRUSTED_REASON, False)])
        self.assertIsNone(getattr(b.reader, "started", None))
        b.stop()

    def test_failures(self):
        b = self.backend()
        failures = []
        b.connect("failed", lambda _b, reason, can: failures.append((reason, can)))
        b._on_exited(None, 1, "", 0)
        b.elevated = True
        b._on_exited(None, 126, "", 0)
        self.assertIn("performance counters", failures[0][0])
        self.assertTrue(failures[0][1])
        self.assertEqual(failures[1], ("Authentication was cancelled or refused", False))

    def test_pause_keeps_history_still(self):
        b = self.backend()
        samples = igt.demo_samples(1000)
        b._on_record(None, next(samples))
        b.paused = True
        b._on_record(None, next(samples))
        self.assertEqual(len(b.history.times), 1)


class StreamTest(unittest.TestCase):
    def test_parser_chunks(self):
        p = JsonStreamParser()
        self.assertEqual(p.feed('[\n{"a": 1},\n{"a"'), [{"a": 1}])
        self.assertEqual(p.feed(': 2},\n'), [{"a": 2}])
        self.assertEqual(p.feed('garbage {"b": 3}'), [{"b": 3}])

    def test_reader_runs_a_process(self):
        r = StreamReader()
        records, exits = [], []
        r.connect("record", lambda _r, rec: records.append(rec))
        r.connect("exited", lambda _r, rc, err, n: exits.append((rc, n)))
        r.start([sys.executable, "-c",
                 "import sys; print('[{\"a\":1},'); print('{\"a\":2},'); "
                 "sys.stderr.write('bye'); sys.exit(3)"])
        self.assertTrue(pump(lambda: exits))
        self.assertEqual(records, [{"a": 1}, {"a": 2}])
        self.assertEqual(exits, [(3, 2)])

    def test_missing_program(self):
        r = StreamReader()
        exits = []
        r.connect("exited", lambda _r, rc, err, n: exits.append(rc))
        r.start(["/nonexistent/program"])
        self.assertTrue(pump(lambda: exits))
        self.assertEqual(exits, [127])

    def test_stop_suppresses_exit(self):
        r = StreamReader()
        exits = []
        r.connect("exited", lambda *_: exits.append(1))
        r.start([sys.executable, "-c", "import time; time.sleep(5)"])
        r.stop()
        pump(lambda: False, timeout=0.3)
        self.assertEqual(exits, [])

    def test_generator(self):
        r = StreamReader()
        records = []
        r.connect("record", lambda _r, rec: records.append(rec))
        r.start_generator(lambda: iter([{"n": 1}, {"n": 2}]), 0.01)
        self.assertTrue(pump(lambda: len(records) == 2))


if __name__ == "__main__":
    unittest.main()
