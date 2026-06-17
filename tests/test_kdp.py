import io
import json
import os
import tempfile
import unittest
import zipfile
from xml.dom import minidom

from bookwriter.config import Settings
from bookwriter.costs import CostLedger
from bookwriter.mock import MockLLM
from bookwriter.pipeline import BookPipeline
from bookwriter.kdp import (
    KDP_SCHEMA, KdpMetadata, generate_kdp_metadata, build_epub, build_kdp_kit,
    MAX_DESCRIPTION_CHARS, MAX_KEYWORDS, MAX_KEYWORD_CHARS, MAX_CATEGORIES,
    STORYTELLER_KEYWORD,
)


def _build_book(tmp, *, premise="a detective hunts a small town killer",
                chapters=3, genre=None):
    """Run the offline pipeline to get a real StoryGraph with chapters."""
    settings = Settings(project_dir=tmp).with_profile("balanced")
    pipe = BookPipeline(MockLLM(), settings)
    pipe.plan(premise=premise, chapters=chapters, words_per_chapter=150)
    if genre:
        pipe.graph.bible.genre = genre
    pipe.write_all()
    return pipe.graph, settings


class TestKdpSchema(unittest.TestCase):
    def test_schema_is_strict_and_has_required(self):
        self.assertEqual(KDP_SCHEMA["additionalProperties"], False)
        for key in ("description", "keywords", "categories", "subtitle",
                    "reading_age_min", "reading_age_max", "series_suggestion"):
            self.assertIn(key, KDP_SCHEMA["properties"])
            self.assertIn(key, KDP_SCHEMA["required"])


class TestGenerateMetadata(unittest.TestCase):
    def test_limits_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph, settings = _build_book(tmp, genre="mystery")
            meta = generate_kdp_metadata(
                MockLLM(), settings, CostLedger(), graph,
                author_first="Jane", author_last="Doe",
            )
            self.assertIsInstance(meta, KdpMetadata)
            # keywords
            self.assertLessEqual(len(meta.keywords), MAX_KEYWORDS)
            self.assertTrue(meta.keywords)
            for k in meta.keywords:
                self.assertLessEqual(len(k), MAX_KEYWORD_CHARS)
            # no dupes
            self.assertEqual(len(meta.keywords), len(set(k.lower() for k in meta.keywords)))
            # categories
            self.assertLessEqual(len(meta.categories), MAX_CATEGORIES)
            self.assertTrue(meta.categories)
            # description
            self.assertLessEqual(len(meta.description), MAX_DESCRIPTION_CHARS)
            self.assertTrue(meta.description)
            # adult -> blank reading age
            self.assertEqual(meta.reading_age_min, "")
            self.assertEqual(meta.reading_age_max, "")
            # author preserved verbatim (not generated)
            self.assertEqual(meta.author_first, "Jane")
            self.assertEqual(meta.author_last, "Doe")
            self.assertEqual(meta.publishing_rights, "owned")
            self.assertEqual(meta.primary_marketplace, "Amazon.com")

    def test_description_truncated_to_4000(self):
        class FatLLM(MockLLM):
            def _kdp(self, user):
                d = super()._kdp(user)
                d["description"] = "word " * 2000  # ~10000 chars
                d["keywords"] = ["x" * 80] + ["only one"]  # over-length + valid
                d["categories"] = [f"Cat {i}" for i in range(10)]
                return d

        with tempfile.TemporaryDirectory() as tmp:
            graph, settings = _build_book(tmp)
            meta = generate_kdp_metadata(
                FatLLM(), settings, CostLedger(), graph,
                author_first="A", author_last="B",
            )
            self.assertLessEqual(len(meta.description), MAX_DESCRIPTION_CHARS)
            self.assertLessEqual(len(meta.categories), MAX_CATEGORIES)
            for k in meta.keywords:
                self.assertLessEqual(len(k), MAX_KEYWORD_CHARS)

    def test_keywords_drop_title_and_author(self):
        class LeakLLM(MockLLM):
            def _kdp(self, user):
                d = super()._kdp(user)
                d["keywords"] = ["the threshold story", "wren calloway thriller",
                                 "clean search phrase"]
                return d

        with tempfile.TemporaryDirectory() as tmp:
            graph, settings = _build_book(tmp)
            graph.bible.title = "The Threshold"
            meta = generate_kdp_metadata(
                LeakLLM(), settings, CostLedger(), graph,
                author_first="Wren", author_last="Calloway",
            )
            low = [k.lower() for k in meta.keywords]
            self.assertNotIn("the threshold story", low)
            self.assertNotIn("wren calloway thriller", low)
            self.assertIn("clean search phrase", low)

    def test_title_subtitle_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph, settings = _build_book(tmp)
            graph.bible.title = "The Long Road : A Journey Home"
            meta = generate_kdp_metadata(
                MockLLM(), settings, CostLedger(), graph,
                author_first="A", author_last="B",
            )
            self.assertEqual(meta.title, "The Long Road")
            self.assertEqual(meta.subtitle, "A Journey Home")
            self.assertEqual(meta.full_title(), "The Long Road: A Journey Home")

    def test_metadata_roundtrip(self):
        meta = KdpMetadata(
            title="T", author_first="A", author_last="B",
            subtitle="Sub", keywords=["k1", "k2"], categories=["c1"],
            contributors=[{"first": "C", "last": "D"}],
        )
        d = meta.to_dict()
        again = KdpMetadata.from_dict(d)
        self.assertEqual(again.to_dict(), d)
        self.assertEqual(again.full_title(), "T: Sub")
        self.assertEqual(again.all_creators(), ["A B", "C D"])


class TestEpub(unittest.TestCase):
    def _meta(self, graph):
        return KdpMetadata(
            title=graph.bible.title or "Test Book",
            subtitle="A Subtitle",
            author_first="Jane", author_last="Doe",
            contributors=[{"first": "John", "last": "Smith"}],
            description="A blurb.",
            keywords=["k1"], categories=["c1"],
        )

    def test_epub_is_valid_zip_with_stored_mimetype(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph, _ = _build_book(tmp)
            data = build_epub(graph, self._meta(graph))
            self.assertIsInstance(data, bytes)
            zf = zipfile.ZipFile(io.BytesIO(data))
            self.assertIsNone(zf.testzip())
            names = zf.namelist()
            # mimetype must be the FIRST entry, STORED, exact content
            self.assertEqual(names[0], "mimetype")
            info = zf.getinfo("mimetype")
            self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
            self.assertEqual(zf.read("mimetype"), b"application/epub+zip")
            # required structural files present
            for required in ("META-INF/container.xml", "OEBPS/content.opf",
                             "OEBPS/nav.xhtml", "OEBPS/toc.ncx",
                             "OEBPS/title.xhtml", "OEBPS/cover.svg",
                             "OEBPS/cover.xhtml"):
                self.assertIn(required, names)
            # one xhtml per chapter
            chap_files = [n for n in names if n.startswith("OEBPS/chap-")]
            self.assertEqual(len(chap_files), len(graph.chapters))

    def test_opf_has_required_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph, _ = _build_book(tmp)
            meta = self._meta(graph)
            zf = zipfile.ZipFile(io.BytesIO(build_epub(graph, meta)))
            opf = zf.read("OEBPS/content.opf").decode("utf-8")
            self.assertIn("<dc:title>", opf)
            self.assertIn(meta.full_title(), opf)
            self.assertIn("<dc:creator", opf)
            self.assertIn("Jane Doe", opf)
            self.assertIn("John Smith", opf)        # contributor
            self.assertIn("<dc:language>", opf)
            self.assertIn("<dc:identifier", opf)
            self.assertIn("urn:uuid:", opf)
            self.assertIn("cover-image", opf)

    def test_all_xml_well_formed(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph, _ = _build_book(tmp)
            zf = zipfile.ZipFile(io.BytesIO(build_epub(graph, self._meta(graph))))
            for name in zf.namelist():
                if name == "mimetype" or name.endswith(".css"):
                    continue
                # raises on malformed XML
                minidom.parseString(zf.read(name))

    def test_chapter_text_never_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph, _ = _build_book(tmp, chapters=4)
            zf = zipfile.ZipFile(io.BytesIO(build_epub(graph, self._meta(graph))))
            for n in sorted(graph.chapters):
                rec = graph.chapters[n]
                # gather all chapter xhtml text content
                xhtml = "".join(
                    zf.read(name).decode("utf-8")
                    for name in zf.namelist() if name.startswith("OEBPS/chap-")
                )
                # every non-trivial word of the prose must survive escaping/split
                src_words = rec.text.split()
                doc_text = "".join(
                    minidom.parseString(zf.read(name)).documentElement.toxml()
                    for name in zf.namelist() if name.startswith("OEBPS/chap-")
                )
                for w in src_words:
                    if w.isalpha() and len(w) > 3:
                        self.assertIn(w, doc_text,
                                      f"chapter {n} lost word {w!r}")

    def test_custom_cover_embedded(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph, _ = _build_book(tmp)
            svg = ('<?xml version="1.0" encoding="UTF-8"?>'
                   '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                   '<rect width="10" height="10" fill="red"/></svg>')
            zf = zipfile.ZipFile(io.BytesIO(build_epub(graph, self._meta(graph),
                                                       cover_svg=svg)))
            self.assertEqual(zf.read("OEBPS/cover.svg").decode("utf-8"), svg)


class TestKit(unittest.TestCase):
    def test_kit_writes_all_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph, settings = _build_book(tmp, genre="mystery")
            meta = generate_kdp_metadata(
                MockLLM(), settings, CostLedger(), graph,
                author_first="Jane", author_last="Doe",
            )
            out = os.path.join(tmp, "kdp")
            result = build_kdp_kit(graph, meta, out)
            paths = result["paths"]
            for key in ("metadata", "epub", "cover", "listing", "checklist"):
                self.assertTrue(os.path.exists(paths[key]), f"missing {key}")
            # metadata.json round-trips to the same dict
            with open(paths["metadata"], encoding="utf-8") as f:
                self.assertEqual(json.load(f), meta.to_dict())
            self.assertEqual(result["metadata"], meta.to_dict())
            # epub on disk is a valid zip
            with open(paths["epub"], "rb") as f:
                zf = zipfile.ZipFile(io.BytesIO(f.read()))
                self.assertIsNone(zf.testzip())
            # listing labels every page-1 field
            with open(paths["listing"], encoding="utf-8") as f:
                listing = f.read()
            for label in ("Language:", "Book Title:", "Subtitle:", "Series:",
                          "Edition Number:", "Primary Author:", "Contributors:",
                          "Description", "Publishing Rights:",
                          "Sexually Explicit", "Reading age:",
                          "Primary marketplace:", "Categories", "Keywords"):
                self.assertIn(label, listing)
            self.assertIn(STORYTELLER_KEYWORD, listing)
            # checklist mentions upload + ISBN + storyteller tip
            with open(paths["checklist"], encoding="utf-8") as f:
                checklist = f.read()
            self.assertIn("manuscript.epub", checklist)
            self.assertIn("ISBN", checklist)
            self.assertIn(STORYTELLER_KEYWORD, checklist)


if __name__ == "__main__":
    unittest.main()
