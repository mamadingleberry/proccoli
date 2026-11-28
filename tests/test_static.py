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


def _load_split():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "split", os.path.join(os.path.dirname(__file__), "..", "packaging", "split.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SPLIT = _load_split()


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
    # Views shipped with the vendor backends (imported lazily by create_views).
    UI_IN_DOMAIN = SPLIT.GUI_IN_DOMAIN       # packaging/split.py: one list

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

    def test_graphs_are_drawn_only_by_the_shared_chart_code(self):
        """One chart family: no module outside ui/ draws its own
        graph (a Gtk.DrawingArea subclass or a draw function)."""
        offenders = []
        for rel, text in modules():
            if rel.startswith("ui/"):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                code = line.split("#", 1)[0]
                if "DrawingArea" in code or "set_draw_func" in code:
                    offenders.append(f"{rel}:{n}: {line.strip()}")
        self.assertEqual(offenders, [])

    def test_graph_preferences_come_through_chart_settings(self):
        """One chart family: only ui/chart_settings.py applies the
        graph preferences to graphs (Preferences and the graph toolbar's
        items set them; domain code may read the time range to size
        histories)."""
        keys = re.compile(r"[\"'](show-graph-axes|show-graph-grids|graph-time-range)[\"']")
        # (preferences_layout only says which page each setting is on.)
        allowed = {"ui/chart_settings.py", "ui/dialogs/preferences.py",
                   "ui/preferences_layout.py", "ui/toolbar_items.py"}
        offenders = []
        for rel, text in modules():
            is_view = rel.startswith("ui/") or (rel.startswith("gpu/")
                                                and rel.endswith("views.py"))
            if not is_view or rel in allowed:
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if keys.search(line.split("#", 1)[0]):
                    offenders.append(f"{rel}:{n}: {line.strip()}")
        self.assertEqual(offenders, [])

    def test_vendor_views_build_only_chart_cards(self):
        """GPU detail tabs build charts from ChartCard and ChartGrid only,
        so every tab looks and behaves the same."""
        widgets = re.compile(r"\b(Graph|GraphBox|GraphPane|LegendChart|DoubleGraphBox)\(")
        offenders = []
        for rel, text in modules():
            if not rel.startswith("gpu/"):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if widgets.search(line.split("#", 1)[0]):
                    offenders.append(f"{rel}:{n}: {line.strip()}")
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
        from proccoli.ui.sidebar_style import STYLE_SETTING
        from proccoli.ui.sidebar_visibility import SETTING
        from proccoli.ui.toolbar_items import SETTING as TOOLBAR_SETTING, SHOW_SETTING
        from proccoli.core.ticker import CUSTOM_KEY
        keys |= {SETTING, STYLE_SETTING, TOOLBAR_SETTING, SHOW_SETTING, CUSTOM_KEY}
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
        """Filled shapes in the recolorable symbolic grey: no outlines."""
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



class PlatformFloorTest(unittest.TestCase):
    """Ubuntu 24.04 ships libadwaita 1.5: newer classes are used only behind
    a ``hasattr`` check (or through ``ui/compat.py``). An unguarded
    ``Adw.Spinner()`` once crashed every GPU page there."""

    # Class -> the libadwaita version that added it (all newer than 1.5).
    NEWER = {
        "Spinner": "1.6", "SpinnerPaintable": "1.6", "ButtonRow": "1.6",
        "BottomSheet": "1.6", "MultiLayoutView": "1.6", "Layout": "1.6",
        "LayoutSlot": "1.6", "AccentColor": "1.6",
        "ToggleGroup": "1.7", "Toggle": "1.7", "WrapBox": "1.7", "WrapLayout": "1.7",
        "InlineViewSwitcher": "1.7",
        "ShortcutsDialog": "1.8", "ShortcutsSection": "1.8", "ShortcutsItem": "1.8",
        "ShortcutLabel": "1.8",
        "Sidebar": "1.9", "SidebarItem": "1.9", "SidebarSection": "1.9",
        "ViewSwitcherSidebar": "1.9",
    }

    def test_newer_libadwaita_classes_are_guarded(self):
        self.assertEqual(self.offenders(modules()), [])

    def offenders(self, files):
        offenders = []
        for rel, text in files:
            guarded = {self.NEWER[name] for name in
                       re.findall(r'hasattr\(\s*adw\s*,\s*"(\w+)"\s*\)', text, re.I)
                       if name in self.NEWER}
            for n, line in enumerate(text.splitlines(), 1):
                for name in re.findall(r"\bAdw\.(\w+)", line.split("#", 1)[0]):
                    # A guard for any class of the same release covers its siblings
                    # (ShortcutsSection behind hasattr(Adw, "ShortcutsDialog")).
                    if name in self.NEWER and self.NEWER[name] not in guarded:
                        offenders.append(f"{rel}:{n}: Adw.{name} needs libadwaita "
                                         f"{self.NEWER[name]}")
        return offenders

    def test_the_check_catches_an_unguarded_spinner(self):
        self.assertEqual(self.offenders([("x.py", "w = Adw.Spinner()\n")]),
                         ["x.py:1: Adw.Spinner needs libadwaita 1.6"])
        self.assertEqual(self.offenders([("x.py", 'if hasattr(Adw, "ShortcutsDialog"):\n'
                                                  '    Adw.ShortcutsItem()\n')]), [])


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


class InstallSplitTest(unittest.TestCase):
    """proccoli installs without the GUI, so nothing on
    its side imports the GUI side, Gtk, Gdk or Adw, at any level. The one
    way across is a GPU backend's ``create_views``, which only the window
    calls."""

    GTK = {"Gtk", "Gdk", "Adw", "GdkPixbuf", "Graphene", "Gsk", "Pango"}

    @staticmethod
    def targets(rel, node):
        """Source paths an import may load, relative to src/proccoli."""
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        else:
            if node.level:
                base = rel.split("/")[:-1]
                base = base[:len(base) - (node.level - 1)] if node.level > 1 else base
                prefix = "/".join(base + ([node.module.replace(".", "/")] if node.module else []))
            else:
                if not (node.module or "").startswith("proccoli"):
                    return []
                prefix = node.module[len("proccoli"):].lstrip(".").replace(".", "/")
            mods = [prefix] + [f"{prefix}/{a.name}".strip("/") for a in node.names]
            return [m + suffix for m in mods for suffix in (".py", "/__init__.py")]
        return [m[len("proccoli."):].replace(".", "/") + ".py" for m in mods
                if m.startswith("proccoli.")]

    def test_the_library_never_imports_the_gui(self):
        offenders = []
        for rel, text in modules():
            if SPLIT.part(rel) != "metrics":
                continue
            tree = ast.parse(text)
            allowed = {id(n) for f in ast.walk(tree)
                       if isinstance(f, ast.FunctionDef) and f.name == "create_views"
                       for n in ast.walk(f)}
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Import, ast.ImportFrom)) or id(node) in allowed:
                    continue
                if isinstance(node, ast.ImportFrom) and node.module == "gi.repository" \
                        and {a.name for a in node.names} & self.GTK:
                    offenders.append(f"{rel}:{node.lineno} Gtk")
                for target in self.targets(rel, node):
                    if os.path.exists(os.path.join(SRC, target)) and SPLIT.part(target) == "gui":
                        offenders.append(f"{rel}:{node.lineno} {target}")
        self.assertEqual(offenders, [])

    def test_every_source_file_is_in_one_install(self):
        everything = SPLIT.sources()
        metrics, gui = set(SPLIT.files("metrics")), set(SPLIT.files("gui"))
        self.assertEqual(metrics | gui, set(everything))
        self.assertEqual(metrics & gui, set())
        self.assertIn("metrics.py", metrics)
        self.assertIn("__init__.py", metrics)
        self.assertIn("app.py", gui)
        self.assertTrue(SPLIT.GUI_IN_DOMAIN <= gui)



class NoPlanningReferencesTest(unittest.TestCase):
    """Code, comments, docstrings and tests carry no planning metadata
    (milestone, idea, bug or step numbers, DESIGN.md / PLAN.md sections):
    that history lives in docs/PLAN.md and docs/DESIGN.md (CLAUDE.md)."""

    PATTERN = re.compile(r"\bM\d{1,3}(\.\d+)?\b|\bMilestones? \d+|\bIdeas? \d+[a-z]?\b"
                         r"|\bFeatures? \d+[a-z]?\b|\bReleases? v?\d+"
                         r"|\bBugs? \d+\b|DESIGN\.md|PLAN\.md|§ ?\d+")
    # The same words split over a line break ("(Idea\n    5)").
    WRAPPED = re.compile(r"\b(Milestones?|Ideas?|Features?|Bugs?)[ \t]*\n[\s#*\"']*\d+\b")
    # SVG path data ("M-2 -2 C…") isn't a milestone.
    EXEMPT = {("packaging/make-logo.py", "<path d=")}
    SUFFIXES = (".py", ".sh", ".service", ".in", ".xml", ".preset", ".desktop")

    def test_none_in_code(self):
        offenders = []
        for top in ("src", "tests", "packaging", "data"):
            for dirpath, _dirs, files in os.walk(os.path.join(ROOT, top)):
                if "fixtures" in dirpath or "__pycache__" in dirpath:
                    continue
                for name in files:
                    path = os.path.join(dirpath, name)
                    rel = os.path.relpath(path, ROOT)
                    if not name.endswith(self.SUFFIXES):
                        continue
                    text = read_file(path)
                    for match in self.WRAPPED.finditer(text):
                        n = text.count("\n", 0, match.start()) + 1
                        offenders.append(f"{rel}:{n}: {match.group()!r}")
                    if rel == "tests/test_static.py":
                        continue   # the patterns themselves name the words
                    for n, line in enumerate(text.splitlines(), 1):
                        if self.PATTERN.search(line) and not any(
                                rel == f and mark in line for f, mark in self.EXEMPT):
                            offenders.append(f"{rel}:{n}: {line.strip()[:90]}")
        self.assertEqual(offenders, [])

    def test_the_patterns_catch_each_form(self):
        for text in ("(Feature 26)", "Release v0.5", "Idea 19c", "Bug 8", "(M52)"):
            self.assertRegex(text, self.PATTERN)
        for text in ("(Idea\n        5)", "(Milestone\n51)", "Features\n# 3"):
            self.assertRegex(text, self.WRAPPED)
        for text in ("a feature flag", "release notes", "IdeaPad 5", "Bugs fixed:\n\n- the"):
            self.assertNotRegex(text, self.PATTERN)
            self.assertNotRegex(text, self.WRAPPED)


if __name__ == "__main__":
    unittest.main()
