"""One projection of a composition's stored melody into Practice Key and the player's written pitch.

The stored melody is the song's melody. Practice, Backing and Creative all show a
*projection* of it, so they must share one definition of:

* the key shift (Original Key -> Practice Key) -- the *nearest* signed shift, so a
  Practice Key a step below the original moves the melody down a step and never up
  ten semitones into a different register;
* the written-pitch offset for transposing instruments (pitch class + sax octave);
* the clef the player reads.
"""

from __future__ import annotations

from typing import Any

_KEY_SHIFT_LOW = -5  # nearest shift is reported in [-5, +6]


def signed_semitone_delta(original_key: str, practice_key: str) -> int:
    """Nearest signed semitone shift from ``original_key`` to ``practice_key``."""
    from music_theory import semitone_distance

    orig = str(original_key or "").strip()
    practice = str(practice_key or "").strip()
    if not orig or not practice:
        return 0
    up = int(semitone_distance(orig, practice) or 0) % 12
    if up == 6:
        # A tritone is equally far both ways. Pick the direction from the two key roots so the
        # shift is antisymmetric: A->B-flat and B-flat->A move by opposite amounts and a
        # round trip lands on the original octave instead of drifting by one.
        pc_orig, pc_practice = _root_pitch_class(orig), _root_pitch_class(practice)
        if pc_orig is not None and pc_practice is not None and pc_orig > pc_practice:
            return -6
        return 6
    return ((up - _KEY_SHIFT_LOW) % 12) + _KEY_SHIFT_LOW


def _root_pitch_class(key: str) -> int | None:
    try:
        from music_theory import CHROMATIC, normalize_root, split_chord

        root, _ = split_chord(str(key or "").strip())
        nr = normalize_root(root)
        return CHROMATIC.index(nr) if nr in CHROMATIC else None
    except Exception:
        return None


def clef_for_instrument(instrument: str) -> str:
    """Clef used to read the melody.

    Guitar reads treble-8: it sounds an octave below what is written, and abcjs draws the
    notes of ``treble-8`` exactly where it draws them for ``treble``, so the written
    octave (+12) is applied in :func:`project_melody_events`. Bass reads bass clef at the
    melody's own pitch (see :func:`melody_range_notice` for when that is out of range).
    """
    name = str(instrument or "").strip().lower()
    if "bass" in name:
        return "bass"
    if "guitar" in name:
        return "treble-8"
    return "treble"


def transpose_events(events: list[dict[str, Any]], semitones: int) -> list[dict[str, Any]]:
    """Copy ``events`` with every pitched note moved by ``semitones`` (rests untouched)."""
    if not semitones:
        return [dict(ev) for ev in events or [] if isinstance(ev, dict)]
    from media_tone_catalog import transpose_note_token

    out: list[dict[str, Any]] = []
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        copy = dict(ev)
        pitch = str(copy.get("pitch") or "")
        if pitch and pitch.lower() != "rest":
            moved = transpose_note_token(pitch, int(semitones))
            if moved:
                copy["pitch"] = moved
        out.append(copy)
    return out


def project_melody_events(
    events: list[dict[str, Any]],
    *,
    original_key: str,
    practice_key: str,
    instrument: str,
    session_state: dict[str, Any] | None = None,
    written: bool = True,
) -> tuple[list[dict[str, Any]], int, int]:
    """Return ``(events, key_semitones, instrument_semitones)`` for display.

    Key shift and instrument offset are applied exactly once, and only here.

    ``written`` is the chart mode: with a transposing instrument it is True only when the
    player chose written notation. In concert mode (False) the melody, key signature and
    chord symbols all stay at concert pitch. Guitar's written octave is a clef convention,
    not a chart mode, so it always applies.
    """
    from composition_songs_bridge import composition_written_pitch_semitones

    key_shift = signed_semitone_delta(original_key, practice_key)
    inst_shift = int(composition_written_pitch_semitones(instrument, session_state) or 0) if written else 0
    if clef_for_instrument(instrument) == "treble-8":
        inst_shift += 12  # guitar is written an octave above where it sounds
    return transpose_events(events, key_shift + inst_shift), key_shift, inst_shift


# (lowest, highest) MIDI note as *displayed* (written for transposing instruments,
# concert for the rest) before the melody is reported as out of the usual range.
_DISPLAY_RANGES: dict[str, tuple[int, int, str]] = {
    "flute": (60, 96, "Flute"),
    "clarinet": (52, 96, "Clarinet"),
    "saxophone": (58, 90, "Saxophone"),
    "trumpet": (54, 84, "Trumpet"),
    "guitar": (40, 88, "Guitar"),
    "bass": (28, 67, "Bass"),
}


def _range_family(instrument: str) -> str:
    low = str(instrument or "").strip().lower()
    for family in ("saxophone", "clarinet", "trumpet", "flute", "bass", "guitar"):
        if family in low or (family == "saxophone" and "sax" in low):
            return family
    return ""


def melody_range_notice(
    projected_events: list[dict[str, Any]],
    instrument: str,
    session_state: dict[str, Any] | None = None,
) -> str:
    """Plain-language note when the *displayed* melody leaves the usual range.

    Only reports; never moves a pitch. Empty when the melody fits (or the
    instrument has no tabulated range).
    """
    family = _range_family(instrument)
    if not family:
        return ""
    from media_tone_catalog import midi_to_note_token, parse_note_token

    low_ok, high_ok, label = _DISPLAY_RANGES[family]
    midis = []
    for ev in projected_events or []:
        pitch = str((ev or {}).get("pitch") or "")
        if pitch and pitch.lower() != "rest":
            midi = parse_note_token(pitch)
            if midi is not None:
                midis.append(int(midi))
    if not midis:
        return ""
    if family == "guitar":
        # The guitar range below is in sounding pitch; the displayed notes are written
        # an octave higher.
        midis = [m - 12 for m in midis]
    lowest, highest = min(midis), max(midis)
    if highest > high_ok:
        return (
            f"This melody reaches {midi_to_note_token(highest)}, above the usual range for "
            f"{label} (up to {midi_to_note_token(high_ok)}). The notation shows the melody as composed."
        )
    if lowest < low_ok:
        return (
            f"This melody dips to {midi_to_note_token(lowest)}, below the usual range for "
            f"{label} (down to {midi_to_note_token(low_ok)}). The notation shows the melody as composed."
        )
    return ""


# Generation window the Composition engine uses when no instrument narrows it (sounding MIDI).
_DEFAULT_GENERATION_RANGE = (55, 79)


def concert_melody_range(
    instrument: str,
    session_state: dict[str, Any] | None = None,
) -> tuple[int, int] | None:
    """Sounding (concert) MIDI window a generated melody should stay inside for *instrument*.

    Compositions are stored at concert pitch; the tabulated display range is written pitch for
    transposing instruments, so the instrument's written-pitch offset is subtracted. The result
    is intersected with the engine's comfortable default window. None when the instrument has no
    tabulated range (piano, voice, unknown): the default window then applies unchanged.
    """
    family = _range_family(instrument)
    if not family or family == "bass":
        return None
    from composition_songs_bridge import composition_written_pitch_semitones

    lo, hi, _label = _DISPLAY_RANGES[family]
    if family == "guitar":
        lo, hi = lo, hi  # tabulated in sounding pitch already
    else:
        shift = int(composition_written_pitch_semitones(instrument, session_state) or 0)
        lo, hi = lo - shift, hi - shift
    d_lo, d_hi = _DEFAULT_GENERATION_RANGE
    n_lo, n_hi = max(lo, d_lo), min(hi, d_hi)
    if n_hi - n_lo < 12:  # instrument window too narrow to intersect: use it as is
        n_lo, n_hi = lo, hi
    return int(n_lo), int(n_hi)
