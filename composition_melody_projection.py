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
    return ((up - _KEY_SHIFT_LOW) % 12) + _KEY_SHIFT_LOW


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
