"""The composition root wires the same graph for the app and for tests."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from helpers import FakeSystem, make_context  # noqa: E402

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.devices.base import DeviceKind  # noqa: E402


class ContextTest(unittest.TestCase):
    def test_real_wiring_on_the_laptop_fixture(self):
        ctx = make_context(self)
        kinds = [d.kind for d in ctx.devices.discoverers]
        self.assertEqual(kinds, [DeviceKind.CPU, DeviceKind.MEMORY, DeviceKind.GPU,
                                 DeviceKind.DRIVE, DeviceKind.NETWORK, DeviceKind.BATTERY])
        self.assertIsNotNone(ctx.processes)
        self.assertIs(ctx.processes.system, ctx.system)
        self.assertIs(ctx.actions.system, ctx.system)
        self.assertFalse(ctx.demo)
        ctx.devices.start()
        self.assertEqual([m.info.id for m in ctx.devices.monitors()],
                         ["cpu", "memory", "gpu-0000:00:02.0", "drive-sda", "net-eno1",
                          "net-wlp43s0"])

    def test_gpu_backends_are_injectable(self):
        from proccoli.gpu.generic_drm import GenericDrmBackend
        from proccoli.gpu.registry import GpuBackendRegistry
        registry = GpuBackendRegistry((GenericDrmBackend,))
        ctx = make_context(self, gpu_registry=registry)
        ctx.devices.start()
        gpu = ctx.devices.monitor("gpu-0000:00:02.0")
        self.assertIs(gpu.registry, registry)
        self.assertIsNone(gpu.detail_class)

    def test_performance_log_is_wired_and_stopped(self):
        ctx = make_context(self)
        self.assertIs(ctx.perf_log.ticker, ctx.ticker)
        ctx.stop()
        self.assertIsNone(ctx.perf_log)

    def test_demo_reads_nothing_real(self):
        ctx = make_context(self, demo=True)
        self.assertNotEqual(str(ctx.app_icons.sysroot.root), str(ctx.sysroot.root))
        self.assertIsNone(ctx.processes)
        self.assertEqual([d.kind for d in ctx.devices.discoverers],
                         [DeviceKind.DEMO, DeviceKind.GPU])

    def test_helper_needs_pkexec_and_a_command(self):
        self.assertIsNone(make_context(self).helper)
        with_pkexec = FakeSystem(programs={"pkexec": "/usr/bin/pkexec"})
        ctx = make_context(self, system=with_pkexec, helper_command=["/x/helper"])
        self.assertEqual(ctx.helper.argv, ["/x/helper"])
        self.assertIs(ctx.actions.helper, ctx.helper)

    def test_grouper_uses_the_systems_desktop_lookup(self):
        from proccoli.core.system import AppInfo
        system = FakeSystem(apps={"org.x.App": AppInfo("X")})
        ctx = make_context(self, system=system)
        self.assertEqual(ctx.grouper.info_for("org.x.App").name, "X")

    def test_ticker_follows_settings_and_start_connects(self):
        settings = Settings.for_tests({"update-interval": "3-seconds"})
        ctx = make_context(self, demo=True, settings=settings)
        self.assertEqual(ctx.ticker.interval_ms, 3000)
        ctx.start()
        ticks = []
        ctx.devices.connect("device-added", lambda *a: ticks.append(a))
        ctx.ticker.tick_now()
        self.assertIsNotNone(ctx.devices.monitor("demo").latest)

    def test_stop_without_providers(self):
        ctx = make_context(self, demo=True)
        ctx.devices = None
        ctx.start()
        ctx.stop()


if __name__ == "__main__":
    unittest.main()
