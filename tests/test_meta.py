import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import proccoli  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


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

    def test_readme_installs_this_version(self):
        """The README's package name follows the release (it said 0.3.0
        after 0.4.0 was tagged)."""
        readme = os.path.join(os.path.dirname(__file__), "..", "README.md")
        with open(readme, encoding="utf-8") as fh:
            versions = set(re.findall(r"proccoli_(\d+\.\d+\.\d+)_all\.deb", fh.read()))
        self.assertEqual(versions, {proccoli.__version__})

    def test_the_user_guide_installs_this_version(self):
        guide = os.path.join(ROOT, "docs", "USER-GUIDE.md")
        with open(guide, encoding="utf-8") as fh:
            versions = set(re.findall(r"proccoli_(\d+\.\d+\.\d+)_all\.deb", fh.read()))
        self.assertEqual(versions, {proccoli.__version__})

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


class ReadmeTest(unittest.TestCase):
    """The README is short, has the parts a reader looks for, and every
    image and link in it (and in the user guide) leads somewhere."""

    def read(self, *path):
        with open(os.path.join(ROOT, *path), encoding="utf-8") as fh:
            return fh.read()

    @staticmethod
    def anchor(heading: str) -> str:
        """GitHub's anchor for a heading."""
        return re.sub(r"[^a-z0-9 -]", "", heading.strip().lower()).replace(" ", "-")

    def links(self, text):
        out = re.findall(r"\]\(([^)\s]+)\)", text) + re.findall(r'<img src="([^"]+)"', text)
        return [t for t in out if not re.match(r"[a-z]+:", t)]

    def check_links(self, *path):
        text = self.read(*path)
        folder = os.path.join(ROOT, *path[:-1])
        for target in self.links(text):
            file, _, anchor = target.partition("#")
            full = os.path.normpath(os.path.join(folder, file)) if file else \
                os.path.join(ROOT, *path)
            with self.subTest(path=path, target=target):
                self.assertTrue(os.path.exists(full), target)
                if anchor:
                    with open(full, encoding="utf-8") as fh:
                        headings = [self.anchor(h) for h in re.findall(r"^#+ (.+)$", fh.read(), re.M)]
                    self.assertIn(anchor, headings)

    def test_readme_links_and_images_resolve(self):
        self.check_links("README.md")

    def test_user_guide_links_resolve(self):
        self.check_links("docs", "USER-GUIDE.md")

    def test_readme_is_short(self):
        self.assertLess(len(self.read("README.md").splitlines()), 150)

    def test_readme_has_the_parts_readers_look_for(self):
        headings = re.findall(r"^## (.+)$", self.read("README.md"), re.M)
        for part in ("Requirements", "Install", "Help", "Disclaimer", "License"):
            self.assertIn(part, headings)
        text = self.read("README.md")
        self.assertIn("SECURITY.md", text)
        self.assertIn("Claude", text)

    def test_the_metainfo_screenshots_are_the_readmes(self):
        meta = self.read("data", "io.github.mamadingleberry.Proccoli.metainfo.xml")
        images = re.findall(r"<image>[^<]*/(docs/screenshots/[^<]+)</image>", meta)
        self.assertGreater(len(images), 0)
        for image in images:
            with self.subTest(image=image):
                self.assertTrue(os.path.exists(os.path.join(ROOT, image)))

    def test_readme_screenshots_are_small(self):
        for target in self.links(self.read("README.md")):
            if target.endswith(".png"):
                with self.subTest(target=target):
                    self.assertLess(os.path.getsize(os.path.join(ROOT, target)), 200 * 1024)


if __name__ == "__main__":
    unittest.main()
