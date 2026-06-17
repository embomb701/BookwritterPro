"""Token accounting and cost reporting — the scoreboard for the project goal.

Every model call records a ``Usage`` against the ``CostLedger``, tagged by stage
and model. The ledger turns raw token counts into dollars using ``MODEL_PRICES``
and can print a per-stage breakdown plus a cost-per-1k-words figure, which is the
number that actually matters for "minimum token cost per book".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .config import MODEL_PRICES


@dataclass
class Usage:
    model: str
    stage: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    cache_ttl: str = "5m"

    def cost(self) -> float:
        p = MODEL_PRICES.get(self.model)
        if p is None:
            return 0.0
        write_rate = p.cache_write_1h if self.cache_ttl == "1h" else p.cache_write_5m
        return (
            self.input_tokens / 1e6 * p.input
            + self.output_tokens / 1e6 * p.output
            + self.cache_creation_tokens / 1e6 * write_rate
            + self.cache_read_tokens / 1e6 * p.cache_read
        )

    def total_input(self) -> int:
        return self.input_tokens + self.cache_creation_tokens + self.cache_read_tokens


class CostLedger:
    def __init__(self) -> None:
        self.entries: List[Usage] = []
        self.words_written: int = 0

    def add(self, usage: Usage) -> None:
        self.entries.append(usage)

    def add_words(self, n: int) -> None:
        self.words_written += n

    def total_cost(self) -> float:
        return sum(u.cost() for u in self.entries)

    def by_stage(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for u in self.entries:
            out[u.stage] = out.get(u.stage, 0.0) + u.cost()
        return out

    def by_model(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for u in self.entries:
            out[u.model] = out.get(u.model, 0.0) + u.cost()
        return out

    def totals(self) -> Dict[str, int]:
        return {
            "input": sum(u.input_tokens for u in self.entries),
            "output": sum(u.output_tokens for u in self.entries),
            "cache_write": sum(u.cache_creation_tokens for u in self.entries),
            "cache_read": sum(u.cache_read_tokens for u in self.entries),
        }

    def cache_savings(self) -> float:
        """Dollars saved by reading from cache instead of paying full input price.

        cache_read tokens would otherwise have cost full input price; they cost
        ~0.1x. This quantifies the single biggest lever in the system.
        """
        saved = 0.0
        for u in self.entries:
            p = MODEL_PRICES.get(u.model)
            if not p or not u.cache_read_tokens:
                continue
            saved += u.cache_read_tokens / 1e6 * (p.input - p.cache_read)
        return saved

    def report(self) -> str:
        t = self.totals()
        lines = ["=== COST REPORT ==="]
        lines.append(f"Total cost: ${self.total_cost():.4f}")
        if self.words_written:
            per_1k = self.total_cost() / self.words_written * 1000
            lines.append(f"Words written: {self.words_written:,}  (${per_1k:.4f} / 1k words)")
        lines.append("")
        lines.append("By stage:")
        for stage, c in sorted(self.by_stage().items(), key=lambda kv: -kv[1]):
            lines.append(f"  {stage:<10} ${c:.4f}")
        lines.append("By model:")
        for model, c in sorted(self.by_model().items(), key=lambda kv: -kv[1]):
            lines.append(f"  {model:<20} ${c:.4f}")
        lines.append("")
        lines.append(
            f"Tokens - in: {t['input']:,}  out: {t['output']:,}  "
            f"cache-write: {t['cache_write']:,}  cache-read: {t['cache_read']:,}"
        )
        savings = self.cache_savings()
        if savings > 0:
            lines.append(f"Prompt-cache savings vs uncached: ${savings:.4f}")
        return "\n".join(lines)
