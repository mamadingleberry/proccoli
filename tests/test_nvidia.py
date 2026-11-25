"""NVIDIA detail source: parsing nvidia-settings and
nvidia-smi, choosing between them, failing with a reason; and the GPU
detection plan that picks each GPU's panel."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from helpers import FIXTURES, FakeSystem, read_file  # noqa: E402

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.sysroot import SysRoot  # noqa: E402
from proccoli.devices.base import DeviceInfo, DeviceKind  # noqa: E402
from proccoli.gpu.backend import BackendRole, GpuDeps, SupportLevel  # noqa: E402
from proccoli.gpu.controller import DetailState, GpuController  # noqa: E402
from proccoli.gpu.detect import plan_gpu  # noqa: E402
from proccoli.gpu.info import GpuInfo, GpuVendor  # noqa: E402
from proccoli.gpu.nvidia import query  # noqa: E402
from proccoli.gpu.nvidia.backend import UNREACHABLE, NvidiaBackend  # noqa: E402
from proccoli.gpu.nvidia.query import NvidiaError  # noqa: E402
from proccoli.gpu.registry import GpuBackendRegistry, standard_registry  # noqa: E402

NV = os.path.join(FIXTURES, "nvidia")
NVIDIA = GpuInfo("card1", "0000:02:00.0", GpuVendor.NVIDIA, 0x10de, 0x2d59, "nvidia",
                 "NVIDIA GPU", False, "renderD129")
INTEL = GpuInfo("card0", "0000:00:02.0", GpuVendor.INTEL, 0x8086, 0x7d67, "i915",
                "Intel Graphics", True, "renderD128")
BOTH = {"nvidia-settings": "/usr/bin/nvidia-settings", "nvidia-smi": "/usr/bin/nvidia-smi"}
MIB = 1024 * 1024


def fixture(name):
    return read_file(os.path.join(NV, name))


def make_deps(programs=None):
    return GpuDeps(SysRoot("/nonexistent"), Settings.for_tests(),
                   FakeSystem(programs=dict(BOTH if programs is None else programs)))


class SmiParseTest(unittest.TestCase):
    def test_real_rtx_5060_output(self):
        s = query.parse_smi(0, fixture("smi-rtx5060-laptop.csv"), "")
        self.assertEqual(s.tool, "nvidia-smi")
        self.assertEqual(s.name, "NVIDIA GeForce RTX 5060 Laptop GPU")
        self.assertEqual(s.driver, "580.178.04")
        self.assertEqual((s.usage, s.memory_util, s.encoder, s.decoder), (19, 3, 0, 0))
        self.assertEqual((s.vram_used, s.vram_total), (571 * MIB, 8151 * MIB))
        self.assertEqual(s.temperature_c, 39)
        self.assertAlmostEqual(s.power_w, 8.83)
        self.assertIsNone(s.power_limit_w)                      # [N/A] on this laptop
        self.assertIsNone(s.fan)                                # [N/A]
        self.assertEqual((s.clock_hz, s.memory_clock_hz), (630e6, 810e6))
        self.assertEqual(s.pstate, "P5")

    def test_summary(self):
        summary = query.parse_smi(0, fixture("smi-rtx5060-laptop.csv"), "").to_summary()
        self.assertEqual(summary.usage, 19)
        self.assertEqual((summary.encode, summary.decode), (0, 0))
        self.assertFalse(summary.combined_video)
        self.assertAlmostEqual(summary.memory_usage, 100 * 571 / 8151)
        self.assertEqual(summary.vram_frequency_hz, 810e6)

    def test_argv_asks_for_one_gpu_by_slot(self):
        argv = query.smi_argv("/usr/bin/nvidia-smi", "0000:02:00.0")
        self.assertEqual(argv[-2:], ["-i", "0000:02:00.0"])
        self.assertIn("--format=csv,noheader,nounits", argv)
        self.assertEqual(argv[1].split("=", 1)[1].split(","), list(query.SMI_FIELDS))

    def test_errors(self):
        with self.assertRaises(NvidiaError) as cm:
            query.parse_smi(6, "No devices were found\n", "")
        self.assertTrue(cm.exception.unreachable)
        with self.assertRaises(NvidiaError) as cm:
            query.parse_smi(0, "garbage\n", "")
        self.assertFalse(cm.exception.unreachable)
        self.assertIn("unexpected", str(cm.exception))


class SettingsParseTest(unittest.TestCase):
    def test_targets_on_x11(self):
        targets = query.parse_settings_targets(0, fixture("settings-targets.txt"), "")
        self.assertEqual(targets, {"0000:01:00.0": 0, "0000:02:00.0": 1})

    def test_targets_on_wayland_real(self):
        # The PCI attributes work without NV-CONTROL; "[gpu:0]" has no host.
        targets = query.parse_settings_targets(0, fixture("settings-targets-wayland.txt"), "")
        self.assertEqual(targets, {"0000:02:00.0": 0})

    def test_readings(self):
        s = query.parse_settings(0, fixture("settings-readings.txt"), "")
        self.assertEqual(s.tool, "nvidia-settings")
        self.assertEqual((s.usage, s.memory_util, s.video, s.pcie), (23, 7, 4, 1))
        self.assertEqual(s.temperature_c, 48)
        self.assertEqual((s.clock_hz, s.memory_clock_hz), (1335e6, 5001e6))
        self.assertEqual((s.vram_used, s.vram_total), (1214 * MIB, 8188 * MIB))
        summary = s.to_summary()
        self.assertTrue(summary.combined_video)                 # one video figure
        self.assertEqual((summary.encode, summary.decode), (4, 4))

    def test_readings_on_wayland_are_unreachable(self):
        with self.assertRaises(NvidiaError) as cm:
            query.parse_settings(1, "", fixture("settings-readings-wayland.stderr"))
        self.assertTrue(cm.exception.unreachable)
        self.assertIn("No targets match", str(cm.exception))
        self.assertFalse(str(cm.exception).startswith("ERROR"))

    def test_no_display(self):
        with self.assertRaises(NvidiaError) as cm:
            query.parse_settings_targets(1, "", "ERROR: Unable to init server: Could not "
                                                "connect: Connection refused\n")
        self.assertTrue(cm.exception.unreachable)

    def test_wrong_line_count(self):
        with self.assertRaises(NvidiaError):
            query.parse_settings(0, "graphics=1, memory=2, video=0, PCIe=0\n", "")

    def test_argv(self):
        argv = query.settings_argv("nvidia-settings", 1)
        self.assertEqual(argv[:2], ["nvidia-settings", "-t"])
        self.assertEqual(argv[2:4], ["-q", "[gpu:1]/GPUUtilization"])


class ProbeTest(unittest.TestCase):
    def test_matrix(self):
        nouveau = GpuInfo("card1", "0000:02:00.0", GpuVendor.NVIDIA, 0x10de, 1, "nouveau",
                          "NVIDIA", False, None)
        for gpu, programs, level, words in (
                (NVIDIA, BOTH, SupportLevel.PREFERRED, "nvidia-settings, then nvidia-smi"),
                (NVIDIA, {"nvidia-smi": "/usr/bin/nvidia-smi"}, SupportLevel.PREFERRED,
                 "nvidia-smi"),
                (NVIDIA, {}, SupportLevel.UNSUPPORTED, "neither"),
                (nouveau, BOTH, SupportLevel.UNSUPPORTED, "nouveau"),
                (INTEL, BOTH, SupportLevel.UNSUPPORTED, "not an NVIDIA GPU")):
            with self.subTest(driver=gpu.driver, programs=list(programs)):
                probe = NvidiaBackend.probe(gpu, make_deps(programs))
                self.assertEqual(probe.level, level)
                self.assertIn(words, probe.reason)
                self.assertFalse(probe.needs_elevation)


class BackendTest(unittest.TestCase):
    def make(self, programs=None, results=()):
        deps = make_deps(programs)
        deps.system.run_results = list(results)
        backend = NvidiaBackend(NVIDIA, deps)
        self.events = []
        backend.connect("updated", lambda _b: self.events.append("updated"))
        backend.connect("failed", lambda _b, reason, _e: self.events.append(("failed", reason)))
        self.system = deps.system
        return backend

    def test_nvidia_settings_on_x11(self):
        targets = fixture("settings-targets.txt")
        readings = fixture("settings-readings.txt")
        b = self.make(results=[(0, targets, ""), (0, readings, ""), (0, readings, "")])
        b.start()
        self.assertEqual(b.tool, "nvidia-settings")
        self.assertEqual(self.system.runs[1][2:4], ["-q", "[gpu:1]/GPUUtilization"])  # by slot
        self.assertEqual(b.summary().usage, 23)
        self.assertTrue(b.has_data())
        b.refresh(2.0)
        self.assertEqual(self.events, ["updated", "updated"])
        self.assertEqual(b.history.series("graphics").latest(), 23)
        self.assertIn("nvidia-settings", b.source_note)

    def test_wayland_falls_back_to_nvidia_smi(self):
        # Real output from this machine's GNOME Wayland session.
        b = self.make(results=[
            (0, fixture("settings-targets-wayland.txt"), ""),
            (1, "", fixture("settings-readings-wayland.stderr")),
            (0, fixture("smi-rtx5060-laptop.csv"), "")])
        with self.assertLogs("proccoli.gpu.nvidia.backend", "INFO") as logs:
            b.start()
        self.assertEqual(b.tool, "nvidia-smi")
        self.assertEqual(self.system.runs[2][0], "/usr/bin/nvidia-smi")
        self.assertEqual(b.summary().usage, 19)
        self.assertEqual(b.source_note, f"nvidia-smi ({UNREACHABLE})")
        self.assertIn("No targets match", logs.output[0])        # the tool's words: logged
        self.assertEqual(self.events, ["updated"])

    def test_without_nvidia_settings_uses_nvidia_smi(self):
        b = self.make({"nvidia-smi": "/usr/bin/nvidia-smi"},
                      [(0, fixture("smi-rtx5060-laptop.csv"), "")])
        with self.assertLogs("proccoli.gpu.nvidia.backend", "INFO"):
            b.start()
        self.assertEqual(b.tool, "nvidia-smi")
        self.assertIn("isn't installed", b.source_note)

    def test_neither_tool_can_read_it_fails_with_the_reason(self):
        b = self.make({"nvidia-settings": "/usr/bin/nvidia-settings"},
                      [(1, "", fixture("settings-readings-wayland.stderr"))])
        b.start()
        self.assertEqual(len(self.events), 1)
        kind, reason = self.events[0]
        self.assertEqual(kind, "failed")
        self.assertTrue(reason.startswith(UNREACHABLE + ", and nvidia-smi isn't installed"))
        self.assertFalse(b.has_data())

    def test_a_running_source_survives_a_few_bad_readings(self):
        good = (0, fixture("smi-rtx5060-laptop.csv"), "")
        bad = (2, "", "Unable to determine the device handle: Unknown Error")
        b = self.make({"nvidia-smi": "/usr/bin/nvidia-smi"}, [good, bad, bad, good, bad, bad, bad])
        with self.assertLogs("proccoli.gpu.nvidia.backend", "INFO"):
            b.start()
        for t in range(2, 8):
            b.refresh(float(t))
        failures = [e for e in self.events if e != "updated"]
        self.assertEqual(len(failures), 1)                       # only after 3 in a row
        self.assertIn("Unknown Error", failures[0][1])

    def test_first_reading_failing_fails_at_once(self):
        b = self.make({"nvidia-smi": "/usr/bin/nvidia-smi"}, [(2, "", "Unknown Error")])
        with self.assertLogs("proccoli.gpu.nvidia.backend", "INFO"):
            b.start()
        self.assertEqual(self.events[0][0], "failed")

    def test_answers_after_stop_are_dropped(self):
        b = self.make({"nvidia-smi": "/usr/bin/nvidia-smi"})
        pending = []
        b.system.run_async = lambda argv, cb: pending.append(cb)
        with self.assertLogs("proccoli.gpu.nvidia.backend", "INFO"):
            b.start()
        b.refresh(1.0)                                           # still busy: no second run
        self.assertEqual(len(pending), 1)
        b.stop()
        pending[0](0, fixture("smi-rtx5060-laptop.csv"), "")
        self.assertEqual(self.events, [])
        self.assertFalse(b.has_data())


class PlanTest(unittest.TestCase):
    """Which panel each GPU gets."""

    def test_this_machines_gpus(self):
        registry = standard_registry()
        nvidia = plan_gpu(NVIDIA, registry, make_deps())
        self.assertEqual(nvidia.summary.backend.id, "generic")
        self.assertEqual(nvidia.detail.backend.id, "nvidia")
        self.assertEqual(nvidia.panel(), "overview + NVIDIA tabs")
        self.assertEqual(nvidia.detail_text(), "NVIDIA (nvidia-settings, then nvidia-smi)")
        intel = plan_gpu(INTEL, registry, make_deps({}))          # no intel_gpu_top
        self.assertIsNone(intel.detail)
        self.assertEqual(intel.panel(), "overview only")
        self.assertEqual(intel.detail_text(),
                         "None: intel_gpu_top is not installed (package intel-gpu-tools)")

    def test_explain_lists_every_backend(self):
        text = plan_gpu(NVIDIA, standard_registry(), make_deps()).explain()
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith("NVIDIA GPU 0000:02:00.0 (driver nvidia): "
                                            "overview + NVIDIA tabs"))
        self.assertIn("  intel_gpu_top (detail) not usable: not an Intel GPU", lines)
        self.assertIn("  nvidia (detail) chosen: nvidia-settings, then nvidia-smi", lines)
        self.assertTrue(any(l.startswith("  generic (summary) chosen") for l in lines))

    def test_nothing_can_serve_it_is_an_error_with_the_plan(self):
        registry = GpuBackendRegistry((NvidiaBackend,))           # no summary source
        plan = plan_gpu(NVIDIA, registry, make_deps())
        self.assertFalse(plan.usable)
        self.assertEqual(plan.panel(), "error page")
        info = DeviceInfo("gpu-0000:02:00.0", DeviceKind.GPU, "GPU", "NVIDIA")
        with self.assertLogs("proccoli.gpu.controller", "INFO"), \
                self.assertRaises(RuntimeError) as cm:
            GpuController(info, NVIDIA, registry, make_deps())
        self.assertIn("No statistics source can read this GPU", str(cm.exception))
        self.assertIn("nvidia (detail) usable", str(cm.exception))

    def test_controller_runs_nvidia_and_feeds_the_overview(self):
        deps = make_deps({"nvidia-smi": "/usr/bin/nvidia-smi"})
        deps.system.run_results = [(0, fixture("smi-rtx5060-laptop.csv"), "")] * 3
        info = DeviceInfo("gpu-0000:02:00.0", DeviceKind.GPU, "GPU", "NVIDIA")
        with self.assertLogs("proccoli.gpu", "INFO"):
            c = GpuController(info, NVIDIA, standard_registry(), deps)
            c.start()
        self.assertEqual(c.plan.detail.backend, NvidiaBackend)
        self.assertEqual(c.detail_state, DetailState.RUNNING)
        c.refresh(1.0)
        self.assertEqual(c.latest.usage, 19)
        self.assertEqual(c.summary().temperature_c, 39)
        self.assertEqual(c.process_usage(), {})                    # summary source's (none)
        self.assertEqual(c.plan.detail.backend.role, BackendRole.DETAIL)


if __name__ == "__main__":
    unittest.main()
