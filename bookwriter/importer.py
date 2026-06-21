"""Import pre-written material into a first-class BookwriterPro book.

The seam: most "AI book" tools only generate from scratch. This module lets a
user bring an existing manuscript (a draft, a finished book, a few chapters) and
turn it into a normal BookwriterPro book they can then edit, revise, illustrate,
continue, and publish — the same pipeline, just seeded from real prose.

What it does:
  1. ``split_into_chapters`` — split raw text into chapters on markdown headings
     or "Chapter N" lines (falls back to a single chapter). Stdlib only.
  2. ``analyze_manuscript`` — reverse-engineer a story *bible* from the prose via
     the LLM (characters, world, themes, style), DESCRIBING what's there rather
     than inventing. Best-effort: skipped cleanly when there's no model.
  3. ``build_graph_from_text`` — assemble a StoryGraph: a bible whose outline
     matches the actual chapters, each chapter recorded, and (when a model is
     available) the continuity extractor run over each chapter so the graph's
     characters / threads / rolling synopsis reflect the imported story.

Everything degrades gracefully: with no LLM the structure is still built from the
real text, so an import never fails just because there are no credentials.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .config import Settings
from .costs import CostLedger
from .graph import StoryGraph
from .models import Bible, ChapterPlan, ChapterRecord
from .planner import build_bible
from .prompts import PLAN_SCHEMA


# --------------------------------------------------------------------------- #
# 1. Chapter splitting
# --------------------------------------------------------------------------- #
_MD_HEADING = re.compile(r"^\s{0,3}#{1,3}\s+(\S.*?)\s*$")
# Spelled-out numbers/ordinals only — NOT any word — so a prose line like
# "Part of her wanted to run away." is not mistaken for a chapter heading.
_NUMWORD = (
    r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|"
    r"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"eleventh|twelfth|thirteenth|fourteenth|fifteenth|twentieth)"
    r"(?:[\-\s]+(?:one|two|three|four|five|six|seven|eight|nine))?"
)
_CHAPTER_NUM = rf"([0-9]+|[ivxlcdm]+|{_NUMWORD})"
# group(1)=number, group(2)=delimiter (":"/"."/"-"/"—") or "", group(3)=title/rest.
_CHAPTER_LINE = re.compile(
    rf"^\s*(?:chapter|ch\.?|part)\s+{_CHAPTER_NUM}\b\s*([:.\-—])?\s*(.*)$",
    re.IGNORECASE,
)
_CHAPTER_PREFIX = re.compile(
    rf"^\s*(?:chapter|ch\.?|part)\s+{_CHAPTER_NUM}\b[\s:.\-—]*",
    re.IGNORECASE,
)


def _clean_title(raw: str, idx: int) -> str:
    """Turn a heading line into a clean chapter title."""
    t = (raw or "").strip().lstrip("#").strip()
    # Drop a leading "Chapter 3:" / "Chapter Three —" so the real title remains.
    stripped = _CHAPTER_PREFIX.sub("", t).strip(" :.-—\t")
    if stripped:
        return stripped[:120]
    if t:
        return t[:120]
    return f"Chapter {idx}"


def _is_heading(line: str) -> Optional[str]:
    """Return the heading's raw title text if *line* is a chapter heading, else None."""
    m = _MD_HEADING.match(line)
    if m:
        return m.group(1)
    m = _CHAPTER_LINE.match(line)
    if m:
        s = line.strip()
        if len(s) > 80:
            return None
        delim = m.group(2)
        rest = (m.group(3) or "").strip()
        # An explicit delimiter ("Chapter 5: …", "Chapter 3 — …", "Chapter 3. …")
        # makes it unambiguously a titled heading — even if the title ends in
        # "?"/"!"/"." (e.g. "Chapter 5: Who Are You?").
        if delim:
            return s
        # No delimiter: "Chapter 3" / "Chapter One" (no title) is a heading; but
        # "Chapter 3 of the deal was signed." is prose — reject when a title
        # actually follows that reads like a sentence continuation (lowercase
        # start, or trailing sentence punctuation).
        if not rest:
            return s
        if rest[0].isupper() and s[-1] not in ".,;?!":
            return s
    return None


def split_into_chapters(text: str) -> List[Dict[str, str]]:
    """Split a manuscript into ``[{"title", "body"}]`` chapters.

    Splits on markdown headings (``#``/``##``/``###``) or ``Chapter N`` lines.
    With no detectable headings the whole text becomes a single chapter. Body
    text is preserved verbatim (only surrounding blank lines trimmed)."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    # Find heading line indices + their titles.
    heads: List[tuple] = []  # (line_index, raw_title)
    for i, ln in enumerate(lines):
        raw = _is_heading(ln)
        if raw is not None:
            heads.append((i, raw))

    chapters: List[Dict[str, str]] = []
    if not heads:
        body = text.strip()
        if body:
            chapters.append({"title": "Chapter 1", "body": body})
        return chapters

    # Any prose BEFORE the first heading becomes a front chapter only if it's
    # substantial (else it's a title page / blank and we drop it).
    pre = "\n".join(lines[: heads[0][0]]).strip()
    if len(pre.split()) >= 40:
        chapters.append({"title": "Opening", "body": pre})

    for h_i, (line_idx, raw) in enumerate(heads):
        start = line_idx + 1
        end = heads[h_i + 1][0] if h_i + 1 < len(heads) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        if not body:
            continue
        chapters.append({"title": _clean_title(raw, len(chapters) + 1), "body": body})

    # Re-number titles that are still generic, and guarantee at least one chapter.
    if not chapters:
        body = text.strip()
        if body:
            chapters.append({"title": "Chapter 1", "body": body})
    return chapters


def _word_count(text: str) -> int:
    return len((text or "").split())


# --------------------------------------------------------------------------- #
# 2. Reverse-engineer a bible from the prose
# --------------------------------------------------------------------------- #
ANALYZER_SYSTEM = """You are a continuity editor and story analyst. You are given an EXISTING, \
already-written manuscript (chapter titles plus excerpts). Reverse-engineer its \
story bible: DESCRIBE what is actually on the page — do not invent new plot, \
characters, or events that aren't there.

Produce:
- title, genre, tone, audience, themes, pov, tense, a one-line logline, and a \
style_guide that captures the manuscript's actual voice.
- the characters, locations, items, and plot threads that genuinely appear, with \
stable lowercase id slugs (e.g. "elara", "the_vault").
- an outline entry for EACH provided chapter (same count, same order), summarizing \
that chapter's actual purpose, central tension, and beats.

Be faithful to the source. Output ONLY the structured bible."""


def _manuscript_digest(chapters: List[Dict[str, str]], *, per_chapter_words: int = 220,
                       max_chapters: int = 40) -> str:
    """A compact, token-bounded digest of the manuscript for the analyzer:
    each chapter's title + an opening excerpt (and a closing line)."""
    out: List[str] = []
    for i, ch in enumerate(chapters[:max_chapters], 1):
        words = ch["body"].split()
        head = " ".join(words[:per_chapter_words])
        tail = " ".join(words[-40:]) if len(words) > per_chapter_words + 60 else ""
        out.append(f"### Chapter {i}: {ch['title']} ({len(words)} words)")
        out.append(head + ("…" if len(words) > per_chapter_words else ""))
        if tail:
            out.append(f"[…ends:] …{tail}")
        out.append("")
    if len(chapters) > max_chapters:
        out.append(f"(+{len(chapters) - max_chapters} more chapters omitted from this digest)")
    return "\n".join(out)


def analyze_manuscript(
    llm, settings: Settings, ledger: CostLedger,
    chapters: List[Dict[str, str]], *,
    title: Optional[str] = None, genre: Optional[str] = None, guidance: str = "",
) -> Optional[Bible]:
    """Reverse-engineer a Bible from the manuscript via the LLM. Returns None on
    any failure (caller falls back to a minimal bible)."""
    try:
        user = [
            f"WORKING TITLE: {title}" if title else "WORKING TITLE: (infer it)",
            f"GENRE HINT: {genre}" if genre else "",
            f"AUTHOR GUIDANCE: {guidance}" if guidance else "",
            f"\nThe manuscript has {len(chapters)} chapters. Produce an outline with "
            f"exactly {len(chapters)} entries, in order.\n",
            "MANUSCRIPT DIGEST (titles + excerpts):\n",
            _manuscript_digest(chapters),
        ]
        data = llm.complete_json(
            stage="plan",
            model=settings.profile.plan,
            system=ANALYZER_SYSTEM,
            user="\n".join(p for p in user if p),
            schema=PLAN_SCHEMA,
            max_tokens=settings.max_tokens_plan,
            ledger=ledger,
            cached=None,
            use_cache=False,
        )
        return build_bible(data)
    except Exception:  # noqa: BLE001 - analysis is best-effort
        return None


def _minimal_bible(chapters: List[Dict[str, str]], *, title: Optional[str],
                   genre: Optional[str]) -> Bible:
    return Bible(
        title=(title or "Imported Manuscript"),
        genre=(genre or ""),
        target_chapters=len(chapters),
    )


def _apply_outline(bible: Bible, chapters: List[Dict[str, str]]) -> None:
    """Make the bible's outline match the ACTUAL imported chapters (authoritative
    over whatever the analyzer returned), carrying over act/purpose/beats when the
    analyzer produced an aligned entry."""
    model_outline = list(bible.outline or [])
    outline: List[ChapterPlan] = []
    for i, ch in enumerate(chapters):
        src = model_outline[i] if i < len(model_outline) else None
        outline.append(ChapterPlan(
            number=i + 1,
            title=ch["title"] or (src.title if src else f"Chapter {i + 1}"),
            act=(src.act if src else 1),
            purpose=(src.purpose if src else ""),
            pov_character=(src.pov_character if src else ""),
            location_ids=(src.location_ids if src else []),
            character_ids=(src.character_ids if src else []),
            beats=(src.beats if src else []),
            tension=(src.tension if src else ""),
            forward_hook=(src.forward_hook if src else ""),
            word_target=_word_count(ch["body"]) or 2000,
        ))
    bible.outline = outline
    bible.target_chapters = len(chapters)


# --------------------------------------------------------------------------- #
# 3. Build a StoryGraph from the manuscript
# --------------------------------------------------------------------------- #
def build_graph_from_text(
    llm, settings: Settings, ledger: CostLedger, *,
    text: str, title: Optional[str] = None, genre: Optional[str] = None,
    guidance: str = "", analyze: bool = True, run_extract: bool = True,
    on_progress=None,
) -> StoryGraph:
    """Turn raw manuscript *text* into a populated StoryGraph.

    ``analyze`` reverse-engineers the bible via the LLM; ``run_extract`` runs the
    continuity extractor over each chapter. Both are best-effort and skip cleanly
    without a model. The returned graph is ready for ``BookStore.save_graph`` +
    per-chapter ``save_chapter`` by the caller."""
    chapters = split_into_chapters(text)
    if not chapters:
        raise ValueError("No text to import — paste or upload a manuscript first.")

    bible: Optional[Bible] = None
    if analyze:
        bible = analyze_manuscript(llm, settings, ledger, chapters,
                                   title=title, genre=genre, guidance=guidance)
    if bible is None:
        bible = _minimal_bible(chapters, title=title, genre=genre)
    if title:
        bible.title = title
    if genre:
        bible.genre = genre
    if not bible.title:
        bible.title = "Imported Manuscript"

    _apply_outline(bible, chapters)
    graph = StoryGraph(bible)

    # Record each chapter; optionally extract continuity so the graph is "live".
    from .extractor import extract_delta
    for i, ch in enumerate(chapters):
        n = i + 1
        plan = bible.plan(n)
        rec = ChapterRecord(number=n, title=ch["title"], text=ch["body"])
        rec.word_count = _word_count(ch["body"])
        rec.compute_fingerprint()
        graph.chapters[n] = rec
        ledger.add_words(rec.word_count)
        if on_progress:
            on_progress(n, len(chapters))
        synopsis = ""
        if run_extract and plan is not None:
            try:
                delta = extract_delta(llm, settings, ledger, graph, plan, rec)
                graph.apply_delta(delta)
                synopsis = delta.synopsis_line
            except Exception:  # noqa: BLE001 - extraction is best-effort
                pass
        graph.record_chapter(rec, synopsis, settings.synopsis_line_chars)

    return graph
