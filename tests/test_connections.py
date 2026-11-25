"""Signal handlers held and disconnected together."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gi.repository import GObject  # noqa: E402

from proccoli.core.connections import Connections  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402


class Source(GObject.Object):
    __gsignals__ = {"poked": (GObject.SignalFlags.RUN_FIRST, None, (int,))}


class ConnectionsTest(unittest.TestCase):
    def test_disconnect_all_stops_every_callback(self):
        a, b, seen = Source(), Source(), []
        c = Connections()
        c.connect(a, "poked", lambda _s, n: seen.append(("a", n)))
        c.connect(b, "poked", lambda _s, n: seen.append(("b", n)))
        a.emit("poked", 1)
        b.emit("poked", 2)
        self.assertEqual(len(c), 2)
        c.disconnect_all()
        a.emit("poked", 3)
        b.emit("poked", 4)
        self.assertEqual(seen, [("a", 1), ("b", 2)])
        self.assertEqual(len(c), 0)

    def test_safe_to_call_twice_and_reusable(self):
        a, seen = Source(), []
        c = Connections()
        c.connect(a, "poked", lambda _s, n: seen.append(n))
        c.disconnect_all()
        c.disconnect_all()
        c.connect(a, "poked", lambda _s, n: seen.append(n))
        a.emit("poked", 5)
        self.assertEqual(seen, [5])

    def test_watch_one_key_or_several(self):
        settings = Settings.for_tests()
        seen = []
        c = Connections()
        c.watch(settings, "palette", lambda k, v: seen.append((k, v)))
        ids = c.watch(settings, ("color-scheme", "base"), lambda k, _v: seen.append(k))
        self.assertEqual(len(ids), 2)
        settings.set("palette", "nord")
        settings.set("color-scheme", "dark")
        c.disconnect_all()
        settings.set("palette", "tango")
        settings.set("color-scheme", "light")
        self.assertEqual(seen, [("palette", "nord"), "color-scheme"])

    def test_handlers_connected_elsewhere_can_be_adopted(self):
        a, seen = Source(), []
        handlers = [a.connect("poked", lambda _s, n: seen.append(n)),
                    a.connect_after("poked", lambda _s, n: seen.append(-n))]
        c = Connections()
        c.adopt(a, handlers)
        a.emit("poked", 1)
        c.disconnect_all()
        a.emit("poked", 2)
        self.assertEqual(seen, [1, -1])


if __name__ == "__main__":
    unittest.main()
