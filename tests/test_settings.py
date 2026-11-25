import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gi.repository import GObject  # noqa: E402

from proccoli import APP_ID  # noqa: E402
from proccoli.core.settings import (  # noqa: E402
    SchemaSpec, Settings, compile_source_schema, source_schema_path)

HAVE_COMPILER = shutil.which("glib-compile-schemas") is not None


class SchemaFileTest(unittest.TestCase):
    def test_schema_matches_app_id(self):
        path = source_schema_path()
        self.assertIsNotNone(path)
        self.assertEqual(path.name, f"{APP_ID}.gschema.xml")
        schema = ET.parse(path).getroot().find("schema")
        self.assertEqual(schema.get("id"), APP_ID)
        self.assertEqual(schema.get("path"), "/" + APP_ID.replace(".", "/") + "/")

    @unittest.skipUnless(HAVE_COMPILER, "glib-compile-schemas not installed")
    def test_schema_compiles_strictly(self):
        r = subprocess.run(["glib-compile-schemas", "--strict", "--dry-run",
                            str(source_schema_path().parent)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_defaults_are_valid(self):
        spec = SchemaSpec.parse(source_schema_path())
        self.assertIn("update-interval", spec.keys)
        for key in spec.keys.values():
            self.assertEqual(key.check(key.default), key.default, key.name)

    def test_keys_used_by_the_design_exist(self):
        spec = SchemaSpec.parse(source_schema_path())
        for k in ("window-width", "window-height", "is-maximized",
                  "base", "temperature-unit", "graph-time-range", "gpu-details-disabled", "gpu-view"):
            self.assertIn(k, spec.keys)
        self.assertNotIn("last-viewed-page", spec.keys)   # always the Overview


class Probe(GObject.Object):
    width = GObject.Property(type=int, default=0)


class SettingsBehaviour:
    """Run against every store; subclasses provide make()."""

    def make(self) -> Settings:
        raise NotImplementedError

    def setUp(self):
        self.s = self.make()

    def test_defaults(self):
        self.assertEqual(self.s.get("update-interval"), "1-second")
        self.assertEqual(self.s.get("graph-time-range"), "1-minute")
        self.assertEqual(self.s.get("gpu-details-disabled"), [])
        self.assertIs(self.s.get("is-maximized"), False)

    def test_set_and_get(self):
        self.s.set("window-width", 1234)
        self.s.set("temperature-unit", "kelvin")
        self.s.set("gpu-details-disabled", ["0000:00:02.0"])
        self.assertEqual(self.s.get("window-width"), 1234)
        self.assertEqual(self.s.get("temperature-unit"), "kelvin")
        self.assertEqual(self.s.get("gpu-details-disabled"), ["0000:00:02.0"])

    def test_validation(self):
        with self.assertRaises(ValueError):
            self.s.set("temperature-unit", "rankine")      # not an enum nick
        with self.assertRaises(ValueError):
            self.s.set("log-max-size", 5)                  # below range
        with self.assertRaises(ValueError):
            self.s.set("gpu-details-disabled", "0000:00:02.0")   # a string, not a list
        with self.assertRaises(ValueError):
            self.s.set("window-width", "wide")             # wrong type
        with self.assertRaises(KeyError):
            self.s.get("no-such-key")
        self.assertEqual(self.s.get("log-max-size"), 1024)  # unchanged

    def test_changed_callback(self):
        seen = []
        hid = self.s.connect_changed("show-graph-grids", lambda k, v: seen.append((k, v)))
        self.s.set("show-graph-grids", True)
        self.assertEqual(seen, [("show-graph-grids", True)])
        self.s.disconnect(hid)
        self.s.set("show-graph-grids", False)
        self.assertEqual(len(seen), 1)

    def test_disconnect_during_teardown_is_harmless(self):
        hid = self.s.connect_changed("base", lambda *_: None)
        del self.s._store            # what cycle collection leaves behind
        self.s.disconnect(hid)

    def test_reset(self):
        self.s.set("graph-time-range", "5-minutes")
        self.s.reset("graph-time-range")
        self.assertEqual(self.s.get("graph-time-range"), "1-minute")

    def test_bind_two_way(self):
        obj = Probe()
        self.s.bind("window-width", obj, "width")
        self.assertEqual(obj.props.width, 1000)
        self.s.set("window-width", 800)
        self.assertEqual(obj.props.width, 800)
        obj.props.width = 640
        self.assertEqual(self.s.get("window-width"), 640)


class DictSettingsTest(SettingsBehaviour, unittest.TestCase):
    def make(self):
        return Settings.for_tests()

    def test_not_persistent(self):
        self.assertFalse(self.s.persistent)

    def test_overrides(self):
        s = Settings.for_tests({"update-interval": "5-seconds"})
        self.assertEqual(s.get("update-interval"), "5-seconds")


class MigrateTest(unittest.TestCase):
    """an old Refresh Speed carries over to Update Interval, once."""

    def test_each_old_speed(self):
        from proccoli.core.settings import migrate
        cases = [("very-slow", "5-seconds"), ("slow", "2-seconds"),
                 ("fast", "1-second"), ("very-fast", "1-second")]
        for old, new in cases:
            s = Settings.for_tests({"refresh-speed": old, "update-interval": "10-seconds"})
            self.assertEqual(len(migrate(s)), 1, old)
            self.assertEqual(s.get("update-interval"), new, old)
            self.assertEqual(s.get("refresh-speed"), "normal")          # reset: only once
            s.set("update-interval", "3-seconds")
            self.assertEqual(migrate(s), [])
            self.assertEqual(s.get("update-interval"), "3-seconds")

    def test_fresh_install_and_the_intel_interval(self):
        from proccoli.core.settings import migrate
        s = Settings.for_tests()
        self.assertEqual(migrate(s), [])
        self.assertEqual(s.get("update-interval"), "1-second")
        s = Settings.for_tests({"intel-gpu-top-interval": "very-fast"})
        self.assertEqual(migrate(s), ["intel-gpu-top-interval very-fast -> 1-second"])
        self.assertEqual(s.get("intel-gpu-top-interval"), "1-second")
        s.set("intel-gpu-top-interval", "")
        self.assertEqual(migrate(s), [])


@unittest.skipUnless(HAVE_COMPILER, "glib-compile-schemas not installed")
class GioSettingsTest(SettingsBehaviour, unittest.TestCase):
    def make(self):
        schema_dir = compile_source_schema()
        self.assertIsNotNone(schema_dir)
        return Settings.in_memory_gio(schema_dir)

    def test_persistent_store(self):
        self.assertTrue(self.s.persistent)

    def test_installed_schema_description_matches_xml(self):
        from gi.repository import Gio
        source = Gio.SettingsSchemaSource.new_from_directory(
            str(compile_source_schema()), None, False)
        from_gio = SchemaSpec.from_gio(source.lookup(APP_ID, False))
        from_xml = SchemaSpec.parse(source_schema_path())
        self.assertEqual(set(from_gio.keys), set(from_xml.keys))
        for name, key in from_xml.keys.items():
            other = from_gio.keys[name]
            self.assertEqual((other.type, other.default, other.choices, other.range),
                             (key.type, key.default, key.choices, key.range), name)



@unittest.skipUnless(shutil.which("glib-compile-schemas"), "needs glib-compile-schemas")
class SchemaChoiceTest(unittest.TestCase):
    """An installed schema older than the code must never be used: GSettings
    aborts the whole program on a key it doesn't have (it crashed a source
    checkout once, against an older installed package)."""

    def compiled(self, drop_key=None):
        import re
        import subprocess
        import tempfile
        from gi.repository import Gio
        from proccoli import APP_ID
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        xml = source_schema_path().read_text()
        if drop_key:
            xml = re.sub(rf'    <key name="{drop_key}".*?</key>\n', "", xml, flags=re.S)
        (Path(tmp.name) / f"{APP_ID}.gschema.xml").write_text(xml)
        subprocess.run(["glib-compile-schemas", tmp.name], check=True)
        src = Gio.SettingsSchemaSource.new_from_directory(tmp.name, None, False)
        return src.lookup(APP_ID, False)

    def test_an_older_schema_does_not_cover_the_spec(self):
        from proccoli.core.settings import schema_covers
        spec = SchemaSpec.parse(source_schema_path())
        self.assertTrue(schema_covers(self.compiled(), spec))
        self.assertFalse(schema_covers(self.compiled(drop_key="sidebar-shown"), spec))
        self.assertFalse(schema_covers(None, spec))

    def test_choose_skips_incomplete_schemas_in_order(self):
        from proccoli.core.settings import choose_schema
        spec = SchemaSpec.parse(source_schema_path())
        old, new = self.compiled(drop_key="sidebar-shown"), self.compiled()
        with self.assertLogs("proccoli.core.settings", "WARNING") as logs:
            self.assertIs(choose_schema([("installed", old), ("source checkout", new)], spec),
                          new)
        self.assertIn("lacks sidebar-shown", logs.output[0])
        self.assertIs(choose_schema([("source checkout", new), ("installed", old)], spec), new)
        with self.assertLogs("proccoli.core.settings", "WARNING"):
            self.assertIsNone(choose_schema([("installed", old), ("x", None)], spec))


if __name__ == "__main__":
    unittest.main()
