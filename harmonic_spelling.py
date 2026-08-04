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


__all__ = [
    "SPELLING_DIAG_KEY",
    "build_scale_suggestion_for_chord",
    "harmonic_reference_for_chord",
    "record_spelling_consistency_check",
    "scale_root_for_label",
    "spelled_chord_root_from_symbol",
]
