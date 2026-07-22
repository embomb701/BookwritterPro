"""Data models for the story bible and continuity graph.

Plain dataclasses (no third-party dependency) with explicit dict (de)serialization
so the whole package imports and tests with zero installs. Each model also knows
how to render itself as a compact "card" for prompts — keeping the prompt-token
footprint small is the point.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict, MISSING
from typing import Dict, List, Optional, Any


def _clean(d: Dict[str, Any]) -> Dict[str, Any]:
    """Drop empty values to keep serialized JSON and rendered cards small."""
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


def _coerce(cls, d: Any):
    """Tolerant dataclass loader for model dicts coming from the LLM or disk.

    The LLM (especially the OpenAI/OpenRouter json_object path, which can't
    structurally enforce the schema) may emit a stray key or omit a required one.
    ``cls(**d)`` would raise and discard the whole bible. Instead: ignore unknown
    keys and fill any missing required field with a type-appropriate empty value
    (0 for ints, "" otherwise). Non-dict entries return ``None`` (callers skip).
    """
    if not isinstance(d, dict):
        return None
    known = cls.__dataclass_fields__
    kwargs = {k: v for k, v in d.items() if k in known}
    for name, f in known.items():
        if name in kwargs:
            continue
        if f.default is not MISSING or f.default_factory is not MISSING:
            continue  # field has its own default
        kwargs[name] = 0 if "int" in str(f.type) else ""
    return cls(**kwargs)


def _load_list(cls, raw: Any) -> list:
    """Build a list of model instances from possibly-malformed LLM/disk data:
    tolerate a non-list (-> empty) and drop entries that aren't dicts."""
    if not isinstance(raw, list):
        return []
    return [obj for obj in (cls.from_dict(x) for x in raw) if obj is not None]


# ---------------------------------------------------------------------------
# Continuity-graph entities
# ---------------------------------------------------------------------------


@dataclass
class Character:
    id: str
    name: str
    role: str = ""                       # protagonist / antagonist / supporting ...
    traits: List[str] = field(default_factory=list)
    appearance: str = ""
    voice: str = ""                      # speech pattern / diction notes
    arc: str = ""                        # intended character arc, one line
    status: str = "active"               # active / dead / departed / ...
    knowledge: List[str] = field(default_factory=list)   # facts this character knows
    relationships: Dict[str, str] = field(default_factory=dict)  # other_id -> relation
    first_chapter: Optional[int] = None

    def static_card(self) -> str:
        """Frozen identity only — no fields the extractor mutates. Goes in the
        cacheable prefix, so it must be byte-stable across the whole run."""
        bits = [f"[{self.id}] {self.name}"]
        if self.role:
            bits.append(f"({self.role})")
        line = " ".join(bits)
        extra = []
        if self.traits:
            extra.append("traits: " + ", ".join(self.traits))
        if self.appearance:
            extra.append("looks: " + self.appearance)
        if self.voice:
            extra.append("voice: " + self.voice)
        if self.arc:
            extra.append("arc: " + self.arc)
        if extra:
            line += "\n    " + "\n    ".join(extra)
        return line

    def dynamic_card(self) -> str:
        """Only the mutable state (status / knowledge / relationships). Empty
        string when nothing has changed from the planned baseline."""
        extra = []
        if self.status != "active":
            extra.append("status: " + self.status)
        if self.knowledge:
            extra.append("knows: " + "; ".join(self.knowledge))
        if self.relationships:
            extra.append("rel: " + ", ".join(f"{k}: {v}" for k, v in self.relationships.items()))
        if not extra:
            return ""
        return f"[{self.id}] {self.name}: " + "; ".join(extra)

    def card(self) -> str:
        bits = [f"[{self.id}] {self.name}"]
        if self.role:
            bits.append(f"({self.role})")
        line = " ".join(bits)
        extra = []
        if self.traits:
            extra.append("traits: " + ", ".join(self.traits))
        if self.appearance:
            extra.append("looks: " + self.appearance)
        if self.voice:
            extra.append("voice: " + self.voice)
        if self.arc:
            extra.append("arc: " + self.arc)
        if self.status != "active":
            extra.append("status: " + self.status)
        if self.knowledge:
            extra.append("knows: " + "; ".join(self.knowledge))
        if self.relationships:
            rel = ", ".join(f"{k}: {v}" for k, v in self.relationships.items())
            extra.append("rel: " + rel)
        if extra:
            line += "\n    " + "\n    ".join(extra)
        return line

    def to_dict(self):
        return _clean(asdict(self))

    @classmethod
    def from_dict(cls, d):
        return _coerce(cls, d)


@dataclass
class Location:
    id: str
    name: str
    description: str = ""
    first_chapter: Optional[int] = None

    def card(self) -> str:
        s = f"[{self.id}] {self.name}"
        if self.description:
            s += f" — {self.description}"
        return s

    def to_dict(self):
        return _clean(asdict(self))

    @classmethod
    def from_dict(cls, d):
        return _coerce(cls, d)


@dataclass
class Item:
    id: str
    name: str
    description: str = ""
    significance: str = ""
    first_chapter: Optional[int] = None

    def card(self) -> str:
        s = f"[{self.id}] {self.name}"
        if self.description:
            s += f" — {self.description}"
        if self.significance:
            s += f" (significance: {self.significance})"
        return s

    def to_dict(self):
        return _clean(asdict(self))

    @classmethod
    def from_dict(cls, d):
        return _coerce(cls, d)


@dataclass
class PlotThread:
    id: str
    name: str
    description: str = ""
    status: str = "open"                 # open / resolved
    opened_chapter: Optional[int] = None
    resolved_chapter: Optional[int] = None

    def card(self) -> str:
        s = f"[{self.id}] {self.name} ({self.status})"
        if self.description:
            s += f" — {self.description}"
        return s

    def to_dict(self):
        return _clean(asdict(self))

    @classmethod
    def from_dict(cls, d):
        return _coerce(cls, d)


@dataclass
class TimelineEvent:
    chapter: int
    summary: str
    time_marker: str = ""                # "next morning", "three years later", ...

    def to_dict(self):
        return _clean(asdict(self))

    @classmethod
    def from_dict(cls, d):
        return _coerce(cls, d)


# ---------------------------------------------------------------------------
# Chapter plan (from the outline) and chapter record (after writing)
# ---------------------------------------------------------------------------


@dataclass
class ChapterPlan:
    number: int
    title: str
    act: int = 1
    purpose: str = ""                    # what this chapter accomplishes for the arc
    pov_character: str = ""              # character id
    location_ids: List[str] = field(default_factory=list)
    character_ids: List[str] = field(default_factory=list)
    beats: List[str] = field(default_factory=list)       # ordered scene beats
    tension: str = ""                    # the chapter's central tension/conflict
    forward_hook: str = ""               # the question/pull into the next chapter
    word_target: int = 2000

    def brief(self) -> str:
        lines = [f"CHAPTER {self.number}: {self.title}  (Act {self.act}, ~{self.word_target} words)"]
        if self.purpose:
            lines.append(f"Purpose: {self.purpose}")
        if self.pov_character:
            lines.append(f"POV: {self.pov_character}")
        if self.tension:
            lines.append(f"Central tension: {self.tension}")
        if self.beats:
            lines.append("Beats:")
            lines.extend(f"  {i + 1}. {b}" for i, b in enumerate(self.beats))
        if self.forward_hook:
            lines.append(f"End by setting up: {self.forward_hook}")
        return "\n".join(lines)

    def to_dict(self):
        return _clean(asdict(self))

    @classmethod
    def from_dict(cls, d):
        return _coerce(cls, d)


@dataclass
class ChapterRecord:
    number: int
    title: str
    text: str
    word_count: int = 0
    synopsis_line: str = ""              # 1-2 sentence compression for the rolling synopsis
    fingerprint: str = ""                # content hash for incremental invalidation

    def compute_fingerprint(self) -> str:
        h = hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]
        self.fingerprint = h
        return h

    def to_dict(self):
        return _clean(asdict(self))

    @classmethod
    def from_dict(cls, d):
        return _coerce(cls, d)


# ---------------------------------------------------------------------------
# Book bible — the stable, cacheable spine of the whole book
# ---------------------------------------------------------------------------


@dataclass
class Bible:
    title: str = ""
    premise: str = ""
    format: str = "novel"
    genre: str = ""
    tone: str = ""
    audience: str = ""
    themes: List[str] = field(default_factory=list)
    pov: str = "third-person limited"
    tense: str = "past"
    style_guide: str = ""                # voice, prose rules, do/don't
    logline: str = ""
    target_chapters: int = 12
    act_structure: str = ""              # one paragraph: where acts turn

    characters: List[Character] = field(default_factory=list)
    locations: List[Location] = field(default_factory=list)
    items: List[Item] = field(default_factory=list)
    threads: List[PlotThread] = field(default_factory=list)
    outline: List[ChapterPlan] = field(default_factory=list)

    # ---- lookups -------------------------------------------------------
    def character(self, cid: str) -> Optional[Character]:
        return next((c for c in self.characters if c.id == cid), None)

    def location(self, lid: str) -> Optional[Location]:
        return next((l for l in self.locations if l.id == lid), None)

    def plan(self, number: int) -> Optional[ChapterPlan]:
        return next((p for p in self.outline if p.number == number), None)

    # ---- serialization -------------------------------------------------
    def to_dict(self):
        d = _clean({
            "title": self.title,
            "premise": self.premise,
            "format": self.format,
            "genre": self.genre,
            "tone": self.tone,
            "audience": self.audience,
            "themes": self.themes,
            "pov": self.pov,
            "tense": self.tense,
            "style_guide": self.style_guide,
            "logline": self.logline,
            "target_chapters": self.target_chapters,
            "act_structure": self.act_structure,
        })
        d["characters"] = [c.to_dict() for c in self.characters]
        d["locations"] = [l.to_dict() for l in self.locations]
        d["items"] = [i.to_dict() for i in self.items]
        d["threads"] = [t.to_dict() for t in self.threads]
        d["outline"] = [p.to_dict() for p in self.outline]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Bible":
        return cls(
            title=d.get("title", ""),
            premise=d.get("premise", ""),
            format=d.get("format", "novel") or "novel",
            genre=d.get("genre", ""),
            tone=d.get("tone", ""),
            audience=d.get("audience", ""),
            themes=d.get("themes", []),
            pov=d.get("pov", "third-person limited"),
            tense=d.get("tense", "past"),
            style_guide=d.get("style_guide", ""),
            logline=d.get("logline", ""),
            target_chapters=d.get("target_chapters", 12),
            act_structure=d.get("act_structure", ""),
            characters=_load_list(Character, d.get("characters")),
            locations=_load_list(Location, d.get("locations")),
            items=_load_list(Item, d.get("items")),
            threads=_load_list(PlotThread, d.get("threads")),
            outline=_load_list(ChapterPlan, d.get("outline")),
        )
