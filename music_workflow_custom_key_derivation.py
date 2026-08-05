"""Derive practice key from custom progression when metadata is explicit (Commit 6)."""

from __future__ import annotations

from typing import Any

from music_workflow_compatibility import _tonic_mode_from_token


def derive_key_from_progression_sections(sections: dict[str, list[str]]) -> tuple[str, str] | None:
    """
    Return (tonic, mode) when unambiguous from the first section's chords.
    Returns None when ambiguous — caller must fail closed.
    """
    if not sections:
        return None
    first_chords: list[str] = []
    for _name, chords in sections.items():
        if isinstance(chords, list) and chords:
            first_chords = [str(c).strip() for c in chords if str(c).strip()]
            break
    if not first_chords:
        return None
    root = first_chords[0]
    try:
        from music_theory import key_is_minor, normalize_root, split_chord

        r, _ = split_chord(root)
        tonic = normalize_root(r) or ""
        if not tonic:
            return None
        mode = "minor" if key_is_minor(root) else "major"
        if len(first_chords) >= 2:
            second = first_chords[1]
            r2, _ = split_chord(second)
            t2 = normalize_root(r2) or ""
            if mode == "major" and t2 and t2 != tonic:
                return tonic, mode
            if mode == "minor" and "m" not in second.lower() and t2:
                return None
        return tonic, mode
    except ImportError:
        pt, pm = _tonic_mode_from_token(root)
        if pt in {"", "C"} and pm == "major" and root.upper() not in {"C", "CMAJ", "CMAJ7"}:
            return None
        return pt, pm


def load_persisted_song_practice_keys(session: dict[str, Any], source_type: str, song_id: str) -> tuple[str, str] | None:
    """Read per-song practice key from song-based workflow blob if present."""
    try:
        from music_workflow_state_store import get_workflow_blob

        sid = song_id if source_type == "catalog" else f"custom|{song_id}"
        blob = get_workflow_blob(session, "song_based_improvisation", sid)
        if blob and str(blob.keys.practice_tonic or "").strip():
            return str(blob.keys.practice_tonic), str(blob.keys.practice_mode or "major")
    except ImportError:
        pass
    return None


__all__ = ["derive_key_from_progression_sections", "load_persisted_song_practice_keys"]
