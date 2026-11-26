"""Generation engine for Practice Melody.

Composes a new, song-specific practice melody for an existing Catalog/Custom
song's chart — NOT a generic improvisation generator, and NOT a
reconstruction/approximation of any copyrighted original melody. The
generator only ever reads **chord symbols, key, meter, tempo and section
structure** that the app already owns for the song; it has no access to,
and never receives, any actual recorded/transcribed melody data. That is a
structural guarantee against reproducing a real song's melody, not just a
policy statement.

This module is independent of:
  * ``improvisation_motif.py`` / ``motif_engine.py`` — the Motif/Phrase
    pattern-vocabulary system, which generates short improvisation patterns
    with no bar/beat timeline. Practice Melody is a *composed, whole-song*
    melody with an explicit measure/beat structure (see
    ``practice_melody_model.py``).
  * ``composition_melody_suggestions.py`` — Composition Studio's melody
    generator for songs a user is *writing*. Practice Melody generates over
    an existing chart the user is *rehearsing*.

The notes themselves come from ``practice_melody_composer`` (phrases, motif,
style rhythms, focus), which reuses the app's theory primitives;
``practice_studio.practice_section_type`` normalizes section types. It does not resolve or own a key — the caller
supplies ``key_center`` (from ``songs/key_state.py``'s resolver).
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import replace

from practice_melody_composer import compose_section, mark_events, note_intent
from practice_melody_model import MelodyEvent, MelodySection, PracticeMelody, SCHEMA_VERSION

try:
    from practice_studio import practice_section_type
except ImportError:  # pragma: no cover - defensive fallback if practice_studio's
    # heavier Streamlit-adjacent imports are ever unavailable in a minimal context.
    import re as _re

    _TRAIL = _re.compile(r"\s+\d+[A-Za-z]?\s*$")

    def practice_section_type(section_name: str | None) -> str:  # type: ignore[misc]
        s = str(section_name or "").strip()
        return _TRAIL.sub("", s).strip() or s


GENERATOR_VERSION = "practice-melody-gen-2"

# Comfortable register per level (MIDI). Advanced gets a wider window but all
# three stay in a singable range — this is a *practice* melody, not an
# instrumental solo.
_LEVEL_RANGE: dict[str, tuple[int, int]] = {
    "Beginner": (60, 74),       # C4 - D5
    "Intermediate": (57, 77),   # A3 - F5
    "Advanced": (55, 81),       # G3 - A5
}


def register_window(level: str, instrument: str = "", written_offset: int = 0) -> tuple[int, int]:
    """(low, high) MIDI for a Practice Melody: the level's comfortable window, placed inside the instrument's
    own comfortable register.

    ``instrument`` is the selected instrument / saxophone type (``"Alto saxophone (Eb)"``, ``"Flute"`` ...).
    ``written_offset`` is how far the melody's pitch domain sits BELOW written pitch: 0 when the melody is in the
    written chart (or the instrument does not transpose), the transposition (e.g. 9 for an Eb saxophone, 2 for a Bb
    one) when the chart is in concert pitch - so a concert-pitch range check never compares against written pitch.
    Only melodic wind families are constrained; piano, guitar and bass keep the level window.
    """
    lo, hi = _LEVEL_RANGE.get(level, _LEVEL_RANGE["Intermediate"])
    if not instrument:
        return lo, hi
    try:
        from instrument_register_fit import comfortable_written_range

        rng = comfortable_written_range(instrument, level)
    except Exception:
        rng = None
    if rng is None:
        return lo, hi
    ilo, ihi = int(rng[0]) - int(written_offset), int(rng[1]) - int(written_offset)
    nlo, nhi = max(lo, ilo), min(hi, ihi)
    if nhi - nlo >= 12:
        return nlo, nhi
    # The level window and the instrument's comfortable register barely overlap (e.g. a baritone saxophone
    # is far below a generic C4-D5): follow the instrument, keeping the level's width.
    width = max(12, hi - lo)
    nlo = max(ilo, min(lo, ihi - 12))
    return nlo, min(ihi, nlo + width)


_START_MIDI: dict[str, int] = {"Beginner": 67, "Intermediate": 65, "Advanced": 64}


def _is_compound(meter: tuple[int, int] | None) -> bool:
    return bool(meter) and int(meter[1]) == 8 and int(meter[0]) % 3 == 0


def _chord_at_factory(beats_per_measure: float):
    """The chord sounding at a beat of a bar token (``C|F``, ``C:3|G:1``, a hit ...)."""
    from chord_subdivisions import bare_chord_token, chord_at_beat, hit_underlying_chord, is_hit_token

    def at(token: str, beat: float) -> str:
        if is_hit_token(token):
            return str(hit_underlying_chord(token) or token)
        found = str(chord_at_beat(token, beat, beats_per_bar=beats_per_measure) or "")
        return str(bare_chord_token(found or token) or found or token)

    return at


def _is_silent(token: str) -> bool:
    t = str(token or "").strip().upper().replace(" ", "")
    return t in {"N.C.", "NC", "N.C"}


def _seed_for(song_id: str, level: str, alt_index: int, explicit_seed: int | None) -> int:
    if explicit_seed is not None:
        return int(explicit_seed)
    digest = hashlib.sha256(f"{song_id}|{level}|{alt_index}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _melody_id(song_id: str, level: str, alt_index: int, seed: int) -> str:
    return f"pm:{song_id}:{level.lower()}:{alt_index}:{seed:x}"


def generate_practice_melody(
    *,
    song_id: str,
    song_title: str,
    sections: dict[str, list[str]],
    section_order: list[str] | None = None,
    key_center: str,
    level: str,
    tempo_bpm: float = 100.0,
    style: str = "",
    meter: tuple[int, int] = (4, 4),
    seed: int | None = None,
    alt_index: int = 0,
    focus: str = "",
    instrument: str = "",
    written_offset: int = 0,
) -> PracticeMelody:
    """Generate a structured Practice Melody for one song, level and alternative.

    ``sections`` follows the existing Catalog/Custom convention: one chord
    symbol per measure, keyed by section name (e.g. ``{"Verse 1": ["G",
    "Em7", ...]}``). This function never mutates or resolves the song's key —
    ``key_center`` is supplied by the caller.

    Reproducible by construction: with an explicit ``seed`` the output is
    byte-identical across runs; without one, a seed is derived deterministically
    from ``(song_id, level, alt_index)`` so the same call always reproduces the
    same melody, while a different ``alt_index`` reliably yields a different
    (but still level/song-appropriate) alternative — the mechanism "Generate
    Another Melody" will build on in a later slice.
    """
    if level not in _LEVEL_RANGE:
        level = "Intermediate"

    order = list(section_order) if section_order else list(sections.keys())
    ordered_names = [name for name in order if name in sections]
    ordered_names += [name for name in sections if name not in ordered_names]

    resolved_seed = _seed_for(song_id, level, alt_index, seed)
    rng = random.Random(resolved_seed)
    beats_per_measure = float(meter[0]) if meter and meter[0] else 4.0
    window = register_window(level, instrument, written_offset)
    prev_end_midi = min(max(_START_MIDI[level], window[0]), window[1])
    intent = note_intent(focus)
    compound = _is_compound(meter)
    chord_at = _chord_at_factory(beats_per_measure)

    generated_by_chords: dict[tuple[str, ...], MelodySection] = {}
    out_sections: list[MelodySection] = []

    for name in ordered_names:
        chords = [str(c) for c in (sections.get(name) or [])]
        if not chords:
            continue
        chord_key = tuple(chords)
        existing = generated_by_chords.get(chord_key)
        if existing is not None:
            # Deliberate repeat handling: reuse the earlier section's melody
            # verbatim rather than generating a fresh (and possibly
            # incoherent) one for an identical repeated progression.
            repeated = replace(existing, section_id=name, repeat_of=existing.section_id)
            out_sections.append(repeated)
            if repeated.events:
                last_sounding = [e for e in repeated.events if not e.is_rest]
                if last_sounding:
                    prev_end_midi = last_sounding[-1].midi  # type: ignore[assignment]
            continue

        # A bar nobody plays a chord in is a bar of rest; its neighbours keep their own harmony.
        playable = [c for c in chords if not _is_silent(c)]
        sounding = [c if not _is_silent(c) else (playable[0] if playable else "C") for c in chords]
        events, prev_end_midi = compose_section(
            chords=sounding,
            key_center=key_center,
            level=level,
            tempo_bpm=tempo_bpm,
            beats_per_measure=beats_per_measure,
            rng=rng,
            start_midi=prev_end_midi,
            style=style,
            intent=intent,
            register=window,
            compound=compound,
            chord_at=chord_at,
        )
        if len(playable) != len(chords):
            events = [e for e in events if not _is_silent(chords[e.measure])] + [
                MelodyEvent(measure=m, beat=0.0, duration_beats=beats_per_measure, is_rest=True, chord=c, tone_role="rest")
                for m, c in enumerate(chords)
                if _is_silent(c)
            ]
            events.sort(key=lambda e: (e.measure, e.beat))
        events = mark_events(events, level=level, style=style, focus=focus, bars=len(chords))
        section = MelodySection(
            section_id=name,
            section_type=practice_section_type(name),
            measures=len(chords),
            beats_per_measure=beats_per_measure,
            chords=tuple(chords),
            events=tuple(events),
            repeat_of=None,
        )
        generated_by_chords[chord_key] = section
        out_sections.append(section)

    return PracticeMelody(
        schema_version=SCHEMA_VERSION,
        melody_id=_melody_id(song_id, level, alt_index, resolved_seed),
        source="generated",
        song_id=song_id,
        song_title=song_title,
        level=level,
        key_center=key_center,
        meter=(int(meter[0]), int(meter[1])),
        tempo_bpm=float(tempo_bpm),
        style=style,
        seed=resolved_seed,
        alt_index=alt_index,
        generator_version=GENERATOR_VERSION,
        section_order=tuple(s.section_id for s in out_sections),
        sections=tuple(out_sections),
        focus=focus,
    )


def generate_another_practice_melody(
    previous: PracticeMelody, **overrides: object
) -> PracticeMelody:
    """Produce the next alternative for the same song/level — the backend for
    a future "Generate Another Melody" action. Deterministic: calling this
    twice on the same ``previous`` melody (with no overrides) always yields
    the same next alternative.
    """
    kwargs: dict[str, object] = dict(
        song_id=previous.song_id,
        song_title=previous.song_title,
        sections={s.section_id: list(s.chords) for s in previous.sections},
        section_order=list(previous.section_order),
        key_center=previous.key_center,
        level=previous.level,
        tempo_bpm=previous.tempo_bpm,
        style=previous.style,
        meter=previous.meter,
        seed=None,
        alt_index=previous.alt_index + 1,
        focus=previous.focus,
    )
    kwargs.update(overrides)
    return generate_practice_melody(**kwargs)  # type: ignore[arg-type]
