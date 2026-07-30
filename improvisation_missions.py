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
    cycle_motif_rhythm,
    generate_motif_for_chord,
    sync_motif_midi,
    transform_motif,
)

MISSION_EXAMPLE_KEY = "improv_mission_example"
MISSION_VARIANT_KEY = "improv_mission_variant"
MISSION_NEW_NONCE_KEY = "improv_mission_new_nonce"
IMPROV_MISSION_BACKING_HANDOFF = "improv_mission_backing_handoff"

_LEVEL_ORDER = ("Beginner", "Intermediate", "Advanced")


def _effective_level(level: str, variant: str) -> str:
    try:
        idx = _LEVEL_ORDER.index(level)
    except ValueError:
        idx = 1
    if variant == "easier":
        idx = max(0, idx - 1)
    elif variant == "harder":
        idx = min(len(_LEVEL_ORDER) - 1, idx + 1)
    return _LEVEL_ORDER[idx]


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
    section: str,
    *,
    nonce: int = 0,
) -> int:
    extra = f"|n{nonce}" if nonce else ""
    raw = f"{mission}|{chord}|{song}|{variant}|{level}|{section}{extra}"
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
    idea_variant: int = 0,
) -> dict[str, Any]:
    low = mission.lower()
    work_level = _effective_level(level, variant)
    idea = idea_variant
    if variant == "easier":
        work_level = _effective_level(level, "easier")
        idea = 0
    elif variant == "harder":
        idea = max(2, idea_variant % 5)

    motif = generate_motif_for_chord(
        chord,
        key_center=key_center,
        level=work_level,
        rng=rng,
        idea_variant=idea,
    )

    if ("chord tone" in low or "guide tone" in low) and work_level == "Beginner" and variant in {"normal", "easier"}:
        if "guide" in low:
            notes = _guide_tones(chord)[:3]
        else:
            notes = chord_tone_names(chord)[:3]
        motif = _motif_chord_tones_only(chord, count=min(3, len(notes)))
        motif["notes"] = notes
        motif["display"] = " – ".join(notes)
        motif["rhythm"] = "♩ ♩ ♩" if variant != "easier" else "♩ 𝅗"
        motif["rhythm_key"] = "quarter-quarter-quarter" if variant != "easier" else "quarter-quarter-half"
        return motif

    if "5 notes" in low:
        insight = chord_coach_insight(chord, key_center=key_center, level=work_level)
        scale_notes = (
            insight.scale_suggestions[0].notes
            if insight.scale_suggestions
            else chord_tone_names(chord)
        )
        count = 3 if work_level == "Beginner" else (5 if work_level == "Intermediate" else 7)
        pick = scale_notes[:count]
        motif = generate_motif_for_chord(
            chord, key_center=key_center, level=work_level, rng=rng, idea_variant=idea
        )
        motif["notes"] = pick[: len(motif["notes"])]
        motif["display"] = " – ".join(motif["notes"])
        motif["variation_prompt"] = "Five-note cell in one register"
        return motif

    if "silence" in low or "rest" in low:
        motif["rhythm"] = "♩ z ♩"
        motif["rhythm_key"] = "quarter-quarter-quarter"
        motif["variation_prompt"] = f"Leave space — play **{motif['notes'][0]}**, rest, continue."
        return motif

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
    elif "scalar" in low and work_level == "Beginner":
        motif["notes"] = chord_tone_names(chord)[:3]
        motif["display"] = " – ".join(motif["notes"])
        motif["variation_prompt"] = "Step between chord tones only — no long scalar runs."
    elif "pattern" in low:
        motif = transform_motif(motif, "rhythmic", key_center=key_center)

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
    from music_theory import NOTE_TO_MIDI, normalize_root, split_chord

    def _pc(note: str) -> int:
        root, _ = split_chord(str(note))
        return NOTE_TO_MIDI.get(normalize_root(root), 60) % 12

    motif_pcs = {_pc(n) for n in highlight_notes}
    chord_pcs = {_pc(n) for n in chord_tones}

    white_midi = [60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79, 81, 83]
    black_midi = [61, 63, 66, 68, 70, 73, 75, 78, 80, 82]
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    def _label(midi: int) -> str:
        return names[midi % 12]

    def _cls(midi: int) -> str:
        pc = midi % 12
        if pc in motif_pcs:
            return "pk hi"
        if pc in chord_pcs:
            return "pk chord"
        return "pk"

    whites_html = []
    for i, midi in enumerate(white_midi):
        whites_html.append(
            f'<div class="{_cls(midi)} white" style="--i:{i}">'
            f"<span>{html.escape(_label(midi))}</span></div>"
        )

    black_positions = {
        61: 0.72,
        63: 1.72,
        66: 3.72,
        68: 4.72,
        70: 5.72,
        73: 7.72,
        75: 8.72,
        78: 10.72,
        80: 11.72,
        82: 12.72,
    }
    blacks_html = []
    for midi in black_midi:
        left = black_positions.get(midi, 0)
        blacks_html.append(
            f'<div class="{_cls(midi)} black" style="left:calc({left} * var(--wk))">'
            f"<span>{html.escape(_label(midi))}</span></div>"
        )

    voicing = " · ".join(html.escape(n) for n in chord_tones[:4])
    chips = "".join(f'<span class="pk-chip">{html.escape(n)}</span>' for n in chord_tones[:4])
    return (
        f'<p class="pk-voicing-hint"><strong>Chord tones:</strong> {voicing}</p>'
        f'<p class="pk-motif-notes"><strong>Highlighted:</strong> {chips or "—"}</p>'
        '<div class="improv-piano-wrap">'
        '<div class="improv-piano-kb" style="--wk:42px">'
        + "".join(whites_html)
        + "".join(blacks_html)
        + "</div></div>"
        "<style>"
        ".improv-piano-wrap{overflow-x:auto;padding:4px 0 8px;}"
        ".improv-piano-kb{position:relative;display:flex;gap:2px;height:118px;--wk:42px;}"
        ".improv-piano-kb .pk.white{width:var(--wk);height:112px;border-radius:0 0 6px 6px;"
        "border:1px solid #cbd5e1;background:#fff;display:flex;align-items:flex-end;"
        "justify-content:center;font-size:0.68rem;font-weight:700;padding-bottom:5px;box-sizing:border-box;}"
        ".improv-piano-kb .pk.black{position:absolute;top:0;width:calc(var(--wk)*0.58);height:68px;"
        "border-radius:0 0 5px 5px;background:#1e293b;color:#f8fafc;border:1px solid #0f172a;"
        "display:flex;align-items:flex-end;justify-content:center;font-size:0.58rem;"
        "font-weight:700;padding-bottom:4px;z-index:2;box-sizing:border-box;}"
        ".improv-piano-kb .pk.hi{background:#bbf7d0;border-color:#16a34a;}"
        ".improv-piano-kb .pk.black.hi{background:#15803d;color:#fff;}"
        ".improv-piano-kb .pk.chord{box-shadow:inset 0 0 0 2px #6366f1;}"
        ".pk-chip{display:inline-block;background:#e0e7ff;border:1px solid #6366f1;"
        "border-radius:6px;padding:2px 8px;margin:2px 4px 2px 0;font-weight:700;}"
        ".pk-voicing-hint,.pk-motif-notes{margin:0 0 6px 0;font-size:0.85rem;color:#475569;}"
        "</style>"
    )


def wind_phrasing_lines(instrument: str, motif: dict[str, Any]) -> list[str]:
    inst = (instrument or "").lower()
    rhythm = str(motif.get("rhythm") or "")
    lines = [
        f"**Notes to play:** {' – '.join(motif.get('notes') or [])}",
        f"**Rhythm:** {rhythm} — tongue lighter on faster subdivisions.",
    ]
    if "sax" in inst:
        lines.append("Keep the throat open; land chord tones on downbeats with a supported tone.")
    elif "trumpet" in inst:
        lines.append("Use steady air; accent the first note of each rhythmic group.")
    elif "flute" in inst:
        lines.append("Breathe before the phrase; let the long note at the end ring.")
    elif "clarinet" in inst:
        lines.append("Alternate light tongue / slur where the rhythm repeats.")
    else:
        lines.append("Phrase in 2-bar questions and answers; breathe at the rests.")
    return lines


def rebuild_mission_outputs(
    motif: dict[str, Any],
    *,
    chord: str,
    instrument: str,
    key_center: str,
    bpm: int,
) -> dict[str, Any]:
    """Rebuild ABC, TAB, and piano HTML from the current motif (no stale displays)."""
    motif = sync_motif_midi(dict(motif))
    family = _instrument_family(instrument)
    abc = build_motif_notation_abc(motif, key_center=key_center, bpm=bpm)
    tab = build_motif_guitar_tab(motif) if family == "guitar" else ""
    piano_html = ""
    if family == "piano":
        piano_html = _piano_keyboard_html(
            list(motif.get("notes") or []),
            chord_tone_names(chord, reference_key=key_center),
        )
    return {
        "motif": motif,
        "abc": abc,
        "tab": tab,
        "piano_html": piano_html,
        "show_tab": family == "guitar",
        "show_piano": family == "piano",
        "show_wind": family == "wind",
    }


def refresh_mission_example(
    example: MissionExample,
    *,
    instrument: str | None = None,
    bpm: int | None = None,
) -> MissionExample:
    """Sync all instrument outputs to the current motif."""
    inst = instrument or example.instrument
    tempo = bpm if bpm is not None else 100
    out = rebuild_mission_outputs(
        example.motif,
        chord=example.chord,
        instrument=inst,
        key_center=example.display_key,
        bpm=tempo,
    )
    example.instrument = inst
    example.motif = out["motif"]
    example.abc = out["abc"]
    example.tab = out["tab"]
    example.piano_html = out["piano_html"]
    example.show_tab = out["show_tab"]
    example.show_piano = out["show_piano"]
    return example


def apply_mission_motif_transform(
    session_state: dict,
    improv_ctx: ImprovSessionContext,
    operation: str,
    *,
    bpm: int = 100,
) -> MissionExample | None:
    """Transform stored mission motif and refresh every output."""
    example = load_mission_example(session_state, improv_ctx)
    if not example:
        return None
    if operation == "change_rhythm":
        motif = cycle_motif_rhythm(dict(example.motif))
    else:
        motif = transform_motif(
            dict(example.motif),
            operation,
            key_center=improv_ctx.display_key,
        )
        motif = sync_motif_midi(motif)
    example.motif = motif
    example = refresh_mission_example(example, instrument=example.instrument, bpm=bpm)
    store_mission_example(session_state, example)
    return example


def instrument_family(instrument: str) -> str:
    inst = (instrument or "").lower()
    if "guitar" in inst or "bass" in inst:
        return "guitar"
    if "piano" in inst or "keys" in inst:
        return "piano"
    if any(x in inst for x in ("sax", "trumpet", "flute", "clarinet", "voice")):
        return "wind"
    return "other"


def _instrument_family(instrument: str) -> str:
    return instrument_family(instrument)


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
    session_state: dict | None = None,
) -> MissionExample:
    variant = variant if variant in ("normal", "easier", "harder", "new") else "normal"
    nonce = 0
    if variant == "new" and session_state is not None:
        nonce = int(session_state.get(MISSION_NEW_NONCE_KEY) or 0) + 1
        session_state[MISSION_NEW_NONCE_KEY] = nonce
    seed = _mission_seed(
        mission, chord, improv_ctx.song_title, variant, level, section, nonce=nonce
    )
    rng = random.Random(seed)

    motif = _build_motif_for_mission(
        mission,
        chord,
        key_center=improv_ctx.display_key,
        level=level,
        variant=variant,
        rng=rng,
        idea_variant=(nonce if variant == "new" else (seed % 1000)),
    )
    motif = sync_motif_midi(motif)
    out = rebuild_mission_outputs(
        motif,
        chord=chord,
        instrument=instrument,
        key_center=improv_ctx.display_key,
        bpm=bpm,
    )
    motif = out["motif"]
    family = _instrument_family(instrument)
    abc = str(out.get("abc") or "")
    tab = str(out.get("tab") or "")
    piano_html = str(out.get("piano_html") or "")

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


def mission_example_for_display(
    example: MissionExample,
    *,
    instrument: str,
    bpm: int,
) -> MissionExample:
    """Always rebuild outputs so sheet music / TAB / piano match the current motif."""
    return refresh_mission_example(example, instrument=instrument, bpm=bpm)
