"""App-wide pre-widget workflow consumers — before any Streamlit widgets."""

from __future__ import annotations

import logging
import traceback
from typing import Any

_LOG = logging.getLogger("music.pre_widget_bootstrap")

PRE_WIDGET_BOOTSTRAP_ACTIVE_KEY = "_music_pre_widget_bootstrap_active"
PRE_WIDGET_BOOTSTRAP_LAST_KEY = "_music_pre_widget_bootstrap_last"
PRE_WIDGET_BOOTSTRAP_RAN_KEY = "_music_pre_widget_bootstrap_ran_this_run"


def _require(module: str, attr: str) -> Any:
    try:
        mod = __import__(module, fromlist=[attr])
        fn = getattr(mod, attr, None)
        if fn is None:
            raise ImportError(f"{module}.{attr} missing")
        return fn
    except ImportError as exc:
        msg = f"PRE_WIDGET_BOOTSTRAP_MISSING: {module}.{attr}: {exc}"
        _LOG.error(msg)
        raise RuntimeError(msg) from exc


def run_pre_widget_application_consumers(session: dict[str, Any], *, st: Any | None = None) -> dict[str, str]:
    """Run pending workflow consumers at top of script — before auth/sidebar widgets."""
    if session.get(PRE_WIDGET_BOOTSTRAP_RAN_KEY):
        prior = session.get(PRE_WIDGET_BOOTSTRAP_LAST_KEY)
        out = dict(prior) if isinstance(prior, dict) else {}
        out["duplicate_call"] = "skipped"
        return out
    session[PRE_WIDGET_BOOTSTRAP_ACTIVE_KEY] = True
    phases: dict[str, str] = {
        "started_run_seq": str(session.get("_script_run_seq") or ""),
        "first_widget_before_start": session.get("_music_first_streamlit_widget"),
    }
    try:
        from music_run_lifecycle import enter_run_phase, exit_run_phase

        enter_run_phase(session, "pre_widget_bootstrap_consumers")
    except ImportError:
        pass
    try:
        consume_return = _require("music_workflow_pending_mission_return", "consume_pending_mission_return_handoff")
        phases["mission_return"] = str(consume_return(session, st=st))
    except RuntimeError as exc:
        phases["mission_return"] = f"FAIL:{exc}"
    try:
        consume_env = _require(
            "music_workflow_pending_mission_envelope",
            "consume_pending_mission_envelope_reconciliation",
        )
        phases["mission_envelope"] = str(consume_env(session, st=st))
    except RuntimeError as exc:
        phases["mission_envelope"] = f"FAIL:{exc}"
    try:
        consume_key = _require(
            "music_workflow_pending_generated_key_edit",
            "consume_pending_generated_key_edit",
        )
        phases["generated_key_edit"] = str(consume_key(session, st=st))
    except RuntimeError as exc:
        phases["generated_key_edit"] = f"FAIL:{exc}"
    try:
        consume_song_key = _require(
            "music_workflow_pending_song_practice_key_edit",
            "consume_pending_song_practice_key_edit",
        )
        phases["song_practice_key_edit"] = str(consume_song_key(session, st=st))
    except RuntimeError as exc:
        phases["song_practice_key_edit"] = f"FAIL:{exc}"
    try:
        consume_gen = _require(
            "music_workflow_pending_generated_progression",
            "consume_pending_generated_progression",
        )
        phases["generated_progression"] = str(consume_gen(session, st=st))
    except RuntimeError as exc:
        phases["generated_progression"] = f"FAIL:{exc}"
    try:
        consume_wf = _require("music_workflow_pending_activation", "consume_pending_workflow_activation")
        phases["workflow_activation"] = str(consume_wf(session))
    except RuntimeError as exc:
        phases["workflow_activation"] = f"FAIL:{exc}"
    try:
        from music_workflow_mission_backing_orchestration import try_finalize_backing_after_mission_envelope

        if try_finalize_backing_after_mission_envelope(session):
            phases["backing_armed_after_envelope"] = "yes"
    except ImportError as exc:
        phases["backing_armed_after_envelope"] = f"SKIP:{exc}"
    try:
        consume_backing = _require(
            "music_workflow_pending_backing_handoff",
            "consume_pending_backing_workflow_handoff",
        )
        phases["backing_handoff"] = str(consume_backing(session, st=st))
    except RuntimeError as exc:
        phases["backing_handoff"] = f"FAIL:{exc}"
    try:
        from music_workflow_pending_generated_key_edit import peek_pending_generated_key_edit

        if peek_pending_generated_key_edit(session):
            phases["generated_key_edit"] = "pending_after_bootstrap"
    except ImportError:
        pass
    phases["finished_run_seq"] = str(session.get("_script_run_seq") or "")
    phases["first_widget_after_consumers"] = session.get("_music_first_streamlit_widget")
    session[PRE_WIDGET_BOOTSTRAP_LAST_KEY] = dict(phases)
    session[PRE_WIDGET_BOOTSTRAP_RAN_KEY] = True
    session.pop(PRE_WIDGET_BOOTSTRAP_ACTIVE_KEY, None)
    try:
        from music_run_lifecycle import exit_run_phase

        exit_run_phase(session, "pre_widget_bootstrap_consumers")
    except ImportError:
        pass
    _LOG.info("[pre_widget_bootstrap] %s", phases)
    return phases


__all__ = [
    "PRE_WIDGET_BOOTSTRAP_ACTIVE_KEY",
    "PRE_WIDGET_BOOTSTRAP_LAST_KEY",
    "PRE_WIDGET_BOOTSTRAP_RAN_KEY",
    "run_pre_widget_application_consumers",
]
