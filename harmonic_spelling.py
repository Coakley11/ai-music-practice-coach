"""Chord-aware enharmonic spelling for coach text, scales, and notation."""

from __future__ import annotations

from typing import Any

SPELLING_DIAG_KEY = "_harmonic_spelling_diag"


def spelled_chord_root_from_symbol(chord: object) -> str:
    """Preserve explicit chord-symbol root spelling (Bb stays Bb, not A#)."""
    from music_theory import normalize_chord_for_theory, split_chord

    head = normalize_chord_for_theory(chord).split("/", 1)[0].strip()
    if not head:
        head = str(chord or "").split("/", 1)[0].strip()
    root_raw, _ = split_chord(head or "C")
    return str(root_raw or "C").strip() or "C"


def harmonic_reference_for_chord(
    chord: object,
    *,
    song_display_key: str = "",
    song_key_center: str = "",
) -> str:
    """
    Reference key for spelling scale degrees.

    Precedence: explicit chord root family → chord-aware mission reference → song context.
    """
    root = spelled_chord_root_from_symbol(chord)
    if "b" in root:
        return root
    if "#" in root:
        return root
    try:
        from music_theory import key_is_minor, normalize_chord_for_theory, normalize_root, split_chord

        head = normalize_chord_for_theory(chord).split("/", 1)[0].strip() or str(chord or "").split("/", 1)[0].strip()
        _, suffix = split_chord(head or "C")
        low = str(suffix or "").lower()
        song = str(song_display_key or song_key_center or "").strip()
        is_minor_chord = "m" in low and "maj" not in low and "dim" not in low
        if song and key_is_minor(song) and not is_minor_chord:
            if normalize_root(split_chord(song)[0]) != normalize_root(root):
                return root
    except ImportError:
        pass
    try:
        from mission_pitch_spelling import coaching_reference_for_mission_chord

        return coaching_reference_for_mission_chord(
            str(chord or ""),
            song_display_key=song_display_key,
            song_key_center=song_key_center,
        )
    except ImportError:
        pass
    song = str(song_display_key or song_key_center or "").strip()
    return song or root


def scale_root_for_label(
    scale_label: str,
    *,
    chord_symbol: str,
    reference_key: str = "",
) -> str:
    """Root token for a scale name, honoring the active chord symbol."""
    text = str(scale_label or "").strip()
    parts = text.split(None, 1)
    label_root = parts[0] if parts else "C"
    if chord_symbol:
        spelled = spelled_chord_root_from_symbol(chord_symbol)
        ref = harmonic_reference_for_chord(
            chord_symbol,
            song_display_key=reference_key,
            song_key_center=reference_key,
        )
        from music_theory import normalize_root, split_chord

        if normalize_root(label_root) == normalize_root(spelled):
            return spelled
        return spelled_chord_root_from_symbol(chord_symbol)
    from music_theory import respell_note_for_key

    return respell_note_for_key(label_root, reference_key or "C")


def build_scale_suggestion_for_chord(
    label: str,
    *,
    chord_symbol: str = "",
    reference_key: str = "C",
) -> Any:
    """Build scale suggestion with chord-first spelling."""
    from improvisation_intelligence import build_scale_suggestion

    if not chord_symbol:
        return build_scale_suggestion(label, reference_key=reference_key)
    text = str(label or "").strip()
    parts = text.split(None, 1)
    kind = parts[1] if len(parts) > 1 else "major"
    root = scale_root_for_label(text, chord_symbol=chord_symbol, reference_key=reference_key)
    ref = harmonic_reference_for_chord(chord_symbol, song_display_key=reference_key, song_key_center=reference_key)
    patched_label = f"{root} {kind}".strip()
    return build_scale_suggestion(patched_label, reference_key=ref)


def record_spelling_consistency_check(
    session: dict[str, Any],
    *,
    chord_symbol: str,
    reference_key: str,
    scale_labels: list[str] | None = None,
) -> dict[str, Any]:
    """Dev helper: detect A# scale labels on Bb chords, etc."""
    violations: list[str] = []
    spelled = spelled_chord_root_from_symbol(chord_symbol)
    for label in scale_labels or []:
        root_token = str(label or "").split(None, 1)[0]
        if spelled.lower().startswith("bb") and root_token.replace("♯", "#").startswith("A#"):
            violations.append("CHORD_SPELLING_CONTEXT_MISMATCH")
            break
        if spelled.startswith("B") and not spelled.startswith("Bb") and "b" not in spelled:
            if root_token.startswith("Bb") and "major" in str(chord_symbol).lower():
                violations.append("CHORD_SPELLING_CONTEXT_MISMATCH")
    diag = {
        "chord_symbol": str(chord_symbol),
        "spelled_root": spelled,
        "reference_key": reference_key,
        "violations": violations,
        "consistent": not violations,
    }
    session[SPELLING_DIAG_KEY] = diag
    return diag


def prefer_sharps_for_chord_symbol(chord: object) -> bool | None:
    """True when the chord's authoritative spelling family is sharp-oriented."""
    from music_theory import reference_spelling_mode

    ref = harmonic_reference_for_chord(chord)
    mode = reference_spelling_mode(ref)
    if mode == "sharp":
        return True
    if mode == "flat":
        return False
    return None


def _note_set_uses_wrong_accidental_family(notes: list[str], *, prefer_sharps: bool) -> bool:
    joined = " ".join(str(n) for n in notes)
    if prefer_sharps:
        for bad in ("Eb", "Gb", "Ab", "Db", "Cb", "Bb", "Fb"):
            if bad in joined and f"{bad}7" not in joined:
                if bad + " " in joined or joined.startswith(bad) or f", {bad}" in joined or f"· {bad}" in joined:
                    return True
                if f" {bad}" in joined or f"{bad}," in joined:
                    return True
    else:
        for bad in ("C#", "D#", "F#", "G#", "A#", "E#", "B#"):
            if bad in joined:
                return True
    return False


def assert_mission_spelling_consistency(
    session: dict[str, Any],
    *,
    chord_symbol: str,
    stable_tones: list[str] | None = None,
    coaching_tones: list[str] | None = None,
    color_tones: list[str] | None = None,
    scale_note_text: str = "",
    motif_notes: list[str] | None = None,
    notation_text: str = "",
) -> dict[str, Any]:
    """Dev/runtime check — one accidental family per mission chord surface."""
    from improvisation_motif import chord_tone_names

    chord = str(chord_symbol or "").strip()
    ref = harmonic_reference_for_chord(chord)
    prefer_sh = prefer_sharps_for_chord_symbol(chord)
    parsed = chord_tone_names(chord, reference_key=ref)[:3]
    violations: list[str] = []

    def _check(label: str, notes: list[str] | None) -> None:
        if prefer_sh is None or not notes:
            return
        if _note_set_uses_wrong_accidental_family(list(notes), prefer_sharps=prefer_sh):
            violations.append(label)

    _check("MISSION_CHORD_TONE_SPELLING_MISMATCH", stable_tones or parsed)
    _check("MISSION_COACHING_SPELLING_MISMATCH", coaching_tones)
    _check("MISSION_COLOR_TONE_SPELLING_MISMATCH", color_tones)
    _check("MISSION_EXAMPLE_SPELLING_MISMATCH", motif_notes)
    if prefer_sh is True and any(x in scale_note_text for x in ("Eb", "Gb", "Ab")):
        if "C#" in scale_note_text or "D#" in scale_note_text or "F#" in scale_note_text:
            pass
        elif "Eb" in scale_note_text or "Gb" in scale_note_text:
            violations.append("MISSION_SCALE_SPELLING_MISMATCH")
    if prefer_sh is True and notation_text:
        if any(x in notation_text for x in ("_e", "_g", "_a", "_d")) and "B major" in chord.upper():
            violations.append("MISSION_NOTATION_SPELLING_MISMATCH")
        if "^D" in notation_text or "^F" in notation_text or "^G" in notation_text:
            pass
        elif "_e" in notation_text.lower() or "_g" in notation_text.lower():
            violations.append("MISSION_NOTATION_SPELLING_MISMATCH")

    diag = {
        "chord_symbol": chord,
        "reference_key": ref,
        "prefer_sharps": prefer_sh,
        "parsed_chord_tones": parsed,
        "violations": violations,
        "consistent": not violations,
    }
    session["_mission_spelling_consistency"] = diag
    return diag


def notation_spelling_mode_for_chord(chord: object, *, song_display_key: str = "") -> str:
    """flat | sharp | natural for ABC and motif note names."""
    from music_theory import reference_spelling_mode

    ref = harmonic_reference_for_chord(
        chord,
        song_display_key=song_display_key,
        song_key_center=song_display_key,
    )
    mode = reference_spelling_mode(ref)
    if mode != "natural":
        return mode
    root = spelled_chord_root_from_symbol(chord)
    return reference_spelling_mode(root)


def spell_pitch_classes_for_chord(
    pitch_classes: list[int],
    chord: object,
    *,
    song_display_key: str = "",
) -> list[str]:
    from music_theory import spell_pitch_class

    mode = notation_spelling_mode_for_chord(chord, song_display_key=song_display_key)
    return [spell_pitch_class(int(pc) % 12, mode=mode) for pc in pitch_classes]


def apply_motif_chord_spelling(
    motif: dict[str, Any],
    chord: object,
    *,
    song_display_key: str = "",
) -> dict[str, Any]:
    """Rewrite motif note names from MIDI using the active chord spelling family."""
    from music_theory import NOTE_TO_MIDI, normalize_root, split_chord

    midis = list(motif.get("midi") or [])
    notes = list(motif.get("notes") or [])
    if not midis and notes:
        midis = []
        for n in notes:
            root = normalize_root(split_chord(str(n))[0])
            midis.append(NOTE_TO_MIDI.get(root, 60))
    if not midis:
        return motif
    ref = harmonic_reference_for_chord(
        str(chord or motif.get("chord") or ""),
        song_display_key=song_display_key,
    )
    spelled = spell_pitch_classes_for_chord(
        [int(m) % 12 for m in midis],
        chord,
        song_display_key=song_display_key,
    )
    motif["notes"] = spelled
    motif["display"] = " – ".join(spelled)
    motif["midi"] = [int(m) for m in midis]
    motif["spelling_reference"] = ref
    motif["chord"] = str(chord or motif.get("chord") or "")
    return motif


__all__ = [
    "SPELLING_DIAG_KEY",
    "assert_mission_spelling_consistency",
    "apply_motif_chord_spelling",
    "build_scale_suggestion_for_chord",
    "harmonic_reference_for_chord",
    "prefer_sharps_for_chord_symbol",
    "record_spelling_consistency_check",
    "scale_root_for_label",
    "spelled_chord_root_from_symbol",
]
