"""core.windows: Switch To for any running app (Idea 5): matching windows to
an app, the order of ways, the extension's states, and that the shipped
GNOME Shell extension and Proccoli agree on its D-Bus interface."""

import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from helpers import FakeSystem  # noqa: E402
from proccoli.core.system import System, activation_token  # noqa: E402
from proccoli.core.windows import (EXTENSION_INTERFACE, EXTENSION_PATH,  # noqa: E402
                                   EXTENSION_UUID, LIST_SIGNATURE, ExtensionState, Way,
                                   Window, WindowSwitcher, extension_source, parse_wmctrl,
                                   windows_for)
from proccoli.processes.apps import App  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
EXTENSION = os.path.join(ROOT, "data", "gnome-shell", "extensions", EXTENSION_UUID)

FIREFOX = App("firefox", "Firefox", pids=[100, 101])


class MatchingTest(unittest.TestCase):
    def test_by_process_most_recent_first(self):
        windows = [Window(1, 100, "firefox", "A", 5), Window(2, 101, "firefox", "B", 9),
                   Window(3, 200, "code", "C", 99)]
        self.assertEqual([w.id for w in windows_for([100, 101], windows)], [2, 1])
        self.assertEqual(windows_for([300], windows), [])

    def test_by_app_id_for_helper_processes(self):
        windows = [Window(7, 999, "org.gnome.Nautilus", "Home", 1)]
        self.assertEqual(windows_for([1], windows, "org.gnome.Nautilus")[0].id, 7)

    def test_wmctrl(self):
        text = ("0x03a00003  0 4242   host Mozilla Firefox\n"
                "0x04000007 -1 1234   host\n"
                "garbage\n")
        self.assertEqual(parse_wmctrl(text), [Window(0x03a00003, 4242, "", "Mozilla Firefox", 0),
                                              Window(0x04000007, 1234, "", "", 1)])


class SwitcherTest(unittest.TestCase):
    def setUp(self):
        self.system = FakeSystem()
        self.switcher = WindowSwitcher(self.system)

    def test_the_extension_first(self):
        self.system.windows = [(1, 100, "firefox", "Old", 5), (2, 101, "firefox", "New", 9)]
        self.system.switchable = {"firefox": "dbus"}
        self.assertEqual(self.switcher.way(FIREFOX), Way.EXTENSION)
        self.assertTrue(self.switcher.switch(FIREFOX))
        self.assertEqual(self.system.raised, [2])               # the most recent
        self.assertEqual(self.system.activated, [])

    def test_then_asking_the_app_with_a_token(self):
        self.system.windows = []                                # running, no window of it
        self.system.switchable = {"firefox": "launch"}
        self.assertEqual(self.switcher.way(FIREFOX), Way.ASK_APP)
        context = object()
        self.assertTrue(self.switcher.switch(FIREFOX, context))
        self.assertEqual(self.system.launch_contexts, [context])

    def test_then_x11(self):
        self.system.session = "x11"
        self.system.wmctrl = "0x0a 0 100 host Firefox\n0x0b 0 101 host Firefox 2\n"
        self.assertEqual(self.switcher.way(FIREFOX), Way.X11)
        self.assertTrue(self.switcher.switch(FIREFOX))
        self.assertEqual(self.system.raised, [0x0b])
        self.system.session = "wayland"
        self.assertIsNone(self.switcher.way(FIREFOX))           # no wmctrl on Wayland

    def test_nothing_reaches_it(self):
        self.assertIsNone(self.switcher.way(FIREFOX))
        self.assertFalse(self.switcher.switch(FIREFOX))

    def test_extension_states(self):
        self.assertEqual(self.switcher.extension_state(), ExtensionState.UNAVAILABLE)
        self.system.extension_info = {}
        self.assertEqual(self.switcher.extension_state(), ExtensionState.NOT_INSTALLED)
        self.assertTrue(self.switcher.install("/src/ext"))
        self.assertEqual(self.system.installed_from, "/src/ext")
        self.assertEqual(self.system.enabled_at_login, EXTENSION_UUID)
        self.assertEqual(self.switcher.extension_state(), ExtensionState.NEEDS_LOGIN)
        self.system.extension_info = {"state": 2.0, "enabled": False}   # after log-in, off
        self.assertEqual(self.switcher.extension_state(), ExtensionState.DISABLED)
        self.assertTrue(self.switcher.enable())
        self.assertEqual(self.switcher.extension_state(), ExtensionState.ENABLED)


class TokenTest(unittest.TestCase):
    def test_activation_token(self):
        class Context:
            def get_startup_notify_id(self, info, files):
                return "token-1"

        class Broken:
            def get_startup_notify_id(self, info, files):
                raise TypeError("no info")

        self.assertEqual(activation_token(Context()), "token-1")
        self.assertEqual(activation_token(None), "")
        self.assertEqual(activation_token(Broken()), "")

    def test_running_gapplications_can_be_asked(self):
        system = System()

        class Info:
            def get_boolean(self, key):
                return False

        system._desktop_info = lambda app_id: Info()
        system.bus_name_owned = lambda name: name == "org.example.Editor"
        self.assertEqual(system.app_switch_method("org.example.Editor"), "dbus")
        self.assertIsNone(system.app_switch_method("org.example.Other"))
        system.bus_name_owned = lambda name: True
        self.assertIsNone(system.app_switch_method("org.gnome.Terminal"))   # new window


class ExtensionFilesTest(unittest.TestCase):
    def test_metadata(self):
        with open(os.path.join(EXTENSION, "metadata.json"), encoding="utf-8") as f:
            meta = json.load(f)
        self.assertEqual(meta["uuid"], EXTENSION_UUID)
        for version in ("46", "47", "48", "49", "50"):           # Ubuntu 24.04 is 46
            self.assertIn(version, meta["shell-version"])
        self.assertEqual(str(extension_source()), os.path.realpath(EXTENSION))

    @unittest.skipUnless(__import__("shutil").which("gjs"), "gjs not installed")
    def test_javascript_parses(self):
        # Outside the Shell its imports can't load, but a syntax error would
        # be reported first.
        import subprocess
        out = subprocess.run(["gjs", "-m", os.path.join(EXTENSION, "extension.js")],
                             capture_output=True, text=True, timeout=20)
        text = out.stdout + out.stderr
        self.assertNotIn("SyntaxError", text)
        self.assertIn("org/gnome/shell", text)        # stopped at a Shell import

    def test_interface_agrees_with_proccoli(self):
        from gi.repository import Gio
        with open(os.path.join(EXTENSION, "extension.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn(f"'{EXTENSION_PATH}'", js)
        xml = re.search(r"const INTERFACE = `(.*?)`;", js, re.S).group(1)
        iface = Gio.DBusNodeInfo.new_for_xml(xml).lookup_interface(EXTENSION_INTERFACE)
        self.assertIsNotNone(iface)
        listing = iface.lookup_method("List")
        self.assertEqual("(" + "".join(a.signature for a in listing.out_args) + ")",
                         LIST_SIGNATURE)
        activate = iface.lookup_method("Activate")
        self.assertEqual([a.signature for a in activate.in_args], ["t"])
        self.assertEqual([a.signature for a in activate.out_args], ["b"])
        self.assertEqual(Window(1, 2, "a", "t", 3), Window(*(1, 2, "a", "t", 3)))  # 5 fields


if __name__ == "__main__":
    unittest.main()
