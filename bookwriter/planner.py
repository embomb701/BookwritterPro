"""Planner stage: premise -> full story bible + chapter outline.

One model call (no caching needed — it runs once). Produces the stable spine that
every chapter then reuses via the prompt cache.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .config import Settings
from .costs import CostLedger
from .llm import LLM
from .models import Bible, Character, Location, Item, PlotThread, ChapterPlan
from .prompts import PLANNER_SYSTEM, PLAN_SCHEMA


def _rel_to_dict(rels: List[Dict[str, str]]) -> Dict[str, str]:
    return {r["with"]: r["relation"] for r in rels if "with" in r and "relation" in r}


def build_bible(d: Dict[str, Any]) -> Bible:
    """Map the planner's JSON into a Bible (converting relationship arrays to maps)."""
    chars: List[Character] = []
    for c in d.get("characters", []):
        rels = _rel_to_dict(c.pop("relationships", []) if isinstance(c.get("relationships"), list) else [])
        chars.append(Character(
            id=c.get("id", ""), name=c.get("name", ""), role=c.get("role", ""),
            traits=c.get("traits", []), appearance=c.get("appearance", ""),
            voice=c.get("voice", ""), arc=c.get("arc", ""),
            relationships=rels,
            first_chapter=None,
        ))
    bible = Bible(
        title=d.get("title", "Untitled"),
        premise=d.get("premise", ""),
        genre=d.get("genre", ""),
        tone=d.get("tone", ""),
        audience=d.get("audience", ""),
        themes=d.get("themes", []),
        pov=d.get("pov", "third-person limited"),
        tense=d.get("tense", "past"),
        style_guide=d.get("style_guide", ""),
        logline=d.get("logline", ""),
        target_chapters=d.get("target_chapters", len(d.get("outline", [])) or 12),
        act_structure=d.get("act_structure", ""),
        characters=chars,
        locations=[Location.from_dict(x) for x in d.get("locations", [])],
        items=[Item.from_dict(x) for x in d.get("items", [])],
        threads=[PlotThread.from_dict({**x, "status": "open"}) for x in d.get("threads", [])],
        outline=[ChapterPlan.from_dict(x) for x in d.get("outline", [])],
    )
    bible.outline.sort(key=lambda p: p.number)
    return bible


def plan_book(
    llm: LLM, settings: Settings, ledger: CostLedger, *,
    premise: str, chapters: Optional[int] = None, words_per_chapter: int = 2000,
    title: Optional[str] = None, genre: Optional[str] = None,
    extra_guidance: str = "",
) -> Bible:
    target = chapters or 12
    user = [
        f"PREMISE:\n{premise}",
        f"\nTarget length: {target} chapters of roughly {words_per_chapter} words each.",
    ]
    if title:
        user.append(f"Working title: {title}")
    if genre:
        user.append(f"Genre: {genre}")
    if extra_guidance:
        user.append(f"\nAdditional guidance:\n{extra_guidance}")
    user.append(
        "\nDesign the bible and a complete outline of exactly "
        f"{target} chapters. Set word_target on each chapter (default {words_per_chapter})."
    )

    data = llm.complete_json(
        stage="plan",
        model=settings.profile.plan,
        system=PLANNER_SYSTEM,
        user="\n".join(user),
        schema=PLAN_SCHEMA,
        max_tokens=settings.max_tokens_plan,
        ledger=ledger,
        cached=None,
        use_cache=False,
    )
    bible = build_bible(data)
    # Backfill word targets if the model omitted them.
    for p in bible.outline:
        if not p.word_target:
            p.word_target = words_per_chapter
    return bible
