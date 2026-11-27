"""Packaging: data files validate, the polkit policy covers the helper, and
install.sh / build-deb.sh produce a complete, removable installation."""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
from helpers import read_file  # noqa: E402

from proccoli import (APP_ID, GPU_ICON, MEMORY_ICON, MISSING_APP_ICON, OVERVIEW_ICON,  # noqa: E402
                     PROCESSOR_ICON, __version__)
from proccoli.core.privileged import INSTALLED_HELPERS  # noqa: E402
from proccoli.metrics import EXIT_SUPERSEDED  # noqa: E402
from proccoli.helper.proccoli_helper import COMMANDS  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")


def data(name):
    return os.path.join(DATA, name)


class DataFilesTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("desktop-file-validate"), "no desktop-file-validate")
    def test_desktop_file_validates(self):
        r = subprocess.run(["desktop-file-validate", data(f"{APP_ID}.desktop")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    @unittest.skipUnless(shutil.which("appstreamcli"), "no appstreamcli")
    def test_metainfo_validates(self):
        r = subprocess.run(["appstreamcli", "validate", "--no-net",
                            data(f"{APP_ID}.metainfo.xml")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_desktop_file_identity(self):
        entries = dict(line.split("=", 1)
                       for line in read_file(data(f"{APP_ID}.desktop")).splitlines()
                       if "=" in line)
        self.assertEqual(entries["Icon"].strip(), APP_ID)
        self.assertEqual(entries["StartupWMClass"].strip(), APP_ID)
        self.assertEqual(entries["Exec"].strip(), "proccoli-gui")

    def test_metainfo_identity(self):
        root = ET.parse(data(f"{APP_ID}.metainfo.xml")).getroot()
        self.assertEqual(root.findtext("id"), APP_ID)
        self.assertEqual(root.findtext("launchable"), f"{APP_ID}.desktop")
        self.assertEqual(root.findtext("project_license"), "0BSD")
        self.assertEqual(root.find("releases/release").get("version"), __version__)


class PolicyTest(unittest.TestCase):
    def setUp(self):
        self.actions = {a.get("id"): a for a in
                        ET.parse(data(f"{APP_ID}.policy")).getroot().findall("action")}

    def annotations(self, action):
        return {a.get("key").rsplit(".", 1)[1]: a.text for a in action.findall("annotate")}

    def test_every_helper_subcommand_has_an_action(self):
        for sub in COMMANDS:
            action = self.actions[f"{APP_ID}.{sub}"]
            ann = self.annotations(action)
            self.assertEqual(ann["argv1"], sub)
            self.assertEqual(ann["path"], "@LIBEXECDIR@/proccoli-helper")
            self.assertEqual(action.findtext("defaults/allow_active"), "auth_admin_keep")

    def test_intel_gpu_top_always_asks(self):
        action = self.actions[f"{APP_ID}.intel-gpu-top"]
        self.assertEqual(self.annotations(action)["path"], "/usr/bin/intel_gpu_top")
        for who in ("allow_any", "allow_inactive", "allow_active"):
            self.assertEqual(action.findtext(f"defaults/{who}"), "auth_admin")

    def test_every_action_has_a_message(self):
        for action in self.actions.values():
            self.assertTrue(action.findtext("message"))
            self.assertTrue(action.findtext("description"))


class InstallTest(unittest.TestCase):
    def install(self, prefix="/usr", uninstall=False, parts=(), ok=True):
        env = dict(os.environ, DESTDIR=self.dest, PREFIX=prefix)
        args = [os.path.join(ROOT, "packaging", "install.sh")] + [f"--{p}" for p in parts]
        if uninstall:
            args.append("--uninstall")
        r = subprocess.run(args, env=env, capture_output=True, text=True)
        if ok:
            self.assertEqual(r.returncode, 0, r.stderr)
        else:
            self.assertNotEqual(r.returncode, 0)
        return r

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dest = tmp.name

    def files(self):
        out = set()
        for dirpath, _d, files in os.walk(self.dest):
            out |= {os.path.relpath(os.path.join(dirpath, f), self.dest) for f in files}
        return out

    def test_install_contents(self):
        self.install()
        files = self.files()
        for expected in (
                "usr/bin/proccoli-gui", "usr/libexec/proccoli/proccoli-helper",
                f"usr/share/applications/{APP_ID}.desktop",
                f"usr/share/metainfo/{APP_ID}.metainfo.xml",
                f"usr/share/glib-2.0/schemas/{APP_ID}.gschema.xml",
                f"usr/share/polkit-1/actions/{APP_ID}.policy",
                f"usr/share/icons/hicolor/scalable/apps/{APP_ID}.svg",
                f"usr/share/icons/hicolor/512x512/apps/{APP_ID}.png",
                f"usr/share/icons/hicolor/symbolic/apps/{PROCESSOR_ICON}.svg",
                f"usr/share/icons/hicolor/symbolic/apps/{GPU_ICON}.svg",
                f"usr/share/icons/hicolor/symbolic/apps/{MISSING_APP_ICON}.svg",
                f"usr/share/icons/hicolor/symbolic/apps/{MEMORY_ICON}.svg",
                f"usr/share/icons/hicolor/symbolic/apps/{OVERVIEW_ICON}.svg",
                "usr/share/proccoli/proccoli/app.py",
                "usr/share/proccoli/proccoli/gpu/intel_gpu_top/views.py"):
            self.assertIn(expected, files)
        self.assertFalse([f for f in files if "__pycache__" in f])
        self.assertTrue(os.access(os.path.join(self.dest, "usr/libexec/proccoli/proccoli-helper"),
                                  os.X_OK))
        launcher = read_file(os.path.join(self.dest, "usr/bin/proccoli-gui"))
        self.assertIn('sys.path.insert(0, "/usr/share/proccoli")', launcher)

    def test_the_background_collector_and_its_unit(self):
        for prefix in ("/usr", "/usr/local"):
            with self.subTest(prefix):
                self.install(prefix)
                base = os.path.join(self.dest, prefix.lstrip("/"))
                unit = read_file(os.path.join(base, "lib/systemd/user/proccoli.service"))
                self.assertIn(f"ExecStart={prefix}/bin/proccoli", unit)
                self.assertNotIn("@BINDIR@", unit)
                self.assertIn("WantedBy=default.target", unit)
                # Restarted after any exit but the one that means another
                # recorder already serves.
                self.assertIn("Restart=always", unit)
                self.assertIn(f"RestartPreventExitStatus={EXIT_SUPERSEDED}", unit)
                self.assertIn(f"SuccessExitStatus={EXIT_SUPERSEDED}", unit)
                # Grouped with the window by the desktop's app slice.
                self.assertIn(f"Slice=app-{APP_ID}.slice", unit)
                self.assertNotIn("@APP_ID@", unit)
                # Always on, started on demand.
                dbus = read_file(os.path.join(base, f"share/dbus-1/services/{APP_ID}.Metrics.service"))
                self.assertIn(f"Name={APP_ID}.Metrics", dbus)
                self.assertIn(f"Exec={prefix}/bin/proccoli", dbus)
                self.assertIn("SystemdService=proccoli.service", dbus)
                preset = read_file(os.path.join(base, "lib/systemd/user-preset/90-proccoli.preset"))
                self.assertIn("enable proccoli.service", preset)
                launcher = os.path.join(base, "bin/proccoli")
                self.assertTrue(os.access(launcher, os.X_OK))
                self.assertIn("from proccoli.metrics import main", read_file(launcher))
                compile(read_file(launcher), "proccoli", "exec")

    @unittest.skipUnless(shutil.which("systemd-analyze"), "no systemd-analyze")
    def test_the_unit_verifies(self):
        self.install()
        unit = os.path.join(self.dest, "usr/lib/systemd/user/proccoli.service")
        r = subprocess.run(["systemd-analyze", "--user", "verify", unit],
                           capture_output=True, text=True)
        # The ExecStart path is /usr/bin (not this staging dir): only that may be reported.
        # Without a user session (some test runners) it can't find the
        # runtime directory: that's the environment, not the unit.
        # Warnings about other units on this machine aren't this unit's.
        problems = [l for l in (r.stdout + r.stderr).splitlines()
                    if l.strip() and "proccoli" not in l.split(":")[-1]
                    and not (re.match(r"/\S+\.(service|socket|target|timer):\d+:", l)
                             and "/proccoli.service:" not in l)
                    and "Command /usr/bin/proccoli" not in l
                    and "RuntimeDirectory" not in l and "runtime directory" not in l]
        self.assertEqual(problems, [], r.stderr)

    def test_policy_points_at_the_installed_helper(self):
        for prefix in ("/usr", "/usr/local"):
            self.install(prefix)
            policy = read_file(os.path.join(self.dest, prefix.lstrip("/"), "share/polkit-1/actions",
                                       f"{APP_ID}.policy"))
            self.assertNotIn("@LIBEXECDIR@", policy)
            path = f"{prefix}/libexec/proccoli/proccoli-helper"
            self.assertIn(path, policy)
            self.assertIn(path, INSTALLED_HELPERS)      # and the app looks there

    def test_installing_over_the_old_names_removes_them(self):
        # Before 0.5.0 the recorder was proccoli-metrics with a unit of that name.
        old = [os.path.join(self.dest, "usr/bin/proccoli-metrics"),
               os.path.join(self.dest, "usr/lib/systemd/user/proccoli-metrics.service")]
        for path in old:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as fh:
                fh.write("old\n")
        self.install()
        for path in old:
            self.assertFalse(os.path.exists(path), path)
        self.assertTrue(os.path.exists(os.path.join(self.dest, "usr/bin/proccoli")))
        self.assertTrue(os.path.exists(os.path.join(self.dest, "usr/bin/proccoli-gui")))

    def test_installed_launcher_runs(self):
        self.install()
        env = dict(os.environ)
        r = subprocess.run([sys.executable, os.path.join(self.dest, "usr/bin/proccoli-gui"),
                            "--version"], capture_output=True, text=True, env=env)
        # The launcher points at /usr/share (not the staging dir), so only
        # check that it is valid Python that reaches the import.
        self.assertIn(r.returncode, (0, 1))
        compile(read_file(os.path.join(self.dest, "usr/bin/proccoli-gui")), "proccoli-gui", "exec")

    def test_the_two_parts_split_the_install(self):
        """--metrics and --gui together are the whole install,
        with no file in both."""
        self.install()
        everything = self.files()
        self.install(uninstall=True)
        self.install(parts=("metrics",))
        metrics = self.files()
        self.install(parts=("gui",))
        gui = self.files() - metrics
        self.assertEqual(metrics | gui, everything)
        self.assertIn("usr/bin/proccoli", metrics)
        self.assertIn(f"usr/share/glib-2.0/schemas/{APP_ID}.gschema.xml", metrics)
        self.assertIn("usr/lib/systemd/user/proccoli.service", metrics)
        self.assertFalse([f for f in metrics if "/proccoli/ui/" in f or f.endswith("app.py")
                          or "polkit" in f or "applications" in f or "icons" in f])
        self.assertIn("usr/bin/proccoli-gui", gui)
        self.assertIn("usr/libexec/proccoli/proccoli-helper", gui)
        self.assertIn("usr/share/proccoli/proccoli/ui/window.py", gui)

    def test_the_window_needs_the_metrics_part(self):
        r = self.install(parts=("gui",), ok=False)
        self.assertIn("needs the metrics part", r.stderr)
        self.install()
        r = self.install(parts=("metrics",), uninstall=True, ok=False)
        self.assertIn("uninstall it first", r.stderr)
        self.install(parts=("gui",), uninstall=True)
        self.assertFalse(os.path.exists(os.path.join(self.dest, "usr/share/proccoli/proccoli/ui")))
        self.assertTrue(os.path.exists(os.path.join(self.dest,
                                                    "usr/share/proccoli/proccoli/metrics.py")))
        self.install(parts=("metrics",), uninstall=True)
        self.assertEqual(self.files(), set())

    def test_the_metrics_part_runs_without_gtk(self):
        """Installed alone, it builds the collector and reads a fixture
        machine with Gtk, Gdk and Adw unimportable."""
        self.install(parts=("metrics",))
        code = f"""
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name in ("gi.repository.Gtk", "gi.repository.Gdk", "gi.repository.Adw") \\
                or name.startswith("proccoli.ui"):
            raise ImportError("blocked: " + name)
sys.meta_path.insert(0, Block())
sys.path.insert(0, {os.path.join(self.dest, "usr/share/proccoli")!r})
from proccoli import metrics
from proccoli.context import build_metrics_context
from proccoli.core import pciids
from proccoli.core.settings import Settings
from proccoli.core.sysroot import SysRoot
ctx = build_metrics_context(metrics.metrics_settings(Settings.for_tests(
          schema_path={os.path.join(ROOT, "data", APP_ID + ".gschema.xml")!r})),
      sysroot=SysRoot({os.path.join(ROOT, "tests", "fixtures", "alderlake-laptop")!r}),
      pci=pciids.load({os.path.join(ROOT, "tests", "fixtures", "pci", "pci.ids")!r}),
      connection_name=None)
ctx.devices.start(); ctx.devices.refresh(1.0)
print(len(ctx.devices.monitors()), metrics.__file__)
"""
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PROCCOLI_UI_TESTS")}
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           env=dict(env, DISPLAY="", WAYLAND_DISPLAY=""), cwd="/")
        self.assertEqual(r.returncode, 0, r.stderr)
        count, path = r.stdout.split()
        self.assertGreater(int(count), 3)
        self.assertTrue(path.startswith(self.dest))           # the installed copy

    def test_uninstall_removes_everything(self):
        self.install()
        self.install(uninstall=True)
        self.assertEqual(self.files(), set())


@unittest.skipUnless(shutil.which("dpkg-deb"), "no dpkg-deb")
class DebTest(unittest.TestCase):
    """Two packages: proccoli (the recorder, no GTK) and proccoli-gui (the
    window, which brings the recorder with it)."""

    @classmethod
    def setUpClass(cls):
        r = subprocess.run([os.path.join(ROOT, "packaging", "build-deb.sh")],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        cls.debs = {name: os.path.join(ROOT, "dist", f"{name}_{__version__}_all.deb")
                    for name in ("proccoli", "proccoli-gui")}

    def field(self, name, key):
        return subprocess.run(["dpkg-deb", "-f", self.debs[name], key], capture_output=True,
                              text=True).stdout.strip()

    def contents(self, name):
        out = subprocess.run(["dpkg-deb", "-c", self.debs[name]], capture_output=True,
                             text=True).stdout
        return {line.split()[5]: line[:10] for line in out.splitlines()
                if not line.split()[5].endswith("/")}

    def test_metrics_needs_no_gtk(self):
        depends = self.field("proccoli", "Depends")
        self.assertIn("python3-gi", depends)
        for gtk in ("gtk", "adw", "cairo", "pkexec"):
            self.assertNotIn(gtk, depends)
        files = self.contents("proccoli")
        self.assertIn("./usr/bin/proccoli", files)
        self.assertIn("./usr/lib/systemd/user/proccoli.service", files)
        self.assertIn("./usr/share/proccoli/proccoli/metrics.py", files)
        self.assertFalse([f for f in files if "/proccoli/ui/" in f or f.endswith("/app.py")])

    def test_gui_needs_the_same_metrics(self):
        depends = self.field("proccoli-gui", "Depends")
        self.assertIn(f"proccoli (= {__version__})", depends)
        self.assertIn("gir1.2-adw-1 (>= 1.5)", depends)
        self.assertIn("pkexec", depends)
        files = self.contents("proccoli-gui")
        self.assertIn("./usr/libexec/proccoli/proccoli-helper", files)
        self.assertEqual(files["./usr/libexec/proccoli/proccoli-helper"], "-rwxr-xr-x")
        self.assertIn("./usr/share/proccoli/proccoli/ui/window.py", files)

    def test_no_file_in_two_packages(self):
        metrics, gui = set(self.contents("proccoli")), set(self.contents("proccoli-gui"))
        shared = {f for f in metrics & gui if "/doc/" not in f}
        self.assertEqual(shared, set())

    def test_two_packages_and_the_window_brings_the_recorder(self):
        built = sorted(f for f in os.listdir(os.path.join(ROOT, "dist"))
                       if f.endswith(f"_{__version__}_all.deb"))
        self.assertEqual(built, [f"proccoli-gui_{__version__}_all.deb",
                                 f"proccoli_{__version__}_all.deb"])
        self.assertTrue(self.field("proccoli-gui", "Depends").startswith(
            f"proccoli (= {__version__}), "))

    def test_the_recorder_replaces_the_old_proccoli_metrics_package(self):
        # Its files move over, and apt removes the old package.
        self.assertEqual(self.field("proccoli", "Conflicts"), "proccoli-metrics")
        self.assertEqual(self.field("proccoli", "Replaces"),
                         "proccoli-metrics, proccoli-gui (<< 0.5.0)")
        self.assertEqual(self.field("proccoli", "Breaks"), "proccoli-gui (<< 0.5.0)")
        self.assertEqual(self.field("proccoli-gui", "Replaces"), "")

    def test_the_programs_are_proccoli_and_proccoli_gui(self):
        self.assertIn("./usr/bin/proccoli", self.contents("proccoli"))
        self.assertIn("./usr/bin/proccoli-gui", self.contents("proccoli-gui"))
        self.assertNotIn("./usr/bin/proccoli", self.contents("proccoli-gui"))

    def test_the_old_unit_is_turned_off_on_upgrade(self):
        import io
        import tarfile
        ctrl = subprocess.run(["dpkg-deb", "--ctrl-tarfile", self.debs["proccoli"]],
                              capture_output=True).stdout
        with tarfile.open(fileobj=io.BytesIO(ctrl)) as tar:
            postinst = tar.extractfile("./postinst").read().decode()
        self.assertIn("systemctl --global disable proccoli-metrics.service", postinst)

    def test_metrics_is_on_for_everyone_after_installing(self):
        import io
        import tarfile
        ctrl = subprocess.run(["dpkg-deb", "--ctrl-tarfile", self.debs["proccoli"]],
                              capture_output=True).stdout
        with tarfile.open(fileobj=io.BytesIO(ctrl)) as tar:
            postinst = tar.extractfile("./postinst").read().decode()
            prerm = tar.extractfile("./prerm").read().decode()
        self.assertIn("systemctl --global enable proccoli.service", postinst)
        self.assertIn("systemctl --global disable proccoli.service", prerm)
        files = self.contents("proccoli")
        self.assertIn(f"./usr/share/dbus-1/services/{APP_ID}.Metrics.service", files)
        self.assertIn("./usr/lib/systemd/user-preset/90-proccoli.preset", files)

    def test_metrics_stops_collectors_before_removal(self):
        script = subprocess.run(["dpkg-deb", "--ctrl-tarfile", self.debs["proccoli"]],
                                capture_output=True).stdout
        import io
        import tarfile
        with tarfile.open(fileobj=io.BytesIO(script)) as tar:
            prerm = tar.extractfile("./prerm").read().decode()
        self.assertIn("systemctl --user -M", prerm)
        self.assertIn("stop proccoli.service", prerm)
        self.assertIn('"$1" = remove', prerm)


class IconsTest(unittest.TestCase):
    def logo(self):
        import importlib.util
        path = os.path.join(os.path.dirname(__file__), "..", "packaging", "make-logo.py")
        spec = importlib.util.spec_from_file_location("make_logo", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_icon_is_the_generated_logo(self):
        # the SVG comes from packaging/make-logo.py, unedited,
        # and the same on every run (seeded buds).
        logo = self.logo()
        with open(data(f"icons/hicolor/scalable/apps/{APP_ID}.svg"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), logo.svg())
        self.assertEqual(logo.svg(), logo.svg())

    def test_logo_stays_inside_the_canvas(self):
        import xml.etree.ElementTree as ET
        logo = self.logo()
        root = ET.fromstring(logo.svg())
        self.assertEqual(root.get("viewBox"), "0 0 128 128")
        self.assertEqual(root.find("{http://www.w3.org/2000/svg}title").text, "Proccoli")
        # The dial and its bottom edge fit with a margin.
        cx, cy = logo.CENTER
        self.assertLessEqual(cy + 3 + logo.DIAL_R, 128)
        self.assertGreaterEqual(cx - logo.DIAL_R, 4)
        # The broccoli's crown (scaled, turned to READING) stays on the canvas.
        import math
        angle = math.radians(logo.scale_angle(logo.READING))
        px, py = logo.PIVOT
        for x, y, r in logo.CLUSTERS:
            x, y = x * logo.BROCCOLI_SCALE, y * logo.BROCCOLI_SCALE
            gx = px + x * math.cos(angle) - y * math.sin(angle)
            gy = py + x * math.sin(angle) + y * math.cos(angle)
            rr = r * logo.BROCCOLI_SCALE
            self.assertTrue(4 <= gx - rr and gx + rr <= 124 and 4 <= gy - rr, (gx, gy))

    def test_pngs_match_the_svg(self):
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
        svg = GdkPixbuf.Pixbuf.new_from_file_at_size(
            data(f"icons/hicolor/scalable/apps/{APP_ID}.svg"), 64, 64)
        png = GdkPixbuf.Pixbuf.new_from_file(data(f"icons/hicolor/64x64/apps/{APP_ID}.png"))
        # Re-rendered after edits. librsvg versions round a few channels
        # differently (Ubuntu 24.04's is off by one here and there), so allow
        # tiny differences; a forgotten re-render changes far more.
        a, b = svg.get_pixels(), png.get_pixels()
        self.assertEqual(len(a), len(b))
        diffs = [abs(x - y) for x, y in zip(a, b) if x != y]
        self.assertLessEqual(max(diffs, default=0), 2)
        self.assertLess(len(diffs), len(a) // 200)

    def test_png_sizes(self):
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
        for size in (16, 24, 32, 48, 64, 128, 256, 512):
            path = data(f"icons/hicolor/{size}x{size}/apps/{APP_ID}.png")
            pix = GdkPixbuf.Pixbuf.new_from_file(path)
            self.assertEqual((pix.get_width(), pix.get_height()), (size, size))


if __name__ == "__main__":
    unittest.main()
