"""Renders a ``practice_melody_model.PracticeMelody`` as ABC notation.

This is deliberately a thin adapter onto the *existing* ABC pipeline
(``composition_melody_notation.build_abc_from_melody_events`` +
``streamlit_music_practice_app.render_abc``, the same abcjs renderer already
used for the Practice page's Notation/TAB tool) rather than a second
notation system: Composition's melody-event builder already accepts events
shaped as ``{pitch, is_rest, duration_beats}`` dicts with an optional chord
annotation list, which is effectively the event shape this app settled on
for Practice Melody too (see practice_melody_model.py's docstring on why).

The one bridging step needed is pitch spelling: Composition's builder wants
an octave-qualified pitch token (e.g. ``"F#4"``) and falls back to octave 4
if it doesn't find one, while ``MelodyEvent.pitch`` stores only the pitch
*class* spelling (e.g. ``"F#"``) alongside a separate ``midi`` field — so the
octave is derived from ``midi`` here rather than changing the accepted
Slice A event schema.
"""

from __future__ import annotations

from composition_melody_notation import build_abc_from_melody_events
from practice_melody_model import MelodySection, PracticeMelody


def _octave_qualified_pitch(pitch: str | None, midi: int | None) -> str:
    if pitch is None or midi is None:
        return "rest"
    octave = midi // 12 - 1
    return f"{pitch}{octave}"


def _section_to_event_dicts(section: MelodySection) -> list[dict[str, object]]:
    return [
        {
            "pitch": _octave_qualified_pitch(event.pitch, event.midi),
            "is_rest": event.is_rest,
            "duration_beats": event.duration_beats,
            # Notation markings (item 10): purely additive ABC decorations
            # (accent/staccato/tenuto, slur parens, dynamics) -- abcjs
            # attaches these to the same note token rather than creating a
            # separate one, so F2's measure/beat-keyed highlight mapping is
            # untouched by adding them here.
            "articulation": event.articulation,
            "slur": event.slur,
            "dynamic": event.dynamic,
        }
        for event in section.events
    ]


def _wrap_abc_music_line(abc_text: str, *, bars_per_line: int = 4) -> str:
    """Break the single long music line abcjs would otherwise render as one
    illegibly compressed row into several bars per staff line. Headers
    (X:/T:/M:/L:/Q:/K:) are left untouched; only the trailing music line is
    reflowed, so this is purely a display concern, not a data-model change.
    """
    lines = abc_text.split("\n")
    if len(lines) < 2:
        return abc_text
    *header_lines, music = lines
    bars = [b.strip() for b in music.strip().split("|") if b.strip()]
    if len(bars) <= bars_per_line:
        return abc_text
    wrapped = [
        " | ".join(bars[i : i + bars_per_line]) + " |"
        for i in range(0, len(bars), bars_per_line)
    ]
    return "\n".join(header_lines + wrapped)


def practice_melody_section_abc(
    melody: PracticeMelody,
    section: MelodySection,
    *,
    title: str | None = None,
) -> str:
    """ABC text for a single section of a Practice Melody."""
    abc = build_abc_from_melody_events(
        _section_to_event_dicts(section),
        key=melody.key_center,
        meter=f"{melody.meter[0]}/{melody.meter[1]}",
        bpm=int(round(melody.tempo_bpm)),
        title=title or f"{melody.song_title} - {section.section_id}",
        chords=list(section.chords),
    )
    return _wrap_abc_music_line(abc)


def practice_melody_sections_abc(
    melody: PracticeMelody,
    sections: list[MelodySection],
    *,
    title: str | None = None,
) -> str:
    """ABC text spanning an arbitrary, ordered subset of a Practice
    Melody's sections -- the Section-Focus-scoped counterpart to
    ``practice_melody_full_song_abc`` (Slice F1). Passing all of
    ``melody.sections`` is equivalent to the full-song render.
    """
    events: list[dict[str, object]] = []
    chords: list[str] = []
    for section in sections:
        events.extend(_section_to_event_dicts(section))
        chords.extend(section.chords)
    section_label = " / ".join(s.section_id for s in sections) if len(sections) <= 2 else "Selected sections"
    abc = build_abc_from_melody_events(
        events,
        key=melody.key_center,
        meter=f"{melody.meter[0]}/{melody.meter[1]}",
        bpm=int(round(melody.tempo_bpm)),
        title=title or f"{melody.song_title} - {section_label}" if sections != list(melody.sections) else (title or melody.song_title),
        chords=chords,
    )
    return _wrap_abc_music_line(abc)


def practice_melody_full_song_abc(melody: PracticeMelody, *, title: str | None = None) -> str:
    """ABC text spanning every section of a Practice Melody, in order."""
    return practice_melody_sections_abc(melody, list(melody.sections), title=title)
