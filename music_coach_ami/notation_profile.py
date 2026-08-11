"""Instrument → staff notation profile (clef + written register)."""

from __future__ import annotations

from dataclasses import dataclass

from music_coach_instrument_voice import instrument_family


@dataclass(frozen=True)
class NotationProfile:
    clef: str
    default_octave: int
    register_hint: str


def notation_profile_for_instrument(instrument: str) -> NotationProfile:
    """Resolve clef and default written octave for AMI staff output."""
    fam = instrument_family(instrument)
    if fam == "fretted":
        return NotationProfile(
            clef="treble",
            default_octave=3,
            register_hint="lower strings / bass-string register",
        )
    if fam == "keyboard":
        return NotationProfile(
            clef="bass",
            default_octave=3,
            register_hint="left-hand bass register",
        )
    if fam == "bass":
        return NotationProfile(
            clef="bass",
            default_octave=2,
            register_hint="comfortable bass-clef range",
        )
    return NotationProfile(
        clef="bass",
        default_octave=3,
        register_hint="supportive bass register",
    )
