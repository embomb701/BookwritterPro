"""Writer stage: generate one chapter's prose.

The stable bible is passed as the cached prefix; only the small volatile brief
(rolling synopsis + previous-chapter tail + this chapter's beats) goes in the
user turn. The model still has full context but we pay ~0.1x for the big part.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from .config import Settings
from .costs import CostLedger
from .graph import StoryGraph
from .llm import LLM
from .models import ChapterPlan, ChapterRecord
from .prompts import WRITER_SYSTEM


def _word_count(text: str) -> int:
    return len(text.split())


def write_chapter(
    llm: LLM, settings: Settings, ledger: CostLedger, graph: StoryGraph,
    plan: ChapterPlan, on_delta: Optional[Callable[[str], None]] = None,
) -> ChapterRecord:
    is_first = plan.number == 1
    is_last = plan.number == graph.bible.target_chapters or plan.number == len(graph.bible.outline)

    # Stable, cacheable prefix: the frozen bible spine (never mutated mid-run).
    cached = graph.static_prefix() if settings.use_cache else None

    # Volatile suffix: only what changes per chapter.
    parts: List[str] = []
    if not settings.use_cache:
        # No caching: include the frozen spine inline so the model still has the
        # canonical bible (paid at full price).
        parts.append(graph.static_prefix())
        parts.append("")

    parts.append("## Story so far (rolling synopsis)")
    parts.append(graph.rolling_synopsis())

    # Current mutable continuity (status/knowledge/open threads) — kept out of the
    # cached prefix on purpose, since it changes every chapter.
    dyn = graph.dynamic_state(plan)
    if dyn:
        parts.append("\n## Continuity state right now")
        parts.append(dyn)

    tail = graph.prev_tail(plan.number, settings.prev_tail_words)
    if tail:
        parts.append("\n## End of the previous chapter (continue cleanly from here)")
        parts.append("…" + tail)

    parts.append("\n## Write this chapter now")
    parts.append(plan.brief())
    if is_first:
        parts.append("\nThis is the OPENING chapter: hook immediately, establish the protagonist "
                     "and the core stakes, and avoid throat-clearing.")
    if is_last:
        parts.append("\nThis is the FINAL chapter: resolve the open threads and deliver a "
                     "satisfying ending. Do not introduce a new cliffhanger.")
    parts.append(f"\nWrite approximately {plan.word_target} words of prose.")

    text = llm.complete_text(
        stage="write",
        model=settings.profile.write,
        system=WRITER_SYSTEM,
        user="\n".join(parts),
        max_tokens=settings.max_tokens_write,
        ledger=ledger,
        cached=cached,
        use_cache=settings.use_cache,
        cache_ttl=settings.cache_ttl,
        on_delta=on_delta,
    ).strip()

    rec = ChapterRecord(number=plan.number, title=plan.title, text=text)
    rec.word_count = _word_count(text)
    ledger.add_words(rec.word_count)
    return rec
