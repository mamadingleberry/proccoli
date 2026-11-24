"""core.trust: which programs may be run as root (Milestone 40)."""

import os
import stat
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.trust import SYSTEM_BIN_DIRS, find_trusted, is_trusted_path, root_only  # noqa: E402


def st(uid=0, mode=0o755, kind=stat.S_IFREG):
    return os.stat_result((kind | mode, 0, 0, 1, uid, 0, 0, 0, 0, 0))


DIR = stat.S_IFDIR


class FakeFs:
    """path -> stat_result; anything missing raises FileNotFoundError."""

    def __init__(self, entries, links=None):
        self.entries = {"/": st(kind=DIR), **entries}
        self.links = links or {}

    def stat(self, path):
        try:
            return self.entries[path]
        except KeyError:
            raise FileNotFoundError(path) from None

    def realpath(self, path):
        return self.links.get(path, path)

    def trusted(self, path):
        return is_trusted_path(path, stat=self.stat, realpath=self.realpath)


SYSTEM = {"/usr": st(kind=DIR), "/usr/bin": st(kind=DIR),
          "/usr/bin/intel_gpu_top": st()}


class TrustTest(unittest.TestCase):
    def test_root_owned_system_program(self):
        self.assertTrue(FakeFs(SYSTEM).trusted("/usr/bin/intel_gpu_top"))

    def test_owned_by_the_user(self):
        fs = FakeFs({**SYSTEM, "/usr/bin/intel_gpu_top": st(uid=1000)})
        self.assertFalse(fs.trusted("/usr/bin/intel_gpu_top"))

    def test_group_or_world_writable(self):
        for mode in (0o775, 0o757):
            fs = FakeFs({**SYSTEM, "/usr/bin/intel_gpu_top": st(mode=mode)})
            self.assertFalse(fs.trusted("/usr/bin/intel_gpu_top"), oct(mode))

    def test_any_writable_directory_above_spoils_it(self):
        # The source checkout: root-owned file, but in the user's home.
        fs = FakeFs({"/home": st(kind=DIR), "/home/u": st(uid=1000, mode=0o750, kind=DIR),
                     "/home/u/helper.py": st()})
        self.assertFalse(fs.trusted("/home/u/helper.py"))
        fs = FakeFs({**SYSTEM, "/usr/bin": st(mode=0o777, kind=DIR)})
        self.assertFalse(fs.trusted("/usr/bin/intel_gpu_top"))

    def test_symlinks_are_judged_by_their_target(self):
        fs = FakeFs({**SYSTEM, "/home": st(kind=DIR), "/home/u": st(uid=1000, kind=DIR),
                     "/home/u/igt": st(uid=1000)},
                    links={"/usr/bin/intel_gpu_top": "/home/u/igt"})
        self.assertFalse(fs.trusted("/usr/bin/intel_gpu_top"))

    def test_missing_not_executable_or_not_a_file(self):
        fs = FakeFs({**SYSTEM, "/usr/bin/data": st(mode=0o644),
                     "/usr/bin/dir": st(kind=DIR)})
        self.assertFalse(fs.trusted("/usr/bin/nothing"))
        self.assertFalse(fs.trusted("/usr/bin/data"))
        self.assertFalse(fs.trusted("/usr/bin/dir"))

    def test_root_only(self):
        self.assertTrue(root_only(st(mode=0o755)))
        self.assertFalse(root_only(st(mode=0o775)))
        self.assertFalse(root_only(st(uid=1)))

    def test_find_trusted_searches_system_folders_only(self):
        fs = FakeFs(SYSTEM)
        self.assertEqual(find_trusted("intel_gpu_top", fs.trusted), "/usr/bin/intel_gpu_top")
        self.assertIsNone(find_trusted("nothing", fs.trusted))
        self.assertFalse(any(d.startswith(("/home", "~")) for d in SYSTEM_BIN_DIRS))

    def test_this_machines_python_and_a_home_file(self):
        # The real check on the real filesystem.
        self.assertTrue(is_trusted_path("/usr/bin/python3"))
        self.assertFalse(is_trusted_path(__file__))


if __name__ == "__main__":
    unittest.main()
