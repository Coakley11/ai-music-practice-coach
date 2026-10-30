"""One Music entry transaction per URL; Streamlit reruns are not new launches."""
from __future__ import annotations

import hashlib
import json
from typing import Any

TOKEN = "_music_launch_token"
CONSUMED = "_music_launch_consumed_token"
ERROR = "_suite_resume_error_music"


def launch_token(st: Any) -> str:
    def qp(name):
        value = st.query_params.get(name, "")
        return str(value[0] if isinstance(value, list) and value else value or "").strip()
    mode = qp("suite_entry_mode")
    fields = {"workspace": qp("suite_workspace"), "mode": mode}
    if mode == "workstream":
        fields["page"] = qp("suite_page")
    elif qp("suite_resume_payload"):
        fields["payload"] = qp("suite_resume_payload")
    else:
        for name in ("suite_resume", "suite_page", "suite_pick_key", "suite_song",
                     "suite_display_key", "suite_instrument", "suite_resume_kind",
                     "suite_section_focus", "suite_bpm", "suite_ami_insight"):
            fields[name] = qp(name)
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def begin_music_launch(st: Any) -> bool:
    ss = st.session_state
    token = launch_token(st)
    if ss.get(CONSUMED) == token:
        return False
    if ss.get(TOKEN) == token and ss.get("_suite_resume_launch_music"):
        return False
    ss[TOKEN] = token
    for key in ("_suite_resume_finalized_music", "_suite_activity_resume_pending", ERROR,
                "_suite_resume_failure_reason_music"):
        ss.pop(key, None)
    return True


def finish_music_launch(session: Any, *, error: str = "") -> None:
    session["_suite_resume_finalized_music"] = True
    session.pop("_suite_resume_launch_music", None)
    session.pop("_suite_activity_resume_pending", None)
    if session.get(TOKEN):
        session[CONSUMED] = session[TOKEN]
    if error:
        session[ERROR] = error


def render_music_resume_failure(st: Any) -> None:
    if not st.session_state.get(ERROR):
        return
    st.title("Unable to restore this saved context")
    st.error("The saved song or document could not be restored. Your saved libraries are preserved.")
    if st.button("Choose a source", key="music_resume_choose_source"):
        for name in tuple(st.query_params):
            if name.startswith("suite_") and name != "suite_workspace":
                del st.query_params[name]
        st.query_params["suite_entry_mode"] = "workstream"
        st.query_params["suite_page"] = "picker"
        st.session_state.pop(ERROR, None)
        st.session_state["studio_page"] = "picker"
        st.rerun()
    st.stop()
