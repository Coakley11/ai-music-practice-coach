"""Scale-degree-aware pitch spelling for mission chord coach (E7 → F# not Gb)."""

from __future__ import annotations

from typing import Any

PITCH_SPELLING_DIAG_KEY = "_mission_pitch_spelling_diag"


def coaching_reference_for_mission_chord(
    chord: str,
    *,
    song_display_key: str = "",
    song_key_center: str = "",
) -> str:
    """
    Reference key for spelling chord tones and scales on the active mission chord.

    Uses the harmony in focus (chord root family), not an unrelated song/display key
    left over from another workflow (e.g. Ab after switching to E7).
    """
    from music_theory import (
        chord_root_for_theory,
        key_is_minor,
        normalize_chord_for_theory,
        normalize_root,
        reference_spelling_mode,
        split_chord,
    )

    symbol = normalize_chord_for_theory(chord) or str(chord or "").strip()
    root_raw, suffix = split_chord(symbol.split("/")[0].strip() or "C")
    root = normalize_root(chord_root_for_theory(symbol) or root_raw or "C")
    low = str(suffix or "").lower()
    song = str(song_display_key or song_key_center or "").strip()
    if song and normalize_root(split_chord(song)[0]) == root:
        return song
    if key_is_minor(song) and "m" in low and "maj" not in low:
        return f"{root} minor"
    if reference_spelling_mode(root) == reference_spelling_mode(song) and song:
        return song
    return root


def chord_coach_insight_for_mission(
    chord: str,
    *,
    song_display_key: str = "",
    song_key_center: str = "",
    **kwargs: Any,
):
    from improvisation_intelligence import chord_coach_insight

    ref = coaching_reference_for_mission_chord(
        chord,
        song_display_key=song_display_key,
        song_key_center=song_key_center,
    )
    insight = chord_coach_insight(chord, key_center=ref, **kwargs)
    try:
        from harmonic_spelling import build_scale_suggestion_for_chord

        insight.scale_suggestions = [
            build_scale_suggestion_for_chord(label, chord_symbol=str(chord or ""), reference_key=ref)
            for label in (insight.scales or [])
        ]
    except Exception:
        pass
    return insight


def record_pitch_spelling_diag(
    session: dict[str, Any],
    *,
    chord: str,
    song_display_key: str,
    reference_key: str,
) -> None:
    session[PITCH_SPELLING_DIAG_KEY] = {
        "chord": str(chord),
        "song_display_key": str(song_display_key),
        "reference_key": str(reference_key),
    }


__all__ = [
    "chord_coach_insight_for_mission",
    "coaching_reference_for_mission_chord",
    "record_pitch_spelling_diag",
]
