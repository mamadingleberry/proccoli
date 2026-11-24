import contextlib
import io
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli import __version__, app  # noqa: E402


class CommandLineTest(unittest.TestCase):
    def _main(self, argv):
        """Run main() with the GTK application and GLib calls mocked out.
        Returns (Application mock, exit code or None, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(app, "Application") as cls, \
             mock.patch.object(app.GLib, "set_prgname"), \
             mock.patch.object(app.GLib, "set_application_name"), \
             mock.patch.object(app, "on_sigint"), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                app.main(argv)
            except SystemExit as exc:
                return cls, exc.code, out.getvalue(), err.getvalue()
        return cls, None, out.getvalue(), err.getvalue()

    def test_defaults(self):
        args = app.parse_args([])
        self.assertFalse(args.demo)
        self.assertFalse(args.debug)

    def test_flags(self):
        args = app.parse_args(["--demo", "--debug"])
        self.assertTrue(args.demo and args.debug)

    def test_version(self):
        cls, code, out, _ = self._main(["--version"])
        self.assertEqual(code, 0)
        self.assertIn(__version__, out)
        cls.assert_not_called()

    def test_unknown_option_is_rejected(self):
        cls, code, _, err = self._main(["--bogus"])
        self.assertEqual(code, 2)
        self.assertIn("--bogus", err)
        cls.assert_not_called()

    def test_runs_application_with_parsed_args(self):
        cls, code, _, _ = self._main(["--demo"])
        self.assertIsNone(code)
        self.assertTrue(cls.call_args.args[0].demo)
        # GApplication must not see our options (it would reject them).
        run_argv = cls.return_value.run.call_args.args[0]
        self.assertEqual(len(run_argv), 1)


if __name__ == "__main__":
    unittest.main()
