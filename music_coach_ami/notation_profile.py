"""Instrument → staff notation profile (clef, written register, sounding offset)."""

from __future__ import annotations

from dataclasses import dataclass, replace

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
    """Resolve clef and practical written register for AMI staff output.

    Bass-line *role* is separate: this maps the selected instrument to clef + register.
    """
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
    if fam == "wind":
        return _wind_notation_profile(low)

    return NotationProfile(
        clef="bass",
        written_octave=3,
        sounding_to_written_shift=0,
        register_hint="supportive bass register",
        midi_low=36,
        midi_high=60,
    )


def notation_profile_for_piano_role(role: str) -> NotationProfile:
    """Piano staff/register by requested hand role — RH treble, LH bass, both grand."""
    key = str(role or "").strip().lower().replace("-", "_").replace(" ", "_")
    if key in {"right_hand", "rh", "melody", "improvisation", "solo"}:
        return NotationProfile(
            clef="treble",
            written_octave=4,
            sounding_to_written_shift=0,
            register_hint="piano right-hand treble register",
            midi_low=60,  # C4
            midi_high=84,  # C6
        )
    if key in {"left_hand", "lh", "accompaniment"}:
        return NotationProfile(
            clef="bass",
            written_octave=2,
            sounding_to_written_shift=0,
            register_hint="piano left-hand bass register",
            midi_low=36,  # C2
            midi_high=55,  # G3
        )
    if key in {"both_hands", "two_hand", "two_hands", "grand"}:
        return NotationProfile(
            clef="grand",
            written_octave=4,
            sounding_to_written_shift=0,
            register_hint="piano grand staff (RH treble + LH bass)",
            midi_low=36,  # C2
            midi_high=84,  # C6
        )
    return notation_profile_for_instrument("Piano")


def _wind_notation_profile(low: str) -> NotationProfile:
    """Treble-clef written ranges for common wind instruments (concert/written defaults)."""
    if "flute" in low:
        # Playable envelope (not the default generation comfort window).
        # Comfortable AMI defaults live in musical_idea_engine.generation_window.
        return NotationProfile(
            clef="treble",
            written_octave=5,
            sounding_to_written_shift=0,
            register_hint="flute playable written envelope",
            midi_low=60,  # C4
            midi_high=96,  # C7
        )
    if "clarinet" in low:
        return NotationProfile(
            clef="treble",
            written_octave=4,
            sounding_to_written_shift=0,
            register_hint="clarinet comfortable chalumeau/clarion middle",
            midi_low=60,  # C4
            midi_high=79,  # G5
        )
    if "tenor" in low and "sax" in low:
        return NotationProfile(
            clef="treble",
            written_octave=4,
            sounding_to_written_shift=0,
            register_hint="tenor sax comfortable middle written register",
            midi_low=55,  # G3
            midi_high=74,  # D5
        )
    if "bari" in low and "sax" in low:
        return NotationProfile(
            clef="treble",
            written_octave=3,
            sounding_to_written_shift=0,
            register_hint="bari sax comfortable middle written register",
            midi_low=48,  # C3
            midi_high=67,  # G4
        )
    if "soprano" in low and "sax" in low:
        return NotationProfile(
            clef="treble",
            written_octave=5,
            sounding_to_written_shift=0,
            register_hint="soprano sax comfortable middle written register",
            midi_low=62,  # D4
            midi_high=81,  # A5
        )
    if "sax" in low or "alto" in low:
        # Default / alto sax
        return NotationProfile(
            clef="treble",
            written_octave=4,
            sounding_to_written_shift=0,
            register_hint="alto sax comfortable middle written register",
            midi_low=58,  # Bb3
            midi_high=77,  # F5
        )
    if "trumpet" in low or "flugel" in low:
        return NotationProfile(
            clef="treble",
            written_octave=4,
            sounding_to_written_shift=0,
            register_hint="trumpet comfortable middle register",
            midi_low=58,  # Bb3
            midi_high=77,  # F5
        )
    if "trombone" in low:
        return NotationProfile(
            clef="bass",
            written_octave=3,
            sounding_to_written_shift=0,
            register_hint="trombone comfortable middle register",
            midi_low=40,  # E2
            midi_high=60,  # C4
        )
    if "tuba" in low:
        return NotationProfile(
            clef="bass",
            written_octave=2,
            sounding_to_written_shift=0,
            register_hint="tuba comfortable bass register",
            midi_low=28,  # E1
            midi_high=48,  # C3
        )
    # Generic wind: treble, mid staff
    return NotationProfile(
        clef="treble",
        written_octave=4,
        sounding_to_written_shift=0,
        register_hint="wind comfortable middle register",
        midi_low=60,
        midi_high=79,
    )


def apply_register_override(profile: NotationProfile, register: str) -> NotationProfile:
    """Shift comfortable written window for explicit high/low user requests.

    Priority: explicit register wording → stay within playable limits of the profile
    (here we bias the window inside a slightly expanded playable envelope).
    """
    reg = str(register or "").strip().lower()
    if not reg or reg == "mid":
        return profile
    span = max(12, profile.midi_high - profile.midi_low)
    playable_low = max(12, profile.midi_low - 7)
    playable_high = min(108, profile.midi_high + 12)
    if reg == "high":
        high = min(playable_high, profile.midi_high + 12)
        low = max(playable_low, high - span)
        octave = min(7, profile.written_octave + 1)
        hint = f"{profile.register_hint} (biased high)"
    elif reg == "low":
        low = max(playable_low, profile.midi_low - 7)
        high = min(playable_high, low + span)
        octave = max(1, profile.written_octave - 1)
        hint = f"{profile.register_hint} (biased low)"
    else:
        return profile
    return replace(
        profile,
        midi_low=int(low),
        midi_high=int(high),
        written_octave=int(octave),
        register_hint=hint,
    )
