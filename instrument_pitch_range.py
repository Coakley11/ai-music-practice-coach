"""Plausible *sounding* pitch range of the selected instrument, for pitch analysis.

Reuses the app's shared per-instrument register table (``music_coach_ami.notation_profile`` via
``chord_navigation_notation.instrument_register``, read-only) and the transposition registry
(``instrument_transposition``), so no instrument gets a one-off hard-coded range here.

Melodic, monophonic instruments (flute, clarinet, saxophones, trumpet, trombone, voice …) get
their sounding range; chordal / full-range instruments (piano, guitar, bass…) keep the generic
analysis window, because a narrow window would hide real notes.
"""

from __future__ import annotations

GENERIC_RANGE = (36, 96)  # C2 .. C7: the analysers' default window
_MARGIN_HIGH = 4  # nothing is added below an instrument's bottom note: that is where bleed lives
# Families the shared register table actually covers with their own profile; anything else
# (piano, guitar, bass, voice, strings …) keeps the generic window.
_MELODIC = ("flute", "piccolo", "clarinet", "sax", "trumpet", "flugel", "cornet", "trombone")


def _sounding_shift(instrument: str) -> int:
    """Semitones the written part sits above sounding pitch (0 for concert instruments)."""
    try:
        from instrument_transposition import get_instrument_transposition_simple

        return int(get_instrument_transposition_simple(instrument).get("semitones_up") or 0)
    except Exception:
        return 0


def sounding_pitch_range(instrument: str) -> tuple[int, int, bool]:
    """(low_midi, high_midi, instrument_specific) in sounding pitch, with a small margin."""
    name = str(instrument or "").strip()
    if not name or not any(word in name.lower() for word in _MELODIC):
        return GENERIC_RANGE[0], GENERIC_RANGE[1], False
    try:
        from chord_navigation_notation import instrument_register
        from music_coach_ami.notation_profile import notation_profile_for_instrument  # read-only

        envelope = "playable" in str(notation_profile_for_instrument(name).register_hint or "").lower()
        # A profile that *is* the playable envelope (flute: C4..C7) gives the true bottom note;
        # a "comfortable middle" profile (clarinet, sax …) does not, so its widened bottom is used.
        lo, _hi, _start = instrument_register(name, "Beginner" if envelope else "Advanced")
        _lo, hi, _start = instrument_register(name, "Advanced")  # the widest playable top
    except Exception:
        return GENERIC_RANGE[0], GENERIC_RANGE[1], False
    shift = _sounding_shift(name)
    lo, hi = int(lo) - shift, int(hi) - shift + _MARGIN_HIGH
    if hi - lo < 12:
        return GENERIC_RANGE[0], GENERIC_RANGE[1], False
    return lo, hi, True


__all__ = ["GENERIC_RANGE", "sounding_pitch_range"]
