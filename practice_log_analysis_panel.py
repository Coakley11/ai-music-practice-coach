"""Practice Analysis panel for the Practice Log page (lightweight import surface)."""

from __future__ import annotations

from typing import Any

# Session keys — kept inline so this module does not depend on practice_history_synthesis at import time.
LATEST_PRACTICE_ANALYSIS_SUMMARY_KEY = "latest_practice_analysis_summary"
LATEST_PRACTICE_ANALYSIS_CREATED_AT_KEY = "latest_practice_analysis_created_at"
LATEST_PRACTICE_ANALYSIS_HANDOFF_STATUS_KEY = "latest_practice_analysis_handoff_status"

__all__ = ["render_practice_analysis_panel"]


def render_practice_analysis_panel(st: Any, session_state: dict[str, Any]) -> None:
    """Visible Practice Analysis panel — concise local summary after Analyze My Practice."""
    summary = session_state.get(LATEST_PRACTICE_ANALYSIS_SUMMARY_KEY)
    created_at = str(session_state.get(LATEST_PRACTICE_ANALYSIS_CREATED_AT_KEY) or "").strip()
    handoff = session_state.get(LATEST_PRACTICE_ANALYSIS_HANDOFF_STATUS_KEY)
    handoff = handoff if isinstance(handoff, dict) else {}

    st.markdown('<p class="ui-log-section-title">Practice Analysis</p>', unsafe_allow_html=True)
    with st.container(key="log_practice_analysis_panel", border=True):
        if not isinstance(summary, dict) or not summary:
            st.markdown(
                "**No analysis yet.** Click **Analyze My Practice** above to generate a concise summary "
                "from your practice logs, saved upload analyses, tone takes, and export metadata."
            )
            st.caption(
                "The Log page shows practical next steps here. Command Center receives the full detailed report."
            )
            return

        if created_at:
            st.caption(f"Last updated: {created_at}")
        if handoff.get("sent_at"):
            if handoff.get("duplicate"):
                st.info("Full report available in Command Center (recent send — use **Continue** there).")
            else:
                st.caption("Full detailed report sent to Command Center → **Music Practice Log Analysis**.")

        sections: tuple[tuple[str, str], ...] = (
            ("Practice Summary", "practice_summary"),
            ("Improvement Notes", "improvement_notes"),
            ("Upload / Recording Review", "upload_recording_review"),
            ("Tone & Tuner Notes", "tone_tuner_notes"),
            ("Recommended Next Session", "recommended_next_session"),
            ("Recommended Focus This Week", "recommended_focus_this_week"),
            ("Evidence Used", "evidence_used"),
        )
        for heading, key in sections:
            text = str(summary.get(key) or "").strip()
            if not text:
                continue
            st.markdown(f"**{heading}**")
            st.markdown(text)
