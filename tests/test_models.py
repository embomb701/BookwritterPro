import unittest

from bookwriter.models import Bible, Character, PlotThread, ChapterPlan, ChapterRecord


class TestModels(unittest.TestCase):
    def test_bible_roundtrip(self):
        b = Bible(
            title="T", premise="p", genre="g", style_guide="s",
            characters=[Character(id="hero", name="Hero", role="protagonist",
                                  traits=["brave"], relationships={"rival": "enemy"})],
            threads=[PlotThread(id="q", name="Quest")],
            outline=[ChapterPlan(number=1, title="One", beats=["a", "b"])],
        )
        b2 = Bible.from_dict(b.to_dict())
        self.assertEqual(b2.title, "T")
        self.assertEqual(b2.character("hero").relationships, {"rival": "enemy"})
        self.assertEqual(b2.plan(1).beats, ["a", "b"])
        self.assertEqual(len(b2.threads), 1)

    def test_character_card_is_compact(self):
        c = Character(id="x", name="X", role="lead", traits=["t"], voice="terse")
        card = c.card()
        self.assertIn("[x] X", card)
        self.assertIn("terse", card)

    def test_chapter_fingerprint_stable(self):
        r1 = ChapterRecord(number=1, title="a", text="hello world")
        r2 = ChapterRecord(number=1, title="a", text="hello world")
        self.assertEqual(r1.compute_fingerprint(), r2.compute_fingerprint())
        r3 = ChapterRecord(number=1, title="a", text="different")
        self.assertNotEqual(r1.compute_fingerprint(), r3.compute_fingerprint())

    def test_clean_drops_empty(self):
        d = Character(id="x", name="X").to_dict()
        self.assertNotIn("voice", d)   # empty string dropped
        self.assertIn("name", d)


if __name__ == "__main__":
    unittest.main()
