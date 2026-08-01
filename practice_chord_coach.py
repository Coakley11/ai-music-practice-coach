"""Practice Chord Coach — canonical coaching pipeline for the Practice page.

Uses the same theory services as Live Coach, Harmony Map, and Missions:
``coaching_reference_key``, ``chord_coach_insight``, ``format_scale_line``,
``analyze_chord_for_harmony_map``, and ``chord_tone_names``.
"""

from __future__ import annotations

import re

from improvisation_harmony import analyze_chord_for_harmony_map
from improvisation_intelligence import (
    ImprovSessionContext,
    chord_coach_insight,
    coaching_reference_key,
    format_scale_line,
)
from music_theory import is_no_chord_token, normalize_chord_for_theory


def practice_reference_key(*, display_key: str, concert_key: str = "") -> str:
    return coaching_reference_key(
        key_center=str(concert_key or display_key or "C"),
        display_key=str(display_key or "C"),
    )


def _is_progression_token(chord: str) -> bool:
    text = str(chord or "")
    if text in ("ii–V–I", "ii-V-I"):
        return True
    if re.search(r"ii\s*[–-]\s*V\s*[–-]\s*I", text, re.I):
        return True
    if "–" in text or "->" in text:
        parts = re.split(r"[–\-]|->", text.replace("->", "–"))
        return len([p for p in parts if p.strip()]) >= 2
    return False


def practice_chord_coach_insight(
    chord: str,
    *,
    display_key: str,
    concert_key: str = "",
    instrument: str = "Guitar",
    level: str = "Intermediate",
    next_chord: str = "",
) -> "ChordCoachInsight | None":
    if is_no_chord_token(chord) or _is_progression_token(chord):
        return None
    symbol = normalize_chord_for_theory(str(chord).split()[0]) or str(chord).strip()
    ref = practice_reference_key(display_key=display_key, concert_key=concert_key)
    return chord_coach_insight(
        symbol,
        key_center=ref,
        next_chord=next_chord,
        instrument=instrument,
        level=level,
    )


def practice_scale_coach_markdown(
    chord: str,
    display_key: str,
    level: str,
    instrument: str,
    *,
    concert_key: str = "",
) -> str:
    """Markdown scale section aligned with Live Coach scale lines."""
    if is_no_chord_token(chord):
        return (
            "**N.C.** — *No chord / tacet.* Harmony instruments lay out; "
            "lock into the **groove and dynamics** instead."
        )
    if _is_progression_token(chord):
        from practice_studio import progression_coach_markdown

        return progression_coach_markdown(str(chord), display_key, level, instrument)

    insight = practice_chord_coach_insight(
        chord,
        display_key=display_key,
        concert_key=concert_key,
        instrument=instrument,
        level=level,
    )
    if insight is None:
        return ""

    lines = [f"**Suggested scales** ({normalize_chord_for_theory(chord) or chord})"]
    for sug in insight.scale_suggestions or []:
        lines.append(format_scale_line(sug, insight.chord_tones))
    if insight.target_notes:
        lines.append(
            "**Target notes:** " + ", ".join(insight.target_notes)
        )
    if insight.avoid_notes:
        lines.append("**Avoid:** " + "; ".join(insight.avoid_notes))
    return "\n\n".join(lines)


def practice_harmony_tone_markdown(
    chord: str,
    *,
    display_key: str,
    instrument: str,
    level: str,
    song_title: str = "your song",
) -> str:
    """Stable / color tones — same engine as Harmony Map."""
    if is_no_chord_token(chord) or _is_progression_token(chord):
        return ""
    ctx = ImprovSessionContext(
        song_title=song_title,
        artist="",
        key_center=display_key,
        display_key=display_key,
        instrument=instrument,
        level=level,
        focus="Harmony",
        sections={"Practice": [chord]},
    )
    guide = analyze_chord_for_harmony_map(chord, improv_ctx=ctx, section="Practice")
    parts = [
        f"**Stable chord tones:** {', '.join(guide.stable_tones)}",
    ]
    if guide.color_tones:
        colors = [
            f"**{c.note}** ({c.role}) — {c.effect}" for c in guide.color_tones[:4]
        ]
        parts.append("**Color tones:** " + " · ".join(colors))
    if guide.avoid_notes and level != "Beginner":
        av = [f"**{a.note}** — {a.reason}" for a in guide.avoid_notes[:2]]
        parts.append("**Use carefully:** " + " · ".join(av))
    return "\n\n".join(parts)


def practice_coach_body_markdown(
    chord: str,
    instrument: str,
    level: str,
    *,
    display_key: str,
    concert_key: str = "",
    function_summary: str = "",
    playing_advice: str = "",
    next_chord: str = "",
) -> str:
    """Main Chord Coach card: function + play advice + canonical theory block."""
    if is_no_chord_token(chord):
        return practice_scale_coach_markdown(chord, display_key, level, instrument)

    insight = practice_chord_coach_insight(
        chord,
        display_key=display_key,
        concert_key=concert_key,
        instrument=instrument,
        level=level,
        next_chord=next_chord,
    )
    head = normalize_chord_for_theory(str(chord).split()[0]) or str(chord)
    blocks = [f"**{head}**"]
    if function_summary:
        blocks.extend(["", function_summary])
    if playing_advice:
        blocks.extend(["", f"**How to play / target it on {instrument}:**", playing_advice])
    if insight:
        blocks.extend(
            [
                "",
                "**Chord tones**",
                "`" + " · ".join(insight.chord_tones) + "`",
            ]
        )
        if insight.tensions:
            blocks.append("**Tensions / extensions:** " + "; ".join(insight.tensions))
        if insight.instrument_tips:
            blocks.append("**Coach tips:**")
            blocks.extend(f"- {t}" for t in insight.instrument_tips[:4])
        if insight.motif_idea:
            blocks.extend(["", insight.motif_idea])
        if insight.resolve_hint:
            blocks.append(insight.resolve_hint)
    return "\n\n".join(blocks)
