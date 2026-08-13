"""Reusable concert → musician-facing written music context for AMI generators."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from music_coach_ami.notation_profile import (
    NotationProfile,
    apply_register_override,
    notation_profile_for_instrument,
)


def _clean(text: object) -> str:
    return str(text or "").strip()


@dataclass(frozen=True)
class WrittenMusicContext:
    """Read-only bridge from Practice/Concert harmony to written notation.

    Generators compose in the concert/practice domain; notation consumes the
    written domain (instrument transposition + optional guitar capo shapes).
    """

    instrument: str
    original_song_key: str
    practice_concert_key: str
    concert_chords: tuple[str, ...]
    written_key: str
    written_chords: tuple[str, ...]
    transposition_semitones: int
    clef: str
    sounding_to_written_octave_shift: int
    capo_fret: int | None
    capo_shape_key: str | None
    notation_profile: NotationProfile
    chart_already_in_practice_key: bool
    written_transposition_applied: bool
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_diagnostics(self) -> dict[str, Any]:
        profile = self.notation_profile
        return {
            "selected_instrument": self.instrument,
            "original_song_key": self.original_song_key,
            "practice_concert_key": self.practice_concert_key,
            "effective_concert_chords": list(self.concert_chords),
            "instrument_transposition_semitones": self.transposition_semitones,
            "written_key": self.written_key,
            "written_chords": list(self.written_chords),
            "notation_clef": self.clef,
            "written_midi_range": [profile.midi_low, profile.midi_high],
            "sounding_to_written_octave_shift": self.sounding_to_written_octave_shift,
            "capo_fret": self.capo_fret,
            "capo_shape_key": self.capo_shape_key,
            "chart_already_in_practice_key": self.chart_already_in_practice_key,
            "written_transposition_applied": self.written_transposition_applied,
            "register_hint": profile.register_hint,
            "written_music_provenance": dict(self.provenance),
        }


def _transpose_chord_list(chords: list[str], steps: int, *, reference_key: str) -> list[str]:
    if not steps:
        return list(chords)
    from music_theory import transpose_chord

    return [transpose_chord(c, steps, reference_key=reference_key) for c in chords]


def build_written_music_context(
    *,
    instrument: str,
    practice_concert_key: str,
    original_song_key: str,
    concert_chords: list[str],
    session_state: dict[str, Any] | None = None,
    register: str = "",
    chart_already_in_practice_key: bool = True,
    chart_source: str = "",
) -> WrittenMusicContext:
    """Resolve musician-facing written key/chords from concert Practice Key harmony.

    Uses ``instrument_transposition.resolve_practice_keys`` and guitar capo SSOT.
    AMI notation always presents the written domain musicians read.
    """
    from music_coach_ami.session_access import as_mutable_session

    session = as_mutable_session(session_state)
    inst = _clean(instrument) or "Piano"
    concert = _clean(practice_concert_key) or "C"
    original = _clean(original_song_key) or concert
    chords = [_clean(c) for c in concert_chords if _clean(c)]
    # Saxophone UI label → Alto/Tenor/… profile via existing transposition SSOT.
    try:
        from music_coach_ami.instrument_realization import (
            notation_instrument_name,
            resolve_transposing_subtype,
        )

        subtype_early = resolve_transposing_subtype(session, inst)
        profile_inst = notation_instrument_name(
            inst, session_state=session, transposing_subtype=subtype_early
        )
    except ImportError:
        profile_inst = inst
        subtype_early = ""
    profile = apply_register_override(notation_profile_for_instrument(profile_inst), register)

    written_key = concert
    steps = 0
    capo_fret: int | None = None
    capo_shape: str | None = None
    mode = "concert"
    transposing_type = ""
    keys: dict[str, str] = {}

    try:
        from instrument_transposition import (
            is_transposing_instrument,
            resolve_practice_keys,
            written_key_for_type,
        )

        keys = resolve_practice_keys(session, concert, inst)
        mode = _clean(keys.get("chart_key_mode") or "concert") or "concert"
        transposing_type = _clean(keys.get("transposing_type"))
        if is_transposing_instrument(inst):
            # AMI staff always uses the musician's written key for Bb/Eb instruments.
            written_key = _clean(keys.get("written_key") or concert) or concert
            mode = "written"
        else:
            written_key = _clean(keys.get("effective_practice_key") or keys.get("written_key") or concert) or concert
            # Display labels like "Alto Sax" / "Bb Clarinet" are not always canonical
            # USER_TRANSPOSING_INSTRUMENTS names — map via type labels.
            low_name = inst.lower()
            type_label = ""
            if "alto" in low_name and "sax" in low_name:
                type_label = "Alto saxophone (Eb)"
            elif "tenor" in low_name and "sax" in low_name:
                type_label = "Tenor saxophone (Bb)"
            elif "soprano" in low_name and "sax" in low_name:
                type_label = "Soprano saxophone (Bb)"
            elif "bari" in low_name and "sax" in low_name:
                type_label = "Baritone saxophone (Eb)"
            elif "clarinet" in low_name:
                type_label = "Bb Clarinet"
            elif "trumpet" in low_name:
                type_label = "Bb Trumpet"
            if type_label:
                written_key = written_key_for_type(concert, type_label)
                transposing_type = type_label
                mode = "written"
    except ImportError:
        keys = {"concert_key": concert, "written_key": concert, "effective_practice_key": concert}

    try:
        from music_theory import semitone_distance

        if written_key and concert and written_key != concert:
            steps = int(semitone_distance(concert, written_key))
    except ImportError:
        steps = 0

    # Guitar capo: resolve_practice_keys already sets effective_practice_key to shape key.
    if inst == "Guitar":
        try:
            from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY, capo_fret_for_shape

            if session.get(CAPO_ENABLED_KEY):
                capo_shape = _clean(session.get(CAPO_SHAPE_KEY)) or _clean(keys.get("chart_key"))
                if capo_shape:
                    capo_fret = int(capo_fret_for_shape(concert, capo_shape))
                    written_key = capo_shape
                    steps = int(semitone_distance(concert, written_key)) if concert != written_key else 0
                    mode = "written"
        except ImportError:
            pass

    # Spell transposed symbols in the *written* key family (A → F#m7, not Gbm7).
    dest_ref = written_key or concert
    written_chords = _transpose_chord_list(chords, steps, reference_key=dest_ref)
    written_applied = bool(steps) or (mode == "written" and written_key != concert)

    return WrittenMusicContext(
        instrument=inst,
        original_song_key=original,
        practice_concert_key=concert,
        concert_chords=tuple(chords),
        written_key=written_key,
        written_chords=tuple(written_chords),
        transposition_semitones=int(steps),
        clef=profile.clef,
        sounding_to_written_octave_shift=int(profile.sounding_to_written_shift),
        capo_fret=capo_fret,
        capo_shape_key=capo_shape,
        notation_profile=profile,
        chart_already_in_practice_key=bool(chart_already_in_practice_key),
        written_transposition_applied=written_applied,
        provenance={
            "chart_source": chart_source,
            "chart_key_mode": mode,
            "transposing_type": transposing_type or subtype_early,
            "notation_instrument": profile_inst,
            "show_chart_in_instrument_key": bool(session.get("show_chart_in_instrument_key", False)),
            "resolve_practice_keys": keys,
        },
    )


def transpose_composition_to_written(composition: Any, wctx: WrittenMusicContext) -> Any:
    """Map a concert-pitch BassLineComposition into the written domain."""
    from music_coach_ami.bass_line_engine import BassLineBar, BassLineComposition, BassLineNote
    from music_theory import pitch_class_from_spelled_note, spell_note_in_key

    if not wctx.written_transposition_applied and wctx.written_key == composition.reference_key:
        # Still attach written profile / key for concert-pitch instruments.
        if composition.notation_profile == wctx.notation_profile and composition.reference_key == wctx.written_key:
            return composition

    steps = int(wctx.transposition_semitones)
    written_key = wctx.written_key
    new_bars: list[BassLineBar] = []
    for bar, wchord in zip(composition.bars, wctx.written_chords or [b.chord for b in composition.bars]):
        notes: list[BassLineNote] = []
        for n in bar.notes:
            if steps:
                pc = (pitch_class_from_spelled_note(n.note) + steps) % 12
                spelled = spell_note_in_key(pc, written_key)
                midi = (n.written_octave + 1) * 12 + pitch_class_from_spelled_note(n.note)
                midi_w = midi + steps
                octv = (midi_w // 12) - 1
                # Keep profile range when possible
                low, high = wctx.notation_profile.midi_low, wctx.notation_profile.midi_high
                while midi_w < low:
                    midi_w += 12
                    octv += 1
                while midi_w > high:
                    midi_w -= 12
                    octv -= 1
                notes.append(BassLineNote(spelled, n.duration, octv))
            else:
                notes.append(n)
        new_bars.append(BassLineBar(chord=wchord or bar.chord, notes=tuple(notes)))

    return BassLineComposition(
        bars=tuple(new_bars),
        reference_key=written_key,
        meter=composition.meter,
        section_label=composition.section_label,
        strategy=composition.strategy,
        notation_profile=wctx.notation_profile,
        style=composition.style,
    )


def written_context_asdict(wctx: WrittenMusicContext) -> dict[str, Any]:
    data = asdict(wctx)
    data["notation_profile"] = {
        "clef": wctx.notation_profile.clef,
        "written_octave": wctx.notation_profile.written_octave,
        "sounding_to_written_shift": wctx.notation_profile.sounding_to_written_shift,
        "register_hint": wctx.notation_profile.register_hint,
        "midi_low": wctx.notation_profile.midi_low,
        "midi_high": wctx.notation_profile.midi_high,
    }
    return data
