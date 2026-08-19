"""Practice Analysis panel for the Practice Log page (lightweight import surface)."""

from __future__ import annotations

import re
from typing import Any

# Session keys — kept inline so this module does not depend on practice_history_synthesis at import time.
LATEST_PRACTICE_ANALYSIS_SUMMARY_KEY = "latest_practice_analysis_summary"
LATEST_PRACTICE_ANALYSIS_CREATED_AT_KEY = "latest_practice_analysis_created_at"
LATEST_PRACTICE_ANALYSIS_EVIDENCE_COUNTS_KEY = "latest_practice_analysis_evidence_counts"
LATEST_PRACTICE_ANALYSIS_HANDOFF_STATUS_KEY = "latest_practice_analysis_handoff_status"

PRACTICE_ANALYSIS_OPEN_KEY = "_plog_practice_analysis_open"
PRACTICE_ANALYSIS_EXPANDER_KEY = "plog_practice_analysis_expander"

__all__ = [
    "inject_practice_analysis_panel_styles",
    "render_practice_analysis_panel",
    "PRACTICE_ANALYSIS_OPEN_KEY",
    "PRACTICE_ANALYSIS_EXPANDER_KEY",
]

_INSTRUMENT_LABELS = frozenset(
    {
        "tenor saxophone",
        "alto saxophone",
        "soprano saxophone",
        "baritone saxophone",
        "flute",
        "guitar",
        "piano",
        "clarinet",
        "trumpet",
        "trombone",
        "saxophone",
        "your instrument",
    }
)

_INVALID_SONG_LABELS = frozenset({"top song", "top song:", "untitled", "—", "-"})

_PRACTICE_ANALYSIS_SECTIONS: tuple[tuple[str, str], ...] = (
    ("Practice Summary", "practice_summary"),
    ("Improvement Notes", "improvement_notes"),
    ("Upload / Recording Review", "upload_recording_review"),
    ("Tone & Tuner Notes", "tone_tuner_notes"),
    ("Recommended Next Session", "recommended_next_session"),
    ("Recommended Focus This Week", "recommended_focus_this_week"),
    ("Evidence Used", "evidence_used"),
)


def inject_practice_analysis_panel_styles(st: Any) -> None:
    """Blue-accent styles for Practice Analysis vs Session History."""
    st.markdown(
        """
<style>
.st-key-log_practice_analysis_panel{
  border:1px solid rgba(37,99,235,.35)!important;border-radius:16px!important;
  background:linear-gradient(180deg,rgba(239,246,255,.98),rgba(255,255,255,.96))!important;
  box-shadow:0 14px 32px rgba(37,99,235,.12)!important;padding:.15rem .35rem .55rem!important;
  margin:.65rem 0!important;
}
.st-key-log_practice_analysis_panel [data-testid="stExpander"]{
  border:none!important;background:transparent!important;box-shadow:none!important;
}
.st-key-log_practice_analysis_panel [data-testid="stExpander"] summary{
  font-size:1.02rem!important;font-weight:850!important;color:#1e3a8a!important;
}
.ui-plog-analysis-banner{
  border-left:4px solid #2563eb;border-radius:10px;padding:.55rem .75rem;margin:.35rem .2rem .15rem;
  background:rgba(37,99,235,.08);
}
.ui-plog-analysis-banner-title{font-size:.92rem;font-weight:850;color:#1e3a8a;margin:0;line-height:1.35;}
.ui-plog-analysis-banner-sub{font-size:.78rem;color:#475569;margin:.15rem 0 0;}
.st-key-log_timed_planner_panel{
  border:1px solid rgba(219,39,119,.28)!important;border-radius:16px!important;
  background:linear-gradient(180deg,rgba(253,242,248,.98),rgba(255,255,255,.96))!important;
  box-shadow:0 14px 32px rgba(219,39,119,.10)!important;padding:.55rem .75rem .65rem!important;
  margin:.65rem 0!important;
}
.st-key-log_timed_planner_panel [data-testid="stExpander"] summary{
  font-size:1rem!important;font-weight:850!important;color:#9d174d!important;
}
.ui-plog-planner-banner{
  border-left:4px solid #db2777;border-radius:10px;padding:.45rem .7rem;margin:0 0 .35rem;
  background:rgba(219,39,119,.08);
}
.ui-plog-planner-banner-title{font-size:.88rem;font-weight:850;color:#9d174d;margin:0;}
.ui-plog-planner-banner-sub{font-size:.76rem;color:#475569;margin:.12rem 0 0;}
</style>
        """,
        unsafe_allow_html=True,
    )


def _hydrate_panel_state(session_state: dict[str, Any], st: Any | None = None) -> None:
    try:
        from practice_history_synthesis import hydrate_latest_practice_analysis_from_storage

        hydrate_latest_practice_analysis_from_storage(session_state, st=st)
    except Exception:
        try:
            from practice_history_synthesis import hydrate_latest_practice_analysis

            hydrate_latest_practice_analysis(session_state)
        except Exception:
            pass


def _analysis_metadata(session_state: dict[str, Any]) -> dict[str, Any]:
    meta = session_state.get(LATEST_PRACTICE_ANALYSIS_EVIDENCE_COUNTS_KEY)
    return meta if isinstance(meta, dict) else {}


def _normalize_song_label(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in _INVALID_SONG_LABELS:
        return ""
    if lowered.startswith("top song"):
        return ""
    return text


def _top_song_from_summary(summary: dict[str, Any], session_state: dict[str, Any]) -> str:
    meta = _analysis_metadata(session_state)
    song = _normalize_song_label(str(meta.get("top_song") or ""))
    if song:
        return song
    for key in ("upload_recording_review", "recommended_next_session", "practice_summary"):
        text = str(summary.get(key) or "")
        for match in re.finditer(r"\*\*([^*]+)\*\*", text):
            candidate = _normalize_song_label(match.group(1).strip())
            if not candidate:
                continue
            if candidate.lower() in _INSTRUMENT_LABELS:
                continue
            if candidate.lower().startswith("upload analysis"):
                continue
            return candidate
    return ""


def _top_instrument_from_summary(summary: dict[str, Any], session_state: dict[str, Any]) -> str:
    meta = _analysis_metadata(session_state)
    instrument = str(meta.get("top_instrument") or "").strip()
    if instrument:
        return instrument
    practice = str(summary.get("practice_summary") or "")
    match = re.search(r"worked mostly on \*\*([^*]+)\*\*", practice, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _compact_header(session_state: dict[str, Any], summary: dict[str, Any]) -> str:
    parts = ["Practice Analysis"]
    top_song = _top_song_from_summary(summary, session_state)
    if top_song:
        parts.append(top_song)
    top_instrument = _top_instrument_from_summary(summary, session_state)
    if top_instrument and top_instrument.lower() != top_song.lower():
        parts.append(top_instrument)
    created_at = str(session_state.get(LATEST_PRACTICE_ANALYSIS_CREATED_AT_KEY) or "").strip()
    if created_at:
        try:
            from suite_analytical_question import format_practice_analysis_updated_label

            updated = format_practice_analysis_updated_label(created_at)
        except Exception:
            updated = created_at[:19].replace("T", " ")
        if updated:
            parts.append(f"Last updated {updated}")
    return " · ".join(parts)


def render_practice_analysis_panel(st: Any, session_state: dict[str, Any]) -> None:
    """Compact Practice Analysis tab — always visible on the Practice Log page."""
    inject_practice_analysis_panel_styles(st)
    _hydrate_panel_state(session_state, st=st)

    summary = session_state.get(LATEST_PRACTICE_ANALYSIS_SUMMARY_KEY)
    handoff = session_state.get(LATEST_PRACTICE_ANALYSIS_HANDOFF_STATUS_KEY)
    handoff = handoff if isinstance(handoff, dict) else {}
    has_summary = isinstance(summary, dict) and any(str(v or "").strip() for v in summary.values())

    header = _compact_header(session_state, summary) if has_summary else "Practice Analysis"
    expanded = bool(session_state.get(PRACTICE_ANALYSIS_OPEN_KEY))

    st.markdown(
        '<div class="ui-plog-analysis-banner">'
        '<p class="ui-plog-analysis-banner-title">Practice Analysis</p>'
        '<p class="ui-plog-analysis-banner-sub">Coaching insight from your saved practice evidence</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    with st.expander(header, expanded=expanded, key=PRACTICE_ANALYSIS_EXPANDER_KEY):
        if not has_summary:
            st.markdown(
                "**No analysis yet.** Click **Analyze My Practice** above to generate a concise summary "
                "from your practice logs, saved upload analyses, tone takes, and export metadata."
            )
            st.caption(
                "The Log page shows practical next steps here. Command Center receives the full detailed report."
            )
            return

        if handoff.get("success"):
            if handoff.get("duplicate"):
                st.info("Full report available in Command Center (recent send — use **Continue** there).")
            else:
                st.caption("Full detailed report sent to Command Center → **Music Practice Log Analysis**.")
        elif handoff and handoff.get("success") is False:
            err = str(handoff.get("error") or "handoff did not complete").strip()
            st.warning(f"Command Center handoff did not complete. {err}")

        for heading, key in _PRACTICE_ANALYSIS_SECTIONS:
            text = str(summary.get(key) or "").strip()
            if not text:
                continue
            with st.container(border=True):
                st.markdown(f"**{heading}**")
                st.markdown(text)
