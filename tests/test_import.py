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


if __name__ == "__main__":
    unittest.main()
