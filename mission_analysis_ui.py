"""Streamlit + HTML UI for improvisation mission analysis."""

from __future__ import annotations

import html
import math
from typing import Any

from mission_analysis import (
    MISSION_GOALS,
    MISSION_LABELS,
    mission_progress_trends,
    resolve_selected_mission_ids,
    sync_analysis_missions_from_creative,
)


def _esc(s: Any) -> str:
    return html.escape(str(s))


def render_mission_goals_selector(st: Any, session_state: dict) -> list[str]:
    """Mission multiselect + custom goal. Returns selected mission ids."""
    st.markdown("##### Improvisation goals / missions practiced")
    creative_mission = str(session_state.get("improv_active_mission") or "")
    if creative_mission:
        st.caption(f"Creative Lab mission: **{creative_mission}**")

    session_state.setdefault("analysis_sync_creative_mission", True)
    st.checkbox(
        "Include active Creative Lab mission",
        key="analysis_sync_creative_mission",
        help="Maps your current Practice Mission to matching analysis goals.",
    )

    label_to_id = {g.label: g.id for g in MISSION_GOALS if g.id != "custom"}
    id_to_label = {g.id: g.label for g in MISSION_GOALS}

    current_ids = list(session_state.get("analysis_mission_ids") or [])
    default_labels = [id_to_label[i] for i in current_ids if i in id_to_label]

    picked_labels = st.multiselect(
        "Select missions to evaluate (choose all that apply)",
        MISSION_LABELS,
        default=default_labels,
        key="analysis_mission_multiselect",
        help="The coach scores your recording against each selected goal.",
    )
    session_state["analysis_mission_ids"] = [label_to_id[l] for l in picked_labels if l in label_to_id]

    session_state.setdefault("analysis_custom_goal_enabled", False)
    custom_on = st.checkbox("Custom goal", key="analysis_custom_goal_enabled")
    if custom_on:
        session_state.setdefault("analysis_custom_goal", "")
        st.text_input(
            "Describe what you practiced",
            key="analysis_custom_goal",
            placeholder="e.g. Call-and-response with backing hits",
        )

    return resolve_selected_mission_ids(session_state)


def render_mission_history_panel(st: Any) -> None:
    from mission_analysis import load_mission_history

    hist = load_mission_history()
    if not hist:
        st.caption("Mission history builds after you analyze takes with goals selected.")
        return

    with st.expander("Mission progress over time", expanded=False):
        mission_ids = sorted(
            {m["id"] for row in hist for m in (row.get("missions") or []) if m.get("id")}
        )
        if not mission_ids:
            return
        from mission_analysis import MISSION_BY_ID

        pick = st.selectbox(
            "Track mission",
            mission_ids,
            format_func=lambda mid: MISSION_BY_ID.get(mid, mid).label if mid in MISSION_BY_ID else mid,
            key="analysis_mission_trend_pick",
        )
        points = mission_progress_trends(pick)
        if len(points) < 2:
            st.info("Record at least two analyzed takes with this mission to see a trend.")
            return
        st.line_chart(
            data={p["date"]: p["score"] for p in points},
            x_label="Session",
            y_label="Score %",
        )
        first, last = points[0]["score"], points[-1]["score"]
        delta = last - first
        arrow = "improved" if delta > 0 else "shifted"
        st.markdown(
            f"**{MISSION_BY_ID.get(pick).label if pick in MISSION_BY_ID else pick}** "
            f"{arrow} from **{first}%** → **{last}%** across {len(points)} uploads."
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

    metrics = result.get("musical_metrics") or {}
    metric_rows = ""
    show_metrics = sorted(metrics.items(), key=lambda x: -x[1])[:10]
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
  <p class="ma-why"><strong>{_esc(m.get('summary', ''))}</strong><br/>{_esc(m.get('why', ''))}</p>
</div>"""

    rec = _esc(result.get("mission_next_recommendation", ""))
    strongest = _esc(result.get("mission_strongest", ""))
    weakest = _esc(result.get("mission_weakest", ""))

    return f"""
{MISSION_ANALYSIS_CSS}
<div class="ma-block">
  <div class="ma-hero">
    <h3>🎯 Improvisation mission evaluation</h3>
    <p>{_esc(result.get('mission_coach_summary', ''))}</p>
    <div style="margin-top:10px">
      <span class="ma-pill good">↑ {strongest}</span>
      <span class="ma-pill warn">→ {weakest}</span>
    </div>
  </div>
  <div class="ma-grid">
    <div class="ma-card">
      <h4>Mission scores</h4>
      {mission_cards}
    </div>
    <div class="ma-card">
      <h4>Mission radar</h4>
      <div class="ma-radar-wrap">{_mission_radar_svg(missions)}</div>
      <h4 style="margin-top:14px">Musical metrics</h4>
      {metric_rows}
    </div>
  </div>
  <div class="ma-card">
    <h4>Next practice recommendation</h4>
    <p>{rec}</p>
  </div>
</div>
"""


def prepare_analysis_from_creative(session_state: dict) -> None:
    sync_analysis_missions_from_creative(session_state)
