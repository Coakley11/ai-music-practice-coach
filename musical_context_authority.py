"""Authoritative practice key (tonic + mode) — separate from original song key."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PRACTICE_KEY_AUTHORITY_DIAG_KEY = "_practice_key_authority_diag"


@dataclass(frozen=True)
class AuthoritativePracticeKey:
    original_tonic: str
    original_mode: str
    practice_tonic: str
    practice_mode: str
    source: str = "session"

    @property
    def practice_key_token(self) -> str:
        root = str(self.practice_tonic or "C").strip() or "C"
        if str(self.practice_mode or "").lower() == "minor":
            if root.lower().endswith("m") and "maj" not in root.lower():
                return root
            return f"{root}m"
        return root

    @property
    def original_key_token(self) -> str:
        root = str(self.original_tonic or "C").strip() or "C"
        if str(self.original_mode or "").lower() == "minor":
            if root.lower().endswith("m"):
                return root
            return f"{root}m"
        return root

    def practice_label(self) -> str:
        try:
            from custom_progression_lab import format_key_label

            return format_key_label(self.practice_key_token)
        except ImportError:
            m = self.practice_mode
            return f"{self.practice_tonic} {m}" if m else self.practice_tonic

    def original_label(self) -> str:
        try:
            from custom_progression_lab import format_key_label

            return format_key_label(self.original_key_token)
        except ImportError:
            return self.original_key_token


def _mode_from_key_token(key: str) -> str:
    from music_theory import key_is_minor

    return "minor" if key_is_minor(str(key or "")) else "major"


def _tonic_from_key_token(key: str) -> str:
    from music_theory import normalize_root, split_chord

    root, _ = split_chord(str(key or "C").strip() or "C")
    return normalize_root(root) if normalize_root(root) else str(root or "C")


def resolve_authoritative_practice_key(
    session: dict[str, Any],
    *,
    rec: dict[str, Any] | None = None,
) -> AuthoritativePracticeKey:
    """Current practice transposition vs catalog original — never infer major from bare tonic."""
    try:
        from songs.key_state import resolve_active_musical_key

        ctx = resolve_active_musical_key(session, rec=rec, surface="practice_key_authority")
        practice_raw = str(ctx.practice_concert_key or "C").strip() or "C"
        original_raw = str(ctx.original_key or "C").strip() or "C"
    except ImportError:
        practice_raw = str(session.get("display_key") or session.get("concert_key") or "C").strip() or "C"
        original_raw = practice_raw
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if live and _mode_from_key_token(live) == "minor" and _mode_from_key_token(practice_raw) != "minor":
        practice_raw = live
    return AuthoritativePracticeKey(
        original_tonic=_tonic_from_key_token(original_raw),
        original_mode=_mode_from_key_token(original_raw),
        practice_tonic=_tonic_from_key_token(practice_raw),
        practice_mode=_mode_from_key_token(practice_raw),
        source="resolve_active_musical_key",
    )


def sidebar_key_list_mode(session: dict[str, Any]) -> str:
    """minor | major — which concert-key dropdown to show."""
    try:
        from creative_key_sync import is_creative_major_jam_active

        if is_creative_major_jam_active(session):
            return "major"
    except ImportError:
        pass
    pk = resolve_authoritative_practice_key(session)
    return pk.practice_mode


def format_practice_concert_key_line(session: dict[str, Any], *, fallback: str = "") -> str:
    """Human label including mode, e.g. 'E♭ minor'."""
    pk = resolve_authoritative_practice_key(session)
    label = pk.practice_label()
    if label:
        return label
    return str(fallback or "C major").strip() or "C major"


def song_catalog_context_owns_practice_key(session: dict[str, Any]) -> bool:
    """True when catalog/custom song (not generated jam) owns sidebar key mode."""
    try:
        from backing_workflow_context import get_backing_workflow_envelope

        env = get_backing_workflow_envelope(session) or {}
        wf = str(env.get("workflow_type") or "")
        if wf in {"entry_jam", "jam_session_generator"}:
            return False
        if env.get("source_type") == "generated":
            return False
        if wf in {"song_based_improvisation", "mission_jam", "regular_catalog_backing", "regular_custom_backing"}:
            return True
    except ImportError:
        pass
    tab = str(
        session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab") or ""
    ).strip()
    if tab in {"Missions", "Song-Based Improvisation"}:
        return True
    page = str(session.get("studio_page") or "").strip().lower()
    if page in {"practice", "picker"}:
        return True
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and str(ctx.source or "") in {"song_improv", "mission", "regular_song"}:
            return True
    except ImportError:
        pass
    return False


def run_musical_context_consistency_checks(session: dict[str, Any]) -> dict[str, Any]:
    """Aggregate violations for ?dev=1."""
    violations: list[str] = []
    pk = resolve_authoritative_practice_key(session)
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if live and _mode_from_key_token(live) != pk.practice_mode:
        violations.append("KEY_MODE_OWNER_MISMATCH")
    try:
        from creative_key_sync import is_creative_major_jam_active

        if song_catalog_context_owns_practice_key(session) and is_creative_major_jam_active(session):
            violations.append("KEY_MODE_OWNER_MISMATCH")
    except ImportError:
        pass
    diag = {
        "practice_key": pk.as_dict() if hasattr(pk, "as_dict") else pk.__dict__,
        "sidebar_key_list_mode": sidebar_key_list_mode(session),
        "violations": violations,
        "consistent": not violations,
    }
    session[PRACTICE_KEY_AUTHORITY_DIAG_KEY] = diag
    return diag


__all__ = [
    "AuthoritativePracticeKey",
    "PRACTICE_KEY_AUTHORITY_DIAG_KEY",
    "format_practice_concert_key_line",
    "resolve_authoritative_practice_key",
    "run_musical_context_consistency_checks",
    "sidebar_key_list_mode",
    "song_catalog_context_owns_practice_key",
]
