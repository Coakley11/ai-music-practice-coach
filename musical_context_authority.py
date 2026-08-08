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
            from music_theory import format_key_label_from_parts

            return format_key_label_from_parts(self.practice_tonic, self.practice_mode)
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
    from music_theory import split_key_center

    _, mode = split_key_center(str(key or "C"))
    return mode


def _tonic_from_key_token(key: str) -> str:
    from music_theory import split_key_center

    tonic, _ = split_key_center(str(key or "C"))
    return str(tonic or "C").strip() or "C"


def resolve_authoritative_practice_key(
    session: dict[str, Any],
    *,
    rec: dict[str, Any] | None = None,
) -> AuthoritativePracticeKey:
    """Current practice transposition vs catalog original — never infer major from bare tonic."""
    try:
        from workflow_key_identity import resolve_practice_key_identity_for_ui

        ident = resolve_practice_key_identity_for_ui(session)
        if ident is not None:
            orig_t, orig_m = ident.practice_tonic, ident.practice_mode
            try:
                from songs.key_state import resolve_active_musical_key

                ctx = resolve_active_musical_key(session, rec=rec, surface="practice_key_authority")
                orig_t = _tonic_from_key_token(str(ctx.original_key or ident.practice_key_token))
                orig_m = _mode_from_key_token(str(ctx.original_key or ident.practice_key_token))
            except ImportError:
                pass
            if ident.workflow_owner in {"song_based_improvisation", "mission_jam"}:
                try:
                    from songs.key_state import resolve_active_musical_key

                    ctx = resolve_active_musical_key(session, rec=rec, surface="practice_key_authority")
                    original_raw = str(ctx.original_key or ident.practice_key_token).strip()
                    orig_t = _tonic_from_key_token(original_raw)
                    orig_m = _mode_from_key_token(original_raw)
                except ImportError:
                    pass
            return AuthoritativePracticeKey(
                original_tonic=orig_t,
                original_mode=orig_m,
                practice_tonic=ident.practice_tonic,
                practice_mode=ident.practice_mode,
                source=ident.source,
            )
    except ImportError:
        pass
    if song_catalog_context_owns_practice_key(session):
        try:
            from music_workflow_song_practice import resolve_song_practice_key_token

            song_tok = resolve_song_practice_key_token(session)
            if song_tok:
                try:
                    from songs.key_state import resolve_active_musical_key

                    ctx = resolve_active_musical_key(session, rec=rec, surface="practice_key_authority")
                    original_raw = str(ctx.original_key or song_tok).strip() or song_tok
                except ImportError:
                    original_raw = song_tok
                return AuthoritativePracticeKey(
                    original_tonic=_tonic_from_key_token(original_raw),
                    original_mode=_mode_from_key_token(original_raw),
                    practice_tonic=_tonic_from_key_token(song_tok),
                    practice_mode=_mode_from_key_token(song_tok),
                    source="song_based_blob_practice_key",
                )
        except ImportError:
            pass
    try:
        from creative_key_sync import resolve_creative_tab_practice_key_token

        jam_tok = resolve_creative_tab_practice_key_token(session)
        if jam_tok:
            return AuthoritativePracticeKey(
                original_tonic=_tonic_from_key_token(jam_tok),
                original_mode=_mode_from_key_token(jam_tok),
                practice_tonic=_tonic_from_key_token(jam_tok),
                practice_mode=_mode_from_key_token(jam_tok),
                source="entry_jam_practice_key",
            )
    except ImportError:
        pass
    try:
        from songs.key_state import resolve_active_musical_key

        ctx = resolve_active_musical_key(session, rec=rec, surface="practice_key_authority")
        practice_raw = str(ctx.practice_concert_key or "C").strip() or "C"
        original_raw = str(ctx.original_key or "C").strip() or "C"
    except ImportError:
        practice_raw = str(session.get("display_key") or session.get("concert_key") or "C").strip() or "C"
        original_raw = practice_raw
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if (
        live
        and _mode_from_key_token(live) == "minor"
        and _mode_from_key_token(practice_raw) != "minor"
        and not song_catalog_context_owns_practice_key(session)
    ):
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
    try:
        from workflow_key_identity import resolve_practice_key_identity_for_ui

        ident = resolve_practice_key_identity_for_ui(session)
        if ident is not None and ident.practice_label:
            return ident.practice_label
    except ImportError:
        pass
    pk = resolve_authoritative_practice_key(session)
    label = pk.practice_label()
    if label:
        return label
    return str(fallback or "C major").strip() or "C major"


def catalog_song_should_own_sidebar_practice_key(session: dict[str, Any]) -> bool:
    """Catalog / mission song workflows must not inherit Style Jam major-key sidebar projection."""
    try:
        from creative_key_sync import entry_jam_practice_key_authority_active

        if entry_jam_practice_key_authority_active(session):
            return False
    except ImportError:
        pass
    pick = str(session.get("active_catalog_pick_key") or session.get("song") or "").strip()
    tab = str(
        session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab") or ""
    ).strip()
    page = str(session.get("studio_page") or "").strip().lower()
    if pick and tab in {"Song-Based Improvisation", "Missions", "Phrase / Motif"}:
        return True
    if pick and page in {"practice", "picker"}:
        return True
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") in {
            "song_based_improvisation",
            "mission_jam",
            "regular_catalog_backing",
            "regular_custom_backing",
        }:
            return True
    except ImportError:
        pass
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and str(ctx.source or "") == "regular_song" and pick:
            return True
    except ImportError:
        pass
    return False


def song_catalog_context_owns_practice_key(session: dict[str, Any]) -> bool:
    """True when catalog/custom song (not generated jam) owns sidebar key mode."""
    if catalog_song_should_own_sidebar_practice_key(session):
        return True
    try:
        from generated_jam_key_context import generated_jam_owns_practice_key

        if generated_jam_owns_practice_key(session):
            return False
    except ImportError:
        pass
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
    if tab in {"Missions", "Song-Based Improvisation", "Phrase / Motif"}:
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
    try:
        from musical_context_coherence import run_musical_context_coherence_checks

        coherence = run_musical_context_coherence_checks(session)
        violations.extend(list(coherence.get("violations") or []))
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
