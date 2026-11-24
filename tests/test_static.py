"""Architecture and hygiene rules, checked mechanically over the source:

- OS access only through the injected System (dependency injection)
- no Gtk in the domain layers
- every settings key used exists in the schema, and every key is used
- every icon name exists
- every module is documented
"""

import ast
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from helpers import read_file  # noqa: E402

from proccoli import GPU_ICON, MEMORY_ICON, MISSING_APP_ICON, PROCESSOR_ICON  # noqa: E402
from proccoli.core.settings import SchemaSpec, Settings, source_schema_path  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
SRC = os.path.join(ROOT, "src", "proccoli")
ADWAITA = "/usr/share/icons/Adwaita"


def modules():
    for dirpath, _dirs, files in os.walk(SRC):
        for name in files:
            if name.endswith(".py"):
                path = os.path.join(dirpath, name)
                yield os.path.relpath(path, SRC), read_file(path)


class DependencyInjectionTest(unittest.TestCase):
    # Only these modules may talk to the OS directly.
    ALLOWED = {
        "core/system.py",           # the injectable OS facade itself
        "core/runner.py",           # StreamReader: runs the child processes
        "core/settings.py",         # bootstraps before any System exists
        "core/privileged.py",       # locates the helper (os.access)
        "helper/proccoli_helper.py",  # standalone program, runs as root
    }
    FORBIDDEN = re.compile(
        r"\bos\.(kill|getpriority|setpriority|sched_getaffinity|sched_setaffinity|"
        r"geteuid|getxattr|sysconf|uname)\b|\bpwd\.|\bshutil\.which\b|\bsubprocess\.|"
        r"\bDesktopAppInfo\b|\bpciids\.load\(")

    def test_os_access_goes_through_system(self):
        offenders = []
        for rel, text in modules():
            if rel in self.ALLOWED or rel == "context.py":
                continue
            for n, line in enumerate(text.splitlines(), 1):
                code = line.split("#", 1)[0]
                if self.FORBIDDEN.search(code) and not code.strip().startswith(('"', "'")):
                    offenders.append(f"{rel}:{n}: {line.strip()}")
        self.assertEqual(offenders, [])


class LayeringTest(unittest.TestCase):
    DOMAIN = ("core/", "devices/", "gpu/", "processes/", "context.py")
    # Views shipped with the Intel backend (imported lazily by create_views).
    UI_IN_DOMAIN = {"gpu/intel_gpu_top/views.py", "gpu/intel_gpu_top/graph.py",
                    "gpu/intel_gpu_top/grid.py", "gpu/intel_gpu_top/clients.py"}

    def test_domain_modules_import_no_gtk_at_module_level(self):
        offenders = []
        for rel, text in modules():
            if not rel.startswith(self.DOMAIN) or rel in self.UI_IN_DOMAIN:
                continue
            for node in ast.parse(text).body:
                if isinstance(node, ast.ImportFrom) and node.module == "gi.repository":
                    names = {a.name for a in node.names}
                    if names & {"Gtk", "Adw", "Gdk"}:
                        offenders.append(rel)
                if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                        ("ui", ".ui", "..ui", "...ui")) and node.level:
                    offenders.append(rel)
        self.assertEqual(offenders, [])

    def test_every_module_has_a_docstring(self):
        missing = [rel for rel, text in modules()
                   if rel != "__main__.py" and ast.get_docstring(ast.parse(text)) is None]
        self.assertEqual(missing, [])


class SettingsKeysTest(unittest.TestCase):
    CALL = re.compile(r"""\b(?:settings|self\.settings|_settings)\.(?:get|set|reset|bind|"""
                      r"""connect_changed)\(\s*["']([a-z0-9-]+)["']""")

    def setUp(self):
        self.keys = set(SchemaSpec.parse(source_schema_path()).keys)

    def literal_keys(self):
        found = set()
        for _rel, text in modules():
            found |= set(self.CALL.findall(text))
        return found

    def generated_keys(self):
        from proccoli.ui.dialogs.preferences import APP_COLUMNS, PROCESS_COLUMNS
        keys = {f"apps-show-{k}" for k, _ in APP_COLUMNS}
        keys |= {f"processes-show-{k}" for k, _ in PROCESS_COLUMNS}
        from proccoli.ui.pages import apps, processes
        settings = Settings.for_tests()
        keys |= {c.setting for c in apps._cols(settings) + processes._cols(settings)
                 if c.setting}
        keys |= {f"{p}-sort-by" for p in ("apps", "processes")}
        keys |= {f"{p}-sort-by-ascending" for p in ("apps", "processes")}
        from proccoli.ui.sidebar_visibility import SETTING
        keys.add(SETTING)
        return keys

    def test_used_keys_exist(self):
        self.assertEqual((self.literal_keys() | self.generated_keys()) - self.keys, set())

    def test_every_key_is_used(self):
        unused = self.keys - self.literal_keys() - self.generated_keys()
        self.assertEqual(unused, set())

    def test_preferences_and_tables_agree_on_columns(self):
        from proccoli.ui.dialogs.preferences import APP_COLUMNS, PROCESS_COLUMNS
        from proccoli.ui.pages import apps, processes
        settings = Settings.for_tests()
        self.assertEqual({c.setting for c in apps._cols(settings) if c.setting},
                         {f"apps-show-{k}" for k, _ in APP_COLUMNS})
        self.assertEqual({c.setting for c in processes._cols(settings) if c.setting},
                         {f"processes-show-{k}" for k, _ in PROCESS_COLUMNS})


@unittest.skipUnless(os.path.isdir(ADWAITA), "Adwaita icon theme not installed")
class IconsTest(unittest.TestCase):
    ICON = re.compile(r"""["']([a-z0-9-]+-symbolic)["']""")

    def available(self):
        names = set()
        for base in (ADWAITA, os.path.join(ROOT, "data", "icons")):
            for _d, _s, files in os.walk(base):
                names |= {f.rsplit(".", 1)[0] for f in files}
        return names

    def test_every_icon_name_exists(self):
        used = set()
        for _rel, text in modules():
            used |= set(self.ICON.findall(text))
        used |= {PROCESSOR_ICON, MEMORY_ICON, GPU_ICON, MISSING_APP_ICON}
        self.assertEqual(used - self.available(), set())

    def test_our_symbolic_icons_are_solid(self):
        """Filled shapes in the recolourable symbolic grey: no outlines."""
        import xml.etree.ElementTree as ET
        folder = os.path.join(ROOT, "data", "icons", "hicolor", "symbolic", "apps")
        names = os.listdir(folder)
        self.assertIn(MISSING_APP_ICON + ".svg", names)
        for name in names:
            root = ET.parse(os.path.join(folder, name)).getroot()
            for el in root.iter():
                self.assertNotIn("stroke", el.attrib, name)
                if el.tag.endswith("path"):
                    self.assertEqual(el.get("fill"), "#222", name)



class TestSuiteTest(unittest.TestCase):
    def test_no_test_class_name_is_defined_twice_in_a_file(self):
        # A second class with the same name silently replaces the first, and
        # its tests never run (this hid six context-menu tests once).
        here = os.path.dirname(os.path.abspath(__file__))
        for name in sorted(os.listdir(here)):
            if not (name.startswith("test_") and name.endswith(".py")):
                continue
            tree = ast.parse(read_file(os.path.join(here, name)))
            seen = set()
            # Module level, including inside top-level ``if HAVE_DISPLAY:``
            # blocks; classes local to a test method may repeat.
            top = list(tree.body)
            top += [n for block in tree.body if isinstance(block, ast.If)
                    for n in block.body + block.orelse]
            for node in top:
                if isinstance(node, ast.ClassDef):
                    self.assertNotIn(node.name, seen, f"{name}: class {node.name} twice")
                    seen.add(node.name)



class UserTextTest(unittest.TestCase):
    """What users see never points at the project's planning documents."""

    FORBIDDEN = ("Milestone", "PLAN.md", "DESIGN.md")

    def test_no_planning_references_in_user_visible_strings(self):
        for rel, text in modules():
            tree = ast.parse(text)
            docstrings = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                     ast.AsyncFunctionDef)) and node.body:
                    first = node.body[0]
                    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                        docstrings.add(id(first.value))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                        and id(node) not in docstrings:
                    for word in self.FORBIDDEN:
                        self.assertNotIn(word, node.value, f"{rel}: {node.value!r}")


if __name__ == "__main__":
    unittest.main()
