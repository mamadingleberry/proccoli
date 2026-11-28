"""core.profile: Lightweight Mode: the profiles, pinned settings,
pci.ids on demand, lazily built pages, and what the context builds."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from helpers import FIXTURES, make_context  # noqa: E402
from proccoli.core import pciids  # noqa: E402
from proccoli.core.profile import (Profile, ProfileSettings, choose_profile,  # noqa: E402
                                   is_pinned, profile_of, profile_settings)
from proccoli.core.settings import Settings  # noqa: E402

PCI_IDS = os.path.join(FIXTURES, "pci", "pci.ids")


class ProfileTest(unittest.TestCase):
    def test_full_and_lightweight(self):
        full, light = Profile.full(), Profile.lightweight()
        self.assertFalse(full.is_lightweight)
        self.assertEqual(full.pins, {})
        self.assertTrue(light.is_lightweight)
        for flag in ("extra_graphs", "app_icons", "gpu_details", "theme_css"):
            self.assertTrue(getattr(full, flag), flag)
            self.assertFalse(getattr(light, flag), flag)
        self.assertTrue(light.lazy_pages and light.pci_on_demand)
        # small charts and short busiest tables on the Overview.
        self.assertEqual((full.overview_chart, light.overview_chart), ("full", "small"))
        self.assertTrue(full.overview_tables and light.overview_tables)
        self.assertEqual((full.overview_top_count, light.overview_top_count), (10, 5))

    def test_full_top_count_is_the_tables(self):
        from proccoli.processes.top import TOP_COUNT
        self.assertEqual(Profile.full().overview_top_count, TOP_COUNT)

    def test_chosen_by_the_setting_or_the_flag(self):
        s = Settings.for_tests()
        self.assertFalse(choose_profile(s).is_lightweight)
        self.assertTrue(choose_profile(s, flag=True).is_lightweight)
        s.set("lightweight", True)
        self.assertTrue(choose_profile(s).is_lightweight)


class PinnedSettingsTest(unittest.TestCase):
    def setUp(self):
        self.base = Settings.for_tests({"graph-time-range": "10-minutes",
                                        "show-graph-axes": True, "log-level": "debug"})
        self.s = profile_settings(self.base, Profile.lightweight())

    def test_pinned_keys(self):
        self.assertIsInstance(self.s, ProfileSettings)
        self.assertEqual(self.s.get("graph-time-range"), "1-minute")     # capped
        self.assertFalse(self.s.get("show-graph-axes"))
        self.assertEqual(self.s.get("log-level"), "warning")
        self.assertEqual(self.s.get("palette"), "system")
        # icons only (or hidden); the meter type is the user's again.
        self.assertEqual(self.s.get("sidebar-style"), "icons")
        self.assertFalse(is_pinned(self.s, "sidebar-meter-type"))
        self.assertTrue(is_pinned(self.s, "show-graph-axes"))
        self.assertFalse(is_pinned(self.s, "base"))
        self.assertFalse(is_pinned(self.base, "show-graph-axes"))
        self.assertTrue(profile_of(self.s).is_lightweight)
        self.assertFalse(profile_of(self.base).is_lightweight)

    def test_a_full_sidebar_comes_back_when_the_mode_is_off(self):
        self.base.set("sidebar-style", "full")
        self.assertEqual(self.s.get("sidebar-style"), "icons")
        self.assertEqual(profile_settings(self.base, Profile.full()).get("sidebar-style"),
                         "full")

    def test_shorter_and_quieter_choices_stay(self):
        self.base.set("graph-time-range", "30-seconds")
        self.base.set("log-level", "error")
        self.assertEqual(self.s.get("graph-time-range"), "30-seconds")
        self.assertEqual(self.s.get("log-level"), "error")

    def test_the_users_choice_is_kept_and_changes_notify_pinned(self):
        seen = []
        self.s.connect_changed("show-graph-axes", lambda _k, v: seen.append(v))
        self.s.set("show-graph-axes", False)
        self.s.set("show-graph-axes", True)
        self.assertEqual(seen, [False, False])                # the profile's value
        self.assertTrue(self.base.get("show-graph-axes"))      # the user's, kept
        self.s.set("base", "binary")                           # not pinned: as usual
        self.assertEqual(self.base.get("base"), "binary")

    def test_tables_keep_only_the_essential_columns(self):
        for key in ("processes-show-cpu", "processes-show-memory", "processes-show-id",
                    "apps-show-cpu"):
            self.assertFalse(is_pinned(self.s, key), key)
        for key in ("processes-show-commandline", "apps-show-gpu", "processes-show-user"):
            self.assertFalse(self.s.get(key), key)
        self.assertTrue(set(self.s.profile.pins) <= set(self.s.keys()))   # all real keys

    def test_full_profile_hands_out_the_settings_themselves(self):
        self.assertIs(profile_settings(self.base, Profile.full()), self.base)


class RestartTest(unittest.TestCase):
    def test_started_the_same_way(self):
        from proccoli.core.system import restart_command
        py = "/usr/bin/python3"
        self.assertEqual(restart_command("/home/u/proccoli/src/proccoli/__main__.py", py, False),
                         (py, [py, "-m", "proccoli"]))
        self.assertEqual(restart_command("/tmp/not-executable", py, False),
                         (py, [py, "/tmp/not-executable"]))

    def test_the_launcher_runs_itself_so_the_process_keeps_its_name(self):
        # Through the interpreter, the kernel would name the window "python3".
        from proccoli.core.system import restart_command
        program, argv = restart_command("/usr/bin/proccoli-gui", "/usr/bin/python3", True)
        self.assertEqual(program, "/usr/bin/proccoli-gui")
        self.assertEqual(argv, ["/usr/bin/proccoli-gui"])

    def test_a_real_restart_keeps_the_process_name(self):
        # Run a launcher like the installed one; it restarts itself once the
        # way Restart Now does, then prints the name the kernel gave it.
        import subprocess
        import tempfile
        src = os.path.join(os.path.dirname(__file__), "..", "src")
        with tempfile.TemporaryDirectory() as tmp:
            launcher = os.path.join(tmp, "proccoli-gui")
            with open(launcher, "w") as fh:
                fh.write(f"""#!{sys.executable}
import os, sys
sys.path.insert(0, {os.path.abspath(src)!r})
from proccoli.core.system import System
if "--again" in sys.argv:
    print(open("/proc/self/comm").read().strip())
else:
    System().restart_self(["--again"])
""")
            os.chmod(launcher, 0o755)
            out = subprocess.run([launcher], capture_output=True, text=True, timeout=30)
        self.assertEqual(out.stdout.strip(), "proccoli-gui", out.stderr)


class OnDemandPciTest(unittest.TestCase):
    def test_same_answers_as_the_full_parse(self):
        full = pciids.load(PCI_IDS)
        lazy = pciids.on_demand(PCI_IDS)
        pairs = list(full.devices)[:40] + [(0x8086, 0xFFFF), (0xFFFF, 0x1)]
        for vendor, device in pairs:
            self.assertEqual(lazy.device(vendor, device), full.device(vendor, device),
                             (hex(vendor), hex(device)))
            self.assertEqual(lazy.vendor(vendor), full.vendor(vendor), hex(vendor))
        self.assertIsNone(lazy.vendor(None))
        self.assertLessEqual(len(lazy._devices), len(pairs))   # only what was asked

    def test_no_database(self):
        lazy = pciids.OnDemandPciIds(None)
        self.assertIsNone(lazy.vendor(0x8086))
        self.assertIsNone(lazy.device(0x8086, 0x1))


class _Page:
    def __init__(self, name):
        self.name = name


class LazyPagesTest(unittest.TestCase):
    def setUp(self):
        from proccoli.ui.lazy import LazyPages
        self.timers = []
        self.lazy = LazyPages(60, schedule=lambda s, cb: self.timers.append((s, cb)))
        self.dropped = []
        self.lazy.on_drop = self.dropped.append
        self.stub = self.lazy.add("cpu", lambda: _Page("real"), lambda: _Page("stub"))

    def test_built_on_first_visit_dropped_a_while_after(self):
        self.assertEqual(self.stub.name, "stub")
        self.assertEqual(self.lazy.shown("cpu").name, "real")
        self.assertIsNone(self.lazy.shown("cpu"))             # already built
        self.assertIsNone(self.lazy.shown("overview"))         # not lazy
        self.assertEqual(self.timers[0][0], 60)
        self.assertFalse(self.timers[0][1]())                  # one-shot
        self.assertEqual(self.dropped, ["cpu"])
        self.assertEqual(self.lazy.shown("cpu").name, "real")  # built again

    def test_coming_back_before_the_timer_keeps_it(self):
        self.lazy.shown("cpu")
        self.lazy.shown("overview")
        self.lazy.shown("cpu")                                 # back in time
        self.timers[0][1]()
        self.assertEqual(self.dropped, [])
        self.lazy.shown("overview")
        self.timers[-1][1]()                                   # the newer timer
        self.assertEqual(self.dropped, ["cpu"])

    def test_removed_pages_are_forgotten(self):
        self.lazy.shown("cpu")
        self.lazy.remove("cpu")
        self.lazy.shown("overview")
        self.assertEqual(self.timers, [])


class ContextTest(unittest.TestCase):
    def test_lightweight_context(self):
        settings = profile_settings(Settings.for_tests(), Profile.lightweight())
        ctx = make_context(self, settings=settings)
        self.assertTrue(ctx.profile.is_lightweight)
        self.assertIsNone(ctx.app_icons)
        full = make_context(self)
        self.assertFalse(full.profile.is_lightweight)
        self.assertIsNotNone(full.app_icons)

    def test_process_list_is_dropped_when_nobody_shows_it(self):
        for profile, kept in ((Profile.lightweight(), False), (Profile.full(), True)):
            ctx = make_context(self, settings=profile_settings(Settings.for_tests(), profile))
            monitor = ctx.processes
            monitor.acquire()
            monitor.processes, monitor._prev = {1: "info"}, {1: "raw"}
            monitor.release()
            self.assertEqual(bool(monitor.processes), kept, profile.name)
            self.assertEqual(bool(monitor._prev), kept, profile.name)

    def test_pci_on_demand_only_without_an_injected_database(self):
        from proccoli.context import build_context
        from helpers import FakeSystem
        from proccoli.core.sysroot import SysRoot
        settings = profile_settings(Settings.for_tests(), Profile.lightweight())
        ctx = build_context(settings, system=FakeSystem(), sysroot=SysRoot(FIXTURES),
                            helper_command=None, connection_name=None)
        self.assertIsInstance(ctx.pci, pciids.OnDemandPciIds)

    def test_tables_show_no_icons(self):
        from proccoli.ui.columns import Column, shown_column
        spec = Column("name", "Name", value=str, text=str, icon=lambda d: None)
        light = profile_settings(Settings.for_tests(), Profile.lightweight())
        self.assertIsNone(shown_column(spec, light).icon)
        self.assertIs(shown_column(spec, Settings.for_tests()), spec)


class GpuDetailsTest(unittest.TestCase):
    def test_details_are_not_started(self):
        from proccoli.gpu.controller import DetailState
        from helpers import FakeSystem
        from proccoli.gpu.backend import GpuDeps
        from proccoli.gpu.controller import GpuController
        from proccoli.gpu.registry import standard_registry
        from proccoli.core.sysroot import SysRoot
        from proccoli.devices.base import DeviceInfo, DeviceKind
        import test_gpu
        settings = profile_settings(Settings.for_tests(), Profile.lightweight())
        info = DeviceInfo("gpu-0000:00:02.0", DeviceKind.GPU, "GPU")
        system = FakeSystem(programs={"intel_gpu_top": "/usr/bin/intel_gpu_top"})
        with self.assertLogs("proccoli.gpu", "INFO"):
            c = GpuController(info, test_gpu.INTEL, standard_registry(),
                              GpuDeps(SysRoot(FIXTURES), settings, system))
            c.start()
        self.addCleanup(c.stop)
        self.assertEqual(c.detail_state, DetailState.OFF)
        self.assertIn("Lightweight Mode", c.detail_message)



class RendererTest(unittest.TestCase):
    """Lightweight Mode draws with Cairo; a user's choice wins, and
    Proccoli's own choice doesn't outlive the mode across *Restart Now*."""

    def test_lightweight_draws_with_cairo(self):
        from proccoli.core.profile import apply_renderer
        env = {}
        self.assertEqual(apply_renderer(Profile.lightweight(), env), "cairo")
        self.assertEqual(env["GSK_RENDERER"], "cairo")

    def test_back_to_full_clears_our_choice(self):
        from proccoli.core.profile import apply_renderer
        env = {}
        apply_renderer(Profile.lightweight(), env)          # carried over by exec
        self.assertEqual(apply_renderer(Profile.full(), env), "")
        self.assertNotIn("GSK_RENDERER", env)

    def test_the_users_choice_wins(self):
        from proccoli.core.profile import apply_renderer
        env = {"GSK_RENDERER": "vulkan"}
        self.assertEqual(apply_renderer(Profile.lightweight(), env), "vulkan")
        self.assertEqual(apply_renderer(Profile.full(), env), "vulkan")
        self.assertEqual(env, {"GSK_RENDERER": "vulkan"})


if __name__ == "__main__":
    unittest.main()
