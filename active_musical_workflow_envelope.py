"""Single authoritative active musical workflow envelope — all renderers consume this."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

ACTIVE_WORKFLOW_ENVELOPE_KEY = "_active_musical_workflow_envelope"
WORKFLOW_ENVELOPE_DIAG_KEY = "_active_workflow_envelope_diag"

VIOLATION_MISSION_SELECTED_CHORD_MISMATCH = "MISSION_SELECTED_CHORD_MISMATCH"
VIOLATION_MISSION_EXAMPLE_OWNER_MISMATCH = "MISSION_EXAMPLE_OWNER_MISMATCH"
VIOLATION_MISSION_BACKING_HANDOFF_MISMATCH = "MISSION_BACKING_HANDOFF_MISMATCH"
VIOLATION_MISSION_RECORDING_SEAL_MISMATCH = "MISSION_RECORDING_SEAL_MISMATCH"
VIOLATION_SONG_PRACTICE_KEY_MISMATCH = "SONG_PRACTICE_KEY_MISMATCH"
VIOLATION_WORKFLOW_KEY_OWNER_MISMATCH = "WORKFLOW_KEY_OWNER_MISMATCH"
VIOLATION_STALE_GENERATED_JAM_KEY_LEAK = "STALE_GENERATED_JAM_KEY_LEAK"
VIOLATION_STALE_MISSION_ARTIFACT_RESTORED = "STALE_MISSION_ARTIFACT_RESTORED"
VIOLATION_DUPLICATE_BACKING_NAV_ACTION = "DUPLICATE_BACKING_NAV_ACTION"


@dataclass
class ActiveMusicalWorkflowEnvelope:
    workflow_owner: str = ""
    workflow_session_id: str = ""
    source_type: str = ""
    song_id: str = ""
    song_title: str = ""
    original_song_tonic: str = ""
    original_song_mode: str = ""
    current_practice_concert_tonic: str = ""
    current_practice_concert_mode: str = ""
    current_practice_concert_key: str = ""
    instrument: str = ""
    section: str = ""
    chord_index: int = 0
    selected_chord_symbol: str = ""
    mission_id: str = ""
    mission_type: str = ""
    artifact_id: str = ""
    artifact_fingerprint: str = ""
    example_chord: str = ""
    example_fingerprint: str = ""
    backing_handoff_chord: str = ""
    recording_seal_chord: str = ""
    backing_display_concert_key: str = ""
    style_owner: str = ""
    style_groove: str = ""
    progression_owner: str = ""
    backing_workflow_type: str = ""
    context_revision: str = ""

    def fingerprint(self) -> str:
        payload = {
            k: v
            for k, v in asdict(self).items()
            if k not in {"context_revision", "artifact_fingerprint", "example_fingerprint"}
        }
        blob = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()[:20]


def _selected_mission_fields(session: dict[str, Any]) -> tuple[str, str, int, str]:
    try:
        from mission_practice_context import _authoritative_chord_fields

        return _authoritative_chord_fields(session)
    except ImportError:
        symbol = str(session.get("ii_selected_chord") or "").strip()
        section = str(session.get("ii_selected_section") or "").strip()
        idx = int(session.get("ii_selected_chord_index") or 0)
        label = str(session.get("ii_selected_chord_label") or symbol).strip()
        return symbol, section, idx, label


def build_active_workflow_envelope(session: dict[str, Any]) -> ActiveMusicalWorkflowEnvelope:
    """Assemble envelope — active store blob is authoritative when pointer is set."""
    ptr = None
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if ptr and ptr.workflow_owner:
            blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
            if blob:
                return _envelope_from_workflow_blob(session, blob, ptr)
    except ImportError:
        pass
    return _build_active_workflow_envelope_legacy(session, ptr)


def project_envelope_from_active_store(session: dict[str, Any]) -> ActiveMusicalWorkflowEnvelope:
    """Compatibility projection: active blob → envelope read model (one-way)."""
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob, record_compat_fallback

        ptr = get_active_workflow_pointer(session)
        if not ptr or not ptr.workflow_owner:
            record_compat_fallback(session, "envelope_projection_no_pointer", "")
            return _build_active_workflow_envelope_legacy(session, None)
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        if blob is None:
            record_compat_fallback(session, "envelope_projection_missing_blob", ptr.workflow_owner)
            return _build_active_workflow_envelope_legacy(session, ptr)
        env = _envelope_from_workflow_blob(session, blob, ptr)
        session[ACTIVE_WORKFLOW_ENVELOPE_KEY] = asdict(env)
        return env
    except ImportError:
        return build_active_workflow_envelope(session)


def _envelope_from_workflow_blob(
    session: dict[str, Any],
    blob: Any,
    ptr: Any,
) -> ActiveMusicalWorkflowEnvelope:
    env = ActiveMusicalWorkflowEnvelope()
    env.workflow_owner = str(blob.workflow_owner or "")
    env.workflow_session_id = str(blob.workflow_session_id or "")
    env.original_song_tonic = str(blob.keys.original_tonic or "")
    env.original_song_mode = str(blob.keys.original_mode or "")
    env.current_practice_concert_tonic = str(blob.keys.practice_tonic or "")
    env.current_practice_concert_mode = str(blob.keys.practice_mode or "")
    tonic = env.current_practice_concert_tonic
    mode = env.current_practice_concert_mode
    env.current_practice_concert_key = f"{tonic}m" if mode == "minor" else tonic
    env.instrument = str(session.get("instrument") or "Piano").strip()
    env.song_id = str(blob.song_id or session.get("active_catalog_pick_key") or "").strip()
    env.song_title = str(blob.song_title or session.get("song") or "").strip()
    env.selected_chord_symbol = str(blob.selected_chord_symbol or "")
    env.section = str(blob.selected_section or "")
    env.chord_index = int(blob.selected_chord_index or 0)
    env.mission_type = str(blob.mission_type or "")
    env.mission_id = str(blob.mission_id or "")
    env.artifact_fingerprint = str(blob.artifact_fingerprint or "")
    env.example_fingerprint = str(blob.example_fingerprint or "")
    env.backing_handoff_chord = str(blob.backing_handoff_chord or "")
    env.recording_seal_chord = str(blob.recording_seal_chord or "")
    env.style_owner = str(blob.style_owner or "")
    env.style_groove = str(blob.groove or blob.style or "")
    env.progression_owner = str(blob.progression_owner or "")
    env.context_revision = str(ptr.context_revision if ptr else blob.context_revision)
    session[ACTIVE_WORKFLOW_ENVELOPE_KEY] = asdict(env)
    return env


def _build_active_workflow_envelope_legacy(session: dict[str, Any], ptr: Any | None) -> ActiveMusicalWorkflowEnvelope:
    """Legacy assembly — compatibility bypass when store pointer/blob unavailable."""
    try:
        from music_workflow_state_store import record_compat_fallback

        record_compat_fallback(session, "envelope_legacy_assembly", "compatibility_bypass")
    except ImportError:
        pass
    env = ActiveMusicalWorkflowEnvelope()
    try:
        from musical_context_authority import resolve_authoritative_practice_key

        pk = resolve_authoritative_practice_key(session)
        env.original_song_tonic = pk.original_tonic
        env.original_song_mode = pk.original_mode
        env.current_practice_concert_tonic = pk.practice_tonic
        env.current_practice_concert_mode = pk.practice_mode
        env.current_practice_concert_key = pk.practice_key_token
    except ImportError:
        env.current_practice_concert_key = str(
            session.get("display_key") or session.get("concert_key") or "C"
        ).strip()

    env.workflow_owner = str(session.get("_active_workflow_owner") or "").strip()
    if ptr and getattr(ptr, "workflow_owner", None):
        env.workflow_owner = str(ptr.workflow_owner)
    env.instrument = str(session.get("instrument") or "Piano").strip()
    env.song_id = str(session.get("active_catalog_pick_key") or session.get("song") or "").strip()
    env.song_title = str(session.get("song") or "").strip()

    try:
        from backing_workflow_context import get_backing_workflow_envelope

        bw = get_backing_workflow_envelope(session) or {}
        env.backing_workflow_type = str(bw.get("workflow_type") or "").strip()
        env.source_type = str(bw.get("source_type") or "").strip()
        if not env.style_groove:
            env.style_groove = str(bw.get("groove") or bw.get("style") or "").strip()
    except ImportError:
        pass

    tab = str(
        session.get("improv_intelligence_tab")
        or session.get("creative_improv_intelligence_tab")
        or ""
    ).strip()
    if not env.workflow_owner:
        if tab == "Missions" or env.backing_workflow_type == "mission_jam":
            try:
                from music_workflow_state_store import record_compat_fallback

                record_compat_fallback(session, "envelope_tab_inference", "compatibility_bypass")
            except ImportError:
                pass
            env.workflow_owner = env.workflow_owner or "mission_jam"

    symbol, section, idx, _label = _selected_mission_fields(session)
    env.selected_chord_symbol = symbol
    env.section = section
    env.chord_index = idx
    try:
        from mission_practice_context import authoritative_mission_type

        env.mission_type = authoritative_mission_type(session)
        env.mission_id = env.mission_type
    except ImportError:
        env.mission_type = str(session.get("improv_active_mission") or "").strip()

    try:
        from improvisation_missions import MISSION_EXAMPLE_KEY, mission_example_artifact_id

        raw = session.get(MISSION_EXAMPLE_KEY)
        if isinstance(raw, dict):
            env.example_chord = str(raw.get("chord") or "").strip()
            env.example_fingerprint = str(raw.get("material_fp") or raw.get("output_fp") or "")[:24]
        env.artifact_id = mission_example_artifact_id(
            session,
            mission=env.mission_type,
            chord=symbol or env.example_chord,
            section=section,
            chord_index=idx,
        )
    except ImportError:
        pass

    try:
        from mission_practice_context import (
            MISSION_RECORDING_SEAL_KEY,
            load_mission_practice_context,
        )

        mpc = load_mission_practice_context(session)
        if mpc is not None:
            env.backing_handoff_chord = str(mpc.chord.symbol or "").strip()
            env.artifact_fingerprint = str(mpc.context_fingerprint or "")[:24]
        seal = session.get(MISSION_RECORDING_SEAL_KEY)
        if isinstance(seal, dict):
            env.recording_seal_chord = str(seal.get("chord_symbol") or seal.get("chord") or "").strip()
    except ImportError:
        pass

    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            env.backing_display_concert_key = str(
                ctx.concert_key or ctx.display_key or ctx.key or ""
            ).strip()
            if str(ctx.source or "") == "mission" and ctx.progression:
                handoff = str(ctx.progression[0] or "").strip()
                if handoff:
                    env.backing_handoff_chord = env.backing_handoff_chord or handoff
    except ImportError:
        pass

    env.style_owner = str((session.get("_mission_jam_style_resolution") or {}).get("source") or "session")
    env.progression_owner = "catalog_song_sections" if session.get("improv_song_concert_sections") else ""
    env.context_revision = env.fingerprint()
    session[ACTIVE_WORKFLOW_ENVELOPE_KEY] = asdict(env)
    return env


def validate_mission_workflow_envelope(session: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed checks before Missions / mission backing render."""
    envelope = build_active_workflow_envelope(session)
    violations: list[str] = []
    actions: list[str] = []
    sel = envelope.selected_chord_symbol

    if sel and envelope.example_chord and sel != envelope.example_chord:
        violations.append(VIOLATION_MISSION_EXAMPLE_OWNER_MISMATCH)
    if sel and envelope.backing_handoff_chord and sel != envelope.backing_handoff_chord:
        violations.append(VIOLATION_MISSION_BACKING_HANDOFF_MISMATCH)
    if sel and envelope.recording_seal_chord and sel != envelope.recording_seal_chord:
        violations.append(VIOLATION_MISSION_RECORDING_SEAL_MISMATCH)

    live_key = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if live_key and envelope.current_practice_concert_key:
        try:
            from music_theory import key_is_minor, normalize_root, split_chord

            def _mode(k: str) -> str:
                return "minor" if key_is_minor(k) else "major"

            live_root = normalize_root(split_chord(live_key)[0])
            pk_root = normalize_root(envelope.current_practice_concert_tonic or split_chord(envelope.current_practice_concert_key)[0])
            if _mode(live_key) != envelope.current_practice_concert_mode:
                violations.append(VIOLATION_SONG_PRACTICE_KEY_MISMATCH)
            elif live_root and pk_root and live_root != pk_root:
                if _mode(live_key) == envelope.current_practice_concert_mode:
                    violations.append(VIOLATION_SONG_PRACTICE_KEY_MISMATCH)
        except ImportError:
            pass

    if envelope.backing_display_concert_key and envelope.current_practice_concert_key:
        try:
            from music_theory import key_is_minor, normalize_root, split_chord

            bk = envelope.backing_display_concert_key
            pk = envelope.current_practice_concert_key
            bk_root = normalize_root(split_chord(bk)[0])
            pk_root = normalize_root(split_chord(pk)[0])
            sel_root = normalize_root(split_chord(sel)[0]) if sel else ""
            if key_is_minor(pk) and not key_is_minor(bk):
                if bk_root != pk_root:
                    violations.append(VIOLATION_WORKFLOW_KEY_OWNER_MISMATCH)
            # Backing concert key collapsed to the selected chord instead of the
            # song Practice Key. Matching tonic + selected chord after a successful
            # Mission restore is consistent, not a pending handoff.
            if sel_root and bk_root == sel_root and pk_root and pk_root != sel_root:
                violations.append(VIOLATION_WORKFLOW_KEY_OWNER_MISMATCH)
        except ImportError:
            pass

    try:
        from generated_jam_key_context import generated_jam_owns_practice_key
        from musical_context_authority import song_catalog_context_owns_practice_key

        if song_catalog_context_owns_practice_key(session) and generated_jam_owns_practice_key(session):
            violations.append(VIOLATION_STALE_GENERATED_JAM_KEY_LEAK)
    except ImportError:
        pass

    try:
        from creative_key_sync import is_creative_major_jam_active
        from musical_context_authority import song_catalog_context_owns_practice_key

        if song_catalog_context_owns_practice_key(session) and is_creative_major_jam_active(session):
            violations.append(VIOLATION_STALE_GENERATED_JAM_KEY_LEAK)
            violations.append(VIOLATION_WORKFLOW_KEY_OWNER_MISMATCH)
    except ImportError:
        pass

    diag = {
        "envelope": asdict(envelope),
        "violations": violations,
        "reconciliation_actions": actions,
        "consistent": not violations,
    }
    session[WORKFLOW_ENVELOPE_DIAG_KEY] = diag
    return diag


def inspect_mission_workflow_envelope(session: dict[str, Any]) -> dict[str, Any]:
    """Read-only validation for Mission renderers (no session mutations)."""
    diag = validate_mission_workflow_envelope(session)
    session[WORKFLOW_ENVELOPE_DIAG_KEY] = diag
    return diag


def apply_mission_workflow_envelope_reconciliation(session: dict[str, Any]) -> dict[str, Any]:
    """Mutating reconciliation — call only before widget-bound keys are instantiated."""
    try:
        from session_widget_safe import widgets_likely_instantiated

        if widgets_likely_instantiated(session):
            return {"applied": False, "reason": "widgets_locked"}
    except ImportError:
        if session.get("_streamlit_widgets_locked_this_run"):
            return {"applied": False, "reason": "widgets_locked"}

    diag = validate_mission_workflow_envelope(session)
    if diag.get("consistent"):
        session[WORKFLOW_ENVELOPE_DIAG_KEY] = diag
        return diag
    actions: list[str] = list(diag.get("reconciliation_actions") or [])
    envelope = build_active_workflow_envelope(session)
    sel = envelope.selected_chord_symbol

    if VIOLATION_MISSION_EXAMPLE_OWNER_MISMATCH in diag.get("violations", []):
        try:
            from improvisation_missions import MISSION_EXAMPLE_KEY

            session.pop(MISSION_EXAMPLE_KEY, None)
            session.pop("_mission_example_output_fp", None)
            actions.append("cleared_stale_mission_example")
            diag["violations"].append(VIOLATION_STALE_MISSION_ARTIFACT_RESTORED)
        except ImportError:
            pass

    if VIOLATION_SONG_PRACTICE_KEY_MISMATCH in diag.get("violations", []) or VIOLATION_STALE_GENERATED_JAM_KEY_LEAK in diag.get(
        "violations", []
    ):
        try:
            from generated_jam_key_context import deactivate_generated_jam_key_ownership

            if deactivate_generated_jam_key_ownership(session, pre_widget=True):
                actions.append("released_generated_jam_key")
        except ImportError:
            pass
        pk = envelope.current_practice_concert_key
        try:
            from music_workflow_state_store import get_active_workflow_pointer, record_compat_fallback

            if get_active_workflow_pointer(session):
                record_compat_fallback(session, "reconcile_skip_blob_key_overwrite", "compatibility_bypass")
            elif pk:
                session["display_key"] = pk
                session["concert_key"] = pk
                session["_pending_display_key"] = pk
                actions.append("restored_practice_concert_key")
        except ImportError:
            if pk:
                session["display_key"] = pk
                session["concert_key"] = pk
                session["_pending_display_key"] = pk
                actions.append("restored_practice_concert_key")

    if sel and (
        VIOLATION_MISSION_BACKING_HANDOFF_MISMATCH in diag.get("violations", [])
        or VIOLATION_MISSION_RECORDING_SEAL_MISMATCH in diag.get("violations", [])
    ):
        session.pop("improv_mission_recording_seal", None)
        try:
            from mission_exact_chord_backing import invalidate_exact_chord_backing_cache

            invalidate_exact_chord_backing_cache(session)
        except ImportError:
            pass
        try:
            from mission_practice_context import refresh_mission_practice_context

            refresh_mission_practice_context(session)
            actions.append("refreshed_mission_practice_context")
        except ImportError:
            pass

    try:
        from workflow_musical_authority import sync_song_improv_sections_to_practice_key

        sync_song_improv_sections_to_practice_key(session)
        actions.append("synced_song_sections_to_practice_key")
    except ImportError:
        pass

    diag["reconciliation_actions"] = actions
    diag["consistent"] = not validate_mission_workflow_envelope(session).get("violations")
    session[WORKFLOW_ENVELOPE_DIAG_KEY] = diag
    return diag


def reconcile_mission_workflow_envelope(session: dict[str, Any]) -> dict[str, Any]:
    """Apply reconciliation when pre-widget; queue deferred work when widgets are locked."""
    try:
        from session_widget_safe import widgets_likely_instantiated

        locked = widgets_likely_instantiated(session)
    except ImportError:
        locked = bool(session.get("_streamlit_widgets_locked_this_run"))
    if locked:
        diag = inspect_mission_workflow_envelope(session)
        if not diag.get("consistent"):
            try:
                from music_workflow_pending_mission_envelope import (
                    peek_pending_mission_envelope_reconciliation,
                    queue_pending_mission_envelope_reconciliation,
                )

                if not peek_pending_mission_envelope_reconciliation(session):
                    queue_pending_mission_envelope_reconciliation(
                        session,
                        reason="reconcile_while_widgets_locked",
                        violations=list(diag.get("violations") or []),
                    )
            except ImportError:
                pass
        return diag
    return apply_mission_workflow_envelope_reconciliation(session)


def apply_atomic_mission_chord_selection(
    session: dict[str, Any],
    *,
    chord: str,
    section: str,
    chord_index: int,
    chord_label: str,
    button_key: str = "",
) -> None:
    """One atomic update for mission chord — authoritative store mutation (Commit 3 B1)."""
    try:
        from music_workflow_mutation import mutate_mission_chord_selection

        result = mutate_mission_chord_selection(
            session,
            chord=chord,
            section=section,
            chord_index=int(chord_index),
            chord_label=chord_label,
            button_key=button_key,
        )
        if not result.ok:
            try:
                import streamlit as st

                raw = str(result.error_message or "").strip()
                low = raw.lower()
                # Internal control tokens / deferred-activation markers — never product UI.
                if (
                    "requires_pre_widget_activation" in low
                    or "active owner mismatch" in low
                    or str(result.error_code or "")
                    in {
                        "OWNER_MISMATCH",
                        "REQUIRES_PRE_WIDGET_ACTIVATION",
                        "PROJECTION_DEFERRED",
                        "CHORD_OWNER_ACTIVATE_DEFERRED",
                    }
                ):
                    return
                if raw:
                    st.warning(raw)
                else:
                    st.warning("Mission chord could not be saved. Reload the page.")
            except ImportError:
                pass
        return
    except ImportError:
        pass
    session["ii_selected_chord"] = chord
    session["ii_selected_section"] = section
    session["ii_selected_chord_index"] = int(chord_index)
    session["ii_selected_chord_label"] = chord_label
    build_active_workflow_envelope(session)


def mission_example_allowed_for_projection(session: dict[str, Any], artifact: Any) -> bool:
    """Block canonical restore of an example that belongs to another chord."""
    if not isinstance(artifact, dict):
        return True
    sel, _, _, _ = _selected_mission_fields(session)
    ex_ch = str(artifact.get("chord") or "").strip()
    if sel and ex_ch and sel != ex_ch:
        return False
    return True


def render_workflow_envelope_dev_panel(st_module: Any, session: dict[str, Any]) -> None:
    try:
        from suite_workspace import is_developer_mode_enabled

        if not is_developer_mode_enabled(st=st_module):
            return
    except ImportError:
        if not session.get("dev_mode"):
            return
    diag = dict(session.get(WORKFLOW_ENVELOPE_DIAG_KEY) or {})
    if not diag:
        diag = validate_mission_workflow_envelope(session)
    env = diag.get("envelope") or session.get(ACTIVE_WORKFLOW_ENVELOPE_KEY) or {}
    deploy = str(session.get("_studio_ui_release_sha") or "—")[:7]
    st_module.caption(
        "DEV workflow envelope · "
        f"owner `{env.get('workflow_owner', '—')}` · "
        f"song `{env.get('song_title', '—')}` · "
        f"practice `{env.get('current_practice_concert_key', '—')}` · "
        f"UI chord `{env.get('selected_chord_symbol', '—')}` · "
        f"example `{env.get('example_chord', '—')}` · "
        f"backing `{env.get('backing_handoff_chord', '—')}` · "
        f"backing concert `{env.get('backing_display_concert_key', '—')}` · "
        f"artifact `{str(env.get('artifact_id', ''))[:28]}` · "
        f"violations `{diag.get('violations', [])}` · "
        f"reconciled `{diag.get('reconciliation_actions', [])}` · "
        f"ok `{diag.get('consistent')}` · sha `{deploy}`"
    )


# Direct reads that bypass this envelope (Missions / Backing) — migrate renderers to envelope:
SOURCE_SCAN_BYPASS_PATHS = (
    "session.display_key / concert_key without resolve_authoritative_practice_key",
    "session.ii_selected_chord without mission_practice_context",
    "load_mission_example without _example_matches_active_context",
    "project_mission_artifacts_from_canonical without mission_example_allowed_for_projection",
    "backing_context.build_mission_context._display_keys_from_session alone",
    "is_creative_major_jam_active on mission/song_improv backing",
    "render_backing_edit_source_action parallel to build_backing_nav_actions",
    "render_mission_practice_lick_on_backing Return to Mission duplicate",
)


__all__ = [
    "ACTIVE_WORKFLOW_ENVELOPE_KEY",
    "WORKFLOW_ENVELOPE_DIAG_KEY",
    "ActiveMusicalWorkflowEnvelope",
    "SOURCE_SCAN_BYPASS_PATHS",
    "apply_atomic_mission_chord_selection",
    "build_active_workflow_envelope",
    "project_envelope_from_active_store",
    "mission_example_allowed_for_projection",
    "apply_mission_workflow_envelope_reconciliation",
    "inspect_mission_workflow_envelope",
    "reconcile_mission_workflow_envelope",
    "render_workflow_envelope_dev_panel",
    "validate_mission_workflow_envelope",
]
