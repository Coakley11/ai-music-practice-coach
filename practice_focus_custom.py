"""Practice Focus adapters for Custom tools and advisory Creative text.

Consumes central ``practice_focus_policy`` / ``practice_focus_coaching``.
Does not own Custom progression state, Creative arrangement documents,
Backing, Mission, or Motif ownership.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from practice_focus_coaching import practice_page_focus_lines, practice_page_watch_for
from practice_focus_policy import (
    CATEGORY_ARTICULATION,
    CATEGORY_HARMONY,
    CATEGORY_MELODY,
    CATEGORY_PHRASING,
    CATEGORY_RHYTHM_GROOVE,
    CATEGORY_TIMING,
    CATEGORY_TONE,
    canonical_instrument_label,
    category_for_focus,
    resolve_focus_profile,
)

# Explicit user asks that should not be replaced by Focus drills.
_EXPLICIT_INTENT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bchord[- ]?tones?\b", re.I), "chord_tones"),
    (re.compile(r"\bguide[- ]?tones?\b", re.I), "guide_tones"),
    (re.compile(r"\bvoice[- ]?lead", re.I), "voice_leading"),
    (re.compile(r"\barpegg", re.I), "arpeggio"),
    (re.compile(r"\bscale\b", re.I), "scale"),
    (re.compile(r"\blong[- ]?tones?\b", re.I), "long_tones"),
    (re.compile(r"\btongu", re.I), "articulation"),
    (re.compile(r"\bmetronome\b", re.I), "timing"),
    (re.compile(r"\bstrum", re.I), "strumming"),
)


def detect_explicit_custom_intent(user_request: str) -> str:
    """Return a coarse intent key when the user named a specific exercise type."""
    text = str(user_request or "").strip()
    if not text:
        return ""
    for pattern, key in _EXPLICIT_INTENT_PATTERNS:
        if pattern.search(text):
            return key
    return ""


def progression_path_label(chords: Sequence[str] | None, *, limit: int = 8) -> str:
    items = [str(c).strip() for c in (chords or []) if str(c).strip()]
    if not items:
        return "your progression"
    path = " · ".join(items[:limit])
    if len(items) > limit:
        path += " · …"
    return path


def custom_focus_exercise_blocks(
    instrument: str,
    focus: str,
    *,
    chords: Sequence[str] | None = None,
    user_request: str = "",
    groove_style: str = "",
) -> dict[str, Any]:
    """Focus-shaped Custom exercise material for the same progression.

    Explicit ``user_request`` takes precedence for the primary task; Focus may
    only add a secondary compatibility hint (bias, not prison).
    """
    profile = resolve_focus_profile(instrument, focus)
    path = progression_path_label(chords)
    first = ""
    second = ""
    items = [str(c).strip() for c in (chords or []) if str(c).strip()]
    if items:
        first = items[0]
        second = items[1] if len(items) > 1 else items[0]

    intent = detect_explicit_custom_intent(user_request)
    primary_lines: list[str] = []
    secondary_hint = ""

    if intent and str(user_request or "").strip():
        req = str(user_request).strip().rstrip(".")
        primary_lines.append(
            f"**Primary task (your request):** {req} over **{path}**."
        )
        if intent == "chord_tones":
            primary_lines.append(
                f"Spell chord tones through **{path}**; land a chord tone on beat 1 of each change."
            )
        elif intent == "guide_tones":
            primary_lines.append(
                f"Connect 3rds/7ths through **{path}** with the smallest motion."
            )
        elif intent == "voice_leading":
            primary_lines.append(
                f"Voice-lead nearest tones through **{first} → {second}** and onward."
            )
        elif intent == "arpeggio":
            primary_lines.append(f"Arpeggiate each chord in **{path}** ascending, then descending.")
        elif intent == "scale":
            primary_lines.append(f"Apply the requested scale material through **{path}**.")
        elif intent == "long_tones":
            primary_lines.append(f"Sustain chord tones from **{path}** with even sound.")
        elif intent == "articulation":
            primary_lines.append(f"Use the requested articulation pattern through **{path}**.")
        elif intent == "timing":
            primary_lines.append(f"Keep the requested timing goal while looping **{path}**.")
        elif intent == "strumming":
            primary_lines.append(f"Apply the requested strumming idea through **{path}**.")
        # Focus may add a light secondary note without replacing the ask.
        if profile.category == CATEGORY_RHYTHM_GROOVE and intent in {
            "chord_tones",
            "guide_tones",
            "voice_leading",
            "arpeggio",
            "scale",
        }:
            secondary_hint = (
                f"Optional Focus note (**{profile.label}**): keep the right hand "
                "moving in a steady grid while you target the tones."
            )
        elif profile.category == CATEGORY_TONE and intent not in {"long_tones"}:
            secondary_hint = (
                f"Optional Focus note (**{profile.label}**): keep sound centered "
                "while you run the requested exercise."
            )
    else:
        focus_lines = practice_page_focus_lines(
            instrument,
            focus,
            first_chord=first,
            second_chord=second,
            chord_path=path,
            section_name="custom progression",
        )
        primary_lines.extend(focus_lines)
        # Category-specific structure so output differs beyond intro text.
        cat = profile.category
        if cat == CATEGORY_RHYTHM_GROOVE:
            primary_lines.extend(
                [
                    f"Isolate one strumming/groove pattern on **{first or 'one chord'}** for 1 minute.",
                    f"Keep continuous hand motion through **{path}** — change chords without stopping the pattern.",
                    "Add accents (e.g. beats 2 and 4) only after the grid stays even.",
                ]
            )
        elif cat == CATEGORY_TIMING:
            primary_lines.extend(
                [
                    f"Metronome first: place every change of **{path}** on beat 1.",
                    "Speak or tap the subdivision, then play; listen for rushing into chord changes.",
                    "Tempo ladder: lock placement, then raise tempo only after clean reps.",
                ]
            )
        elif cat == CATEGORY_HARMONY:
            primary_lines.extend(
                [
                    f"Spell chord tones for each harmony in **{path}**.",
                    f"Guide-tone line (3rds/7ths) through **{first} → {second}** with nearest motion.",
                    "Name the function of the hardest change before improvising.",
                ]
            )
        elif cat == CATEGORY_TONE:
            primary_lines.extend(
                [
                    f"Long tones on chord tones from **{path}** — stable center, even air/bow/pick.",
                    "Match register quality high and low before adding speed.",
                    "One dynamic swell per sustained tone; keep attack/release consistent.",
                ]
            )
        elif cat == CATEGORY_ARTICULATION:
            primary_lines.extend(
                [
                    f"Repeated-note tonguing/picking on one pitch, then apply through **{path}**.",
                    "Alternate slurred vs separated versions of the same 2-bar cell.",
                    "Clean entrances on every chord change — tone must not thin.",
                ]
            )
        elif cat == CATEGORY_PHRASING:
            primary_lines.extend(
                [
                    f"Play 2 bars / rest 2 bars over **{path}**.",
                    "Question-and-answer: short idea, then a varied reply that resolves.",
                    "Leave audible space; shape contour toward a clear ending.",
                ]
            )
        elif cat == CATEGORY_MELODY:
            primary_lines.extend(
                [
                    f"Build a contour that peaks once and resolves into **{second or path}**.",
                    "Target chord tones on strong beats; use passing tones between them.",
                    "Sequence a 2-bar motif through the next chords.",
                ]
            )
        if groove_style and groove_style not in {"", "Auto"}:
            primary_lines.append(f"Match the **{groove_style}** feel only after the Focus goal stays clean.")

    # Deduplicate while preserving order
    seen: set[str] = set()
    drills: list[str] = []
    for line in primary_lines:
        text = str(line).strip()
        if text and text not in seen:
            seen.add(text)
            drills.append(text)

    listen = practice_page_watch_for(instrument, focus)
    return {
        "focus": profile.label,
        "category": profile.category,
        "instrument": canonical_instrument_label(instrument) or str(instrument or ""),
        "progression": path,
        "explicit_intent": intent,
        "drills": drills[:8],
        "listen_for": listen[:3],
        "secondary_hint": secondary_hint,
        "user_request": str(user_request or "").strip(),
    }


def format_custom_focus_markdown(payload: dict[str, Any]) -> str:
    """Markdown body for the Focus-driven Custom exercise section."""
    lines = [
        f"## Practice Focus drills — **{payload.get('focus') or 'General'}**",
        f"**Instrument:** {payload.get('instrument') or '—'}  ",
        f"**Progression:** {payload.get('progression') or '—'}  ",
        "",
    ]
    if payload.get("explicit_intent"):
        lines.append(
            "_Your explicit request owns the primary task; Practice Focus is secondary._"
        )
        lines.append("")
    for drill in payload.get("drills") or []:
        lines.append(f"- {drill}")
    if payload.get("secondary_hint"):
        lines.append(f"- {payload['secondary_hint']}")
    listen = payload.get("listen_for") or []
    if listen:
        lines.append("")
        lines.append("**Listen for:** " + "; ".join(str(x) for x in listen))
    return "\n".join(lines)


def arrangement_focus_recommendations(instrument: str, focus: str) -> list[str]:
    """Advisory Arrangement Assistant bullets. Never mutates arrangement state."""
    profile = resolve_focus_profile(instrument, focus)
    cat = profile.category
    inst = canonical_instrument_label(instrument) or (instrument or "your instrument")
    if cat == CATEGORY_HARMONY:
        return [
            f"**{profile.label}:** clarify chord function with voicing choice — thin vs dense by section role.",
            "Prefer guide-tone clarity (3rds/7ths) in the inner parts before adding extensions.",
            "Watch register conflicts that muddy harmonic motion between parts.",
        ]
    if cat == CATEGORY_MELODY:
        return [
            f"**{profile.label}:** keep one clear melodic foreground; demote competing lines.",
            "Use doubling or a quiet countermelody only where it supports the hook.",
            f"Separate registers so the **{inst}** melody stays readable.",
        ]
    if cat in {CATEGORY_TIMING, CATEGORY_RHYTHM_GROOVE}:
        return [
            f"**{profile.label}:** manage rhythmic density — leave space between overlapping attacks.",
            "Align groove accents with section energy; avoid constant syncopation in every part.",
            "Thin rhythmic activity in verses if the chorus needs lift.",
        ]
    if cat == CATEGORY_PHRASING:
        return [
            f"**{profile.label}:** stagger entrances/exits for call-and-response.",
            "Avoid phrase-overlap clutter; leave breath/space between answering parts.",
            "Shape a clear musical arc across the form (enter small, peak, thin out).",
        ]
    if cat == CATEGORY_TONE:
        return [
            f"**{profile.label}:** choose registers that keep tone clear for **{inst}**.",
            "Reduce density that obscures sustained tone or soft dynamics.",
            "Give the main tone color room — fewer competing midrange parts.",
        ]
    if cat == CATEGORY_ARTICULATION:
        return [
            f"**{profile.label}:** align attack language across parts (legato bed vs marked hits).",
            "Avoid stacking conflicting articulations on the same beat.",
        ]
    # Generic useful arrangement coaching without inventing Focus-specific claims.
    tips = [str(s).strip() for s in profile.practice_suggestions[:2] if str(s).strip()]
    if tips:
        return [f"**{profile.label}:** {tips[0]}"] + [
            "Bias arrangement choices toward today's Practice Focus without rewriting the form."
        ]
    return [
        f"**{profile.label}:** bias density, register, and space toward this Focus — "
        "do not rewrite harmony unless you choose to."
    ]


def custom_signature(
    instrument: str,
    focus: str,
    *,
    progression: str = "",
    user_request: str = "",
    groove_style: str = "",
) -> str:
    return "|".join(
        [
            str(instrument or "").strip(),
            str(focus or "").strip(),
            str(progression or "").strip(),
            str(user_request or "").strip(),
            str(groove_style or "").strip(),
        ]
    )
