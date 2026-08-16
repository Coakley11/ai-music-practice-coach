"""Pre-widget consume for Song-Based / Mission sidebar Practice Concert Key edits."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from typing import Any, Literal

_LOG = logging.getLogger("music.song_practice_key_change")

PENDING_SONG_PRACTICE_KEY_EDIT_KEY = "_music_pending_song_practice_key_edit"
PENDING_SONG_PRACTICE_KEY_EDIT_CONSUMED_SEQ_KEY = "_music_pending_song_practice_key_edit_consumed_seq"
PENDING_SONG_PRACTICE_KEY_EDIT_CONSUMED_TOKEN_KEY = "_music_pending_song_practice_key_edit_consumed_token"
PENDING_SONG_PRACTICE_KEY_EDIT_LAST_DIAG_KEY = "_music_pending_song_practice_key_edit_last_diag"
SONG_PRACTICE_KEY_EDIT_OUTCOME_KEY = "_music_song_practice_key_edit_outcome"

ConsumePhase = Literal["applied", "skipped", "failed", "already_consumed", "invalid"]

_VALID_OWNERS = frozenset({"song_based_improvisation", "mission_jam"})
_CALLBACK_SOURCE = "sidebar_song_practice_key"


def _next_seq(session: dict[str, Any]) -> int:
    prev = int(session.get(PENDING_SONG_PRACTICE_KEY_EDIT_CONSUMED_SEQ_KEY) or 0)
    raw = session.get(PENDING_SONG_PRACTICE_KEY_EDIT_KEY)
    if isinstance(raw, dict):
        prev = max(prev, int(raw.get("request_seq") or 0))
    return prev + 1


def _parse_key_token(key: str) -> tuple[str, str]:
    try:
        from music_workflow_compatibility import _tonic_mode_from_token

        return _tonic_mode_from_token(str(key or "C"))
    except ImportError:
        token = str(key or "C").strip()
        if token.endswith("m") and len(token) > 1:
            return token[:-1], "minor"
        return token, "major"


def _workflow_identity_fingerprint(owner: str, session_id: str) -> str:
    return hashlib.sha256(f"{owner}|{session_id}".encode()).hexdigest()[:16]


def _blob_practice_key_token(blob: Any) -> str:
    try:
        from music_theory import key_center_token

        tonic = str(getattr(getattr(blob, "keys", None), "practice_tonic", "") or "").strip()
        mode = str(getattr(getattr(blob, "keys", None), "practice_mode", "major") or "major").strip().lower()
        return key_center_token(tonic, mode)
    except ImportError:
        tonic = str(getattr(getattr(blob, "keys", None), "practice_tonic", "") or "").strip()
        mode = str(getattr(getattr(blob, "keys", None), "practice_mode", "major") or "major").strip().lower()
        if mode == "minor" and tonic and not tonic.endswith("m"):
            return f"{tonic}m"
        return tonic or "C"


def _stable_song_id(session: dict[str, Any], owner: str, sid: str) -> str:
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    if pick:
        return pick
    return sid


def peek_pending_song_practice_key_edit(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(PENDING_SONG_PRACTICE_KEY_EDIT_KEY)
    return copy.deepcopy(raw) if isinstance(raw, dict) else None


def pending_selected_practice_key_token(session: dict[str, Any]) -> str:
    """Pending Practice Key for same-rerun Creative readers. Empty if owner no longer matches."""
    pending = peek_pending_song_practice_key_edit(session)
    if pending:
        token = str(pending.get("selected_key_token") or "").strip()
        if token:
            try:
                from music_workflow_state_store import get_active_workflow_pointer

                ptr = get_active_workflow_pointer(session)
                if ptr is None:
                    return ""
                if str(pending.get("workflow_owner") or "") != str(ptr.workflow_owner or ""):
                    return ""
                if str(pending.get("workflow_session_id") or "") != str(ptr.workflow_session_id or ""):
                    return ""
            except ImportError:
                return token
            return token
    try:
        from workflow_key_identity import generated_workflow_owns_practice_key

        if generated_workflow_owns_practice_key(session):
            return ""
    except ImportError:
        pass
    try:
        from songs.key_state import PENDING_DISPLAY_KEY

        return str(session.get(PENDING_DISPLAY_KEY) or "").strip()
    except ImportError:
        return str(session.get("_pending_display_key") or "").strip()


def overlay_destination_practice_key(session: dict[str, Any]) -> str:
    """Effective Practice Key for same-rerun readers.

    Prefer the queued sidebar edit, then the saved catalog Practice Key map,
    then live ``display_key`` when a catalog/song owner still holds the page.
    Generated-jam Concert Key must not become the overlay destination for
    catalog sections.
    """
    try:
        from creative_key_sync import generated_backing_owns_left_panel_key

        if generated_backing_owns_left_panel_key(session):
            return ""
    except ImportError:
        pass
    pending = pending_selected_practice_key_token(session)
    if pending:
        return pending
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    if pick and not pick.startswith("custom::"):
        try:
            from songs.practice_key_state import get_practice_concert_key

            saved = str(get_practice_concert_key(session, pick) or "").strip()
            if saved:
                return saved
        except ImportError:
            pass
    try:
        from workflow_key_identity import generated_workflow_owns_practice_key

        if generated_workflow_owns_practice_key(session):
            tab = str(
                session.get("improv_intelligence_tab") or session.get("improv_entry_mode") or ""
            ).strip()
            if tab in {"Style Jam Mode", "Jam Session Generator", "Entry & Jam"}:
                return ""
    except ImportError:
        pass
    return str(
        session.get("display_key") or session.get("_pending_display_key") or ""
    ).strip()


def infer_catalog_sections_spelled_in_key(
    session: dict[str, Any],
    sections: dict[str, list[str]],
    *,
    fallback: str = "",
) -> str:
    """Key the current catalog section map is actually spelled in.

    Blob Practice Key identity can already be the destination while the map is
    still original-pitch. Overlay must transpose from the map's real pitch.
    """
    orig = ""
    sel = session.get("selected_song")
    if isinstance(sel, dict):
        orig = str(sel.get("key") or sel.get("original_key") or "").strip()
    dest = overlay_destination_practice_key(session)
    blob = str(fallback or "").strip()
    catalog = None
    try:
        from songs.music_source import catalog_chart_sections_for_pick

        pick = str(session.get("active_catalog_pick_key") or "").strip()
        if pick:
            catalog = catalog_chart_sections_for_pick(session, pick)
    except ImportError:
        catalog = None
    home = session.get("home_sections") if isinstance(session.get("home_sections"), dict) else None
    if not isinstance(sections, dict) or not sections:
        return blob or orig or dest
    try:
        from music_theory import transpose_sections_dict
        from workflow_musical_authority import section_maps_equivalent
    except ImportError:
        return blob or orig or dest
    if isinstance(catalog, dict) and catalog and section_maps_equivalent(sections, catalog):
        return orig or dest
    if isinstance(home, dict) and home and section_maps_equivalent(sections, home):
        return orig or dest
    if orig and dest and dest != orig:
        try:
            from music_theory import normalize_root, split_chord

            first = ""
            for chs in sections.values():
                if isinstance(chs, list) and chs:
                    first = str(chs[0] or "").strip()
                    if first:
                        break
            if first:
                orig_root = normalize_root(split_chord(orig)[0])
                first_root = normalize_root(split_chord(first)[0])
                dest_root = normalize_root(split_chord(dest)[0])
                if orig_root and first_root == orig_root and first_root != dest_root:
                    return orig
        except Exception:
            pass
    if orig and dest and dest != orig and isinstance(catalog, dict) and catalog:
        try:
            expected = transpose_sections_dict(catalog, orig, dest)
            if section_maps_equivalent(sections, expected):
                return dest
        except Exception:
            pass
    if orig and blob and blob != orig and isinstance(catalog, dict) and catalog:
        try:
            expected = transpose_sections_dict(catalog, orig, blob)
            if section_maps_equivalent(sections, expected):
                return blob
        except Exception:
            pass
    return blob or orig or dest


def overlay_concert_token_with_pending_practice_key(
    session: dict[str, Any],
    canonical_token: str,
) -> str:
    """Same-rerun concert Practice Key: pending/saved edit wins over the still-uncommitted blob."""
    dest = overlay_destination_practice_key(session)
    return dest or str(canonical_token or "").strip()


def overlay_sections_with_pending_practice_key(
    session: dict[str, Any],
    sections: dict[str, list[str]],
    *,
    spelled_in_key: str,
) -> dict[str, list[str]]:
    """Transpose a concert section map toward a queued Practice Key without writing session.

    ``spelled_in_key`` must be the key the sections are currently spelled in
    (committed blob / last committed practice key), not the destination.
    """
    dest = overlay_destination_practice_key(session)
    src = infer_catalog_sections_spelled_in_key(
        session, sections, fallback=str(spelled_in_key or "")
    )
    if not dest or not src or dest == src or not isinstance(sections, dict) or not sections:
        return sections
    try:
        from music_theory import transpose_sections_dict

        return transpose_sections_dict(sections, src, dest)
    except ImportError:
        return sections


def overlay_chord_with_pending_practice_key(
    session: dict[str, Any],
    chord: str,
    *,
    spelled_in_key: str,
) -> str:
    dest = overlay_destination_practice_key(session)
    src = str(spelled_in_key or "").strip()
    raw = str(chord or "").strip()
    orig = ""
    sel = session.get("selected_song")
    if isinstance(sel, dict):
        orig = str(sel.get("key") or sel.get("original_key") or "").strip()
    if dest and orig and dest == src and orig != dest and raw:
        home = session.get("home_sections") if isinstance(session.get("home_sections"), dict) else {}
        catalog_hit = False
        for chs in (home or {}).values():
            if isinstance(chs, list) and any(str(c).strip() == raw for c in chs):
                catalog_hit = True
                break
        if catalog_hit:
            src = orig
    if not dest or not src or dest == src or not raw:
        return raw
    try:
        from music_theory import semitone_distance, transpose_chord

        steps = semitone_distance(src, dest)
        if not steps:
            return raw
        return transpose_chord(raw, steps, reference_key=dest)
    except ImportError:
        return raw


def clear_pending_song_practice_key_edit(session: dict[str, Any]) -> None:
    session.pop(PENDING_SONG_PRACTICE_KEY_EDIT_KEY, None)


def queue_pending_song_practice_key_edit(
    session: dict[str, Any],
    *,
    selected_key_token: str,
    workflow_owner: str = "",
    workflow_session_id: str = "",
) -> dict[str, Any] | None:
    selected = str(selected_key_token or session.get("display_key") or "").strip()
    owner = str(workflow_owner or "").strip()
    sid = str(workflow_session_id or "").strip()
    if not selected:
        return None
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if not owner and ptr:
            owner = str(ptr.workflow_owner or "")
        if not sid and ptr:
            sid = str(ptr.workflow_session_id or "")
        if owner not in _VALID_OWNERS:
            return None
        if not sid:
            from music_workflow_compatibility import legacy_session_id_for_owner

            sid = str(legacy_session_id_for_owner(session, owner) or "").strip()
        blob = get_workflow_blob(session, owner, sid) if sid else None
        fp = str(getattr(blob, "material_fingerprint", "") or "") if blob else ""
        rev = int(getattr(blob, "context_revision", 0) or 0) if blob else 0
    except ImportError:
        return None
    if not sid:
        return None
    tonic, mode = _parse_key_token(selected)
    if not tonic:
        return None
    pick_key = str(session.get("active_catalog_pick_key") or "").strip()
    stable_id = _stable_song_id(session, owner, sid)
    seq = _next_seq(session)
    payload = {
        "request_seq": seq,
        "request_token": hashlib.sha256(
            json.dumps(
                {
                    "seq": seq,
                    "owner": owner,
                    "sid": sid,
                    "pick": pick_key,
                    "stable": stable_id,
                    "key": selected,
                    "src": _CALLBACK_SOURCE,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()[:24],
        "workflow_owner": owner,
        "workflow_session_id": sid,
        "stable_song_id": stable_id,
        "active_catalog_pick_key": pick_key,
        "selected_key_token": selected,
        "practice_tonic": tonic,
        "practice_mode": mode,
        "callback_source": _CALLBACK_SOURCE,
        "material_fingerprint": fp[:32],
        "context_revision": rev,
        "identity_fingerprint": _workflow_identity_fingerprint(owner, sid),
    }
    try:
        from music_workflow_pending_intent_scope import capture_pending_intent_scope

        payload["scope"] = capture_pending_intent_scope(session)
    except ImportError:
        pass
    session[PENDING_SONG_PRACTICE_KEY_EDIT_KEY] = payload
    return copy.deepcopy(payload)


def _widgets_locked(session: dict[str, Any]) -> bool:
    try:
        from music_workflow_pre_widget_bootstrap import PRE_WIDGET_BOOTSTRAP_ACTIVE_KEY

        if session.get(PRE_WIDGET_BOOTSTRAP_ACTIVE_KEY):
            return False
    except ImportError:
        pass
    if session.get("_music_first_streamlit_widget"):
        return True
    try:
        from session_widget_safe import widgets_likely_instantiated

        return bool(widgets_likely_instantiated(session))
    except ImportError:
        return bool(session.get("_streamlit_widgets_locked_this_run"))


def _validate_pending(session: dict[str, Any], pending: dict[str, Any]) -> str | None:
    if not str(pending.get("request_token") or "").strip():
        return "malformed_request_token"
    owner = str(pending.get("workflow_owner") or "").strip()
    if owner not in _VALID_OWNERS:
        return "invalid_owner"
    if str(pending.get("callback_source") or "") != _CALLBACK_SOURCE:
        return "callback_source_mismatch"
    selected = str(pending.get("selected_key_token") or "").strip()
    if not selected:
        return "invalid_selected_key_token"
    pt, pm = _parse_key_token(selected)
    if not pt or pm not in {"major", "minor"}:
        return "invalid_tonic"
    pending_sid = str(pending.get("workflow_session_id") or "").strip()
    if not pending_sid:
        return "session_id_mismatch"
    pending_pick = str(pending.get("active_catalog_pick_key") or "").strip()
    live_pick = str(session.get("active_catalog_pick_key") or "").strip()
    if pending_pick and live_pick and pending_pick != live_pick:
        return "catalog_pick_mismatch"
    pending_stable = str(pending.get("stable_song_id") or "").strip()
    live_stable = _stable_song_id(session, owner, pending_sid)
    if pending_stable and live_stable and pending_stable != live_stable:
        return "stable_song_id_mismatch"
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if ptr is None:
            return "workflow_owner_mismatch"
        if str(ptr.workflow_owner or "") != owner:
            return "workflow_owner_mismatch"
        if str(ptr.workflow_session_id or "") != pending_sid:
            return "workflow_session_mismatch"
        if get_workflow_blob(session, owner, pending_sid) is None:
            return "session_id_mismatch"
    except ImportError:
        return "session_id_mismatch"
    return None


def _mark_consumed(session: dict[str, Any], pending: dict[str, Any], *, outcome: str) -> None:
    seq = pending.get("request_seq")
    token = str(pending.get("request_token") or "").strip()
    if seq is not None:
        session[PENDING_SONG_PRACTICE_KEY_EDIT_CONSUMED_SEQ_KEY] = seq
    if token:
        session[PENDING_SONG_PRACTICE_KEY_EDIT_CONSUMED_TOKEN_KEY] = token
    clear_pending_song_practice_key_edit(session)
    session[PENDING_SONG_PRACTICE_KEY_EDIT_LAST_DIAG_KEY] = {"result": outcome}


def consume_pending_song_practice_key_edit(session: dict[str, Any], *, st: Any | None = None) -> ConsumePhase:
    pending = session.get(PENDING_SONG_PRACTICE_KEY_EDIT_KEY)
    if not isinstance(pending, dict):
        return "skipped"
    token = str(pending.get("request_token") or "").strip()
    seq = pending.get("request_seq")
    if token and session.get(PENDING_SONG_PRACTICE_KEY_EDIT_CONSUMED_TOKEN_KEY) == token:
        clear_pending_song_practice_key_edit(session)
        return "already_consumed"
    if _widgets_locked(session):
        return "skipped"
    err = _validate_pending(session, pending)
    if err:
        session[PENDING_SONG_PRACTICE_KEY_EDIT_LAST_DIAG_KEY] = {"failed_predicate": err, "pending": copy.deepcopy(pending)}
        clear_pending_song_practice_key_edit(session)
        _LOG.info("[song_practice_key_change] consume_rejected %s", err)
        return "invalid"
    try:
        from music_workflow_pending_intent_scope import pending_intent_scope_matches, workflow_mutation_consume_allowed

        allowed, auth_reason = workflow_mutation_consume_allowed(session)
        if not allowed:
            session[PENDING_SONG_PRACTICE_KEY_EDIT_LAST_DIAG_KEY] = {
                "failed_predicate": auth_reason,
                "consume_deferred": True,
            }
            return "skipped"
        scope_ok, scope_reason = pending_intent_scope_matches(session, pending)
        if not scope_ok:
            clear_pending_song_practice_key_edit(session)
            session[PENDING_SONG_PRACTICE_KEY_EDIT_LAST_DIAG_KEY] = {"failed_predicate": scope_reason}
            return "invalid"
    except ImportError:
        pass
    owner = str(pending.get("workflow_owner") or "").strip()
    pending_sid = str(pending.get("workflow_session_id") or "").strip()
    selected = str(pending.get("selected_key_token") or "").strip()
    try:
        from music_workflow_state_store import get_workflow_blob

        blob = get_workflow_blob(session, owner, pending_sid)
        if blob is not None and _blob_practice_key_token(blob) == selected:
            session[SONG_PRACTICE_KEY_EDIT_OUTCOME_KEY] = {"canonical_commit": "NOOP_ALREADY"}
            _mark_consumed(session, pending, outcome="applied_noop")
            return "applied"
    except ImportError:
        pass
    try:
        from song_practice_key_change_trace import collect_song_practice_key_snapshot

        collect_song_practice_key_snapshot(session, phase="pre_widget_consume_before")
    except ImportError:
        pass
    try:
        from song_practice_key_sidebar_change import apply_pending_song_practice_key_edit_pre_widget

        ok = apply_pending_song_practice_key_edit_pre_widget(session, pending, st_like=st)
    except ImportError:
        ok = False
    if not ok:
        session[PENDING_SONG_PRACTICE_KEY_EDIT_LAST_DIAG_KEY] = {"failed_predicate": "mutation_or_projection_failed"}
        clear_pending_song_practice_key_edit(session)
        return "failed"
    _mark_consumed(session, pending, outcome="applied")
    try:
        from song_practice_key_change_trace import collect_song_practice_key_snapshot

        collect_song_practice_key_snapshot(session, phase="pre_widget_consume_after")
    except ImportError:
        pass
    return "applied"


__all__ = [
    "PENDING_SONG_PRACTICE_KEY_EDIT_KEY",
    "PENDING_SONG_PRACTICE_KEY_EDIT_CONSUMED_SEQ_KEY",
    "PENDING_SONG_PRACTICE_KEY_EDIT_CONSUMED_TOKEN_KEY",
    "PENDING_SONG_PRACTICE_KEY_EDIT_LAST_DIAG_KEY",
    "clear_pending_song_practice_key_edit",
    "consume_pending_song_practice_key_edit",
    "overlay_chord_with_pending_practice_key",
    "overlay_concert_token_with_pending_practice_key",
    "overlay_destination_practice_key",
    "overlay_sections_with_pending_practice_key",
    "peek_pending_song_practice_key_edit",
    "pending_selected_practice_key_token",
    "queue_pending_song_practice_key_edit",
]
