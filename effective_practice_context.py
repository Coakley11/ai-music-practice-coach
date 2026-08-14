"""Single effective practice key + transposed sections for all coaching surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from improvisation_intelligence import coaching_reference_key
from music_theory import semitone_distance, transpose_chord, transpose_sections_dict


def musician_facing_chart_key(session: dict[str, Any], concert_key: str = "") -> str:
    """Written or guitar-shape chart key for the given concert Practice Key.

    Shape Key is tonic-only; major/minor is inherited from ``concert_key``.
    Does not replace canonical concert identity with a stale resolver chart key.
    """
    from instrument_transposition import effective_chart_key
    from songs.key_state import resolve_active_musical_key

    musical = resolve_active_musical_key(session, surface="musician_facing_chart")
    concert = str(concert_key or musical.practice_concert_key or "C").strip() or "C"
    inst = str(musical.instrument or session.get("instrument") or "Piano").strip() or "Piano"
    try:
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY, shape_chart_key_for_concert

        if inst == "Guitar" and session.get(CAPO_ENABLED_KEY):
            shape = str(session.get(CAPO_SHAPE_KEY) or "").strip()
            if shape:
                return shape_chart_key_for_concert(concert, shape)
    except ImportError:
        pass
    chart, _mode = effective_chart_key(concert, inst, session)
    return str(chart or concert).strip() or concert


def musician_facing_chord(chord: str, *, concert_key: str, chart_key: str) -> str:
    """Transpose one concert chord symbol into the player-facing chart key."""
    src = str(chord or "").strip()
    concert = str(concert_key or "").strip()
    chart = str(chart_key or "").strip()
    if not src or not concert or not chart or concert == chart:
        return src
    steps = semitone_distance(concert, chart)
    if not steps:
        return src
    return transpose_chord(src, steps, reference_key=chart)


@dataclass(frozen=True)
class EffectivePracticeContext:
    original_key: str
    practice_concert_key: str
    chart_key: str
    written_key: str
    chart_key_mode: str
    instrument: str
    sections_original: dict[str, list[str]]
    sections_concert: dict[str, list[str]]
    sections_chart: dict[str, list[str]]
    coaching_reference_key: str


def build_effective_practice_context(
    session: dict[str, Any],
    *,
    original_key: str,
    sections: dict[str, list[str]],
    instrument: str,
    song_data: dict[str, Any] | None = None,
) -> EffectivePracticeContext:
    """Original catalog sections → concert practice key → chart/written display key."""
    from backing_context import sections_dict_for_chart_display
    from songs.key_state import resolve_active_musical_key

    musical = resolve_active_musical_key(
        session,
        rec=song_data,
        instrument=instrument,
        surface="effective_practice_context",
    )
    orig = str(original_key or musical.original_key or "C").strip() or "C"
    try:
        from practice_key_mode import resolve_practice_concert_key_for_song

        concert = resolve_practice_concert_key_for_song(
            session,
            orig,
            fallback=str(musical.practice_concert_key or "C"),
        )
    except ImportError:
        concert = str(musical.practice_concert_key or "C").strip() or "C"
    inst = str(instrument or musical.instrument or "Piano").strip() or "Piano"
    chart_key = str(musical.chart_key or concert).strip() or concert
    chart_mode = str(musical.chart_key_mode or "concert")
    written_key = str(musical.written_key or "").strip()
    try:
        from instrument_transposition import (
            chart_in_instrument_key,
            effective_chart_key,
            is_transposing_instrument,
        )

        if is_transposing_instrument(inst) and chart_in_instrument_key(session):
            chart_key, chart_mode = effective_chart_key(concert, inst, session)
            from instrument_transposition import written_key_for_instrument

            written_key = written_key_for_instrument(concert, inst, session)
    except ImportError:
        pass
    sec_orig = {k: list(v or []) for k, v in (sections or {}).items()}
    if orig != concert:
        sections_concert = transpose_sections_dict(sec_orig, orig, concert)
    else:
        sections_concert = dict(sec_orig)
    sections_chart = sections_dict_for_chart_display(
        session,
        sections_concert,
        concert_key=concert,
    )
    ref = coaching_reference_key(
        key_center=concert,
        display_key=chart_key,
    )
    return EffectivePracticeContext(
        original_key=orig,
        practice_concert_key=concert,
        chart_key=chart_key,
        written_key=written_key,
        chart_key_mode=chart_mode,
        instrument=inst,
        sections_original=sec_orig,
        sections_concert=sections_concert,
        sections_chart=sections_chart,
        coaching_reference_key=ref,
    )


def verse_cycle_from_sections(sections: dict[str, list[str]]) -> list[str]:
    """First four unique chords in section order (deduped) for tests and copy."""
    from deep_harmonic_analyzer import single_progression_cycle

    for _name, chords in sections.items():
        cycle = single_progression_cycle(list(chords or []))
        if cycle:
            return cycle[:4]
    return []
