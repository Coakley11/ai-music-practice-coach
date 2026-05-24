"""Interactive practice missions for Improvisation Intelligence."""

from __future__ import annotations

import hashlib
import html
import random
from dataclasses import dataclass, field
from typing import Any

from improvisation_intelligence import (
    ChordCoachInsight,
    ImprovSessionContext,
    PRACTICE_MISSIONS,
    chord_coach_insight,
)
from improvisation_motif import (
    build_motif_guitar_tab,
    build_motif_notation_abc,
    chord_tone_names,
    generate_motif_for_chord,
    transform_motif,
)

MISSION_EXAMPLE_KEY = "improv_mission_example"
MISSION_VARIANT_KEY = "improv_mission_variant"


@dataclass
class MissionExample:
    mission: str
    variant: str
    chord: str
    section: str
    song_title: str
    display_key: str
    instrument: str
    level: str
    focus: str
    motif: dict[str, Any]
    abc: str
    tab: str
    piano_html: str
    why: str
    practice_steps: list[str]
    insight: ChordCoachInsight
    show_tab: bool
    show_piano: bool


def _mission_seed(
    mission: str,
    chord: str,
    song: str,
    variant: str,
    level: str,
) -> int:
    raw = f"{mission}|{chord}|{song}|{variant}|{level}"
    return int(hashlib.md5(raw.encode()).hexdigest()[:8], 16)


def _pick_rhythm(level: str, variant: str, rng: random.Random) -> str:
    keys = list(
        {
            "Beginner": ["quarter-quarter-quarter", "quarter-eighth-eighth"],
            "Intermediate": [
                "quarter-quarter-quarter",
                "eighth-eighth-quarter",
                "quarter-eighth-eighth",
            ],
            "Advanced": [
                "eighth-eighth-quarter",
                "quarter-dotted-eighth",
                "quarter-eighth-eighth",
            ],
        }.get(level, ["quarter-quarter-quarter"])
    )
    if variant == "easier":
        return keys[0]
    if variant == "harder":
        return keys[-1]
    if variant == "new":
        return rng.choice(keys)
    return keys[0]


def _guide_tones(chord: str) -> list[str]:
    tones = chord_tone_names(chord)
    if len(tones) >= 4:
        return [tones[0], tones[1], tones[3]]
    if len(tones) >= 2:
        return [tones[0], tones[1]]
    return tones


def _motif_chord_tones_only(chord: str, *, count: int = 3) -> dict[str, Any]:
    tones = chord_tone_names(chord)
    notes = tones[:count] if len(tones) >= count else tones
    return {
        "chord": chord,
        "notes": notes,
        "display": " – ".join(notes),
        "rhythm": "♩ ♩ ♩",
        "rhythm_key": "quarter-quarter-quarter",
        "midi": [],
        "variation_prompt": f"Chord-tone line on **{chord}**",
    }


def _build_motif_for_mission(
    mission: str,
    chord: str,
    *,
    key_center: str,
    level: str,
    variant: str,
    rng: random.Random,
) -> dict[str, Any]:
    rhythm = _pick_rhythm(level, variant, rng)
    low = mission.lower()

    if "chord tone" in low or "guide tone" in low:
        if "guide" in low:
            notes = _guide_tones(chord)
        else:
            notes = chord_tone_names(chord)[:4]
        motif = _motif_chord_tones_only(chord, count=min(4, len(notes)))
        motif["notes"] = notes[:3]
        motif["display"] = " – ".join(motif["notes"])
        return motif

    if "5 notes" in low:
        insight = chord_coach_insight(chord, key_center=key_center, level=level)
        scale_notes = (
            insight.scale_suggestions[0].notes
            if insight.scale_suggestions
            else chord_tone_names(chord)
        )
        pick = scale_notes[:5]
        return {
            "chord": chord,
            "notes": pick,
            "display": " – ".join(pick),
            "rhythm": "♩ ♩ ♩ ♩ ♩",
            "rhythm_key": rhythm,
            "variation_prompt": "Five-note cell in one register",
        }

    if "silence" in low or "rest" in low:
        motif = generate_motif_for_chord(chord, key_center=key_center, rhythm_key=rhythm)
        motif["rhythm"] = "♩ z ♩"
        motif["rhythm_key"] = rhythm
        motif["variation_prompt"] = f"Leave space — play **{motif['notes'][0]}**, rest, continue."
        return motif

    motif = generate_motif_for_chord(chord, key_center=key_center, rhythm_key=rhythm)

    if "rhythm" in low and "note" in low:
        motif["variation_prompt"] = (
            f"Rhythm-first idea on **{chord}**: repeat the rhythm, change only one pitch."
        )
    elif "motif" in low and "solo" in low:
        motif["variation_prompt"] = (
            f"Core motif for **{chord}** — repeat through every section of the song."
        )
    elif "dominant" in low or "tension" in low:
        motif["variation_prompt"] = (
            f"Tension color on **{chord}** — lean on 3rd and 7th, resolve on the next change."
        )
    elif "resolve" in low and "beat 1" in low:
        motif["notes"] = [chord_tone_names(chord)[0]] + motif["notes"][1:3]
        motif["display"] = " – ".join(motif["notes"])
        motif["variation_prompt"] = "Land the first note of each phrase on beat 1."
    elif "scalar" in low:
        motif["notes"] = chord_tone_names(chord)[:3]
        motif["display"] = " – ".join(motif["notes"])
        motif["variation_prompt"] = "Step between chord tones only — no long scalar runs."
    elif "pattern" in low:
        motif = transform_motif(motif, "rhythmic", key_center=key_center)

    if variant == "easier":
        motif["notes"] = motif["notes"][:2]
        motif["display"] = " – ".join(motif["notes"])
    elif variant == "harder":
        motif = transform_motif(motif, "sequence_up", key_center=key_center)

    if variant == "new" and "last_transform" not in motif:
        ops = ["invert", "rhythmic", "sequence_up"]
        motif = transform_motif(motif, rng.choice(ops), key_center=key_center)

    return motif


def _why_it_works(
    mission: str,
    chord: str,
    *,
    improv_ctx: ImprovSessionContext,
    section: str,
    insight: ChordCoachInsight,
) -> str:
    low = mission.lower()
    song = improv_ctx.song_title or "this song"
    if "chord tone" in low:
        return (
            f"On **{chord}** in **{section}** ({song}), chord tones ({', '.join(insight.chord_tones)}) "
            f"always sound like they belong — you outline the harmony while improvising in **{improv_ctx.display_key}**."
        )
    if "guide tone" in low:
        return (
            f"3rds and 7ths define the quality of **{chord}**. In **{song}**, connecting those guide tones "
            f"makes your lines sound intentional over the backing."
        )
    if "motif" in low:
        return (
            f"A short motif on **{chord}** can travel through every section of **{song}** — "
            f"transpose or rhythmically vary it while keeping the same contour."
        )
    if "dominant" in low or "tension" in low:
        return (
            f"**{chord}** wants motion toward the next harmony in **{song}**. "
            f"Use tensions, then resolve into the following chord."
        )
    if "rhythm" in low:
        return (
            f"Strong rhythm on **{chord}** carries the groove in **{song}** even when pitch choices stay simple."
        )
    return (
        f"This idea fits **{chord}** in **{section}** for **{song}** in **{improv_ctx.display_key}** — "
        f"stay with the harmony and let your {improv_ctx.instrument} articulation sell the phrase."
    )


def _practice_steps(mission: str, level: str, instrument: str) -> list[str]:
    steps = [
        "Sing the example, then play it slowly with the metronome.",
        "Loop the motif 4× on one chord before moving to the next change.",
    ]
    low = mission.lower()
    if "motif" in low and "solo" in low:
        steps.append("Carry the same contour into the next section — only change the starting note to match the chord.")
    if "silence" in low:
        steps.append("Count rests out loud — silence is part of the phrase.")
    if level == "Advanced":
        steps.append("Transpose the idea up or down one scale step without changing the rhythm.")
    if instrument == "Guitar":
        steps.append("Try the TAB fingering, then move the shape to another string set.")
    elif instrument == "Piano":
        steps.append("Practice in one hand position, then answer in the other hand.")
    return steps[:4]


def _piano_keyboard_html(highlight_notes: list[str], chord_tones: list[str]) -> str:
    white = ["C", "D", "E", "F", "G", "A", "B"]
    hi = set(highlight_notes) | set(chord_tones)
    cells = []
    for n in white:
        cls = "pk white"
        if n in hi:
            cls += " hi"
        if n in chord_tones:
            cls += " chord"
        cells.append(f'<div class="{cls}"><span>{html.escape(n)}</span></div>')
    return (
        '<div class="improv-piano-kb">'
        + "".join(cells)
        + "</div>"
        '<style>.improv-piano-kb{display:flex;gap:4px;margin:8px 0;}'
        ".improv-piano-kb .pk{min-width:36px;height:72px;border-radius:6px;"
        "border:1px solid #cbd5e1;display:flex;align-items:flex-end;justify-content:center;"
        "font-size:0.72rem;font-weight:700;padding-bottom:6px;background:#fff;}"
        ".improv-piano-kb .pk.hi{background:#bbf7d0;border-color:#16a34a;}"
        ".improv-piano-kb .pk.chord{box-shadow:0 0 0 2px #15803d;}</style>"
    )


def _instrument_family(instrument: str) -> str:
    inst = (instrument or "").lower()
    if "guitar" in inst or "bass" in inst:
        return "guitar"
    if "piano" in inst or "keys" in inst:
        return "piano"
    if any(x in inst for x in ("sax", "trumpet", "flute", "clarinet")):
        return "wind"
    return "other"


def generate_mission_example(
    mission: str,
    *,
    improv_ctx: ImprovSessionContext,
    chord: str,
    section: str,
    level: str,
    instrument: str,
    focus: str,
    variant: str = "normal",
    bpm: int = 100,
) -> MissionExample:
    variant = variant if variant in ("normal", "easier", "harder", "new") else "normal"
    seed = _mission_seed(mission, chord, improv_ctx.song_title, variant, level)
    rng = random.Random(seed)

    motif = _build_motif_for_mission(
        mission,
        chord,
        key_center=improv_ctx.display_key,
        level=level,
        variant=variant,
        rng=rng,
    )
    if not motif.get("midi"):
        from improvisation_motif import _midi_from_note

        motif["midi"] = [_midi_from_note(n, 4) for n in motif.get("notes", [])]

    abc = build_motif_notation_abc(
        motif,
        key_center=improv_ctx.display_key,
        bpm=bpm,
    )
    family = _instrument_family(instrument)
    tab = build_motif_guitar_tab(motif) if family == "guitar" else ""
    piano_html = ""
    if family == "piano":
        piano_html = _piano_keyboard_html(
            list(motif.get("notes") or []),
            chord_tone_names(chord),
        )

    insight = chord_coach_insight(
        chord,
        key_center=improv_ctx.display_key,
        instrument=instrument,
        level=level,
    )

    return MissionExample(
        mission=mission,
        variant=variant,
        chord=chord,
        section=section,
        song_title=improv_ctx.song_title,
        display_key=improv_ctx.display_key,
        instrument=instrument,
        level=level,
        focus=focus,
        motif=motif,
        abc=abc,
        tab=tab,
        piano_html=piano_html,
        why=_why_it_works(mission, chord, improv_ctx=improv_ctx, section=section, insight=insight),
        practice_steps=_practice_steps(mission, level, instrument),
        insight=insight,
        show_tab=family == "guitar",
        show_piano=family == "piano",
    )


def store_mission_example(session_state: dict, example: MissionExample) -> None:
    session_state[MISSION_EXAMPLE_KEY] = {
        "mission": example.mission,
        "variant": example.variant,
        "chord": example.chord,
        "section": example.section,
        "motif": example.motif,
        "abc": example.abc,
        "tab": example.tab,
        "piano_html": example.piano_html,
        "why": example.why,
        "practice_steps": example.practice_steps,
        "show_tab": example.show_tab,
        "show_piano": example.show_piano,
    }
    session_state[MISSION_VARIANT_KEY] = example.variant


def load_mission_example(session_state: dict, improv_ctx: ImprovSessionContext) -> MissionExample | None:
    raw = session_state.get(MISSION_EXAMPLE_KEY)
    if not raw or not isinstance(raw, dict):
        return None
    try:
        insight = chord_coach_insight(
            str(raw.get("chord", "C")),
            key_center=improv_ctx.display_key,
            instrument=str(session_state.get("instrument", improv_ctx.instrument)),
            level=str(session_state.get("level", improv_ctx.level)),
        )
    except Exception:
        return None
    return MissionExample(
        mission=str(raw.get("mission", "")),
        variant=str(raw.get("variant", "normal")),
        chord=str(raw.get("chord", "")),
        section=str(raw.get("section", "")),
        song_title=improv_ctx.song_title,
        display_key=improv_ctx.display_key,
        instrument=str(session_state.get("instrument", improv_ctx.instrument)),
        level=str(session_state.get("level", improv_ctx.level)),
        focus=str(session_state.get("focus", improv_ctx.focus)),
        motif=dict(raw.get("motif") or {}),
        abc=str(raw.get("abc", "")),
        tab=str(raw.get("tab", "")),
        piano_html=str(raw.get("piano_html", "")),
        why=str(raw.get("why", "")),
        practice_steps=list(raw.get("practice_steps") or []),
        insight=insight,
        show_tab=bool(raw.get("show_tab")),
        show_piano=bool(raw.get("show_piano")),
    )
