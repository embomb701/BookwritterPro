"""System prompts and JSON schemas for the structured stages.

Schemas obey the structured-output constraints: every object sets
``additionalProperties: false``; free-form maps (arbitrary keys) are modelled as
arrays of ``{key, value}`` pairs and converted in Python, since strict schemas
can't express open maps.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

PLANNER_SYSTEM = """You are a master story architect. Given a premise, you design a \
complete, internally-consistent story bible and a chapter-by-chapter outline.

Craft requirements:
- A clear three-act spine: a hooking intro that establishes character + stakes fast, \
a rising middle with escalating complications and a real midpoint turn, and a \
satisfying ending that pays off the threads you open.
- Every chapter must have a purpose that moves the arc, a central tension, and a \
forward hook that pulls the reader on. No filler chapters.
- Characters must be distinct in voice and motivation. Give each a one-line arc.
- Open exactly the plot threads you intend to resolve, and resolve every thread \
you open by the final chapters.
- Respect the requested story format. For prose novels, plan for scene-by-scene \
chapters with strong narrative escalation. For comics / graphic novels / manga / \
webtoons, plan visually-driven chapters with drawable beats, page-turn reveals, \
concise dialogue/captions, and action that can be staged panel-by-panel.
- Assign stable lowercase id slugs (e.g. "elara", "the_vault") to every character, \
location, item, and thread; reuse those ids in the outline's character_ids / \
location_ids. This id discipline is what keeps later chapters consistent.

Output ONLY the structured bible."""

_REL_ARRAY = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "with": {"type": "string", "description": "other character id"},
            "relation": {"type": "string"},
        },
        "required": ["with", "relation"],
        "additionalProperties": False,
    },
}

_CHARACTER = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "role": {"type": "string"},
        "traits": {"type": "array", "items": {"type": "string"}},
        "appearance": {"type": "string"},
        "voice": {"type": "string"},
        "arc": {"type": "string"},
        "relationships": _REL_ARRAY,
    },
    "required": ["id", "name", "role", "arc"],
    "additionalProperties": False,
}

_LOCATION = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
    },
    "required": ["id", "name"],
    "additionalProperties": False,
}

_ITEM = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "significance": {"type": "string"},
    },
    "required": ["id", "name"],
    "additionalProperties": False,
}

_THREAD = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
    },
    "required": ["id", "name"],
    "additionalProperties": False,
}

_CHAPTER_PLAN = {
    "type": "object",
    "properties": {
        "number": {"type": "integer"},
        "title": {"type": "string"},
        "act": {"type": "integer", "enum": [1, 2, 3]},
        "purpose": {"type": "string"},
        "pov_character": {"type": "string"},
        "location_ids": {"type": "array", "items": {"type": "string"}},
        "character_ids": {"type": "array", "items": {"type": "string"}},
        "beats": {"type": "array", "items": {"type": "string"}},
        "tension": {"type": "string"},
        "forward_hook": {"type": "string"},
        "word_target": {"type": "integer"},
    },
    "required": ["number", "title", "act", "purpose", "beats"],
    "additionalProperties": False,
}

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "logline": {"type": "string"},
        "premise": {"type": "string"},
        "format": {"type": "string"},
        "genre": {"type": "string"},
        "tone": {"type": "string"},
        "audience": {"type": "string"},
        "themes": {"type": "array", "items": {"type": "string"}},
        "pov": {"type": "string"},
        "tense": {"type": "string"},
        "style_guide": {"type": "string"},
        "act_structure": {"type": "string"},
        "target_chapters": {"type": "integer"},
        "characters": {"type": "array", "items": _CHARACTER},
        "locations": {"type": "array", "items": _LOCATION},
        "items": {"type": "array", "items": _ITEM},
        "threads": {"type": "array", "items": _THREAD},
        "outline": {"type": "array", "items": _CHAPTER_PLAN},
    },
    "required": [
        "title", "logline", "premise", "format", "genre", "tone", "pov", "tense",
        "style_guide", "act_structure", "characters", "threads", "outline",
    ],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

WRITER_SYSTEM = """You are a professional storyteller writing one chapter of a book. You have the full \
story bible (characters, world, style, format, and the complete outline) in context, so \
you always know where the story has been and where it is going.

Rules:
- Write in the bible's POV and tense when they apply. Obey the style guide exactly.
- Honor continuity: a character only knows what the bible says they know; respect \
established appearance, voice, relationships, locations, and timeline.
- Hit the chapter's beats and central tension. Open with momentum (especially \
chapter 1 — hook fast). End on the chapter's forward hook unless it is the final \
chapter, which must land a satisfying resolution.
- Match the previous chapter's voice and pick up cleanly from where it left off.
- For prose formats, write immersive prose only — no author notes, no beat labels, \
no meta-commentary. Do not restate the outline.
- For comic / graphic-novel / manga / webtoon formats, write a clean production-ready \
script: use clear page/scene headings, distinct panel/action beats, and concise \
dialogue/captions with blank lines between panels so the script stays readable in \
the app. Do not include camera jargon unless it materially affects storytelling.
- Never explain the process. Just deliver the story in the requested format."""


# ---------------------------------------------------------------------------
# Extractor (cheap model) — turn freshly written prose into a structured delta
# ---------------------------------------------------------------------------

EXTRACTOR_SYSTEM = """You are a continuity editor. You read one freshly written chapter and emit a \
compact, structured record of what changed in the story state. You do NOT rewrite \
or critique prose. Be terse and factual.

Produce:
- synopsis_line: one or two sentences capturing what happened this chapter (for a \
running synopsis; keep it tight).
- timeline_summary + time_marker: when this chapter sits in story time.
- character_updates: for characters whose status/knowledge/relationships changed, \
note only the deltas. Use existing character ids.
- new_characters / new_locations / new_items: anything introduced this chapter that \
is not already in the bible, with stable lowercase ids.
- threads_opened / threads_resolved: plot threads started or closed this chapter.
- continuity_flags: anything that looks like a contradiction with the established \
bible (wrong eye color, a dead character speaking, a timeline jump). Empty if none."""

_CHAR_UPDATE = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "status": {"type": "string"},
        "knowledge_added": {"type": "array", "items": {"type": "string"}},
        "relationship_updates": _REL_ARRAY,
        "note": {"type": "string"},
    },
    "required": ["id"],
    "additionalProperties": False,
}

_NEW_CHAR = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "role": {"type": "string"},
        "traits": {"type": "array", "items": {"type": "string"}},
        "appearance": {"type": "string"},
        "voice": {"type": "string"},
    },
    "required": ["id", "name"],
    "additionalProperties": False,
}

DELTA_SCHEMA = {
    "type": "object",
    "properties": {
        "synopsis_line": {"type": "string"},
        "timeline_summary": {"type": "string"},
        "time_marker": {"type": "string"},
        "character_updates": {"type": "array", "items": _CHAR_UPDATE},
        "new_characters": {"type": "array", "items": _NEW_CHAR},
        "new_locations": {"type": "array", "items": _LOCATION},
        "new_items": {"type": "array", "items": _ITEM},
        "threads_opened": {"type": "array", "items": _THREAD},
        "threads_resolved": {"type": "array", "items": {"type": "string"}},
        "continuity_flags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["synopsis_line"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Continuity checker (cheap model, optional)
# ---------------------------------------------------------------------------

CHECKER_SYSTEM = """You are a continuity checker. Given the established story state and a chapter, \
list concrete continuity errors only — contradictions with established facts \
(appearance, knowledge, relationships, status, location, timeline) or with the \
chapter's intended beats. Do not give style notes. If there are no real errors, \
return an empty issues array."""

CHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    "description": {"type": "string"},
                },
                "required": ["severity", "description"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["issues"],
    "additionalProperties": False,
}
