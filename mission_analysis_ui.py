"""Streamlit + HTML UI for improvisation mission / AI metric analysis."""

from __future__ import annotations

import html
import math
from typing import Any

from mission_analysis import (
    AI_IMPROV_METRIC_IDS,
    AI_IMPROV_METRIC_LABELS,
    MISSION_BY_ID,
    mission_progress_trends,
    resolve_selected_mission_ids,
    sync_analysis_missions_from_creative,
)


def _esc(s: Any) -> str:
    return html.escape(str(s))


def _metric_id_label_maps() -> tuple[dict[str, str], dict[str, str]]:
    label_to_id = {MISSION_BY_ID[mid].label: mid for mid in AI_IMPROV_METRIC_IDS if mid in MISSION_BY_ID}
    id_to_label = {mid: MISSION_BY_ID[mid].label for mid in AI_IMPROV_METRIC_IDS if mid in MISSION_BY_ID}
    return label_to_id, id_to_label


def render_ai_improv_metrics_selector(
    st: Any,
    session_state: dict,
    *,
    key_prefix: str = "improv",
    show_history: bool = True,
) -> list[str]:
    """AI Improvisation Metrics multiselect (Improvisation Intelligence). Returns metric ids."""
    st.markdown("##### AI Improvisation Metrics")
    st.caption("Choose what you want the AI to evaluate when you upload a recording.")

    creative_mission = str(session_state.get("improv_active_mission") or "")
    if creative_mission:
        st.caption(f"Practice mission in progress: **{creative_mission}**")

    label_to_id, id_to_label = _metric_id_label_maps()
    store_key = f"{key_prefix}_ai_metric_ids"
    session_state.setdefault(store_key, list(session_state.get("analysis_ai_metric_ids") or []))

    current_ids = list(session_state.get(store_key) or [])
    default_labels = [id_to_label[i] for i in current_ids if i in id_to_label]

    picked = st.multiselect(
        "Choose what you want AI to evaluate",
        AI_IMPROV_METRIC_LABELS,
        default=default_labels,
        key=f"{key_prefix}_ai_metric_multiselect",
        help="Select every skill you practiced — Upload Analysis scores each one.",
    )
    selected_ids = [label_to_id[l] for l in picked if l in label_to_id]
    session_state[store_key] = selected_ids
    session_state["analysis_ai_metric_ids"] = selected_ids
    session_state["analysis_mission_ids"] = selected_ids

    if show_history:
        render_mission_history_panel(st)

    return resolve_selected_mission_ids(session_state)


def render_mission_goals_selector(st: Any, session_state: dict) -> list[str]:
    """Upload Analysis — same metric catalog as Improvisation Intelligence."""
    st.markdown("##### AI Improvisation Metrics")
    st.caption("Choose the improvisation skills you practiced in this take.")

    session_state.setdefault("analysis_sync_creative_mission", True)
    st.checkbox(
        "Include active Creative Lab / Practice mission",
        key="analysis_sync_creative_mission",
        help="Adds criteria mapped from your current Practice Mission.",
    )

    label_to_id, id_to_label = _metric_id_label_maps()
    current_ids = list(
        session_state.get("analysis_ai_metric_ids")
        or session_state.get("analysis_mission_ids")
        or []
    )
    default_labels = [id_to_label[i] for i in current_ids if i in id_to_label]

    picked = st.multiselect(
        "Choose what you want AI to evaluate",
        AI_IMPROV_METRIC_LABELS,
        default=default_labels,
        key="analysis_ai_metric_multiselect",
    )
    selected_ids = [label_to_id[l] for l in picked if l in label_to_id]
    session_state["analysis_ai_metric_ids"] = selected_ids
    session_state["analysis_mission_ids"] = selected_ids

    session_state.setdefault("analysis_custom_goal_enabled", False)
    if st.checkbox("Add custom goal", key="analysis_custom_goal_enabled"):
        session_state.setdefault("analysis_custom_goal", "")
        st.text_input(
            "Custom criterion",
            key="analysis_custom_goal",
            placeholder="e.g. Trade fours with backing hits",
        )

    render_mission_history_panel(st)
    return resolve_selected_mission_ids(session_state)


def render_mission_history_panel(st: Any) -> None:
    from mission_analysis import load_mission_history

    hist = load_mission_history()
    if not hist:
        st.caption("Progress history appears after you analyze takes with metrics selected.")
        return

    with st.expander("Metric progress over time", expanded=False):
        mission_ids = sorted(
            {m["id"] for row in hist for m in (row.get("missions") or []) if m.get("id")}
        )
        if not mission_ids:
            return

        pick = st.selectbox(
            "Track metric",
            mission_ids,
            format_func=lambda mid: MISSION_BY_ID[mid].label if mid in MISSION_BY_ID else mid,
            key="analysis_mission_trend_pick",
        )
        points = mission_progress_trends(pick)
        if len(points) < 2:
            st.info("Analyze at least two takes with this metric selected to see a trend.")
            return
        st.line_chart(
            data={p["date"]: p["score"] for p in points},
            x_label="Session",
            y_label="Score %",
        )
        first, last = points[0]["score"], points[-1]["score"]
        delta = last - first
        arrow = "improved" if delta > 0 else "shifted"
        label = MISSION_BY_ID[pick].label if pick in MISSION_BY_ID else pick
        st.markdown(
            f"**{label}** {arrow} from **{first}%** → **{last}%** across {len(points)} uploads."
        )


def _mission_radar_svg(mission_results: list[dict[str, Any]]) -> str:
    if not mission_results:
        return ""
    items = mission_results[:8]
    n = len(items)
    cx, cy, r = 120, 120, 82
    pts = []
    for i, m in enumerate(items):
        ang = -1.5708 + (2 * math.pi * i / n)
        v = int(m.get("score", 50)) / 100.0
        x = cx + r * v * math.cos(ang)
        y = cy + r * v * math.sin(ang)
        pts.append(f"{x:.1f},{y:.1f}")
    grid_pts = []
    labels = ""
    for i, m in enumerate(items):
        ang = -1.5708 + (2 * math.pi * i / n)
        x = cx + r * math.cos(ang)
        y = cy + r * math.sin(ang)
        grid_pts.append(f"{x:.1f},{y:.1f}")
        short = str(m.get("label", ""))[:14]
        lx = cx + (r + 18) * math.cos(ang)
        ly = cy + (r + 18) * math.sin(ang)
        labels += f'<text x="{lx:.0f}" y="{ly:.0f}" text-anchor="middle" class="ma-radar-label">{_esc(short)}</text>'
    return f"""
<svg class="ma-radar" viewBox="0 0 240 240" xmlns="http://www.w3.org/2000/svg">
  <polygon points="{' '.join(grid_pts)}" class="ma-radar-grid"/>
  <polygon points="{' '.join(pts)}" class="ma-radar-fill"/>
  {labels}
</svg>"""


MISSION_ANALYSIS_CSS = """
<style>
.ma-block { font-family: system-ui, sans-serif; color: #0f172a; margin-top: 8px; }
.ma-hero {
  border-radius: 14px; padding: 16px 18px; margin-bottom: 14px;
  background: linear-gradient(135deg, #f5f3ff 0%, #ecfdf5 100%);
  border: 1px solid rgba(15,23,42,0.1);
}
.ma-hero h3 { margin: 0 0 8px 0; font-size: 1.12rem; }
.ma-overall { font-size: 1.35rem; font-weight: 900; color: #4f46e5; margin: 8px 0; }
.ma-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }
@media (max-width: 900px) { .ma-grid { grid-template-columns: 1fr; } }
.ma-card {
  border: 1px solid rgba(15,23,42,0.12); border-radius: 14px;
  padding: 14px 16px; background: #fff;
}
.ma-card h4 { margin: 0 0 10px 0; }
.ma-mission-row {
  border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px 14px;
  margin-bottom: 10px; background: #fafafa;
}
.ma-mission-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.ma-mission-title { font-weight: 800; font-size: 0.98rem; }
.ma-mission-score { font-weight: 900; font-size: 1.1rem; color: #15803d; }
.ma-bar-track { height: 8px; border-radius: 999px; background: #e2e8f0; margin: 8px 0; overflow: hidden; }
.ma-bar-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #a78bfa, #6366f1); }
.ma-why { font-size: 0.88rem; color: #475569; line-height: 1.5; margin: 6px 0 0 0; }
.ma-sub { font-size: 0.84rem; margin: 4px 0 0 0; }
.ma-good { color: #166534; }
.ma-grow { color: #b45309; }
.ma-pill {
  display: inline-block; border-radius: 999px; padding: 4px 10px; font-size: 0.76rem;
  font-weight: 700; background: #fff; border: 1px solid #cbd5e1; margin-right: 6px;
}
.ma-pill.good { border-color: #86efac; background: #f0fdf4; color: #166534; }
.ma-pill.warn { border-color: #fcd34d; background: #fffbeb; color: #92400e; }
.ma-metric-row { display: grid; grid-template-columns: 140px 1fr 32px; gap: 8px; align-items: center; margin-bottom: 6px; font-size: 0.82rem; }
.ma-radar-wrap { display: flex; justify-content: center; }
.ma-radar-grid { fill: none; stroke: #cbd5e1; stroke-width: 1; }
.ma-radar-fill { fill: rgba(99, 102, 241, 0.28); stroke: #6366f1; stroke-width: 2; }
.ma-radar-label { font-size: 8px; fill: #64748b; font-weight: 700; }
</style>
"""


def render_mission_analysis_html(result: dict[str, Any]) -> str:
    """HTML block appended to recording analysis dashboard."""
    missions = result.get("mission_results") or []
    if not missions:
        return ""

    overall = int(result.get("overall_improv_score") or 0)
    metrics = result.get("musical_metrics") or {}
    metric_rows = ""
    show_metrics = sorted(metrics.items(), key=lambda x: -x[1])[:8]
    for name, val in show_metrics:
        label = name.replace("_", " ").title()
        metric_rows += f"""
<div class="ma-metric-row">
  <span>{_esc(label)}</span>
  <div class="ma-bar-track"><div class="ma-bar-fill" style="width:{max(8, min(100, int(val)))}%"></div></div>
  <span>{int(val)}</span>
</div>"""

    mission_cards = ""
    for m in missions:
        sc = int(m.get("score", 0))
        mission_cards += f"""
<div class="ma-mission-row">
  <div class="ma-mission-head">
    <span class="ma-mission-title">{_esc(m.get('label', ''))}</span>
    <span class="ma-mission-score">{sc}%</span>
  </div>
  <div class="ma-bar-track"><div class="ma-bar-fill" style="width:{max(8, sc)}%"></div></div>
  <p class="ma-why">{_esc(m.get('summary', ''))}</p>
  <p class="ma-sub ma-good"><strong>What went well:</strong> {_esc(m.get('went_well', ''))}</p>
  <p class="ma-sub ma-grow"><strong>To improve:</strong> {_esc(m.get('improve_to', ''))}</p>
</div>"""

    rec = _esc(result.get("mission_next_recommendation", ""))
    strongest = _esc(result.get("mission_strongest", ""))
    weakest = _esc(result.get("mission_weakest", ""))

    return f"""
{MISSION_ANALYSIS_CSS}
<div class="ma-block">
  <div class="ma-hero">
    <h3>🎯 AI improvisation evaluation</h3>
    <p class="ma-overall">Overall Improvisation Score: {overall}%</p>
    <p>{_esc(result.get('mission_coach_summary', ''))}</p>
    <div style="margin-top:10px">
      <span class="ma-pill good">Strongest: {strongest}</span>
      <span class="ma-pill warn">Weakest: {weakest}</span>
    </div>
  </div>
  <div class="ma-grid">
    <div class="ma-card">
      <h4>Criteria scores</h4>
      {mission_cards}
    </div>
    <div class="ma-card">
      <h4>Criteria radar</h4>
      <div class="ma-radar-wrap">{_mission_radar_svg(missions)}</div>
      <h4 style="margin-top:14px">Underlying signals</h4>
      {metric_rows}
    </div>
  </div>
  <div class="ma-card">
    <h4>Recommended next practice</h4>
    <p>{rec}</p>
  </div>
</div>
"""


ANALYSIS_CRITERIA_LOCKED = "analysis_criteria_locked"
ANALYSIS_RETURN_TO_METRICS = "analysis_return_to_improv_metrics"


def criteria_labels_from_session(session_state: dict) -> list[str]:
    from mission_analysis import MISSION_BY_ID, resolve_selected_mission_ids

    return [
        MISSION_BY_ID[mid].label
        for mid in resolve_selected_mission_ids(session_state, include_creative=True)
        if mid in MISSION_BY_ID
    ]


def prepare_analysis_from_creative(session_state: dict, *, locked: bool = False) -> None:
    sync_analysis_missions_from_creative(session_state)
    if locked:
        session_state[ANALYSIS_CRITERIA_LOCKED] = True


def prepare_metrics_upload_workflow(session_state: dict) -> None:
    """Metrics & AI → Upload Analysis → return to Metrics & AI with results."""
    prepare_analysis_from_creative(session_state, locked=True)
    session_state[ANALYSIS_RETURN_TO_METRICS] = True


def is_analysis_criteria_locked(session_state: dict) -> bool:
    return bool(session_state.get(ANALYSIS_CRITERIA_LOCKED))


def clear_analysis_workflow_flags(session_state: dict) -> None:
    session_state.pop(ANALYSIS_CRITERIA_LOCKED, None)
    session_state.pop(ANALYSIS_RETURN_TO_METRICS, None)


def render_analysis_criteria_summary(st: Any, session_state: dict) -> list[str]:
    """Read-only summary when criteria were chosen on Metrics & AI."""
    from mission_analysis import resolve_selected_mission_ids

    labels = criteria_labels_from_session(session_state)
    st.markdown("##### Evaluating")
    if labels:
        st.markdown(
            '<div class="ui-card soft" style="padding:0.75rem 1rem;">'
            + ", ".join(f"<strong>{_esc(l)}</strong>" for l in labels)
            + "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.warning(
            "No metrics selected yet. Go to **Creative Lab → Improvisation Intelligence → Metrics & AI** "
            "and choose what to evaluate."
        )
    if st.button("Change criteria on Metrics & AI", key="analysis_change_criteria_btn"):
        session_state[ANALYSIS_CRITERIA_LOCKED] = False
        session_state[ANALYSIS_RETURN_TO_METRICS] = False
        st.rerun()
    return resolve_selected_mission_ids(session_state, include_creative=True)


def render_improv_metrics_results(st: Any, result: dict[str, Any]) -> None:
    """Show completed upload analysis on the Metrics & AI tab."""
    if not result or not result.get("ok"):
        return
    st.markdown("---")
    st.markdown("#### Your latest AI coach results")
    st.caption(
        f"**{result.get('song') or 'Take'}** · {result.get('instrument', '')} · "
        f"{result.get('level', '')} · {result.get('focus', '')}"
    )
    overall = result.get("overall_improv_score")
    if overall:
        st.metric("Overall Improvisation Score", f"{overall}%")
    if result.get("mission_strongest"):
        st.success(f"Strongest: {result.get('mission_strongest')}")
    if result.get("mission_weakest"):
        st.warning(f"Grow next: {result.get('mission_weakest')}")
    if result.get("mission_next_recommendation"):
        st.info(f"**Practice recommendation:** {result.get('mission_next_recommendation')}")
    if result.get("went_well"):
        st.success(f"**What went well:** {result.get('went_well')}")
    if result.get("improve_to"):
        st.warning(f"**What needs improvement:** {result.get('improve_to')}")
    if result.get("mission_coach_summary") and not result.get("went_well"):
        st.markdown(result.get("mission_coach_summary"))

    missions = result.get("mission_results") or []
    if missions:
        for m in missions:
            with st.expander(f"{m.get('label', '')} — {m.get('score', 0)}%", expanded=True):
                st.markdown(m.get("summary", ""))
                if m.get("went_well"):
                    st.markdown(f"**What went well:** {m.get('went_well')}")
                if m.get("improve_to"):
                    st.markdown(f"**To improve:** {m.get('improve_to')}")
                for tip in m.get("tips") or []:
                    st.markdown(f"- {tip}")

    st.markdown(
        render_mission_analysis_html(result),
        unsafe_allow_html=True,
    )
