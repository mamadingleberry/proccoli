import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import proccoli  # noqa: E402


class MetaTest(unittest.TestCase):
    def test_version_is_semver(self):
        self.assertRegex(proccoli.__version__, r"^\d+\.\d+\.\d+$")

    def test_app_id_is_a_valid_application_id(self):
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio
        self.assertTrue(Gio.Application.id_is_valid(proccoli.APP_ID), proccoli.APP_ID)
        # Reverse-DNS with at least three parts, as desktop files expect.
        self.assertGreaterEqual(len(proccoli.APP_ID.split(".")), 3)

    def test_app_name(self):
        self.assertTrue(proccoli.APP_NAME.strip())

    def test_identity_is_not_hard_coded_elsewhere(self):
        """Renaming must only need __init__.py: no other module may spell
        out the app ID or display name."""
        src = os.path.join(os.path.dirname(__file__), "..", "src", "proccoli")
        # The ID anywhere, or the name as a whole string literal ("Proccoli").
        pattern = re.compile(re.escape(proccoli.APP_ID) + "|" +
                             r"([\"'])" + re.escape(proccoli.APP_NAME) + r"\1")
        offenders = []
        for dirpath, _dirs, files in os.walk(src):
            for name in files:
                path = os.path.join(dirpath, name)
                if not name.endswith(".py") or os.path.samefile(
                        path, os.path.join(src, "__init__.py")):
                    continue
                with open(path, encoding="utf-8") as fh:
                    if pattern.search(fh.read()):
                        offenders.append(os.path.relpath(path, src))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
