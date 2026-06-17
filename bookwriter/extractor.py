"""Extractor stage: chapter prose -> structured state delta (cheap model).

This is the incremental-update step. Instead of re-summarizing the whole world,
it emits only what changed, which the graph merges in. Runs on the cheapest
capable model — it's mechanical, not creative.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .config import Settings
from .costs import CostLedger
from .graph import StoryGraph, StateDelta
from .llm import LLM
from .models import ChapterPlan, ChapterRecord
from .prompts import EXTRACTOR_SYSTEM, DELTA_SCHEMA


def _rels_to_map(updates: List[Dict[str, Any]]) -> None:
    """Convert each character_update's relationship_updates array -> dict in place."""
    for upd in updates:
        rels = upd.get("relationship_updates")
        if isinstance(rels, list):
            upd["relationship_updates"] = {
                r["with"]: r["relation"] for r in rels if "with" in r and "relation" in r
            }


def extract_delta(
    llm: LLM, settings: Settings, ledger: CostLedger, graph: StoryGraph,
    plan: ChapterPlan, rec: ChapterRecord,
) -> StateDelta:
    # Give the extractor the relevant slice (small) plus the prose — it only needs
    # the entities in play to detect deltas and contradictions, not the full bible.
    context = graph.relevant_slice(plan)
    user = (
        f"ESTABLISHED STATE (relevant slice):\n{context}\n\n"
        f"CHAPTER {plan.number}: {plan.title}\n"
        f"Intended beats: {'; '.join(plan.beats) if plan.beats else '(none)'}\n\n"
        f"CHAPTER TEXT:\n{rec.text}"
    )
    data = llm.complete_json(
        stage="extract",
        model=settings.profile.extract,
        system=EXTRACTOR_SYSTEM,
        user=user,
        schema=DELTA_SCHEMA,
        max_tokens=settings.max_tokens_extract,
        ledger=ledger,
        cached=None,
        use_cache=False,
    )
    _rels_to_map(data.get("character_updates", []))
    return StateDelta.from_dict(plan.number, data)
