"""AI Lyric Generation Engine for Composition Studio (Slice 3).

Generates lyrics using AI based on musical context extracted from the
composition document.  Returns structured suggestions — never overwrites
existing user lyrics.

Public API
----------
extract_musical_context(doc, section_id)  -> MusicalContext
build_lyric_prompt(context, request)      -> list[dict]  (chat messages)
generate_section_lyrics(doc, section_id, request, *, api_key) -> LyricGenerationResult
parse_ai_lyric_response(raw_text, section_id, section_label, melody_informed) -> list[LyricSuggestion]
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MusicalContext:
    """Musical context extracted from a composition document for one section."""

    key: str
    bpm: int
    time_signature: str
    style: str
    mood: str
    description: str
    section_label: str
    section_label_variant: str
    section_role: str
    chords: list[str]
    melody_pitches: list[str]
    melody_rhythm_summary: str
    has_melody: bool
    existing_lyrics: str
    has_existing_lyrics: bool
    lyric_intent: dict[str, str]
    song_themes: list[str]
    total_sections: int
    section_index: int


@dataclass(frozen=True)
class LyricSuggestion:
    """A single AI-generated lyric suggestion — never overwrites existing lyrics."""

    lines: list[str]
    raw_text: str
    section_id: str
    section_label: str
    rationale: str
    melody_informed: bool
    confidence: str  # high | medium | low


@dataclass(frozen=True)
class LyricGenerationResult:
    """Outcome of a generation request."""

    ok: bool
    suggestions: list[LyricSuggestion]
    error: str = ""
    musical_context_summary: str = ""
    generation_mode: str = "full_section"


@dataclass
class LyricGenerationRequest:
    """User-facing generation parameters."""

    section_id: str
    keywords: list[str] = field(default_factory=list)
    theme: str = ""
    mood: str = ""
    style: str = ""
    instructions: str = ""
    num_suggestions: int = 2
    max_lines: int = 8
    generation_mode: str = "full_section"  # full_section | single_line | refine


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_GENERATION_MODES = ("full_section", "single_line", "refine")

_MAX_PROMPT_CHARS = 6000
_MAX_RESPONSE_LINES = 16
_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_TEMPERATURE = 0.7
_DEFAULT_MAX_TOKENS = 800

_SECTION_ROLE_GUIDANCE: dict[str, str] = {
    "story": "This is a narrative verse — paint a scene or advance the story.",
    "question": "This section poses a question — leave the listener wondering.",
    "tension": "Build tension here — something unresolved that drives toward the chorus.",
    "release": "Resolve the tension — deliver an emotional payoff or answer.",
    "message": "This is the chorus hook — deliver the central message the listener remembers.",
}


# ---------------------------------------------------------------------------
# Context extraction
# ---------------------------------------------------------------------------

def extract_musical_context(
    doc: dict[str, Any],
    section_id: str,
) -> MusicalContext:
    """Pull musical context from *doc* for the section identified by *section_id*."""
    from composition_document import (
        ordered_sections,
        section_by_id,
        section_melody_events,
    )
    from composition_lyric_suggestions import (
        collect_song_lyric_themes,
        default_role_for_section,
    )
    from custom_progression_lab import expand_entries_to_chords

    sec = section_by_id(doc, section_id)
    if sec is None:
        raise ValueError(f"Section {section_id!r} not found in document")

    g = doc.get("global") or {}
    meta = doc.get("metadata") or {}

    # Chords
    raw_chords = sec.get("chords") or []
    try:
        chords = expand_entries_to_chords(raw_chords)
    except Exception:
        chords = [str(c.get("chord", "")) for c in raw_chords if isinstance(c, dict)]

    # Melody
    events = section_melody_events(sec)
    pitches = [str(e.get("pitch", "")) for e in events if e.get("pitch")]
    rhythm_parts: list[str] = []
    for ev in events[:12]:
        dur = float(ev.get("duration_beats", 1.0))
        if dur >= 4.0:
            rhythm_parts.append("whole")
        elif dur >= 2.0:
            rhythm_parts.append("half")
        elif dur >= 1.0:
            rhythm_parts.append("quarter")
        else:
            rhythm_parts.append("eighth")
    rhythm_summary = ", ".join(rhythm_parts) if rhythm_parts else ""

    # Lyrics
    lyrics_block = sec.get("lyrics") or {}
    existing_lyrics = str(lyrics_block.get("raw_text") or "").strip()
    intent = lyrics_block.get("intent") or {}
    lyric_intent = {
        "communicate": str(intent.get("communicate") or ""),
        "emotion": str(intent.get("emotion") or ""),
        "role": str(intent.get("role") or ""),
        "remember": str(intent.get("remember") or ""),
    }

    # Section position
    sections = ordered_sections(doc)
    section_index = 0
    for i, s in enumerate(sections):
        if str(s.get("id", "")) == section_id:
            section_index = i
            break

    role = lyric_intent["role"] or default_role_for_section(sec)

    return MusicalContext(
        key=str(g.get("original_key_center") or "C"),
        bpm=int(g.get("bpm") or 120),
        time_signature=str(g.get("time_signature") or "4/4"),
        style=str(meta.get("style") or ""),
        mood=str(meta.get("mood") or ""),
        description=str(meta.get("description") or ""),
        section_label=str(sec.get("label") or "Verse"),
        section_label_variant=str(sec.get("label_variant") or sec.get("label") or "Verse"),
        section_role=role,
        chords=chords,
        melody_pitches=pitches,
        melody_rhythm_summary=rhythm_summary,
        has_melody=bool(events),
        existing_lyrics=existing_lyrics,
        has_existing_lyrics=bool(existing_lyrics),
        lyric_intent=lyric_intent,
        song_themes=collect_song_lyric_themes(doc),
        total_sections=len(sections),
        section_index=section_index,
    )


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def _musical_context_block(ctx: MusicalContext) -> str:
    """Format musical context as a concise text block for the AI prompt."""
    parts: list[str] = []
    parts.append(f"Key: {ctx.key}")
    parts.append(f"Tempo: {ctx.bpm} BPM")
    parts.append(f"Time signature: {ctx.time_signature}")
    if ctx.style:
        parts.append(f"Style: {ctx.style}")
    if ctx.mood:
        parts.append(f"Mood: {ctx.mood}")
    if ctx.description:
        parts.append(f"Song idea: {ctx.description[:200]}")
    parts.append(f"Section: {ctx.section_label_variant} ({ctx.section_label})")
    parts.append(f"Section role: {ctx.section_role}")
    if ctx.chords:
        parts.append(f"Chord progression: {' | '.join(ctx.chords)}")
    if ctx.has_melody:
        pitch_preview = " ".join(ctx.melody_pitches[:16])
        parts.append(f"Melody pitches: {pitch_preview}")
        if ctx.melody_rhythm_summary:
            parts.append(f"Melody rhythm: {ctx.melody_rhythm_summary}")
    else:
        parts.append("Melody: not yet composed (write provisional lyrics)")
    if ctx.song_themes:
        parts.append("Themes so far: " + "; ".join(ctx.song_themes[:5]))
    if ctx.has_existing_lyrics:
        parts.append(f"Existing lyrics (DO NOT overwrite — suggest alternatives): {ctx.existing_lyrics[:300]}")
    return "\n".join(parts)


def _system_prompt() -> str:
    return (
        "You are a skilled songwriter assistant. You generate original lyric suggestions "
        "based on musical context (key, tempo, chords, melody, mood, style). "
        "You never reproduce copyrighted lyrics or closely imitate published songs. "
        "You respect the composer's existing work and never overwrite it. If lyrics already exist for a section, "
        "you offer fresh alternatives rather than overwriting. "
        "You return structured JSON and nothing else."
    )


def _user_prompt(
    ctx: MusicalContext,
    request: LyricGenerationRequest,
) -> str:
    """Build the user-role prompt from context and request."""
    parts: list[str] = []

    # Musical context
    parts.append("=== Musical Context ===")
    parts.append(_musical_context_block(ctx))

    # Section role guidance
    role_guide = _SECTION_ROLE_GUIDANCE.get(ctx.section_role, "")
    if role_guide:
        parts.append(f"\nSection guidance: {role_guide}")

    # User creative direction
    direction: list[str] = []
    if request.keywords:
        direction.append(f"Keywords: {', '.join(request.keywords[:10])}")
    if request.theme:
        direction.append(f"Theme: {request.theme[:200]}")
    if request.mood:
        direction.append(f"Desired mood: {request.mood[:100]}")
    if request.style:
        direction.append(f"Lyric style: {request.style[:100]}")
    if request.instructions:
        direction.append(f"Instructions: {request.instructions[:500]}")
    if ctx.lyric_intent.get("communicate"):
        direction.append(f"Composer wants to communicate: {ctx.lyric_intent['communicate'][:200]}")
    if ctx.lyric_intent.get("emotion"):
        direction.append(f"Emotion: {ctx.lyric_intent['emotion']}")
    if ctx.lyric_intent.get("remember"):
        direction.append(f"Key line to remember: {ctx.lyric_intent['remember'][:200]}")

    if direction:
        parts.append("\n=== Creative Direction ===")
        parts.extend(direction)

    # Generation instructions
    mode_label = {
        "full_section": "full section lyrics",
        "single_line": "a single lyric line",
        "refine": "a refined version of the existing lyrics",
    }.get(request.generation_mode, "full section lyrics")

    num = min(max(request.num_suggestions, 1), 4)
    max_lines = min(max(request.max_lines, 1), _MAX_RESPONSE_LINES)

    parts.append(f"\n=== Task ===")
    parts.append(f"Generate {num} suggestion(s) of {mode_label} for the {ctx.section_label_variant}.")
    parts.append(f"Maximum {max_lines} lines per suggestion.")

    if ctx.has_melody:
        parts.append("The melody exists — match syllable stress to strong beats where possible.")
    else:
        parts.append("No melody yet — write provisional lyrics that sing naturally in the given key and tempo.")

    if ctx.has_existing_lyrics:
        parts.append("IMPORTANT: The composer already wrote lyrics for this section. "
                      "Offer fresh alternatives — do NOT repeat or closely paraphrase the existing text.")

    parts.append(
        "\nReturn ONLY valid JSON in this format:\n"
        '{"suggestions": [{"lines": ["line1", "line2", ...], '
        '"rationale": "brief explanation of fit", '
        '"confidence": "high|medium|low"}]}'
    )

    full = "\n".join(parts)
    return full[:_MAX_PROMPT_CHARS]


def build_lyric_prompt(
    ctx: MusicalContext,
    request: LyricGenerationRequest,
) -> list[dict[str, str]]:
    """Assemble chat messages for the AI lyric generation call."""
    return [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": _user_prompt(ctx, request)},
    ]


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _strip_markdown_fence(text: str) -> str:
    """Remove ```json ... ``` wrappers if present."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return text


def parse_ai_lyric_response(
    raw_text: str,
    section_id: str,
    section_label: str,
    melody_informed: bool,
) -> list[LyricSuggestion]:
    """Parse AI response text into validated LyricSuggestion objects."""
    cleaned = _strip_markdown_fence(raw_text)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
        if lines:
            return [LyricSuggestion(
                lines=lines[:_MAX_RESPONSE_LINES],
                raw_text="\n".join(lines[:_MAX_RESPONSE_LINES]),
                section_id=section_id,
                section_label=section_label,
                rationale="Parsed from plain text (non-JSON response)",
                melody_informed=melody_informed,
                confidence="low",
            )]
        return []

    suggestions_raw = data if isinstance(data, list) else data.get("suggestions", [])
    if not isinstance(suggestions_raw, list):
        suggestions_raw = [data] if isinstance(data, dict) else []

    out: list[LyricSuggestion] = []
    for item in suggestions_raw[:4]:
        if not isinstance(item, dict):
            continue
        lines = item.get("lines")
        if isinstance(lines, str):
            lines = [ln.strip() for ln in lines.splitlines() if ln.strip()]
        elif isinstance(lines, list):
            lines = [str(ln).strip() for ln in lines if str(ln).strip()]
        else:
            continue
        if not lines:
            continue
        lines = lines[:_MAX_RESPONSE_LINES]
        rationale = str(item.get("rationale") or "").strip()
        confidence = str(item.get("confidence") or "medium").strip().lower()
        if confidence not in ("high", "medium", "low"):
            confidence = "medium"
        out.append(LyricSuggestion(
            lines=lines,
            raw_text="\n".join(lines),
            section_id=section_id,
            section_label=section_label,
            rationale=rationale[:500],
            melody_informed=melody_informed,
            confidence=confidence,
        ))
    return out


# ---------------------------------------------------------------------------
# AI caller
# ---------------------------------------------------------------------------

def _call_openai(
    api_key: str,
    messages: list[dict[str, str]],
    *,
    model: str = _DEFAULT_MODEL,
    temperature: float = _DEFAULT_TEMPERATURE,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> str:
    """Call OpenAI chat completion and return the assistant's text."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key.strip())
    resp = client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return (resp.choices[0].message.content or "").strip()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_section_lyrics(
    doc: dict[str, Any],
    section_id: str,
    request: LyricGenerationRequest,
    *,
    api_key: str = "",
) -> LyricGenerationResult:
    """Generate AI lyric suggestions for a section.

    Returns a ``LyricGenerationResult`` with suggestions — never modifies *doc*.
    The caller decides whether to apply any suggestion.
    """
    if request.generation_mode not in SUPPORTED_GENERATION_MODES:
        return LyricGenerationResult(
            ok=False,
            suggestions=[],
            error=f"Unsupported generation mode: {request.generation_mode!r}",
            generation_mode=request.generation_mode,
        )

    # Extract context
    try:
        ctx = extract_musical_context(doc, section_id)
    except ValueError as exc:
        return LyricGenerationResult(
            ok=False,
            suggestions=[],
            error=str(exc),
            generation_mode=request.generation_mode,
        )

    context_summary = _musical_context_block(ctx)

    # Resolve API key
    if not api_key:
        try:
            from openai_secrets_config import resolve_openai_api_key
            api_key, _probe = resolve_openai_api_key()
        except Exception:
            pass

    if not api_key or not api_key.strip():
        return LyricGenerationResult(
            ok=False,
            suggestions=[],
            error="No OpenAI API key configured",
            musical_context_summary=context_summary,
            generation_mode=request.generation_mode,
        )

    # Build prompt and call AI
    messages = build_lyric_prompt(ctx, request)

    try:
        raw_response = _call_openai(api_key, messages)
    except Exception as exc:
        return LyricGenerationResult(
            ok=False,
            suggestions=[],
            error=f"AI call failed: {exc}",
            musical_context_summary=context_summary,
            generation_mode=request.generation_mode,
        )

    # Parse response
    suggestions = parse_ai_lyric_response(
        raw_response,
        section_id=section_id,
        section_label=ctx.section_label_variant,
        melody_informed=ctx.has_melody,
    )

    if not suggestions:
        return LyricGenerationResult(
            ok=False,
            suggestions=[],
            error="AI returned no usable lyric suggestions",
            musical_context_summary=context_summary,
            generation_mode=request.generation_mode,
        )

    return LyricGenerationResult(
        ok=True,
        suggestions=suggestions,
        musical_context_summary=context_summary,
        generation_mode=request.generation_mode,
    )
