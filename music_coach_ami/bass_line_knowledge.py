"""Bass-line phrase normalization and musical bass-line suggestions for active song context."""

from __future__ import annotations

import re
from typing import Any

from music_coach_ami.types import CoachRequest


def is_non_musical_baseline(low: str) -> bool:
    if "baseline" not in low:
        return False
    if any(
        p in low
        for p in (
            "practice time",
            "for comparison",
            "baseline for comparison",
            "as a baseline for",
            "performance baseline",
            "baseline metric",
            "establish a baseline",
            "baseline practice time",
        )
    ):
        return True
    if re.search(r"\bbaseline\b.*\b(practice time|comparison|metrics?|standard|benchmark)\b", low):
        return True
    if re.search(r"\b(use|using)\b.*\bbaseline\b.*\b(comparison|compare)\b", low):
        return True
    return False


def _has_bass_line_concept(low: str) -> bool:
    if re.search(r"\bbass line\b|\bbass-line\b|\bwalking bass\b", low):
        return True
    compact = low.replace(" ", "").replace("-", "")
    if "bassline" in compact:
        return True
    if "baseline" in low and not is_non_musical_baseline(low):
        return True
    return False


def normalize_bass_line_phrases(normalized: str) -> tuple[str, list[str]]:
    """Contextually map baseline/bassline spellings to canonical bass line wording."""
    text = str(normalized or "").strip()
    low = text.lower()
    notes: list[str] = []
    if is_non_musical_baseline(low):
        return text, notes
    if not _has_bass_line_concept(low):
        return text, notes

    music_context = any(
        p in low
        for p in (
            "this song",
            "for this song",
            "this section",
            "these chords",
            "progression",
            " play ",
            "line",
            "notes",
            "groove",
            "walking",
            "root",
            "harmony",
            "accompaniment",
            "to use",
            "should i play",
            "over these",
            "what baseline",
            "give me a baseline",
            "make me a baseline",
            "bassline",
            "bass-line",
            "bass line",
        )
    )
    if "baseline" in low and not music_context:
        return text, notes

    replacements: tuple[tuple[str, str, str], ...] = (
        (r"\bbaseline\b", "bass line", "baseline -> bass line"),
        (r"\bbassline\b", "bass line", "bassline -> bass line"),
        (r"\bbass-line\b", "bass line", "bass-line -> bass line"),
    )
    for pattern, canonical, note in replacements:
        if re.search(pattern, text, flags=re.I):
            new_text = re.sub(pattern, canonical, text, flags=re.I)
            if new_text != text:
                notes.append(note)
                text = new_text
                low = text.lower()
    return text, notes


def is_bass_line_practice_session(normalized: str, low: str) -> bool:
    if not re.search(r"\bbass line\b|\bwalking bass\b", low):
        return False
    from music_coach_ami.entities import parse_duration_minutes

    if parse_duration_minutes(normalized) and any(
        p in low for p in ("session", "practice", "routine", "workout", "minute")
    ):
        return True
    if re.search(r"\bbass line\b.*\b(session|workout|routine)\b", low):
        return True
    if ("session" in low or "workout" in low or "routine" in low) and "bass line" in low:
        return True
    return False


def is_bass_line_content_request(normalized: str, low: str) -> bool:
    if is_non_musical_baseline(low):
        return False
    text, _ = normalize_bass_line_phrases(normalized)
    low = text.lower()
    if not re.search(r"\bbass line\b|\bwalking bass\b", low):
        return False
    if is_bass_line_practice_session(text, low):
        return False
    content_markers = (
        "to use",
        "should i play",
        "what bass line",
        "give me a bass line",
        "make me a bass line",
        "simple bass line",
        "works with",
        "over these chords",
        "for this section",
        "for this song",
        "what line",
        "play here",
        "can you make me",
    )
    if any(marker in low for marker in content_markers):
        return True
    if re.search(r"\bgive me (?:a |an )?bass line\b", low):
        return True
    if re.search(r"\bwhat bass line\b", low):
        return True
    return False


def _clean(text: object) -> str:
    return str(text or "").strip()


def _usable_section(section: str) -> str:
    text = _clean(section)
    low = text.lower()
    if low in {"full song", "full", "all", "song", "entire song"}:
        return ""
    return text


def _parse_progression_chords(progression_summary: str) -> list[str]:
    text = _clean(progression_summary)
    if not text:
        return []
    parts = re.split(r"\s*[|/]\s*|\s*–\s*|\s+-\s+|\s*,\s*", text)
    try:
        from music_theory import normalize_chord_for_theory
    except ImportError:
        return [p.strip() for p in parts if p.strip()][:8]

    chords: list[str] = []
    for part in parts:
        token = normalize_chord_for_theory(part.strip())
        if token and token not in chords:
            chords.append(token)
    return chords[:8]


def _level_label(level: str) -> str:
    low = _clean(level).lower()
    if "advanced" in low:
        return "advanced"
    if "begin" in low:
        return "beginner"
    if "intermediate" in low:
        return "intermediate"
    return "intermediate"


def _spell_root(chord: str, reference_key: str) -> str:
    try:
        from music_theory import chord_root_for_theory, spell_note_in_key

        root = chord_root_for_theory(chord)
        if reference_key:
            return spell_note_in_key(root, reference_key)
        return root
    except ImportError:
        return chord[:1] if chord else "?"


def _chord_line_hint(chord: str, *, reference_key: str, level: str) -> str:
    root = _spell_root(chord, reference_key)
    lvl = _level_label(level)
    if lvl == "beginner":
        return f"**{chord}:** root **{root}** on beat 1 (quarter or half note)."
    if lvl == "advanced":
        return (
            f"**{chord}:** root **{root}** on beat 1; add a chord tone on beat 2; "
            f"use a chromatic or diatonic approach into the next root on beat 4."
        )
    return (
        f"**{chord}:** root **{root}** on beat 1; connect with a nearby chord tone "
        f"(3rd or 5th) before the next change."
    )


def _instrument_playing_guidance(family: str, instrument: str) -> str:
    if family == "bass":
        return f"On **{instrument}**, keep one note per beat at first; land each root cleanly before adding approach notes."
    if family == "keyboard":
        return "In the **left hand**, keep roots on strong beats and connect smoothly into the next bass note."
    if family == "fretted":
        return (
            f"On **{instrument}**, place each root on the **lowest practical string**; "
            "keep the bass pulse steady before adding upper notes."
        )
    return (
        f"On **{instrument}**, outline roots on strong beats first; "
        "keep the line supportive rather than busy."
    )


def compose_bass_line_suggestion(req: CoachRequest) -> dict[str, Any]:
    from music_coach_instrument_voice import instrument_family
    from music_coach_ami.request_resolution import display_coach_instrument

    normalized, phrase_norms = normalize_bass_line_phrases(req.raw_question or req.normalized_question)
    if not phrase_norms:
        _, phrase_norms = normalize_bass_line_phrases(req.normalized_question)
    instrument = display_coach_instrument(req.entities.instrument or req.context.instrument)
    family = instrument_family(instrument)
    level = _clean(req.context.level) or "Intermediate"
    song = _clean(req.context.active_song_title)
    section = _usable_section(req.context.active_section)
    chords = _parse_progression_chords(req.context.progression_summary)
    if not chords and req.context.current_chord:
        chords = _parse_progression_chords(req.context.current_chord)
    reference_key = _clean(req.context.current_practice_key or req.context.song_original_key)

    if section and song:
        target = f"the **{section}** of **{song}**"
    elif song:
        target = f"**{song}**"
    else:
        target = "your active song"

    direct = (
        f"**Try this approach:** a playable bass line for {target}."
        if song
        else "**Try this approach:** a simple bass line you can apply once your active song is set."
    )

    steps: list[str] = []
    steps.append(_instrument_playing_guidance(family, instrument))

    if chords:
        prog_label = " → ".join(f"**{c}**" for c in chords[:4])
        if len(chords) > 4:
            prog_label += " → …"
        steps.append(
            f"**Harmony in context:** {prog_label}"
            + (f" (concert key **{reference_key}**)" if reference_key else "")
            + "."
        )
        lvl = _level_label(level)
        if lvl == "beginner":
            steps.append(
                "**Rhythm:** start with **quarter notes** or **half notes** — one bass note per chord on beat 1."
            )
        elif lvl == "advanced":
            steps.append(
                "**Rhythm:** keep beat 1 anchored; vary beats 2–4 with chord tones, approaches, or short rests."
            )
        else:
            steps.append(
                "**Rhythm:** root on beat 1; use beats 2–3 for a chord tone or simple stepwise connection."
            )
        steps.append("**Line by chord:**")
        for chord in chords[:4]:
            steps.append(f"- {_chord_line_hint(chord, reference_key=reference_key, level=level)}")
        if len(chords) > 4:
            steps.append("- Continue the same root–connection pattern through the rest of the progression.")
    else:
        steps.append(
            "**Note:** I do not have a trustworthy chord chart for this song in the current Coach context, "
            "so this is a safe pattern rather than song-specific notes."
        )
        steps.append(
            "**Pattern:** play each chord root on beat 1, then add one chord tone before moving to the next root."
        )
        steps.append(
            "Open the active song chart or loop **Backing** on one section so you can map roots to the real changes."
        )

    listen = [
        "Bass notes land with the chord changes",
        "Steady pulse — roots on strong beats",
        "Clean movement between roots",
        "The line supports the harmony instead of fighting it",
    ]

    return {
        "direct_answer": direct,
        "practice_steps": steps,
        "what_to_listen_for": listen,
        "suggested_next_action": (
            f"Loop one section of **{song}** in **Backing** and play the line slowly before adding fills."
            if song
            else "Set your active song, then loop one section in **Backing** and apply the pattern."
        ),
        "diagnostics": {
            "bass_line_content": True,
            "normalized_phrases": phrase_norms,
            "chord_context_available": bool(chords),
            "chord_count": len(chords),
            "resolved_instrument": instrument,
            "instrument_family": family,
            "resolved_level": level,
            "progression_summary_used": bool(req.context.progression_summary),
        },
    }
