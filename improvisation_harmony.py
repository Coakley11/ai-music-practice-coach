"""Harmony Map — section progressions with stable and color-tone coaching."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from improvisation_intelligence import (
    ImprovSessionContext,
    _chord_quality,
    _chord_root,
    build_scale_suggestion,
    chord_coach_insight,
    format_scale_line,
    instrument_coaching_lines,
)
from improvisation_motif import chord_tone_names
from music_theory import CHROMATIC, normalize_root, split_chord


@dataclass
class ColorToneNote:
    note: str
    role: str
    effect: str
    min_level: str = "Beginner"


@dataclass
class AvoidNote:
    note: str
    reason: str


@dataclass
class HarmonyChordGuide:
    chord: str
    section: str
    stable_tones: list[str]
    color_tones: list[ColorToneNote]
    avoid_notes: list[AvoidNote]
    phrase_idea: str
    instrument_tips: list[str]
    scale_lines: list[str] = field(default_factory=list)
    focus_note: str = ""


def _note_at_semitone(root: str, semitone: int) -> str:
    r = _chord_root(root)
    if r not in CHROMATIC:
        r = "C"
    return CHROMATIC[(CHROMATIC.index(r) + semitone) % 12]


def _stable_tones(chord: str) -> list[str]:
    tones = chord_tone_names(chord)
    qual = _chord_quality(chord)
    if qual in ("major", "minor", "dom") and len(tones) >= 3:
        if qual == "major":
            return tones[:3]
        if qual == "minor":
            return tones[:3]
        return [tones[0], tones[1], tones[3]] if len(tones) >= 4 else tones[:3]
    return tones


def _style_is_ballad(style_label: str, song_title: str) -> bool:
    text = f"{style_label} {song_title}".lower()
    return any(k in text for k in ("ballad", "pop", "soul", "folk", "acoustic", "sheeran", "perfect"))


def _style_is_jazz(style_label: str, song_title: str) -> bool:
    text = f"{style_label} {song_title}".lower()
    return any(k in text for k in ("jazz", "bossa", "swing", "bebop", "blues", "blue bossa"))


def _color_catalog(
    chord: str,
    *,
    level: str,
    style_label: str,
    song_title: str,
) -> tuple[list[ColorToneNote], list[AvoidNote]]:
    root = _chord_root(chord)
    qual = _chord_quality(chord)
    ballad = _style_is_ballad(style_label, song_title)
    jazz = _style_is_jazz(style_label, song_title)
    colors: list[ColorToneNote] = []
    avoids: list[AvoidNote] = []

    if qual in ("major", "maj7"):
        if "maj7" in str(chord).lower() or qual == "maj7":
            colors.extend([
                ColorToneNote(
                    _note_at_semitone(root, 14),
                    "9th",
                    "open, lyrical top — singer-songwriter or jazz-ballad color",
                    "Beginner" if ballad else "Intermediate",
                ),
                ColorToneNote(
                    _note_at_semitone(root, 21),
                    "13th / 6th",
                    "warm extension over maj7 — land on phrase endings",
                    "Intermediate",
                ),
            ])
            if level == "Advanced" or jazz:
                colors.append(
                    ColorToneNote(
                        _note_at_semitone(root, 18),
                        "#11 (lydian)",
                        "dreamy lift — use on sustained chords, not every beat",
                        "Advanced",
                    )
                )
        else:
            colors.extend([
                ColorToneNote(
                    _note_at_semitone(root, 9),
                    "6th / 13th",
                    "warmer, softer, more emotional — great on ballad endings",
                    "Beginner",
                ),
                ColorToneNote(
                    _note_at_semitone(root, 14),
                    "9th",
                    "open, modern pop color — light and bright",
                    "Beginner" if ballad else "Intermediate",
                ),
                ColorToneNote(
                    _note_at_semitone(root, 11),
                    "maj7",
                    "dreamy, smooth — connects toward the next chord in a lift",
                    "Intermediate",
                ),
            ])
            avoids.append(
                AvoidNote(
                    _note_at_semitone(root, 5),
                    "4th / 11th — can clash with the major 3rd unless used as sus4 or a quick passing tone",
                )
            )
    elif qual in ("m7", "minor"):
        colors.extend([
            ColorToneNote(
                _note_at_semitone(root, 14),
                "9th",
                "dorian color — soulful, not too dark",
                "Intermediate",
            ),
            ColorToneNote(
                _note_at_semitone(root, 9),
                "6th / 13th",
                "dorian 6 — hopeful minor color",
                "Intermediate",
            ),
            ColorToneNote(
                _note_at_semitone(root, 17),
                "11th",
                "suspended, open minor — use on longer notes",
                "Advanced",
            ),
        ])
    elif qual == "dom":
        colors.extend([
            ColorToneNote(
                _note_at_semitone(root, 14),
                "9th",
                "classic dominant color — resolves forward",
                "Intermediate",
            ),
            ColorToneNote(
                _note_at_semitone(root, 21),
                "13th",
                "bluesy dominant — strong on beat 4 before resolution",
                "Intermediate",
            ),
        ])
        if level == "Advanced" or jazz:
            colors.extend([
                ColorToneNote(
                    _note_at_semitone(root, 13),
                    "b9",
                    "sharp tension — resolve quickly into the next chord",
                    "Advanced",
                ),
                ColorToneNote(
                    _note_at_semitone(root, 15),
                    "#9",
                    "blues/jazz bite — short accent only",
                    "Advanced",
                ),
            ])
    elif qual == "half-dim":
        colors.append(
            ColorToneNote(
                _note_at_semitone(root, 14),
                "9th",
                "half-diminished line color — approach from below",
                "Advanced",
            )
        )
        avoids.append(
            AvoidNote(
                _note_at_semitone(root, 4),
                "major 3rd — fights the minor-third quality of this chord",
            )
        )

    level_rank = {"Beginner": 0, "Intermediate": 1, "Advanced": 2}
    max_rank = level_rank.get(level, 1)
    filtered = [c for c in colors if level_rank.get(c.min_level, 1) <= max_rank]

    if level == "Beginner":
        filtered = filtered[:1]
    elif level == "Intermediate":
        filtered = filtered[:4]
    else:
        filtered = filtered[:6]

    seen: set[str] = set()
    unique: list[ColorToneNote] = []
    stable = set(_stable_tones(chord))
    for item in filtered:
        if item.note in stable or item.note in seen:
            continue
        seen.add(item.note)
        unique.append(item)
    return unique, avoids


def _phrase_idea(
    chord: str,
    *,
    stable: list[str],
    colors: list[ColorToneNote],
    next_chord: str,
    section: str,
    song_title: str,
    level: str,
    focus: str,
) -> str:
    focus_low = (focus or "").lower()
    color_note = colors[0].note if colors else stable[-1] if stable else _chord_root(chord)
    if "rhythm" in focus_low:
        return (
            f"In **{section}** of **{song_title}**, hit chord tones on beats 1 and 3, "
            f"then place **{color_note}** on the and-of-4 for a lift before the next bar."
        )
    if "scale" in focus_low:
        return (
            f"Over **{chord}**, outline {' · '.join(stable)} on strong beats, "
            f"then use scale passing tones to reach **{color_note}** at the end of a 2-bar phrase."
        )
    if "chord tone" in focus_low or "harmony" in focus_low:
        return (
            f"Stay on **{' · '.join(stable)}** for most of the bar — "
            f"only touch **{color_note}** once per phrase for color."
        )
    landing = ""
    if next_chord:
        landing = f" Aim for a chord tone of **{next_chord}** on beat 1 of the next bar."
    return (
        f"Over **{chord}**, **{' · '.join(stable)}** are safe home tones. "
        f"**{color_note}** adds a softer lift — try it on the last note of a phrase.{landing}"
    )


def _instrument_harmony_tips(
    instrument: str,
    chord: str,
    *,
    stable: list[str],
    colors: list[ColorToneNote],
    level: str,
) -> list[str]:
    qual = _chord_quality(chord)
    root = _chord_root(chord)
    lines = instrument_coaching_lines(instrument, chord, level, qual, root)
    inst = (instrument or "").lower()
    color = colors[0].note if colors else ""
    if "guitar" in inst:
        lines.append(
            f"Grip **{chord}** in one position; chord tones on strings you can reach without shifting."
        )
        if color:
            lines.append(
                f"Add **{color}** on a higher string at the end of a phrase — keep the root in the bass."
            )
        if level != "Beginner":
            lines.append("Optional: arpeggiate root–3rd–5th, then tag the color tone on beat 4.")
    elif "piano" in inst:
        lines.append(f"LH: root + 5th or shell of **{chord}**; RH: {'–'.join(stable[:3])}.")
        if color:
            lines.append(f"RH color: add **{color}** above the triad — don't crowd both hands.")
    elif any(x in inst for x in ("sax", "trumpet", "flute", "clarinet")):
        lines.append(f"Land **{stable[0]}** or **{stable[1]}** on downbeats; breathe before the next bar.")
        if color:
            lines.append(f"Use **{color}** as a pick-up into the next chord — tongue lighter, longer air.")
    return lines[:5]


def analyze_chord_for_harmony_map(
    chord: str,
    *,
    improv_ctx: ImprovSessionContext,
    section: str = "",
    next_chord: str = "",
    prev_chord: str = "",
) -> HarmonyChordGuide:
    level = improv_ctx.level or "Intermediate"
    focus = improv_ctx.focus or "Improvisation"
    stable = _stable_tones(chord)
    colors, avoids = _color_catalog(
        chord,
        level=level,
        style_label=improv_ctx.style_label,
        song_title=improv_ctx.song_title,
    )

    insight = chord_coach_insight(
        chord,
        key_center=improv_ctx.display_key,
        next_chord=next_chord,
        instrument=improv_ctx.instrument,
        level=level,
    )

    scale_lines: list[str] = []
    focus_low = focus.lower()
    if "scale" in focus_low or level != "Beginner":
        suggestions = insight.scale_suggestions or [
            build_scale_suggestion(label) for label in insight.scales
        ]
        max_scales = 2 if level == "Beginner" else 4
        scale_lines = [
            format_scale_line(s, stable) for s in suggestions[:max_scales]
        ]

    focus_note = ""
    if "rhythm" in focus_low:
        focus_note = "Rhythm focus: keep the note set small — let placement and rests create interest."
    elif "scale" in focus_low:
        focus_note = "Scale focus: chord tones on strong beats; scale tones between changes."
    elif "chord tone" in focus_low or "harmony" in focus_low:
        focus_note = "Chord-tone focus: prioritize stable tones; color tones are brief accents."

    return HarmonyChordGuide(
        chord=chord,
        section=section,
        stable_tones=stable,
        color_tones=colors,
        avoid_notes=avoids,
        phrase_idea=_phrase_idea(
            chord,
            stable=stable,
            colors=colors,
            next_chord=next_chord,
            section=section or "this section",
            song_title=improv_ctx.song_title or "your song",
            level=level,
            focus=focus,
        ),
        instrument_tips=_instrument_harmony_tips(
            improv_ctx.instrument,
            chord,
            stable=stable,
            colors=colors,
            level=level,
        ),
        scale_lines=scale_lines,
        focus_note=focus_note,
    )


def deduped_section_chords(sections: dict[str, list[str]]) -> list[tuple[str, list[str]]]:
    """One row per unique section with one harmonic cycle of chords."""
    from improvisation_motif import dedupe_sections_for_display

    return dedupe_sections_for_display(sections)


def render_chord_chip_html(chord: str, *, selected: bool = False) -> str:
    cls = "hm-chord-chip selected" if selected else "hm-chord-chip"
    return (
        f'<span class="{cls}">{html.escape(chord)}</span>'
    )


HARMONY_MAP_CHIP_CSS = """
<style>
.hm-section-block { margin: 0.75rem 0 1.1rem 0; }
.hm-section-title { font-weight: 800; font-size: 1.02rem; margin: 0 0 0.45rem 0; color: #0f172a; }
.hm-chord-row { display: flex; flex-wrap: wrap; gap: 0.45rem; }
.hm-chord-chip {
  display: inline-block; padding: 0.35rem 0.65rem; border-radius: 10px;
  border: 1px solid #cbd5e1; background: #f8fafc; font-weight: 750;
  font-size: 0.92rem; color: #0f172a;
}
.hm-chord-chip.selected { background: #dcfce7; border-color: #16a34a; box-shadow: 0 0 0 2px rgba(22,163,74,0.25); }
.hm-guide-card { border: 1px solid #e2e8f0; border-radius: 14px; padding: 1rem; background: #fff; margin-top: 0.75rem; }
.hm-stable { color: #15803d; font-weight: 700; }
.hm-color { color: #7c3aed; }
.hm-avoid { color: #b45309; }
</style>
"""
