"""Tests for importing pre-written material + modifying existing chapters."""
import tempfile
import unittest

from bookwriter.config import Settings
from bookwriter.costs import CostLedger
from bookwriter.mock import MockLLM
from bookwriter.importer import split_into_chapters, build_graph_from_text
from bookwriter.planner import extend_outline
from bookwriter.writer import revise_chapter


class TestSplitter(unittest.TestCase):
    def test_markdown_headings(self):
        t = "## Chapter 1: Dawn\nThe sun rose.\n\n## Chapter 2: Dusk\nNight fell at last."
        ch = split_into_chapters(t)
        self.assertEqual([c["title"] for c in ch], ["Dawn", "Dusk"])
        self.assertIn("sun rose", ch[0]["body"])

    def test_chapter_word_lines(self):
        t = "Chapter One\nIt began.\n\nChapter Two\nIt ended."
        ch = split_into_chapters(t)
        self.assertEqual(len(ch), 2)

    def test_no_headings_single_chapter(self):
        ch = split_into_chapters("Just a blob of prose with no headings at all.")
        self.assertEqual(len(ch), 1)
        self.assertEqual(ch[0]["title"], "Chapter 1")

    def test_empty(self):
        self.assertEqual(split_into_chapters("   "), [])

    def test_prose_starting_with_chapter_or_part_is_not_a_heading(self):
        # Regression: "Part of her..." / "Chapter house..." are prose, not headings.
        for line in ("Part of her wanted to run away.",
                     "Chapter and verse, he quoted the law.",
                     "Chapter house was empty."):
            self.assertIsNone(__import__("bookwriter.importer", fromlist=["_is_heading"])._is_heading(line))
        t = "She walked in slowly.\nPart of her wanted to run away.\nBut she stayed and faced him."
        ch = split_into_chapters(t)
        self.assertEqual(len(ch), 1)
        # no text is lost
        for frag in ("walked in slowly", "Part of her wanted to run away", "faced him"):
            self.assertIn(frag, ch[0]["body"])

    def test_digit_heading_with_trailing_sentence_is_not_a_heading(self):
        # "Chapter 3 of the deal was signed." ends like a sentence -> not a heading.
        imp = __import__("bookwriter.importer", fromlist=["_is_heading"])
        self.assertIsNone(imp._is_heading("Chapter 3 of the deal was signed."))
        # but a real numbered heading still works
        self.assertIsNotNone(imp._is_heading("Chapter 3: The Vault"))
        self.assertIsNotNone(imp._is_heading("Chapter 3"))

    def test_titled_heading_ending_in_sentence_punctuation_is_a_heading(self):
        # Regression: a colon-titled heading whose title ends in ?/!/. is still a heading.
        imp = __import__("bookwriter.importer", fromlist=["_is_heading"])
        for h in ("Chapter 5: Who Are You?", "Chapter 7: Run!", "Chapter One: The Beginning."):
            self.assertIsNotNone(imp._is_heading(h), h)
        text = ("Chapter 1: The Start\nHe woke early.\n\n"
                "Chapter 2: Who Are You?\nA stranger appeared.\n\n"
                "Chapter 3: The End.\nIt was over.")
        ch = split_into_chapters(text)
        # 3 boundaries preserved; the "?" title survives (a trailing "." is trimmed
        # by the title cleaner, which is fine).
        self.assertEqual(len(ch), 3)
        self.assertEqual([c["title"] for c in ch][:2], ["The Start", "Who Are You?"])
        for frag in ("He woke early.", "A stranger appeared.", "It was over."):
            self.assertTrue(any(frag in c["body"] for c in ch), frag)

    def test_single_char_markdown_heading(self):
        imp = __import__("bookwriter.importer", fromlist=["_is_heading"])
        self.assertEqual(imp._is_heading("## X"), "X")
        self.assertEqual(imp._is_heading("## A long title"), "A long title")


class TestImportGraph(unittest.TestCase):
    def _settings(self):
        return Settings(project_dir=tempfile.mkdtemp()).with_profile("draft")

    def test_build_graph_structure_only(self):
        # no LLM -> structure-only import never fails
        g = build_graph_from_text(
            None, self._settings(), CostLedger(),
            text="## Chapter 1: A\nHello world here.\n\n## Chapter 2: B\nGoodbye world now.",
            title="My Draft", genre="memoir", analyze=False, run_extract=False)
        self.assertEqual(len(g.bible.outline), 2)
        self.assertEqual(len(g.chapters), 2)
        self.assertEqual(g.bible.title, "My Draft")
        self.assertEqual(g.chapters[1].text.strip(), "Hello world here.")
        # word_target reflects the real chapter length
        self.assertEqual(g.bible.outline[0].word_target, 3)

    def test_build_graph_with_mock_analysis(self):
        g = build_graph_from_text(
            MockLLM(), self._settings(), CostLedger(),
            text="## Chapter 1: A\n" + ("word " * 60) + "\n\n## Chapter 2: B\n" + ("word " * 60),
            title="Analyzed", analyze=True, run_extract=True)
        self.assertEqual(len(g.chapters), 2)
        # outline count always matches the actual chapters (authoritative)
        self.assertEqual(len(g.bible.outline), 2)


class TestModify(unittest.TestCase):
    def _graph(self):
        return build_graph_from_text(
            None, Settings().with_profile("draft"), CostLedger(),
            text="## Chapter 1: A\n" + ("alpha " * 30) + "\n\n## Chapter 2: B\n" + ("beta " * 30),
            analyze=False, run_extract=False)

    def test_revise_chapter_replaces_text(self):
        g = self._graph()
        plan = g.bible.plan(1)
        new = revise_chapter(MockLLM(), Settings().with_profile("draft"), CostLedger(),
                             g, plan, g.chapters[1].text, instructions="tighten")
        self.assertEqual(new.number, 1)
        self.assertGreater(new.word_count, 0)

    def test_extend_outline_appends(self):
        g = self._graph()
        plans = extend_outline(MockLLM(), Settings().with_profile("draft"), CostLedger(),
                               g, count=3)
        self.assertEqual(len(plans), 3)
        self.assertEqual([p.number for p in plans], [3, 4, 5])

    def test_revise_preserves_synopsis_line(self):
        g = self._graph()
        g.chapters[1].synopsis_line = "Ch1 synopsis kept"
        new = revise_chapter(MockLLM(), Settings().with_profile("draft"), CostLedger(),
                             g, g.bible.plan(1), g.chapters[1].text, instructions="polish")
        # a revise that doesn't re-extract must NOT blank the synopsis
        self.assertEqual(new.synopsis_line, "Ch1 synopsis kept")

    def test_extend_outline_tolerates_non_int_fields(self):
        class _BadLLM:
            def complete_json(self, **kw):
                return {"outline": [{"title": "Next", "act": "three", "word_target": "lots"}]}
            def complete_text(self, **kw):
                return ""
        g = self._graph()
        plans = extend_outline(_BadLLM(), Settings().with_profile("draft"), CostLedger(),
                               g, count=1)  # must not raise on "three"/"lots"
        self.assertEqual(plans[0].act, 3)
        self.assertEqual(plans[0].word_target, 2000)

    def test_extend_outline_zero_word_target_backfills(self):
        class _ZeroLLM:
            def complete_json(self, **kw):
                return {"outline": [{"title": "Next", "word_target": 0}]}
            def complete_text(self, **kw):
                return ""
        g = self._graph()
        plans = extend_outline(_ZeroLLM(), Settings().with_profile("draft"), CostLedger(),
                               g, count=1, words_per_chapter=1500)
        self.assertEqual(plans[0].word_target, 1500)  # 0 -> default, not "write 0 words"


if __name__ == "__main__":
    unittest.main()
