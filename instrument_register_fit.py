"""Keep generated exercises inside an instrument's comfortable *written* register.

The shared per-instrument register table (``chord_navigation_notation.instrument_register``, the same one
the pitch-range analyser reads) says what is playable; ordinary Tone / Chord-Tone practice should sit well
inside it, not on the extreme ledger lines. Fitting moves the WHOLE phrase by whole octaves only, so pitch
classes, intervals, rhythm and harmonic identity are untouched - nothing is wrapped note by note.

Only melodic wind families are fitted (flute, clarinet, saxophones, trumpet, trombone ...). Chordal
instruments (piano, guitar, bass) keep the phrase generators' own register.
"""

from __future__ import annotations

from typing import Any

_FITTED = ("flute", "piccolo", "clarinet", "sax", "trumpet", "flugel", "cornet", "trombone")
# Written-pitch ceilings for ordinary practice: A5 (two ledger lines above the treble staff) for Beginner,
# C6 for Intermediate. Advanced / range exercises may use the instrument's whole playable top.
_COMFORT_CEILING = {"beginner": 81, "intermediate": 84}


def is_fitted_instrument(instrument: str) -> bool:
    name = str(instrument or "").lower()
    return any(word in name for word in _FITTED)


def comfortable_written_range(instrument: str, level: str = "Intermediate") -> tuple[int, int] | None:
    """(low, high) written MIDI the exercise should stay inside, or None when not fitted."""
    if not is_fitted_instrument(instrument):
        return None
    try:
        from chord_navigation_notation import instrument_register

        from music_coach_ami.notation_profile import notation_profile_for_instrument

        envelope = "playable" in str(notation_profile_for_instrument(instrument).register_hint or "").lower()
        # A profile that IS the playable envelope (flute C4..C7) gives its true bottom note at Beginner;
        # "comfortable middle" profiles are widened at Advanced for their bottom.
        lo, _h, _s = instrument_register(instrument, "Beginner" if envelope else "Advanced")
        _l, hi, _s2 = instrument_register(instrument, "Advanced")
    except Exception:
        return None
    ceiling = _COMFORT_CEILING.get(str(level or "").strip().lower())
    if ceiling is not None:
        hi = min(int(hi), ceiling)
    return int(lo), int(hi)


def fit_midis_to_register(midis: list[int], low: int, high: int) -> list[int]:
    """Whole-phrase octave shift into [low, high]; when no octave fits, the least-bad one.

    A note below the instrument's floor is unplayable, one above the comfortable ceiling is only
    awkward, so falling short at the bottom costs three times as much as overshooting the top.
    """
    out = [int(m) for m in midis]
    if not out:
        return out

    def cost(shift: int) -> tuple[int, int]:
        lo_m, hi_m = min(out) + shift, max(out) + shift
        return (3 * max(0, low - lo_m) + max(0, hi_m - high), abs(shift))

    best = min((-24, -12, 0, 12, 24), key=cost)
    return [m + best for m in out]


def fit_motif_to_instrument(motif: dict[str, Any], instrument: str, level: str = "") -> dict[str, Any]:
    """Return ``motif`` with ``midi`` octave-fitted for ``instrument`` (a copy; note names are unchanged)."""
    midis = [m for m in (motif.get("midi") or []) if isinstance(m, (int, float))]
    if not midis or len(midis) != len(motif.get("notes") or midis):
        return motif
    lvl = level or str(motif.get("pattern_level") or motif.get("student_level") or "Intermediate")
    rng = comfortable_written_range(instrument, lvl)
    if rng is None:
        return motif
    fitted = fit_midis_to_register(midis, *rng)
    if fitted == [int(m) for m in midis]:
        return motif
    out = dict(motif)
    out["midi"] = fitted
    return out
