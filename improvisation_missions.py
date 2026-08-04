"""Interactive practice missions for Improvisation Intelligence."""

from __future__ import annotations

import hashlib
import html
import json
import random
from dataclasses import dataclass, field
from typing import Any

from improvisation_intelligence import (
    ChordCoachInsight,
    ImprovSessionContext,
    PRACTICE_MISSIONS,
    chord_coach_insight,
)
from motif_engine import generate_mission_phrase_validated
from improvisation_motif import (
    build_motif_abc,
    build_motif_guitar_tab,
    chord_tone_names,
    cycle_motif_rhythm,
    sync_motif_midi,
    transform_motif,
    _normalize_motif_level,
)


def build_mission_notation_abc(
    motif: dict[str, Any],
    *,
    mission: str = "",
    key_center: str = "C",
    bpm: int = 100,
) -> str:
    """ABC title for Missions (not Phrase & Motif)."""
    chord = str(motif.get("chord") or "").strip()
    short = str(mission or "").strip()
    if short and len(short) <= 48:
        title = f"Mission: {short} — {chord}" if chord else f"Mission: {short}"
    elif chord:
        title = f"Mission Example — {chord}"
    else:
        title = "Mission Example"
    return build_motif_abc(motif, key_center=key_center, bpm=bpm, title=title)

MISSION_EXAMPLE_KEY = "improv_mission_example"
MISSION_VARIANT_KEY = "improv_mission_variant"
MISSION_NEW_NONCE_KEY = "improv_mission_new_nonce"
MISSION_NEW_IDEA_DIAG_KEY = "_mission_new_idea_diag"
MISSION_EXAMPLE_GEN_DIAG_KEY = "_mission_example_gen_diag"
MISSION_EXAMPLE_FRESH_RUN_KEY = "_mission_example_fresh_this_run"
MISSIONS_GENERATE_CONTEXT_KEY = "_missions_tab_generate_context"
MISSIONS_LAST_EXAMPLE_CALLBACK_KEY = "_missions_last_example_callback"
IMPROV_MISSION_BACKING_HANDOFF = "improv_mission_backing_handoff"
MISSION_PRACTICE_LICK_KEY = "improv_mission_practice_lick"
IMPROV_MISSION_PRACTICE_LICK_HANDOFF = "improv_mission_practice_lick_handoff"

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
    return generate_mission_phrase_validated(
        mission,
        chord,
        key_center=key_center,
        level=level,
        variant=variant,
        rng=rng,
        idea_variant=idea_variant,
    )


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


def mission_brief_for_practice(mission: str) -> str:
    """User-facing mission instructions (no example required)."""
    low = str(mission or "").lower()
    if "chord tone" in low:
        return "Outline the harmony using chord tones while improvising your own lines and rhythms."
    if "guide tone" in low:
        return "Connect 3rds and 7ths in your phrases while keeping your own melodic choices."
    if "motif" in low:
        return "Develop a short idea: repeat, vary, and grow it while improvising freely over the target chord."
    if "silence" in low or "space" in low:
        return "Use rests and space deliberately as part of your phrasing over the target chord."
    if "rhythm" in low:
        return "Explore rhythmic variety and groove while staying with the mission over the target chord."
    return "Focus on the mission goal while improvising freely over the selected chord."


def _practice_steps(mission: str, level: str, instrument: str) -> list[str]:
    steps = [
        "Optional: use the example idea for inspiration — invent your own notes and phrases.",
        "Loop your idea on one chord before moving to the next change.",
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


def _piano_keyboard_html(
    highlight_notes: list[str],
    chord_tones: list[str],
    *,
    reference_key: str = "C",
) -> str:
    from piano_keyboard_display import build_piano_keyboard_html

    return build_piano_keyboard_html(
        highlight_notes,
        chord_tones,
        reference_key=reference_key,
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
    mission: str = "",
) -> dict[str, Any]:
    """Rebuild ABC, TAB, and piano HTML from the current motif (no stale displays)."""
    motif = sync_motif_midi(dict(motif))
    family = _instrument_family(instrument)
    abc = build_mission_notation_abc(
        motif, mission=mission, key_center=key_center, bpm=bpm
    )
    tab = build_motif_guitar_tab(motif) if family == "guitar" else ""
    piano_html = ""
    if family == "piano":
        piano_html = _piano_keyboard_html(
            list(motif.get("notes") or []),
            chord_tone_names(chord, reference_key=key_center),
            reference_key=key_center,
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
        mission=example.mission,
    )
    example.instrument = inst
    example.motif = out["motif"]
    example.abc = out["abc"]
    example.tab = out["tab"]
    example.piano_html = out["piano_html"]
    example.show_tab = out["show_tab"]
    example.show_piano = out["show_piano"]
    return example


def motif_material_fingerprint(motif: dict[str, Any] | None) -> str:
    if not isinstance(motif, dict):
        return ""
    payload = {
        "notes": list(motif.get("notes") or []),
        "rhythm_key": motif.get("rhythm_key"),
        "rhythm_symbols": motif.get("rhythm_symbols"),
        "display": motif.get("display"),
    }
    return hashlib.md5(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def mission_example_artifact_id(
    session_state: dict,
    *,
    mission: str,
    chord: str,
    section: str,
    chord_index: int,
) -> str:
    song = str(session_state.get("song") or session_state.get("active_catalog_pick_key") or "song")
    workspace = str(session_state.get("suite_active_workspace") or session_state.get("music_user_id") or "")
    return f"mission_example|{workspace}|{song}|{section}|{chord_index}|{chord}|{mission}"


def generate_mission_example_distinct(
    mission: str,
    *,
    improv_ctx: ImprovSessionContext,
    chord: str,
    section: str,
    level: str,
    instrument: str,
    focus: str,
    variant: str = "new",
    bpm: int = 100,
    session_state: dict | None = None,
    nonce_override: int | None = None,
    prior_material_fp: str = "",
    max_attempts: int = 8,
) -> tuple[MissionExample, int, bool]:
    """Generate a new idea; retry when material matches prior (not nonce-only)."""
    base_nonce = int(session_state.get(MISSION_NEW_NONCE_KEY) or 0) if session_state else 0
    if variant == "new" and session_state is not None:
        base_nonce = int(nonce_override if nonce_override is not None else base_nonce + 1)

    last: MissionExample | None = None
    retries = 0
    for attempt in range(max(1, int(max_attempts))):
        nonce = base_nonce + attempt if variant == "new" else 0
        ex = generate_mission_example(
            mission,
            improv_ctx=improv_ctx,
            chord=chord,
            section=section,
            level=level,
            instrument=instrument,
            focus=focus,
            variant=variant,
            bpm=bpm,
            session_state=session_state,
            nonce_override=nonce if variant == "new" else None,
        )
        last = ex
        mat = motif_material_fingerprint(ex.motif)
        if variant != "new":
            return ex, retries, False
        if not prior_material_fp or mat != prior_material_fp:
            return ex, retries, retries > 0
        retries += 1
    assert last is not None
    return last, retries, retries > 0


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
    idx = int(session_state.get("ii_selected_chord_index") or 0)
    artifact_id = mission_example_artifact_id(
        session_state,
        mission=example.mission,
        chord=example.chord,
        section=example.section,
        chord_index=idx,
    )
    session_state["_mission_example_artifact_id"] = artifact_id
    session_state["_mission_example_last_transform"] = operation
    store_mission_example(
        session_state,
        example,
        persist_artifact=True,
        interaction=f"mission_transform_{operation}",
    )
    session_state["_mission_example_output_fp"] = mission_example_fingerprint(example)
    session_state["_mission_example_material_fp"] = motif_material_fingerprint(example.motif)
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
    nonce_override: int | None = None,
) -> MissionExample:
    variant = variant if variant in ("normal", "easier", "harder", "new") else "normal"
    nonce = 0
    if variant == "new" and session_state is not None:
        if nonce_override is not None:
            nonce = int(nonce_override)
            session_state[MISSION_NEW_NONCE_KEY] = nonce
        else:
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
        mission=mission,
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


def mission_example_fingerprint(example: MissionExample | None) -> str:
    if example is None:
        return ""
    motif = example.motif if isinstance(example.motif, dict) else {}
    payload = {
        "mission": example.mission,
        "variant": example.variant,
        "chord": example.chord,
        "section": example.section,
        "display": motif.get("display"),
        "rhythm": motif.get("rhythm"),
        "notes": motif.get("notes"),
    }
    return hashlib.md5(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def store_mission_example(
    session_state: dict,
    example: MissionExample,
    *,
    persist_artifact: bool = False,
    interaction: str = "store_mission_example",
) -> None:
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
        "artifact_id": session_state.get("_mission_example_artifact_id"),
        "last_transform": session_state.get("_mission_example_last_transform"),
        "material_fp": motif_material_fingerprint(example.motif),
    }
    session_state[MISSION_VARIANT_KEY] = example.variant
    if persist_artifact:
        try:
            from creative_mission_artifact_persistence import handle_user_mission_example_artifact_saved

            handle_user_mission_example_artifact_saved(session_state, interaction=interaction)
        except ImportError:
            pass
    try:
        from improvisation_mission_persistence import mark_mission_workspace_dirty

        mark_mission_workspace_dirty(session_state)
    except ImportError:
        pass


def _fallback_chord_insight(chord: str) -> ChordCoachInsight:
    tones = chord_tone_names(str(chord or "C"))
    return ChordCoachInsight(
        chord=str(chord or "C"),
        scales=["major"],
        scale_suggestions=[],
        chord_tones=tones,
        tensions=[],
        avoid_notes=[],
        target_notes=tones[:2],
        motif_idea="",
        resolve_hint="",
        instrument_tips=[],
    )


def load_mission_example(session_state: dict, improv_ctx: ImprovSessionContext) -> MissionExample | None:
    raw = session_state.get(MISSION_EXAMPLE_KEY)
    if not raw or not isinstance(raw, dict):
        return None
    chord = str(raw.get("chord", "C"))
    try:
        from mission_pitch_spelling import chord_coach_insight_for_mission

        insight = chord_coach_insight_for_mission(
            chord,
            song_display_key=improv_ctx.display_key,
            song_key_center=improv_ctx.key_center,
            instrument=str(session_state.get("instrument", improv_ctx.instrument)),
            level=str(session_state.get("level", improv_ctx.level)),
        )
    except ImportError:
        try:
            insight = chord_coach_insight(
                chord,
                key_center=improv_ctx.display_key,
                instrument=str(session_state.get("instrument", improv_ctx.instrument)),
                level=str(session_state.get("level", improv_ctx.level)),
            )
        except Exception:
            insight = _fallback_chord_insight(chord)
    except Exception:
        insight = _fallback_chord_insight(chord)
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


def store_mission_practice_lick_for_backing(
    session_state: dict,
    *,
    example: MissionExample,
    mission_title: str,
    instrument: str,
    bpm: int,
    groove: str,
    meter: str,
    song_title: str,
    section_label: str,
    persist_artifact: bool = True,
) -> None:
    """Persist the current mission lick for Mission Backing Jam (single motif source of truth)."""
    ex = mission_example_for_display(example, instrument=instrument, bpm=bpm)
    payload = {
        "motif": dict(ex.motif),
        "abc": ex.abc,
        "tab": ex.tab,
        "instrument": instrument,
        "bpm": int(bpm),
        "groove": groove,
        "meter": meter,
        "song_title": song_title,
        "section_label": section_label,
        "chord": ex.chord,
        "mission_title": mission_title,
        "level": ex.level,
        "key_center": ex.display_key,
        "example_variant": ex.variant,
        "backing_track_scope": str(session_state.get("backing_track_scope") or ""),
        "backing_track_loops": session_state.get("backing_track_loops"),
        "backing_track_single_section": str(session_state.get("backing_track_single_section") or ""),
        "backing_track_multi_sections": list(session_state.get("backing_track_multi_sections") or []),
    }
    session_state[MISSION_PRACTICE_LICK_KEY] = payload
    try:
        if persist_artifact:
            from creative_mission_artifact_persistence import handle_user_mission_practice_lick_saved

            handle_user_mission_practice_lick_saved(
                session_state,
                interaction="store_practice_lick_for_backing",
            )
        else:
            from creative_mission_artifact_persistence import (
                commit_mission_practice_lick_for_navigation_handoff,
            )

            commit_mission_practice_lick_for_navigation_handoff(
                session_state,
                interaction="store_practice_lick_for_backing",
            )
    except ImportError:
        try:
            from improvisation_mission_persistence import mark_mission_workspace_dirty

            mark_mission_workspace_dirty(session_state)
        except ImportError:
            pass


def mission_practice_lick_payload(session_state: dict) -> dict[str, Any] | None:
    raw = session_state.get(MISSION_PRACTICE_LICK_KEY)
    return raw if isinstance(raw, dict) and raw.get("motif") else None


def clear_mission_practice_lick_handoff(session_state: dict) -> None:
    session_state.pop(IMPROV_MISSION_PRACTICE_LICK_HANDOFF, None)


def queue_mission_practice_lick_handoff(session_state: dict) -> None:
    session_state[IMPROV_MISSION_PRACTICE_LICK_HANDOFF] = True
