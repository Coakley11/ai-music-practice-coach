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
MISSION_NOTATION_STAFF_AUTHORITY_VERSION = 2

_LEVEL_ORDER = ("Beginner", "Intermediate", "Advanced")


def parse_abc_k_field(abc: str) -> str:
    for line in str(abc or "").splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("K:"):
            return stripped[2:].strip()
    return ""


def abc_staff_key_matches_concert(abc: str, song_concert_key: str) -> bool:
    k = parse_abc_k_field(abc)
    if not k or not str(song_concert_key or "").strip():
        return bool(k)
    try:
        from improvisation_motif import _abc_key_header

        return _abc_key_header(str(song_concert_key)).lower() == k.lower()
    except ImportError:
        return str(song_concert_key).lower().startswith(k.lower())


def ensure_mission_sheet_music_authority(
    session_state: dict,
    example: MissionExample,
    *,
    improv_ctx: ImprovSessionContext,
    instrument: str,
    bpm: int,
) -> MissionExample:
    """Rebuild visible mission ABC when staff-key authority is stale.

    Staff / insight / scales follow the musician-facing chart key (Shape/Written),
    not concert. Comparing ABC against concert collapsed D#m examples back to Dm.
    """
    concert = str(improv_ctx.key_center or session_state.get("concert_key") or "").strip()
    chart = str(improv_ctx.display_key or example.display_key or concert).strip()
    try:
        from effective_practice_context import musician_facing_chart_key

        chart = str(musician_facing_chart_key(session_state, concert or chart) or chart).strip() or chart
    except ImportError:
        pass
    staff_key = chart or concert
    ver = int(session_state.get("_mission_notation_staff_version") or 0)
    needs = (
        ver < MISSION_NOTATION_STAFF_AUTHORITY_VERSION
        or not abc_staff_key_matches_concert(str(example.abc or ""), staff_key)
    )
    if not needs:
        return example
    example.display_key = staff_key
    if concert:
        example.concert_key = concert
    refreshed = mission_example_for_display(
        example,
        instrument=instrument,
        bpm=bpm,
        song_concert_key=concert,
        session_state=session_state,
        authoritative_concert_key=concert,
        authoritative_display_key=staff_key,
    )
    session_state["_mission_notation_staff_version"] = MISSION_NOTATION_STAFF_AUTHORITY_VERSION
    session_state["_mission_example_output_fp"] = mission_example_fingerprint(refreshed)
    raw = session_state.get(MISSION_EXAMPLE_KEY)
    if isinstance(raw, dict):
        raw = dict(raw)
        raw["abc"] = refreshed.abc
        raw["motif"] = refreshed.motif
        raw["display_key"] = str(refreshed.display_key or staff_key)
        raw["concert_key"] = str(refreshed.concert_key or concert)
        raw["why"] = refreshed.why
        session_state[MISSION_EXAMPLE_KEY] = raw
    abc_k = parse_abc_k_field(refreshed.abc or "")
    session_state["_mission_notation_diag"] = {
        "concert_key": concert,
        "written_key": staff_key,
        "chord": str(example.chord or ""),
        "abc_key": abc_k,
        "authority_version": MISSION_NOTATION_STAFF_AUTHORITY_VERSION,
    }
    return refreshed


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
    concert_key: str = ""


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
    song_display_key: str = "",
    song_concert_key: str = "",
) -> dict[str, Any]:
    """Rebuild ABC, TAB, and piano HTML from the current motif (no stale displays)."""
    motif = sync_motif_midi(dict(motif))
    spell_ref = str(key_center or song_display_key or song_concert_key or "C")
    staff_key = str(song_display_key or key_center or song_concert_key or "C")
    try:
        from harmonic_spelling import (
            apply_motif_chord_spelling,
            harmonic_reference_for_chord,
            mission_notation_staff_key,
        )

        spell_ref = harmonic_reference_for_chord(
            chord,
            song_display_key=song_display_key or key_center,
            song_key_center=song_concert_key or key_center,
        )
        apply_motif_chord_spelling(
            motif,
            chord,
            song_display_key=song_display_key or song_concert_key or key_center,
        )
        staff_key = mission_notation_staff_key(
            song_concert_key=song_concert_key or key_center,
            song_display_key=song_display_key,
        )
    except ImportError:
        pass
    family = _instrument_family(instrument)
    abc = build_mission_notation_abc(
        motif, mission=mission, key_center=staff_key, bpm=bpm
    )
    tab = build_motif_guitar_tab(motif) if family == "guitar" else ""
    piano_html = ""
    if family == "piano":
        piano_html = _piano_keyboard_html(
            list(motif.get("notes") or []),
            chord_tone_names(chord, reference_key=spell_ref),
            reference_key=spell_ref,
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
    song_concert_key: str = "",
) -> MissionExample:
    """Sync all instrument outputs to the current motif."""
    inst = instrument or example.instrument
    tempo = bpm if bpm is not None else 100
    concert_auth = str(song_concert_key or example.concert_key or "").strip()
    spell_display = str(example.display_key or concert_auth).strip()
    display_motif = dict(example.motif or {})
    concert_chord = str(display_motif.get("_concert_chord") or example.chord or "").strip()
    concert_notes = display_motif.get("_concert_notes")
    already_projected = str(display_motif.get("_projected_display_key") or "").strip()
    # Recover when a prior Shape projection was wrongly stored as "_concert_chord".
    if (
        already_projected
        and concert_auth
        and already_projected != concert_auth
        and concert_chord
    ):
        try:
            from effective_practice_context import musician_facing_chord
            from music_theory import semitone_distance, transpose_chord

            motif_display_chord = str(display_motif.get("chord") or "").strip()
            projected_claim = musician_facing_chord(
                concert_chord,
                concert_key=concert_auth,
                chart_key=already_projected,
            )
            looks_like_display = (
                (motif_display_chord and concert_chord == motif_display_chord)
                or projected_claim == concert_chord
            )
            if looks_like_display:
                back = semitone_distance(already_projected, concert_auth)
                if back:
                    concert_chord = transpose_chord(
                        concert_chord, back, reference_key=concert_auth
                    )
                    display_motif["_concert_chord"] = concert_chord
        except ImportError:
            pass
    if not isinstance(concert_notes, list) or not concert_notes:
        live_notes = list(display_motif.get("notes") or [])
        if not already_projected:
            concert_notes = live_notes
            display_motif["_concert_notes"] = list(concert_notes)
            display_motif["_concert_chord"] = concert_chord
        elif live_notes and concert_auth:
            # Recover concert notes by unprojecting from the previous Shape/Written domain.
            try:
                from music_theory import semitone_distance
                from improvisation_motif import _midi_from_note, _note_from_midi

                back = semitone_distance(already_projected, concert_auth)
                if back:
                    recovered = []
                    for n in live_notes:
                        midi = _midi_from_note(str(n), 4)
                        recovered.append(_note_from_midi(midi + back, concert_auth))
                    concert_notes = recovered
                else:
                    concert_notes = live_notes
                display_motif["_concert_notes"] = list(concert_notes)
                display_motif["_concert_chord"] = concert_chord
            except ImportError:
                concert_notes = None
        else:
            concert_notes = None
    display_chord = concert_chord
    if concert_auth and spell_display and concert_auth != spell_display:
        try:
            from effective_practice_context import musician_facing_chord

            display_chord = musician_facing_chord(
                concert_chord,
                concert_key=concert_auth,
                chart_key=spell_display,
            )
        except ImportError:
            display_chord = concert_chord
    if concert_auth and spell_display and concert_auth != spell_display and isinstance(concert_notes, list):
        try:
            from effective_practice_context import musician_facing_chord
            from music_theory import semitone_distance
            from improvisation_motif import _midi_from_note, _note_from_midi

            display_chord = musician_facing_chord(
                concert_chord,
                concert_key=concert_auth,
                chart_key=spell_display,
            )
            steps = semitone_distance(concert_auth, spell_display)
            notes = list(concert_notes or [])
            if steps and notes:
                out_notes = []
                for n in notes:
                    midi = _midi_from_note(str(n), 4)
                    out_notes.append(_note_from_midi(midi + steps, spell_display))
                display_motif = dict(display_motif)
                display_motif["notes"] = out_notes
                display_motif["display"] = " – ".join(out_notes)
                display_motif["chord"] = display_chord
            display_motif["_projected_display_key"] = spell_display
            display_motif["_concert_notes"] = list(concert_notes or [])
            display_motif["_concert_chord"] = concert_chord
            display_motif["chord"] = display_chord
        except ImportError:
            pass
    else:
        display_motif["_projected_display_key"] = spell_display
        display_motif["_concert_notes"] = list(concert_notes or [])
        display_motif["_concert_chord"] = concert_chord
        display_motif["chord"] = display_chord
    ref_key = spell_display
    try:
        from harmonic_spelling import harmonic_reference_for_chord

        ref_key = harmonic_reference_for_chord(
            display_chord,
            song_display_key=spell_display,
        )
    except ImportError:
        try:
            from mission_pitch_spelling import coaching_reference_for_mission_chord

            ref_key = coaching_reference_for_mission_chord(
                display_chord,
                song_display_key=spell_display,
            )
        except ImportError:
            pass
    out = rebuild_mission_outputs(
        display_motif,
        chord=display_chord,
        instrument=inst,
        key_center=ref_key,
        bpm=tempo,
        mission=example.mission,
        song_display_key=spell_display,
        song_concert_key=concert_auth or example.concert_key or example.display_key,
    )
    example.instrument = inst
    example.abc = out["abc"]
    example.tab = out["tab"]
    example.piano_html = out["piano_html"]
    example.show_tab = out["show_tab"]
    example.show_piano = out["show_piano"]
    example.motif = out.get("motif") or display_motif
    if isinstance(example.motif, dict):
        example.motif = dict(example.motif)
        if isinstance(concert_notes, list):
            example.motif["_concert_notes"] = list(concert_notes)
        example.motif["_concert_chord"] = concert_chord
        example.motif["_projected_display_key"] = spell_display
        example.motif["chord"] = display_chord
    # Keep example.chord as canonical concert identity; player-facing fields are projections.
    example.chord = concert_chord or str(example.chord or "")
    example.display_key = spell_display or example.display_key
    if concert_auth:
        example.concert_key = concert_auth
    try:
        from improvisation_intelligence import ImprovSessionContext, chord_coach_insight

        try:
            from mission_pitch_spelling import chord_coach_insight_for_mission

            shown_insight = chord_coach_insight_for_mission(
                display_chord,
                song_display_key=spell_display or concert_auth,
                song_key_center=concert_auth or spell_display,
                instrument=inst,
                level=str(example.level or "Intermediate"),
            )
        except ImportError:
            shown_insight = chord_coach_insight(
                display_chord,
                key_center=spell_display or concert_auth,
                instrument=inst,
                level=str(example.level or "Intermediate"),
            )
        example.insight = shown_insight
        fake_ctx = ImprovSessionContext(
            song_title=str(example.song_title or ""),
            artist="",
            key_center=concert_auth or example.concert_key or "C",
            display_key=spell_display or example.display_key or concert_auth or "C",
            instrument=inst,
            level=str(example.level or "Intermediate"),
            focus=str(example.focus or "Improvisation"),
            sections={},
        )
        example.why = _why_it_works(
            example.mission,
            display_chord,
            improv_ctx=fake_ctx,
            section=str(example.section or ""),
            insight=shown_insight,
        )
    except Exception:
        pass
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
    spell_ref = str(improv_ctx.key_center or improv_ctx.display_key or "C")
    try:
        from harmonic_spelling import harmonic_reference_for_chord

        spell_ref = harmonic_reference_for_chord(
            chord,
            song_display_key=improv_ctx.key_center,
            song_key_center=improv_ctx.key_center,
        )
    except ImportError:
        spell_ref = improv_ctx.key_center

    motif = _build_motif_for_mission(
        mission,
        chord,
        key_center=spell_ref,
        level=level,
        variant=variant,
        rng=rng,
        idea_variant=(nonce if variant == "new" else (seed % 1000)),
    )
    motif = sync_motif_midi(motif)
    if isinstance(motif, dict):
        motif = dict(motif)
        motif["_concert_notes"] = list(motif.get("notes") or [])
        motif["_concert_chord"] = str(chord or "").strip()
        motif.pop("_projected_display_key", None)
    concert = str(improv_ctx.key_center or "C").strip() or "C"
    chart = str(improv_ctx.display_key or concert).strip() or concert
    out = rebuild_mission_outputs(
        motif,
        chord=chord,
        instrument=instrument,
        key_center=spell_ref,
        bpm=bpm,
        mission=mission,
        song_display_key=chart,
        song_concert_key=concert,
    )
    motif = out["motif"]
    family = _instrument_family(instrument)
    abc = str(out.get("abc") or "")
    tab = str(out.get("tab") or "")
    piano_html = str(out.get("piano_html") or "")

    insight = chord_coach_insight(
        chord,
        key_center=concert,
        instrument=instrument,
        level=level,
    )

    example = MissionExample(
        mission=mission,
        variant=variant,
        chord=chord,
        section=section,
        song_title=improv_ctx.song_title,
        display_key=chart,
        concert_key=concert,
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
    example = refresh_mission_example(
        example,
        instrument=instrument,
        bpm=bpm,
        song_concert_key=concert,
    )
    shown_chord = chord
    if concert and chart and concert != chart:
        try:
            from effective_practice_context import musician_facing_chord

            shown_chord = musician_facing_chord(chord, concert_key=concert, chart_key=chart)
        except ImportError:
            shown_chord = chord
    try:
        from mission_pitch_spelling import chord_coach_insight_for_mission

        shown_insight = chord_coach_insight_for_mission(
            shown_chord,
            song_display_key=chart,
            song_key_center=concert,
            instrument=instrument,
            level=level,
        )
    except ImportError:
        shown_insight = chord_coach_insight(
            shown_chord,
            key_center=chart,
            instrument=instrument,
            level=level,
        )
    example.insight = shown_insight
    example.why = _why_it_works(
        mission,
        shown_chord,
        improv_ctx=improv_ctx,
        section=section,
        insight=shown_insight,
    )
    return example


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
        "concert_key": str(example.concert_key or ""),
        "display_key": str(example.display_key or ""),
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
    fp = motif_material_fingerprint(example.motif)
    blob_mut_ok = True
    blob_mut_code = ""
    try:
        from music_workflow_mutation import update_mission_example_on_blob

        mut = update_mission_example_on_blob(
            session_state,
            chord=str(example.chord or ""),
            example_fingerprint=fp,
            artifact_fingerprint=str(session_state.get("_mission_example_artifact_id") or "")[:24],
            mission_type=str(example.mission or ""),
            section=str(example.section or ""),
        )
        blob_mut_ok = bool(mut.ok)
        blob_mut_code = str(mut.error_code or "")
    except ImportError:
        pass
    session_state["_mission_example_blob_mutation_ok"] = blob_mut_ok
    session_state["_mission_example_blob_mutation_code"] = blob_mut_code
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


def _transpose_mission_example_payload(raw: dict, *, from_key: str, to_key: str) -> dict | None:
    src = str(from_key or "").strip()
    dest = str(to_key or "").strip()
    if not src or not dest or src == dest or not isinstance(raw, dict):
        return None
    already = str(raw.get("concert_key") or raw.get("display_key") or "").strip()
    if already == dest:
        return None
    from music_theory import semitone_distance, transpose_chord
    from improvisation_motif import _midi_from_note, _note_from_midi

    steps = semitone_distance(src, dest)
    if not steps:
        return None
    out = dict(raw)
    chord = str(out.get("chord") or "").strip()
    if chord:
        out["chord"] = transpose_chord(chord, steps, reference_key=dest)
    motif = dict(out.get("motif") or {})
    notes = list(motif.get("notes") or [])
    if notes:
        existing_midi = list(motif.get("midi") or [])
        out_notes: list[str] = []
        out_midi: list[int] = []
        for i, n in enumerate(notes):
            if i < len(existing_midi) and isinstance(existing_midi[i], (int, float)):
                midi = int(existing_midi[i])
            else:
                midi = _midi_from_note(str(n), 4)
            midi2 = midi + steps
            out_notes.append(_note_from_midi(midi2, dest))
            out_midi.append(midi2)
        motif["notes"] = out_notes
        motif["midi"] = out_midi
        motif["display"] = " – ".join(out_notes)
        if motif.get("chord"):
            motif["chord"] = transpose_chord(str(motif.get("chord")), steps, reference_key=dest)
        concert_notes = motif.get("_concert_notes")
        if isinstance(concert_notes, list) and concert_notes:
            concert_out = []
            for n in concert_notes:
                midi = _midi_from_note(str(n), 4)
                concert_out.append(_note_from_midi(midi + steps, dest))
            motif["_concert_notes"] = concert_out
        concert_chord = str(motif.get("_concert_chord") or "").strip()
        if concert_chord:
            motif["_concert_chord"] = transpose_chord(concert_chord, steps, reference_key=dest)
        motif.pop("_projected_display_key", None)
        try:
            from improvisation_motif import sync_motif_midi

            sync_motif_midi(motif)
        except Exception:
            pass
        out["motif"] = motif
    out["concert_key"] = dest
    out["display_key"] = dest
    # Rebuild ABC immediately so K: / pitches track the new Practice Key
    # (cleared-empty ABC previously left a stale Cm staff until a later refresh).
    try:
        bpm = int(out.get("bpm") or 100)
    except (TypeError, ValueError):
        bpm = 100
    try:
        out["abc"] = build_mission_notation_abc(
            motif if isinstance(out.get("motif"), dict) else {"notes": [], "chord": out.get("chord")},
            mission=str(out.get("mission") or ""),
            key_center=dest,
            bpm=bpm,
        )
    except Exception:
        out["abc"] = ""
    out["tab"] = ""
    out["piano_html"] = ""
    return out


def transpose_stored_mission_practice_lick(
    session_state: dict, *, from_key: str, to_key: str
) -> bool:
    """Transpose sealed Mission Practice lick on Backing with Practice Key.

    The lick panel reads ``MISSION_PRACTICE_LICK_KEY``, not only ``MISSION_EXAMPLE_KEY``.
    Key changes must update both or Notes/MIDI/ABC stay at the old pitch while the
    chord label / sidebar key move.
    """
    raw = session_state.get(MISSION_PRACTICE_LICK_KEY)
    if not isinstance(raw, dict) or not raw.get("motif"):
        return False
    blob = {
        "chord": raw.get("chord") or raw.get("_concert_chord") or "",
        "motif": dict(raw.get("motif") or {}),
        "concert_key": str(raw.get("key_center") or from_key or ""),
        "display_key": str(raw.get("key_center") or from_key or ""),
    }
    transposed = _transpose_mission_example_payload(blob, from_key=from_key, to_key=to_key)
    if transposed is None:
        return False
    out = dict(raw)
    out["chord"] = transposed.get("chord") or out.get("chord")
    out["_concert_chord"] = str(
        (transposed.get("motif") or {}).get("_concert_chord")
        or transposed.get("chord")
        or out.get("_concert_chord")
        or ""
    )
    out["motif"] = transposed.get("motif") or out.get("motif")
    out["key_center"] = str(to_key or "").strip() or out.get("key_center")
    out["abc"] = str(transposed.get("abc") or "")
    out["tab"] = ""
    session_state[MISSION_PRACTICE_LICK_KEY] = out
    try:
        from creative_mission_artifact_persistence import handle_user_mission_practice_lick_saved

        handle_user_mission_practice_lick_saved(
            session_state,
            interaction="transpose_mission_practice_lick",
        )
    except ImportError:
        pass
    return True


def transpose_stored_mission_example(session_state: dict, *, from_key: str, to_key: str) -> bool:
    """Transpose cached Mission example with Practice Key. Concert audio identity follows ``to_key``."""
    raw = session_state.get(MISSION_EXAMPLE_KEY)
    if not isinstance(raw, dict):
        lick_only = transpose_stored_mission_practice_lick(
            session_state, from_key=from_key, to_key=to_key
        )
        return lick_only
    transposed = _transpose_mission_example_payload(raw, from_key=from_key, to_key=to_key)
    if transposed is None:
        return False
    session_state[MISSION_EXAMPLE_KEY] = transposed
    session_state.pop("_mission_example_output_fp", None)
    transpose_stored_mission_practice_lick(session_state, from_key=from_key, to_key=to_key)
    try:
        from pathlib import Path

        motif = dict(transposed.get("motif") or {})
        out = Path(__file__).resolve().parent / "scripts" / "evidence-creative-backing"
        out.mkdir(parents=True, exist_ok=True)
        (out / "_mission_midi_abc_diag.json").write_text(
            __import__("json").dumps(
                {
                    "from_key": from_key,
                    "to_key": to_key,
                    "chord": transposed.get("chord"),
                    "notes": motif.get("notes"),
                    "midi": motif.get("midi"),
                    "abc_k": parse_abc_k_field(str(transposed.get("abc") or "")),
                    "abc_len": len(str(transposed.get("abc") or "")),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass
    return True


def load_mission_example(session_state: dict, improv_ctx: ImprovSessionContext) -> MissionExample | None:
    raw = session_state.get(MISSION_EXAMPLE_KEY)
    if not raw or not isinstance(raw, dict):
        return None
    try:
        from music_workflow_pending_song_practice_key_edit import overlay_destination_practice_key
        from music_workflow_song_practice import resolve_song_practice_key_token

        dest = overlay_destination_practice_key(session_state) or str(
            improv_ctx.key_center or session_state.get("display_key") or ""
        )
        spelled = str(raw.get("concert_key") or "").strip() or resolve_song_practice_key_token(
            session_state
        ) or str(improv_ctx.key_center or session_state.get("concert_key") or "")
        if dest and spelled and dest != spelled:
            overlaid = _transpose_mission_example_payload(raw, from_key=spelled, to_key=dest)
            if overlaid is not None:
                overlaid["concert_key"] = dest
                raw = overlaid
                session_state[MISSION_EXAMPLE_KEY] = overlaid
    except ImportError:
        pass
    chord = str(raw.get("chord", "C"))
    display_chord = chord
    motif_raw = raw.get("motif") if isinstance(raw.get("motif"), dict) else {}
    motif_display_chord = str(motif_raw.get("chord") or "").strip()
    try:
        from effective_practice_context import musician_facing_chord

        concert = str(improv_ctx.key_center or raw.get("concert_key") or "").strip()
        chart = str(improv_ctx.display_key or raw.get("display_key") or concert).strip()
        if concert and chart and concert != chart:
            display_chord = musician_facing_chord(chord, concert_key=concert, chart_key=chart)
        elif motif_display_chord:
            display_chord = motif_display_chord
    except ImportError:
        display_chord = motif_display_chord or chord
    if motif_display_chord and display_chord and motif_display_chord != display_chord:
        # Motif already holds the player-facing spelling for this chart key.
        display_chord = motif_display_chord
    try:
        from mission_pitch_spelling import chord_coach_insight_for_mission

        insight = chord_coach_insight_for_mission(
            display_chord,
            song_display_key=improv_ctx.display_key,
            song_key_center=improv_ctx.key_center,
            instrument=str(session_state.get("instrument", improv_ctx.instrument)),
            level=str(session_state.get("level", improv_ctx.level)),
        )
    except ImportError:
        try:
            insight = chord_coach_insight(
                display_chord,
                key_center=improv_ctx.display_key,
                instrument=str(session_state.get("instrument", improv_ctx.instrument)),
                level=str(session_state.get("level", improv_ctx.level)),
            )
        except Exception:
            insight = _fallback_chord_insight(display_chord)
    except Exception:
        insight = _fallback_chord_insight(display_chord)
    why = _why_it_works(
        str(raw.get("mission", "")),
        display_chord,
        improv_ctx=improv_ctx,
        section=str(raw.get("section", "")),
        insight=insight,
    )
    return MissionExample(
        mission=str(raw.get("mission", "")),
        variant=str(raw.get("variant", "normal")),
        chord=str(raw.get("chord", "")),
        section=str(raw.get("section", "")),
        song_title=improv_ctx.song_title,
        display_key=improv_ctx.display_key,
        concert_key=improv_ctx.key_center,
        instrument=str(session_state.get("instrument", improv_ctx.instrument)),
        level=str(session_state.get("level", improv_ctx.level)),
        focus=str(session_state.get("focus", improv_ctx.focus)),
        motif=dict(raw.get("motif") or {}),
        abc=str(raw.get("abc", "")),
        tab=str(raw.get("tab", "")),
        piano_html=str(raw.get("piano_html", "")),
        why=why,
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
    song_concert_key: str = "",
    session_state: dict | None = None,
    authoritative_concert_key: str = "",
    authoritative_display_key: str = "",
) -> MissionExample:
    """Always rebuild outputs so sheet music / TAB / piano match the current motif."""
    from mission_example_normalization import normalize_mission_example_for_display

    norm = normalize_mission_example_for_display(
        example,
        session_state=session_state,
        authoritative_concert_key=authoritative_concert_key or song_concert_key,
        authoritative_display_key=authoritative_display_key,
        instrument=instrument,
    )
    if not norm.ok or norm.example is None:
        raise ValueError(norm.message or norm.error_code or "MISSION_EXAMPLE_NORMALIZE_FAILED")
    typed = norm.example
    concert = str(song_concert_key or norm.authoritative_concert_key or typed.concert_key or "")
    return refresh_mission_example(
        typed,
        instrument=instrument,
        bpm=bpm,
        song_concert_key=concert,
    )


def store_mission_practice_lick_for_backing(
    session_state: dict,
    *,
    example: MissionExample | dict[str, Any],
    mission_title: str,
    instrument: str,
    bpm: int,
    groove: str,
    meter: str,
    song_title: str,
    section_label: str,
    persist_artifact: bool = True,
    song_concert_key: str = "",
    song_display_key: str = "",
) -> bool:
    """Persist the current mission lick for Mission Backing Jam (single motif source of truth)."""
    from mission_example_normalization import MISSION_BACKING_EXAMPLE_ERROR_KEY, normalize_mission_example_for_display

    norm = normalize_mission_example_for_display(
        example,
        session_state=session_state,
        authoritative_concert_key=song_concert_key,
        authoritative_display_key=song_display_key,
        instrument=instrument,
        mission=mission_title,
        song_title=song_title,
        section=section_label,
    )
    if not norm.ok or norm.example is None:
        session_state[MISSION_BACKING_EXAMPLE_ERROR_KEY] = norm.message or norm.error_code or "MISSION_EXAMPLE_NORMALIZE_FAILED"
        return False
    concert = str(song_concert_key or norm.authoritative_concert_key or norm.example.concert_key or "")
    try:
        ex = mission_example_for_display(
            norm.example,
            instrument=instrument,
            bpm=bpm,
            song_concert_key=concert,
            session_state=session_state,
            authoritative_concert_key=song_concert_key,
            authoritative_display_key=song_display_key,
        )
    except ValueError as exc:
        session_state[MISSION_BACKING_EXAMPLE_ERROR_KEY] = str(exc)
        return False
    session_state.pop(MISSION_BACKING_EXAMPLE_ERROR_KEY, None)
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
        "_concert_chord": str((ex.motif or {}).get("_concert_chord") or ex.chord or ""),
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
    return True


def mission_practice_lick_payload(session_state: dict) -> dict[str, Any] | None:
    raw = session_state.get(MISSION_PRACTICE_LICK_KEY)
    return raw if isinstance(raw, dict) and raw.get("motif") else None


def clear_mission_practice_lick_handoff(session_state: dict) -> None:
    session_state.pop(IMPROV_MISSION_PRACTICE_LICK_HANDOFF, None)


def queue_mission_practice_lick_handoff(session_state: dict) -> None:
    session_state[IMPROV_MISSION_PRACTICE_LICK_HANDOFF] = True
