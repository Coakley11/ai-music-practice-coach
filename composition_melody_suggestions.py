"""Rule-based melodic concept suggestions for Composition Studio (CS-B3)."""

from __future__ import annotations

from typing import Any

MELODY_FEELINGS: tuple[tuple[str, str], ...] = (
    ("smooth", "Smooth — flowing and connected"),
    ("bold", "Bold — confident leaps and strong peaks"),
    ("lyrical", "Lyrical — singable, speech-like phrases"),
    ("rhythmic", "Rhythmic — groove-driven and syncopated"),
    ("emotional", "Emotional — expressive arcs and dynamic contour"),
    ("energetic", "Energetic — forward motion and lift"),
)

MELODY_STYLES: tuple[tuple[str, str], ...] = (
    ("simple", "Simple & singable — easy to remember after one listen"),
    ("expressive", "More expressive — room for nuance and variation"),
)

DEFAULT_MELODY_FEEL_BY_SECTION: dict[str, str] = {
    "Intro": "smooth",
    "Verse": "lyrical",
    "Pre-Chorus": "energetic",
    "Chorus": "bold",
    "Bridge": "emotional",
    "Solo": "energetic",
    "Interlude": "smooth",
    "Outro": "smooth",
}

_CONCEPT_LIBRARY: dict[str, list[dict[str, Any]]] = {
    "smooth": [
        {
            "id": "smooth_stepwise",
            "name": "Gentle stepwise line",
            "contour": "Move mostly by step within the chord tones — calm and approachable.",
            "motif_hint": "Root → 2nd → 3rd → 2nd → root (small steps, no big jumps)",
            "why": "Stepwise motion feels natural to sing and keeps the focus on your lyrics.",
        },
        {
            "id": "smooth_arc",
            "name": "Soft arch",
            "contour": "Rise through the phrase, then settle back down by step.",
            "motif_hint": "Climb to the 5th on beat 1–2, float down to the 3rd by bar end",
            "why": "A gentle arch creates emotional shape without demanding vocal range.",
        },
    ],
    "bold": [
        {
            "id": "bold_leap_hook",
            "name": "Leap to the hook",
            "contour": "Open with a confident interval jump landing on a strong chord tone.",
            "motif_hint": "Leap from 5th down to root, then jump up to the 3rd on the hook word",
            "why": "Strategic leaps make a chorus feel anthemic and memorable.",
        },
        {
            "id": "bold_peak",
            "name": "High-point arrival",
            "contour": "Build toward one peak note that lands with the harmony change.",
            "motif_hint": "Hold the 3rd, then leap to the 5th (or 6th) when the chord shifts",
            "why": "One clear peak gives listeners something to wait for and remember.",
        },
    ],
    "lyrical": [
        {
            "id": "lyrical_conversation",
            "name": "Conversational phrase",
            "contour": "Short groups of notes that mirror natural speech rhythm.",
            "motif_hint": "Three-note cells: down-up-rest, repeat with small variation each line",
            "why": "Speech-like phrasing helps verses feel like storytelling, not exercise.",
        },
        {
            "id": "lyrical_question",
            "name": "Question & answer",
            "contour": "First phrase rises (question), second phrase resolves (answer).",
            "motif_hint": "Bar 1 ends up on 2nd or 4th; bar 2 steps down to root or 3rd",
            "why": "Call-and-response contour keeps verses engaging across multiple lines.",
        },
    ],
    "rhythmic": [
        {
            "id": "rhythmic_syncopated",
            "name": "Off-beat accent",
            "contour": "Emphasize notes that sit slightly ahead of the beat.",
            "motif_hint": "Repeat a 3-note pattern with the accent on the 'and' of beat 2",
            "why": "Syncopation adds groove without changing your chord progression.",
        },
        {
            "id": "rhythmic_pocket",
            "name": "Groove pocket",
            "contour": "Fewer notes, stronger rhythm — let space do the work.",
            "motif_hint": "Root on 1, rest, 5th on the 'and' of 2, rest, 3rd on 4",
            "why": "A rhythmic pocket feels modern and leaves room for production.",
        },
    ],
    "emotional": [
        {
            "id": "emotional_sigh",
            "name": "Sighing descent",
            "contour": "Start high, descend by step — like an exhale.",
            "motif_hint": "Begin on 5th or 6th, step down through 4th → 3rd → 2nd → root",
            "why": "Descending stepwise lines carry melancholy and intimacy.",
        },
        {
            "id": "emotional_delayed",
            "name": "Delayed resolution",
            "contour": "Hold tension on a non-root tone, then resolve late in the bar.",
            "motif_hint": "Sit on the 2nd or 4th for beats 1–3, resolve to root or 3rd on 4",
            "why": "Delaying resolution creates yearning before the lyric lands.",
        },
    ],
    "energetic": [
        {
            "id": "energy_rise",
            "name": "Forward climb",
            "contour": "Steady upward motion through the phrase.",
            "motif_hint": "Root → 2nd → 3rd → 4th → 5th across the section opening",
            "why": "Rising lines build momentum into a chorus or pre-chorus.",
        },
        {
            "id": "energy_repetition",
            "name": "Motif repetition",
            "contour": "Repeat a short cell with one note changing each time.",
            "motif_hint": "Do-Mi-Sol, Do-Mi-La, Do-Mi-Sol — same rhythm, shifting top note",
            "why": "Repetition with tiny variation is how hooks get stuck in memory.",
        },
    ],
}


def default_melody_feel_for_section(section: dict[str, Any]) -> str:
    label = str(section.get("label") or "Verse")
    return DEFAULT_MELODY_FEEL_BY_SECTION.get(label, "lyrical")


def feel_label(feel_id: str) -> str:
    for fid, label in MELODY_FEELINGS:
        if fid == feel_id:
            return label
    return feel_id


def style_label(style_id: str) -> str:
    for sid, label in MELODY_STYLES:
        if sid == style_id:
            return label
    return style_id


def suggest_melody_concepts(
    doc: dict[str, Any],
    section: dict[str, Any],
    feel: str,
    style: str = "simple",
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    feel = str(feel or default_melody_feel_for_section(section)).strip().lower()
    style = str(style or "simple").strip().lower()
    recipes = list(_CONCEPT_LIBRARY.get(feel) or _CONCEPT_LIBRARY["lyrical"])

    section_label = str(section.get("label") or "")
    if section_label == "Chorus" and feel not in {"bold", "energetic"}:
        recipes = list(_CONCEPT_LIBRARY.get("bold", [])) + recipes
    elif section_label == "Verse" and feel not in {"lyrical", "smooth"}:
        recipes = list(_CONCEPT_LIBRARY.get("lyrical", [])) + recipes

    if style == "simple":
        recipes = sorted(recipes, key=lambda r: "step" in str(r.get("contour", "")).lower(), reverse=True)

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for recipe in recipes:
        rid = str(recipe.get("id") or "")
        if rid in seen:
            continue
        seen.add(rid)
        out.append(
            {
                "id": rid,
                "name": str(recipe.get("name") or "Melodic idea"),
                "contour": str(recipe.get("contour") or ""),
                "motif_hint": str(recipe.get("motif_hint") or ""),
                "why": str(recipe.get("why") or ""),
                "feel": feel,
                "style": style,
            }
        )
        if len(out) >= limit:
            break
    return out


def coach_line_for_melody(
    doc: dict[str, Any],
    section: dict[str, Any],
    *,
    feel: str = "",
    remember: str = "",
) -> str:
    variant = str(section.get("label_variant") or section.get("label") or "this section")
    label = str(section.get("label") or "Section")
    feel_txt = feel_label(feel or default_melody_feel_for_section(section)).split("—")[0].strip().lower()
    remember_bit = (
        f' You said listeners should remember: <em>"{remember[:120]}"</em>.'
        if remember.strip()
        else ""
    )
    jobs = {
        "Intro": "invite the listener in without giving everything away",
        "Verse": "carry the story in a way that feels natural to sing",
        "Pre-Chorus": "build anticipation toward the hook",
        "Chorus": "deliver the line everyone hums after the song ends",
        "Bridge": "offer a fresh melodic angle before the final return",
        "Solo": "express personality over the harmony",
        "Interlude": "create breathing room",
        "Outro": "leave a lasting final image",
    }
    job = jobs.get(label, "give this section its own musical identity")
    return (
        f"For <strong>{variant}</strong>, imagine a <strong>{feel_txt}</strong> melody that will {job}."
        f"{remember_bit}<br><br>"
        f"Hum it first, explore a few concepts, compare approaches — then refine. "
        f"Direct note entry is there when you need it, not before."
    )
