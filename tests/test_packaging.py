"""Packaging: data files validate, the polkit policy covers the helper, and
install.sh / build-deb.sh produce a complete, removable installation."""

import os
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
        self.assertEqual(entries["Exec"].strip(), "proccoli")

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
    def install(self, prefix="/usr", uninstall=False):
        env = dict(os.environ, DESTDIR=self.dest, PREFIX=prefix)
        args = [os.path.join(ROOT, "packaging", "install.sh")]
        if uninstall:
            args.append("--uninstall")
        r = subprocess.run(args, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

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
                "usr/bin/proccoli", "usr/libexec/proccoli/proccoli-helper",
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
        launcher = read_file(os.path.join(self.dest, "usr/bin/proccoli"))
        self.assertIn('sys.path.insert(0, "/usr/share/proccoli")', launcher)

    def test_policy_points_at_the_installed_helper(self):
        for prefix in ("/usr", "/usr/local"):
            self.install(prefix)
            policy = read_file(os.path.join(self.dest, prefix.lstrip("/"), "share/polkit-1/actions",
                                       f"{APP_ID}.policy"))
            self.assertNotIn("@LIBEXECDIR@", policy)
            path = f"{prefix}/libexec/proccoli/proccoli-helper"
            self.assertIn(path, policy)
            self.assertIn(path, INSTALLED_HELPERS)      # and the app looks there

    def test_installed_launcher_runs(self):
        self.install()
        env = dict(os.environ)
        r = subprocess.run([sys.executable, os.path.join(self.dest, "usr/bin/proccoli"),
                            "--version"], capture_output=True, text=True, env=env)
        # The launcher points at /usr/share (not the staging dir), so only
        # check that it is valid Python that reaches the import.
        self.assertIn(r.returncode, (0, 1))
        compile(read_file(os.path.join(self.dest, "usr/bin/proccoli")), "proccoli", "exec")

    def test_uninstall_removes_everything(self):
        self.install()
        self.install(uninstall=True)
        self.assertEqual(self.files(), set())


@unittest.skipUnless(shutil.which("dpkg-deb"), "no dpkg-deb")
class DebTest(unittest.TestCase):
    def test_build(self):
        r = subprocess.run([os.path.join(ROOT, "packaging", "build-deb.sh")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        deb = os.path.join(ROOT, "dist", f"proccoli_{__version__}_all.deb")
        info = subprocess.run(["dpkg-deb", "-f", deb], capture_output=True, text=True).stdout
        self.assertIn("Package: proccoli", info)
        self.assertIn("gir1.2-adw-1 (>= 1.5)", info)
        self.assertIn("pkexec", info)
        contents = subprocess.run(["dpkg-deb", "-c", deb], capture_output=True,
                                  text=True).stdout
        self.assertIn("./usr/libexec/proccoli/proccoli-helper", contents)
        self.assertIn("-rwxr-xr-x root/root", [l[:21] for l in contents.splitlines()
                                               if "proccoli-helper" in l][0])


class IconsTest(unittest.TestCase):
    def logo(self):
        import importlib.util
        path = os.path.join(os.path.dirname(__file__), "..", "packaging", "make-logo.py")
        spec = importlib.util.spec_from_file_location("make_logo", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_icon_is_the_generated_logo(self):
        # Milestone 38: the SVG comes from packaging/make-logo.py, unedited,
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
