"""Concert vs written pitch labels for Claude enrichment. All values come from `instrument_transposition`; Claude never computes them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# How written pitch relates to sounding pitch for each transposing type (octave included).
_WRITTEN_RELATION: dict[str, str] = {
    "Soprano saxophone (Bb)": "a major second above",
    "Alto saxophone (Eb)": "a major sixth above",
    "Tenor saxophone (Bb)": "a major second plus an octave above",
    "Baritone saxophone (Eb)": "a major sixth plus an octave above",
    "Bb Trumpet": "a major second above",
    "Bb Clarinet": "a major second above",
}


@dataclass(frozen=True)
class PitchReference:
    """`status`: 'concert' (non-transposing), 'verified' (written values below are deterministic), 'unverified' (transposing but ambiguous)."""

    status: str = "concert"
    instrument_label: str = ""
    transposing_type: str = ""
    relation: str = ""
    key_pairs: tuple[tuple[str, str], ...] = ()
    chord_pairs: tuple[tuple[str, str], ...] = ()

    @property
    def transposing(self) -> bool:
        return self.status in {"verified", "unverified"}

    def written_key(self, concert_key: str) -> str:
        return dict(self.key_pairs).get(concert_key, "")

    def written_chord(self, concert_chord: str) -> str:
        return dict(self.chord_pairs).get(concert_chord, "")

    def as_fact(self) -> dict[str, Any]:
        """What Claude sees: only that names are concert pitch. No written values are ever handed to the model."""
        return {
            "names_are": "concert pitch",
            "instrument_transposes": self.transposing,
            "app_adds_written_pitch_labels": self.status == "verified",
        }


def build_pitch_reference(
    instrument: str,
    session_state: Any,
    *,
    keys: tuple[str, ...],
    chords: tuple[str, ...],
) -> PitchReference:
    try:
        from instrument_transposition import (
            is_transposing_instrument,
            instrument_display_name,
            options_for_instrument,
            semitone_steps_for_label,
            written_key_for_type,
            SELECTED_TRANSPOSING_INSTRUMENT_KEY,
            selected_transposing_type,
        )
    except ImportError:
        return PitchReference()
    inst = str(instrument or "").strip()
    try:
        if not is_transposing_instrument(inst):
            return PitchReference()
    except Exception:
        return PitchReference()

    try:
        options = options_for_instrument(inst)
        t_type = ""
        is_default = False
        if len(options) == 1:
            t_type = options[0]
        elif options and session_state is not None:
            pick = session_state.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY)
            if pick in options:
                t_type = pick
            else:
                # No explicit pick in this session: use the app's own authoritative default selection and say so.
                # Alto is never inferred from the generic word "Saxophone" alone; without a session handle it stays unverified.
                t_type = selected_transposing_type(session_state, inst)
                is_default = bool(t_type)
        label = instrument_display_name(t_type, inst) if t_type else inst
        if is_default:
            label += " (the app's default saxophone selection)"
        relation = _WRITTEN_RELATION.get(t_type, "")
        if not t_type or not relation:
            return PitchReference(status="unverified", instrument_label=label)
        steps = semitone_steps_for_label(t_type)
        from music_theory import transpose_chord

        practice_ref = next((k for k in keys if k), "C")
        key_pairs = tuple((k, written_key_for_type(k, t_type)) for k in keys if k)
        chord_pairs = tuple(
            (c, transpose_chord(c, steps, reference_key=practice_ref)) for c in chords if c
        )
        if not key_pairs or any(not w for _c, w in key_pairs + chord_pairs):
            return PitchReference(status="unverified", instrument_label=label, transposing_type=t_type)
        return PitchReference(
            status="verified",
            instrument_label=label,
            transposing_type=t_type,
            relation=relation,
            key_pairs=key_pairs,
            chord_pairs=chord_pairs,
        )
    except Exception:
        return PitchReference(status="unverified", instrument_label=inst)


def pitch_note(ref: PitchReference, used_keys: list[str], used_chords: list[str]) -> str:
    """Deterministic one-line label appended to the note. Empty for non-transposing instruments."""
    if not ref.transposing:
        return ""
    if ref.status != "verified":
        return (
            "Chord and key names in this note are concert pitch. "
            "Your instrument's written-pitch equivalents could not be verified, so none are shown."
        )
    text = (
        f"Chord and key names in this note are concert pitch. For your {ref.instrument_label}, "
        f"written pitch is {ref.relation} sounding pitch."
    )
    keys = [f"{k} concert = {ref.written_key(k)} written" for k in dict.fromkeys(used_keys) if ref.written_key(k)]
    chords = [f"{c} → {ref.written_chord(c)}" for c in dict.fromkeys(used_chords) if ref.written_chord(c)]
    if keys:
        text += " " + "; ".join(keys) + "."
    if chords:
        text += " Written chords: " + ", ".join(chords[:8]) + "."
    return text
