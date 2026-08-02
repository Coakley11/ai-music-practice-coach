"""Developer diagnostics for Music workspace save transactions (?dev=1)."""

from __future__ import annotations

import json
from typing import Any

from music_workspace_cloud_save import MUSIC_SAVE_TX_KEY

HISTORY_KEY = "_music_workspace_save_tx_rerun_history"
_TX_GLOBAL_SEQ_KEY = "_music_workspace_save_tx_global_seq"
_CURRENT_RUN_ID_KEY = "_music_workspace_save_tx_current_run_id"
_STREAMLIT_RUN_SEQ_KEY = "_music_workspace_save_tx_streamlit_run_seq"

_SUITE_CLOUD_RESULT_KEY = "_suite_last_cloud_save_result"
_MUSIC_CLOUD_DIAG_KEY = "_music_last_cloud_save_diag"
_FORCE_BLOCKED_KEY = "_music_force_save_blocked_reason"
_PASSIVE_SKIP_KEY = "_music_passive_autosave_cloud_skip_reason"
_PERSIST_LAST_CLOUD_KEY = "_suite_persist_last_save_cloud"

SNAPSHOT_SUMMARY_FIELDS: tuple[str, ...] = (
    "transaction_sequence",
    "streamlit_run_sequence",
    "event",
    "raw_save_reason",
    "normalized_save_reason",
    "strict_egress_plan_action",
    "strict_egress_approved",
    "duplicate_write_skipped",
    "payload_changed_since_last_confirmed_save",
    "pending_payload_fingerprint",
    "last_confirmed_cloud_fingerprint",
    "envelope_revision_before",
    "envelope_revision_after",
    "revision_advanced",
    "cloud_write_attempted",
    "cloud_write_succeeded",
    "cloud_write_error",
    "save_cloud_full_session_return_value",
    "save_cloud_full_session_failure_stage",
    "save_cloud_full_session_exception",
    "cloud_upsert_attempted",
    "cloud_upsert_succeeded",
    "supabase_response_status",
    "cloud_readback_authoritative",
    "cloud_readback_attempted",
    "cloud_readback_revision",
    "cloud_readback_matches",
    "cloud_confirmed",
    "force_save_block_reason",
    "dirty_cleared_after_confirmed_save",
    "dirty_after_failed_cloud_save",
    "retry_required",
    "passive_autosave_cloud_skip",
    "suite_persist_last_save_cloud",
    "trace_last_save_cloud",
)


def _display(val: Any) -> str:
    if val is None:
        return "(not set)"
    if isinstance(val, bool):
        return str(val)
    text = str(val).strip()
    return text if text else "(empty)"


def _streamlit_script_run_id(st: Any) -> str:
    try:
        ctx = st.runtime.scriptrunner.get_script_run_ctx()
        run_id = getattr(ctx, "script_run_id", None)
        if run_id is not None:
            return str(run_id)
    except Exception:
        pass
    return "run_unknown"


def ensure_streamlit_run_sequence(session: dict[str, Any], st: Any) -> int:
    """Bump run sequence once per Streamlit script run (history filtered by run id)."""
    run_id = _streamlit_script_run_id(st)
    if session.get(_CURRENT_RUN_ID_KEY) != run_id:
        session[_CURRENT_RUN_ID_KEY] = run_id
        session[_STREAMLIT_RUN_SEQ_KEY] = int(session.get(_STREAMLIT_RUN_SEQ_KEY) or 0) + 1
    return int(session.get(_STREAMLIT_RUN_SEQ_KEY) or 0)


def _history_for_current_run(session: dict[str, Any]) -> list[dict[str, Any]]:
    current = str(session.get(_CURRENT_RUN_ID_KEY) or "")
    history = session.get(HISTORY_KEY)
    if not isinstance(history, list):
        return []
    out: list[dict[str, Any]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        if current and str(item.get("script_run_id") or "") not in ("", current):
            continue
        out.append(item)
    return out


def _next_transaction_sequence(session: dict[str, Any]) -> int:
    n = int(session.get(_TX_GLOBAL_SEQ_KEY) or 0) + 1
    session[_TX_GLOBAL_SEQ_KEY] = n
    return n


def _merge_cloud_diag(session: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in (_SUITE_CLOUD_RESULT_KEY, _MUSIC_CLOUD_DIAG_KEY):
        raw = session.get(key)
        if isinstance(raw, dict):
            out.update(raw)
    return out


def _revision_advanced(tx: dict[str, Any]) -> bool | None:
    if "revision_advanced" in tx:
        return bool(tx.get("revision_advanced"))
    before = tx.get("envelope_revision_before")
    after = tx.get("envelope_revision_after")
    if before is None and after is None:
        return None
    try:
        b = int(before or 0)
        a = int(after or 0)
    except (TypeError, ValueError):
        return None
    return a > b or (b == 0 and a >= 1)


def _cloud_confirmed(tx: dict[str, Any], *, revision_advanced: bool | None) -> bool | None:
    if "cloud_confirmed" in tx:
        return bool(tx.get("cloud_confirmed"))
    if revision_advanced is None:
        return None
    duplicate = bool(tx.get("duplicate_write_skipped"))
    saved = bool(tx.get("cloud_write_succeeded"))
    readback = tx.get("cloud_readback_matches")
    if readback is None and duplicate:
        readback = True
    if readback is None:
        return None
    return bool((saved or duplicate) and readback and revision_advanced)


def build_save_transaction_debug_bundle(session: dict[str, Any]) -> dict[str, Any]:
    """Merge live session keys into one diagnostic bundle (read-only)."""
    tx_raw = session.get(MUSIC_SAVE_TX_KEY)
    tx = dict(tx_raw) if isinstance(tx_raw, dict) else {}
    cloud = _merge_cloud_diag(session)

    try:
        from music_egress_strict_save import last_confirmed_cloud_fingerprint

        confirmed_fp = last_confirmed_cloud_fingerprint(session)
    except ImportError:
        confirmed_fp = str(session.get("_music_last_confirmed_cloud_fp") or "").strip()

    rev_adv = _revision_advanced(tx)
    cloud_ok = _cloud_confirmed(tx, revision_advanced=rev_adv)

    block = tx.get("force_save_block_reason")
    if not block:
        block = session.get(_FORCE_BLOCKED_KEY)

    summary: dict[str, Any] = {
        "raw_save_reason": tx.get("raw_save_reason") or tx.get("force_save_reason"),
        "normalized_save_reason": tx.get("normalized_save_reason"),
        "strict_egress_plan_action": tx.get("strict_egress_plan_action"),
        "strict_egress_approved": tx.get("strict_egress_approved"),
        "duplicate_write_skipped": tx.get("duplicate_write_skipped"),
        "payload_changed_since_last_confirmed_save": tx.get("payload_changed_since_last_confirmed_save"),
        "pending_payload_fingerprint": tx.get("pending_payload_fingerprint"),
        "last_confirmed_cloud_fingerprint": confirmed_fp or "(none)",
        "envelope_revision_before": tx.get("envelope_revision_before"),
        "envelope_revision_after": tx.get("envelope_revision_after"),
        "revision_advanced": rev_adv,
        "cloud_write_attempted": tx.get("cloud_write_attempted"),
        "cloud_write_succeeded": tx.get("cloud_write_succeeded"),
        "cloud_write_error": tx.get("cloud_write_error"),
        "save_cloud_full_session_return_value": cloud.get("save_cloud_full_session_return_value"),
        "save_cloud_full_session_failure_stage": cloud.get("save_cloud_full_session_failure_stage"),
        "save_cloud_full_session_exception": cloud.get("save_cloud_full_session_exception"),
        "cloud_upsert_attempted": cloud.get("cloud_upsert_attempted"),
        "cloud_upsert_succeeded": cloud.get("cloud_upsert_succeeded"),
        "supabase_response_status": cloud.get("supabase_response_status"),
        "cloud_readback_authoritative": tx.get("cloud_readback_authoritative"),
        "cloud_readback_attempted": tx.get("cloud_readback_attempted"),
        "cloud_readback_revision": tx.get("cloud_readback_revision"),
        "cloud_readback_matches": tx.get("cloud_readback_matches"),
        "cloud_confirmed": cloud_ok,
        "force_save_block_reason": block,
        "dirty_cleared_after_confirmed_save": tx.get("dirty_cleared_after_confirmed_save"),
        "dirty_after_failed_cloud_save": tx.get("dirty_after_failed_cloud_save"),
        "retry_required": tx.get("retry_required") if tx.get("retry_required") is not None else session.get("_music_retry_required"),
        "passive_autosave_cloud_skip": session.get(_PASSIVE_SKIP_KEY),
        "suite_persist_last_save_cloud": session.get(_PERSIST_LAST_CLOUD_KEY),
        "trace_last_save_cloud": session.get("last_save_cloud"),
    }

    return {
        "summary": summary,
        MUSIC_SAVE_TX_KEY: tx,
        _SUITE_CLOUD_RESULT_KEY: session.get(_SUITE_CLOUD_RESULT_KEY),
        _MUSIC_CLOUD_DIAG_KEY: session.get(_MUSIC_CLOUD_DIAG_KEY),
        _FORCE_BLOCKED_KEY: session.get(_FORCE_BLOCKED_KEY),
        _PASSIVE_SKIP_KEY: session.get(_PASSIVE_SKIP_KEY),
        _PERSIST_LAST_CLOUD_KEY: session.get(_PERSIST_LAST_CLOUD_KEY),
    }


def append_workspace_save_transaction_snapshot(
    session: dict[str, Any],
    *,
    st: Any | None = None,
    event: str = "save_complete",
) -> None:
    """Append a snapshot for this Streamlit rerun (dev history)."""
    run_id = str(session.get(_CURRENT_RUN_ID_KEY) or "")
    if st is not None:
        run_id = _streamlit_script_run_id(st)
        if session.get(_CURRENT_RUN_ID_KEY) != run_id:
            session[_CURRENT_RUN_ID_KEY] = run_id
            session[_STREAMLIT_RUN_SEQ_KEY] = int(session.get(_STREAMLIT_RUN_SEQ_KEY) or 0) + 1
    run_seq = int(session.get(_STREAMLIT_RUN_SEQ_KEY) or 0)
    tx_seq = _next_transaction_sequence(session)
    bundle = build_save_transaction_debug_bundle(session)
    summary = dict(bundle["summary"])
    summary["transaction_sequence"] = tx_seq
    summary["streamlit_run_sequence"] = run_seq
    summary["event"] = event

    history = session.get(HISTORY_KEY)
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "script_run_id": run_id,
            "transaction_sequence": tx_seq,
            "streamlit_run_sequence": run_seq,
            "event": event,
            "summary": summary,
            "bundle": bundle,
        }
    )
    session[HISTORY_KEY] = history[-48:]


def format_save_transaction_debug_text(session: dict[str, Any]) -> str:
    bundle = build_save_transaction_debug_bundle(session)
    summary = bundle["summary"]
    lines = ["=== Current save transaction (summary) ==="]
    for key in SNAPSHOT_SUMMARY_FIELDS:
        if key in ("transaction_sequence", "streamlit_run_sequence", "event"):
            continue
        lines.append(f"{key}: {_display(summary.get(key))}")

    history = _history_for_current_run(session)
    if history:
        lines.append("")
        lines.append(f"=== This rerun: {len(history)} transaction snapshot(s) ===")
        for item in history:
            if not isinstance(item, dict):
                continue
            snap = item.get("summary") if isinstance(item.get("summary"), dict) else item
            lines.append(
                f"  #{snap.get('transaction_sequence')} "
                f"run={snap.get('streamlit_run_sequence')} "
                f"event={snap.get('event')} "
                f"reason={_display(snap.get('raw_save_reason'))} "
                f"plan={_display(snap.get('strict_egress_plan_action'))} "
                f"cloud_confirmed={_display(snap.get('cloud_confirmed'))} "
                f"last_save_cloud={_display(snap.get('suite_persist_last_save_cloud'))}"
            )

    lines.append("")
    lines.append("=== Raw session blobs (JSON) ===")
    for label, key in (
        ("_music_workspace_save_transaction", MUSIC_SAVE_TX_KEY),
        ("_suite_last_cloud_save_result", _SUITE_CLOUD_RESULT_KEY),
        ("_music_last_cloud_save_diag", _MUSIC_CLOUD_DIAG_KEY),
    ):
        val = bundle.get(key) if key in bundle else session.get(key)
        try:
            lines.append(f"{label}: {json.dumps(val, sort_keys=True, default=str)}")
        except TypeError:
            lines.append(f"{label}: {_display(val)}")

    return "\n".join(lines)


def render_music_workspace_save_transaction_debug(st: Any) -> None:
    """Sidebar expander for ?dev=1 — does not mutate save or restore behavior."""
    ss = st.session_state
    ensure_streamlit_run_sequence(ss, st)
    bundle = build_save_transaction_debug_bundle(ss)
    summary = bundle["summary"]

    with st.expander("Music workspace save transaction", expanded=False):
        st.caption(
            "Live workspace save stack. History lists every completed save (or passive skip) "
            "in this Streamlit rerun — use it to spot success then duplicate/fail, "
            "multiple song_edit flushes, or passive autosave changing the final outcome."
        )
        st.text(f"streamlit_run_sequence: {_display(ss.get(_STREAMLIT_RUN_SEQ_KEY))}")
        st.text(f"transaction_sequence (last): {_display(ss.get(_TX_GLOBAL_SEQ_KEY))}")

        for key in SNAPSHOT_SUMMARY_FIELDS:
            if key in ("transaction_sequence", "streamlit_run_sequence", "event"):
                continue
            st.text(f"{key}: {_display(summary.get(key))}")

        try:
            from music_startup_save_suppression import collect_startup_save_suppression_diagnostics

            st.markdown("**Startup save suppression**")
            for label, val in collect_startup_save_suppression_diagnostics(ss).items():
                st.text(f"{label}: {_display(val)}")
        except ImportError:
            pass

        history = _history_for_current_run(ss)
        if history:
            st.markdown("**This rerun — transaction history**")
            for item in history:
                if not isinstance(item, dict):
                    continue
                snap = item.get("summary") if isinstance(item.get("summary"), dict) else item
                st.text(
                    f"#{snap.get('transaction_sequence')} "
                    f"[{snap.get('event')}] "
                    f"reason={_display(snap.get('raw_save_reason'))} "
                    f"plan={_display(snap.get('strict_egress_plan_action'))} "
                    f"dup_skip={_display(snap.get('duplicate_write_skipped'))} "
                    f"cloud_confirmed={_display(snap.get('cloud_confirmed'))} "
                    f"last_save_cloud={_display(snap.get('suite_persist_last_save_cloud'))} "
                    f"block={_display(snap.get('force_save_block_reason'))}"
                )

        st.text_area(
            "Copy full save transaction debug",
            value=format_save_transaction_debug_text(ss),
            height=420,
            label_visibility="collapsed",
        )


__all__ = [
    "append_workspace_save_transaction_snapshot",
    "build_save_transaction_debug_bundle",
    "ensure_streamlit_run_sequence",
    "format_save_transaction_debug_text",
    "render_music_workspace_save_transaction_debug",
]
