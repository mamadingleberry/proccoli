import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.jsonstream import JsonStreamParser  # noqa: E402


class ParserEdgeCasesTest(unittest.TestCase):
    def test_object_split_across_feeds(self):
        p = JsonStreamParser()
        self.assertEqual(p.feed('[\n{"a": {"b": '), [])
        self.assertEqual(p.feed('1}}'), [{"a": {"b": 1}}])

    def test_non_dict_values_are_dropped(self):
        self.assertEqual(JsonStreamParser().feed('[1, "x", {"a": 1}, null]'), [{"a": 1}])

    def test_garbage_without_any_object_is_discarded(self):
        p = JsonStreamParser()
        self.assertEqual(p.feed("no json here"), [])
        self.assertEqual(p.feed('{"a": 1}'), [{"a": 1}])

    def test_garbage_between_objects(self):
        self.assertEqual(JsonStreamParser().feed('{"a": 1} oops {"a": 2}'),
                         [{"a": 1}, {"a": 2}])

    def test_braces_inside_strings(self):
        self.assertEqual(JsonStreamParser().feed('{"name": "}{,["}'),
                         [{"name": "}{,["}])

    def test_unicode(self):
        self.assertEqual(JsonStreamParser().feed('{"name": "Résumé ✓"}'),
                         [{"name": "Résumé ✓"}])


L_OUTPUT = """\
card1                    Intel Alderlake_p (Gen12)         pci:vendor=8086,device=46A3,card=0
└─renderD128
card0                    Intel Dg2 (Gen12)                 pci:vendor=8086,device=56A0,card=1
cardX without filter
"""


if __name__ == "__main__":
    unittest.main()
