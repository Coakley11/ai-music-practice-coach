"""Instrument → staff notation profile (clef, written register, sounding offset)."""

from __future__ import annotations

from dataclasses import dataclass

from music_coach_instrument_voice import instrument_family


@dataclass(frozen=True)
class NotationProfile:
    """Written-pitch profile for AMI staff output.

    ``written_octave`` is the scientific pitch octave used for ABC tokens.
    ``sounding_to_written_shift`` is +1 when the instrument's conventional
    notation is written an octave above sounding pitch (bass guitar, guitar).
    Generation should target *written* pitches in [midi_low, midi_high].
    """

    clef: str
    written_octave: int
    sounding_to_written_shift: int
    register_hint: str
    midi_low: int
    midi_high: int

    @property
    def default_octave(self) -> int:
        """Backward-compatible alias for written_octave."""
        return self.written_octave


def notation_profile_for_instrument(instrument: str) -> NotationProfile:
    """Resolve clef and practical written register for AMI staff output."""
    fam = instrument_family(instrument)
    low = str(instrument or "").strip().lower()

    if fam == "bass" or "bass guitar" in low or low == "bass":
        # Electric bass: bass clef, written an octave above sounding.
        # Written E2–G3 sits on/near the bass staff (sounding E1–G2).
        return NotationProfile(
            clef="bass",
            written_octave=2,
            sounding_to_written_shift=1,
            register_hint="electric-bass written register (octave above sounding)",
            midi_low=40,  # E2 written
            midi_high=55,  # G3 written
        )
    if fam == "keyboard" or "piano" in low:
        # Concert pitch left-hand register on the bass staff.
        return NotationProfile(
            clef="bass",
            written_octave=2,
            sounding_to_written_shift=0,
            register_hint="piano left-hand bass register",
            midi_low=36,  # C2
            midi_high=55,  # G3
        )
    if fam == "fretted":
        # Guitar bass-line idea: treble clef, conventional guitar written pitch
        # (sounds an octave below written).
        return NotationProfile(
            clef="treble",
            written_octave=3,
            sounding_to_written_shift=1,
            register_hint="guitar written register (octave above sounding)",
            midi_low=52,  # E3 written (open low E convention)
            midi_high=67,  # G4
        )
    return NotationProfile(
        clef="bass",
        written_octave=3,
        sounding_to_written_shift=0,
        register_hint="supportive bass register",
        midi_low=36,
        midi_high=60,
    )
