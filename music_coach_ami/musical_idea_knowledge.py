"""Compose musician-facing musical ideas (patterns / licks / phrases) for AMI."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from music_coach_ami.types import CoachRequest

_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "intro": ("intro", "introduction"),
    "verse": ("verse",),
    "chorus": ("chorus", "refrain"),
    "pre-chorus": ("pre-chorus", "prechorus", "pre chorus"),
    "bridge": ("bridge",),
    "solo": ("solo", "instrumental"),
    "outro": ("outro", "ending", "coda"),
    "groove": ("groove",),
    "a": ("a", "section a"),
    "b": ("b", "section b"),
    "c": ("c", "section c"),
}


def is_musical_idea_content_request(normalized: str, low: str) -> bool:
    if not any(w in low for w in ("give me", "show me", "write", "make me")):
        return False
    if any(w in low for w in ("lick", "phrase", "pattern", "riff", "sequence")):
        return True
    if "bars" in low and any(w in low for w in ("minor", "major", "dorian", "blues", "scale")):
        return True
    return False


def extract_requested_section(question: str) -> str:
    low = str(question or "").lower()
    m = re.search(
        r"\bover (?:the )?(intro|verse|chorus|pre[- ]?chorus|bridge|solo|outro|groove|[abc])\b",
        low,
    )
    if not m:
        m = re.search(
            r"\b(?:for|on) (?:the )?(intro|verse|chorus|pre[- ]?chorus|bridge|solo|outro|groove)\b",
            low,
        )
    if not m:
        return ""
    token = re.sub(r"\s+", "-", m.group(1).strip().lower())
    if token == "prechorus":
        token = "pre-chorus"
    return token


def resolve_chart_section(
    requested: str,
    *,
    chart_sections: dict[str, Any] | None,
    fallback_section: str = "",
    fallback_chords: list[str] | None = None,
) -> dict[str, Any]:
    """Honor explicit section names; never silently substitute another section."""
    sections = chart_sections if isinstance(chart_sections, dict) else {}
    names = [str(k) for k in sections.keys() if str(k).strip()]
    if not requested:
        chords = list(fallback_chords or [])
        if not chords and fallback_section and fallback_section in sections:
            chords = list(sections.get(fallback_section) or [])
        return {
            "ok": True,
            "section": fallback_section or "",
            "chords": chords,
            "explicit": False,
            "available": names,
        }

    req = requested.lower().strip()
    aliases = _SECTION_ALIASES.get(req, (req,))
    for name in names:
        nlow = name.lower().strip()
        if nlow == req or nlow in aliases or any(a == nlow for a in aliases):
            return {
                "ok": True,
                "section": name,
                "chords": list(sections.get(name) or []),
                "explicit": True,
                "available": names,
            }
        # "Verse 1" matches verse
        if any(nlow.startswith(a) for a in aliases if len(a) > 1):
            return {
                "ok": True,
                "section": name,
                "chords": list(sections.get(name) or []),
                "explicit": True,
                "available": names,
            }
    return {
        "ok": False,
        "section": "",
        "chords": [],
        "explicit": True,
        "requested": requested,
        "available": names,
        "message": (
            f"This chart doesn't have a section labeled **{requested.title()}**. "
            + (
                f"Available sections: {', '.join(names)}."
                if names
                else "No section map is available in the current chart context."
            )
        ),
    }


def _transpose_composition_preserving_degrees(composition: Any, written_key: str, steps: int, profile: Any) -> Any:
    """Transpose events by semitone while keeping degree metadata; spell in written key family."""
    from music_coach_ami.musical_idea_engine import (
        MusicalEvent,
        MusicalIdeaComposition,
        _place_spelled_note,
        authoritative_scale_degrees,
    )
    from music_theory import pitch_class_from_spelled_note, spell_note_in_key

    tonality = composition.tonality
    written_tonic = written_key.rstrip("m")
    # Build written-domain scale spelling when tonality is known.
    written_scale: list[str] = []
    if tonality:
        written_scale = authoritative_scale_degrees(written_tonic, tonality)

    low = int(getattr(profile, "midi_low", 60) or 60)
    high = int(getattr(profile, "midi_high", 84) or 84)
    prefer = (low + high) // 2
    prev_midi: int | None = None

    new_events: list[MusicalEvent] = []
    for ev in composition.events:
        if written_scale and ev.scale_degree:
            idx = (int(ev.scale_degree) - 1) % len(written_scale)
            spelled = written_scale[idx]
        else:
            pc = (pitch_class_from_spelled_note(ev.spelled) + steps) % 12
            spelled = spell_note_in_key(pc, written_key)
        spelled2, octv, midi = _place_spelled_note(
            spelled,
            prefer_midi=prefer,
            low=low,
            high=high,
            direction="ascending",
            previous_midi=prev_midi,
        )
        new_events.append(
            MusicalEvent(
                spelled=spelled2,
                octave=octv,
                duration=ev.duration,
                bar_index=ev.bar_index,
                beat=ev.beat,
                articulation=ev.articulation,
                scale_degree=ev.scale_degree,
                pitch_class=pitch_class_from_spelled_note(spelled2),
                chord=ev.chord,
                role=ev.role,
                cell_index=ev.cell_index,
                domain="written",
            )
        )
        prev_midi = midi
        prefer = midi + 1
    written_tonality = tonality
    return MusicalIdeaComposition(
        events=tuple(new_events),
        reference_key=written_tonic,
        meter=composition.meter,
        bars=composition.bars,
        object_type=composition.object_type,
        style=composition.style,
        notation_profile=profile,
        strategy=composition.strategy + "+written",
        tonic=written_tonic,
        tonality=written_tonality,
        scale_spelling=tuple(written_scale) if written_scale else composition.scale_spelling,
    )


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
    active_section = str(chart.get("active_section") or req.context.active_section or "").strip()
    chart_sections = None
    for key in ("chart_sections", "sections"):
        raw = chart.get(key)
        if isinstance(raw, dict) and raw:
            chart_sections = raw
            break
    if chart_sections is None and isinstance(extra.get("chart_sections"), dict):
        chart_sections = extra.get("chart_sections")

    q_text = req.raw_question or req.normalized_question
    requested_section = extract_requested_section(q_text)
    section_resolve = resolve_chart_section(
        requested_section,
        chart_sections=chart_sections,
        fallback_section=active_section,
        fallback_chords=list(chart.get("active_section_chords") or []),
    )

    idea = resolve_musical_idea_request(
        q_text,
        default_object="lick",
        instrument=instrument,
        level=level,
        practice_focus=focus,
        meter=meter,
        tempo_bpm=bpm,
        section=str(section_resolve.get("section") or active_section),
        duration_minutes=req.constraints.requested_duration_minutes,
    )
    if not idea.bars:
        idea = replace(idea, bars=4)
    if requested_section:
        idea = replace(idea, section=str(section_resolve.get("section") or ""), song_relative=True)

    if section_resolve.get("explicit") and not section_resolve.get("ok"):
        msg = str(section_resolve.get("message") or "That section is not on this chart.")
        return {
            "direct_answer": msg,
            "practice_steps": [
                "Open the active song chart and pick a listed section, or name one of the available sections in your question."
            ],
            "what_to_listen_for": [],
            "suggested_next_action": "Ask again with one of the available section names.",
            "notation_abc": "",
            "notation_abc_sections": [],
            "diagnostics": {
                "musical_idea_content": True,
                "section_resolution": section_resolve,
                "fallback_reason": "section_not_found",
                **musical_idea_to_diagnostics(idea),
            },
        }

    concert_key = str(
        idea.explicit_key
        or chart.get("practice_key")
        or req.context.current_practice_key
        or "C"
    ).strip()
    concert_chords = list(section_resolve.get("chords") or [])
    section_label = str(section_resolve.get("section") or active_section or "").strip()

    # Choose generator
    if idea.object_type == "pattern" or (
        idea.object_type in {"", "general"}
        and idea.tonality
        and "pattern" in (req.normalized_question or "").lower()
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
            where = section_label or "the active section"
            label = f"{idea.bars}-bar phrase over {where}"
    else:
        composition = generate_lick(idea, notation_instrument=notation_inst)
        key_bit = f" in {idea.explicit_key}" if idea.explicit_key else ""
        ton_bit = f" {idea.tonality}" if idea.tonality else ""
        label = f"{idea.bars}-bar {idea.object_type}{ton_bit}{key_bit}".strip()

    written_ctx = build_written_music_context(
        instrument=instrument,
        practice_concert_key=concert_key if not idea.explicit_key else (
            idea.explicit_key if not str(idea.tonality).endswith("minor") else idea.explicit_key
        ),
        original_song_key=str(req.context.song_original_key or concert_key),
        concert_chords=concert_chords[: composition.bars] if concert_chords else [],
        session_state=session_ref,
        register=idea.register,
        chart_already_in_practice_key=bool(chart.get("sections_in_practice_key")),
        chart_source=str(chart.get("chart_source") or ""),
    )

    concert_tonic = composition.tonic or idea.explicit_key or concert_key
    concert_tonality = composition.tonality or idea.tonality or ""
    written_note = ""
    if (
        written_ctx.written_transposition_applied
        and written_ctx.written_key
        and written_ctx.written_key.rstrip("m") != str(concert_tonic).rstrip("m")
    ):
        composition = _transpose_composition_preserving_degrees(
            composition,
            written_ctx.written_key,
            int(written_ctx.transposition_semitones),
            written_ctx.notation_profile,
        )
        ton_label = (concert_tonality or "idea").strip()
        written_note = (
            f"Concert **{concert_tonic}** {ton_label} — "
            f"written **{composition.tonic}** {composition.tonality or ton_label} "
            f"for **{notation_inst}**"
        ).replace("  ", " ").strip()

    bpm_out = int(idea.tempo_bpm or bpm or 96)
    if written_note and composition.tonic:
        ton_title = (composition.tonality or concert_tonality or label).replace("_", " ").title()
        title = f"{ton_title} In {composition.tonic} (written)"
    else:
        title = label.title()
    abc, abc_diag = composition_to_abc(composition, title=title, bpm=bpm_out)

    ton = idea.tonality or composition.tonality or composition.style
    if written_note and idea.explicit_key:
        direct = f"**Try this {idea.bars}-bar {ton} idea**\n\n{written_note}"
    elif idea.explicit_key and ton:
        direct = f"**Try this {idea.bars}-bar {ton} pattern in {idea.explicit_key}:**"
    else:
        direct = f"**Try this {label.strip()}:**"

    steps = [
        f"**{composition.object_type.replace('_', ' ').title()}** — read the staff notation below.",
        "**How to play it**",
        *play_summary(composition),
    ]
    if written_note:
        steps.insert(1, written_note)
    listen = [
        "Even rhythm across the bar line",
        "Clean direction changes" if idea.direction else "Clear phrase shape",
        "Target notes land with intention",
        "Tone and articulation match your practice focus",
    ]

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
        "section_resolution": section_resolve,
        "chart_in_instrument_key": bool(session_ref.get("show_chart_in_instrument_key"))
        if isinstance(session_ref, dict)
        else None,
        **realization_diagnostics(instrument, session_state=session_ref),
        **musical_idea_to_diagnostics(idea),
        **composition_diagnostics(composition),
        **abc_diag,
    }
    return {
        "direct_answer": direct,
        "practice_steps": steps,
        "what_to_listen_for": listen,
        "suggested_next_action": (
            "Loop the line at a slower tempo, then raise BPM by 4–8 once it is clean three times."
        ),
        "notation_abc": abc,
        "notation_abc_sections": [abc] if abc else [],
        "diagnostics": diag,
    }
