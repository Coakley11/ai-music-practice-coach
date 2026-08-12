"""Compose musician-facing musical ideas (patterns / licks / phrases) for AMI."""

from __future__ import annotations

from typing import Any

from music_coach_ami.types import CoachRequest


def is_musical_idea_content_request(normalized: str, low: str) -> bool:
    if not any(w in low for w in ("give me", "show me", "write", "make me")):
        return False
    if any(w in low for w in ("lick", "phrase", "pattern", "riff", "sequence")):
        return True
    if "bars" in low and any(w in low for w in ("minor", "major", "dorian", "blues", "scale")):
        return True
    return False


def compose_musical_idea_suggestion(req: CoachRequest) -> dict[str, Any]:
    from music_coach_ami.instrument_realization import (
        notation_instrument_name,
        realization_diagnostics,
    )
    from music_coach_ami.musical_idea_engine import (
        composition_diagnostics,
        composition_to_abc,
        generate_lick,
        generate_phrase_over_chords,
        generate_scale_pattern,
        generate_sequence,
        play_summary,
    )
    from music_coach_ami.musical_idea_request import (
        musical_idea_to_diagnostics,
        resolve_musical_idea_request,
    )
    from music_coach_ami.request_resolution import display_coach_instrument
    from music_coach_ami.written_music_context import build_written_music_context

    raw_instrument = str(req.entities.instrument or req.context.instrument or "").strip()
    instrument = display_coach_instrument(raw_instrument)
    if instrument.lower() == "your instrument":
        instrument = raw_instrument or "Piano"

    extra = req.context.extra if isinstance(req.context.extra, dict) else {}
    session_ref = extra.get("session_ref")
    if session_ref is not None:
        try:
            from music_coach_ami.session_access import as_mutable_session

            session_ref = as_mutable_session(session_ref)
        except ImportError:
            session_ref = session_ref if isinstance(session_ref, dict) else {}
    else:
        session_ref = {}

    real = realization_diagnostics(instrument, session_state=session_ref)
    notation_inst = notation_instrument_name(
        instrument,
        session_state=session_ref,
        transposing_subtype=str(real.get("selected_transposing_subtype") or ""),
    )

    level = str(req.context.level or "Intermediate").strip()
    focus = str(req.context.practice_focus or "").strip()
    chart = extra.get("chart_snapshot") if isinstance(extra.get("chart_snapshot"), dict) else {}
    meter = str(chart.get("chart_meter") or "4/4")
    bpm = int(chart.get("bpm") or req.context.tempo_bpm or 96)
    section = str(chart.get("active_section") or req.context.active_section or "").strip()

    idea = resolve_musical_idea_request(
        req.raw_question or req.normalized_question,
        default_object="lick",
        instrument=instrument,
        level=level,
        practice_focus=focus,
        meter=meter,
        tempo_bpm=bpm,
        section=section,
        duration_minutes=req.constraints.requested_duration_minutes,
    )
    if not idea.bars:
        from dataclasses import replace

        idea = replace(idea, bars=4)

    concert_key = str(
        idea.explicit_key
        or chart.get("practice_key")
        or req.context.current_practice_key
        or "C"
    ).strip()
    concert_chords = list(chart.get("active_section_chords") or [])

    # Choose generator
    if idea.object_type == "pattern" or (
        idea.object_type in {"", "general"} and idea.tonality and "pattern" in (req.normalized_question or "").lower()
    ):
        composition = generate_scale_pattern(idea, notation_instrument=notation_inst)
        label = f"{idea.bars}-bar {idea.tonality or idea.style or 'scale'} pattern"
    elif idea.object_type == "sequence":
        composition = generate_sequence(idea, notation_instrument=notation_inst)
        label = f"{idea.bars}-bar sequence"
    elif idea.song_relative or (idea.object_type == "phrase" and concert_chords and not idea.explicit_key):
        if not concert_chords:
            composition = generate_lick(idea, notation_instrument=notation_inst)
            label = f"{idea.bars}-bar phrase"
        else:
            composition = generate_phrase_over_chords(
                idea,
                concert_chords,
                notation_instrument=notation_inst,
                reference_key=concert_key,
            )
            label = f"{idea.bars}-bar phrase over the active section"
    else:
        composition = generate_lick(idea, notation_instrument=notation_inst)
        key_bit = f" in {idea.explicit_key}" if idea.explicit_key else ""
        ton_bit = f" {idea.tonality}" if idea.tonality else ""
        label = f"{idea.bars}-bar {idea.object_type}{ton_bit}{key_bit}".strip()

    # Written transformation for transposing instruments when we have a concert key.
    written_ctx = build_written_music_context(
        instrument=instrument,
        practice_concert_key=concert_key,
        original_song_key=str(req.context.song_original_key or concert_key),
        concert_chords=concert_chords[: composition.bars] if concert_chords else [],
        session_state=session_ref,
        register=idea.register,
        chart_already_in_practice_key=bool(chart.get("sections_in_practice_key")),
        chart_source=str(chart.get("chart_source") or ""),
    )
    # For standalone tonal ideas, written key may differ; re-spell events into written key.
    if written_ctx.written_transposition_applied and written_ctx.written_key != composition.reference_key:
        from music_theory import pitch_class_from_spelled_note, spell_note_in_key
        from music_coach_ami.musical_idea_engine import MusicalEvent, MusicalIdeaComposition

        steps = int(written_ctx.transposition_semitones)
        new_events = []
        for ev in composition.events:
            pc = (pitch_class_from_spelled_note(ev.spelled) + steps) % 12
            spelled = spell_note_in_key(pc, written_ctx.written_key)
            new_events.append(
                MusicalEvent(
                    spelled=spelled,
                    octave=ev.octave,
                    duration=ev.duration,
                    bar_index=ev.bar_index,
                    beat=ev.beat,
                    articulation=ev.articulation,
                    scale_degree=ev.scale_degree,
                    chord=ev.chord,
                    role=ev.role,
                )
            )
        composition = MusicalIdeaComposition(
            events=tuple(new_events),
            reference_key=written_ctx.written_key,
            meter=composition.meter,
            bars=composition.bars,
            object_type=composition.object_type,
            style=composition.style,
            notation_profile=written_ctx.notation_profile,
            strategy=composition.strategy + "+written",
        )

    bpm_out = int(idea.tempo_bpm or bpm or 96)
    abc = composition_to_abc(composition, title=label.title(), bpm=bpm_out)
    key_label = composition.reference_key
    ton = idea.tonality or composition.style
    direct = f"**Try this {label.strip()}:**"
    if idea.explicit_key and ton:
        direct = f"**Try this {idea.bars}-bar {ton} pattern in {idea.explicit_key}:**"

    steps = [
        f"**{composition.object_type.replace('_', ' ').title()}** — read the staff notation below.",
        "**How to play it**",
        *play_summary(composition),
    ]
    listen = [
        "Even rhythm across the bar line",
        "Clean direction changes" if idea.direction else "Clear phrase shape",
        "Target notes land with intention",
        "Tone and articulation match your practice focus",
    ]
    next_action = (
        "Loop the line at a slower tempo, then raise BPM by 4–8 once it is clean three times."
    )

    diag = {
        "musical_idea_content": True,
        "resolved_instrument": instrument,
        "notation_instrument": notation_inst,
        "practice_concert_key": concert_key,
        "written_key": written_ctx.written_key,
        "notation_abc_present": bool(abc),
        "bars_generated": composition.bars,
        "notation_clef": composition.notation_profile.clef,
        "written_music_context": written_ctx.to_diagnostics(),
        **realization_diagnostics(instrument, session_state=session_ref),
        **musical_idea_to_diagnostics(idea),
        **composition_diagnostics(composition),
        "abc_key_field": next((ln for ln in abc.splitlines() if ln.startswith("K:")), None),
    }
    return {
        "direct_answer": direct,
        "practice_steps": steps,
        "what_to_listen_for": listen,
        "suggested_next_action": next_action,
        "notation_abc": abc,
        "notation_abc_sections": [abc] if abc else [],
        "diagnostics": diag,
    }
