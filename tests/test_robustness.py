"""Regression tests for the adversarial-audit fixes: tolerant model loading,
graph guards against degenerate chapter numbers / null deltas, the prev_tail
off-by-zero, and CLI --only parsing. All offline."""
import unittest

from bookwriter.models import Bible, ChapterPlan, Character
from bookwriter.graph import StoryGraph
from bookwriter.extractor import _rels_to_map
from bookwriter.cli import _parse_only


class TestTolerantModelLoading(unittest.TestCase):
    def test_extra_key_ignored(self):
        cp = ChapterPlan.from_dict({"number": 1, "title": "X", "bogus": "drop me"})
        self.assertEqual(cp.number, 1)
        self.assertEqual(cp.title, "X")

    def test_missing_required_gets_default(self):
        # missing required 'number' (int) -> 0, not a crash
        cp = ChapterPlan.from_dict({"title": "Only title"})
        self.assertEqual(cp.number, 0)
        self.assertEqual(cp.title, "Only title")

    def test_non_dict_entry_returns_none(self):
        self.assertIsNone(Character.from_dict("not a dict"))

    def test_bible_from_dict_skips_bad_entries(self):
        b = Bible.from_dict({
            "title": "T",
            "characters": ["garbage", {"id": "hero", "name": "Wren", "junk": 1}],
            "outline": "not a list",  # tolerated -> empty
        })
        self.assertEqual(len(b.characters), 1)
        self.assertEqual(b.characters[0].id, "hero")
        self.assertEqual(b.outline, [])


class TestGraphGuards(unittest.TestCase):
    def _graph(self):
        return StoryGraph(Bible(title="T", outline=[ChapterPlan(number=1, title="C1")]))

    def test_record_chapter_number_zero_no_crash(self):
        from bookwriter.models import ChapterRecord
        g = self._graph()
        g.record_chapter(ChapterRecord(number=1, title="C1", text="hi"), "syn1", 240)
        # degenerate number 0 must not crash or clobber chapter 1's synopsis
        g.record_chapter(ChapterRecord(number=0, title="bad", text="x"), "synbad", 240)
        self.assertEqual(g.synopsis[0], "syn1")
        self.assertIn(0, g.chapters)  # still stored

    def test_apply_delta_null_collections(self):
        from bookwriter.extractor import StateDelta
        g = self._graph()
        g.bible.characters.append(Character(id="alice", name="Alice"))
        delta = StateDelta.from_dict(1, {"character_updates": [
            {"id": "alice", "knowledge_added": None, "relationship_updates": None},
        ]})
        g.apply_delta(delta)  # must not raise
        self.assertEqual(g.bible.character("alice").knowledge, [])

    def test_apply_delta_non_list_knowledge_not_shredded(self):
        # a bare string must NOT be iterated char-by-char into knowledge
        from bookwriter.extractor import StateDelta
        g = self._graph()
        g.bible.characters.append(Character(id="bob", name="Bob"))
        delta = StateDelta.from_dict(1, {"character_updates": [
            {"id": "bob", "knowledge_added": "a secret"},
        ]})
        g.apply_delta(delta)
        self.assertEqual(g.bible.character("bob").knowledge, [])

    def test_apply_delta_non_dict_entries_tolerated(self):
        from bookwriter.extractor import StateDelta
        g = self._graph()
        # via from_dict: non-dict entries in every list field are filtered
        delta = StateDelta.from_dict(1, {
            "character_updates": [{"id": "ghost"}, "junk"],
            "new_characters": ["junk", {"id": "z", "name": "Zed"}],
            "threads_opened": ["junk", {"name": "A thread"}],
            "threads_resolved": [{"bad": 1}, "central"],
        })
        g.apply_delta(delta)  # must not raise
        self.assertIsNotNone(g.bible.character("z"))
        # via direct construction (bypasses from_dict): loop guards still hold
        g.apply_delta(StateDelta(chapter=1, character_updates=[{"id": "z"}, "strjunk"]))

    def test_knowledge_added_non_string_elements_filtered(self):
        from bookwriter.extractor import StateDelta
        g = self._graph()
        g.bible.characters.append(Character(id="c1", name="Cee"))
        delta = StateDelta.from_dict(1, {"character_updates": [
            {"id": "c1", "knowledge_added": ["a real fact", {"k": "v"}, 123]},
        ]})
        g.apply_delta(delta)
        kn = g.bible.character("c1").knowledge
        self.assertEqual(kn, ["a real fact"])
        # rendering must not raise (this is the deferred crash the fix prevents)
        g.bible.character("c1").dynamic_card()
        g.bible.character("c1").card()

    def test_prev_tail_zero_returns_empty(self):
        from bookwriter.models import ChapterRecord
        g = self._graph()
        g.chapters[1] = ChapterRecord(number=1, title="C1", text="a b c d e")
        self.assertEqual(g.prev_tail(2, 0), "")
        self.assertEqual(g.prev_tail(2, 2), "d e")


class TestExtractorRels(unittest.TestCase):
    def test_non_dict_relationship_entries_filtered(self):
        upd = [{"id": "x", "relationship_updates": ["with relation here", {"with": "y", "relation": "ally"}]}]
        _rels_to_map(upd)  # must not raise
        self.assertEqual(upd[0]["relationship_updates"], {"y": "ally"})

    def test_outer_non_dict_and_non_list_tolerated(self):
        # a stray non-dict update entry, and a non-list argument, must not crash
        upd = [{"id": "c1"}, "junkentry"]
        _rels_to_map(upd)  # must not raise
        _rels_to_map("not a list")  # must not raise
        _rels_to_map({"id": "c1"})  # must not raise


class TestParseOnly(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(_parse_only("1,3,5"), [1, 3, 5])
        self.assertEqual(_parse_only("2-4"), [2, 3, 4])

    def test_reversed_range_normalized(self):
        self.assertEqual(_parse_only("4-2"), [2, 3, 4])

    def test_invalid_raises_clear(self):
        with self.assertRaises(ValueError):
            _parse_only("a-b")
        with self.assertRaises(ValueError):
            _parse_only("5-")


if __name__ == "__main__":
    unittest.main()
