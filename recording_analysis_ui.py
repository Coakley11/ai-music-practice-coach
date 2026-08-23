"""Premium HTML dashboard for recording analysis results."""

from __future__ import annotations

import html
import math
from typing import Any


def _esc(s: Any) -> str:
    return html.escape(str(s))


def _score_bar(label: str, value: int, tone: str = "") -> str:
    tone_cls = f" tone-{tone}" if tone else ""
    return f"""
<div class="ra-score-row{tone_cls}">
  <div class="ra-score-label">{_esc(label)}</div>
  <div class="ra-score-track"><div class="ra-score-fill" style="width:{max(8, min(100, value))}%"></div></div>
  <div class="ra-score-num">{value}</div>
</div>"""


def _radar_svg(scores: dict[str, int]) -> str:
    keys = ["timing", "pitch", "technique", "groove", "musicality", "confidence", "tone"]
    labels = ["Timing", "Pitch", "Technique", "Groove", "Music", "Conf.", "Tone"]
    cx, cy, r = 120, 120, 88
    pts = []
    for i, k in enumerate(keys):
        ang = -1.5708 + (2 * 3.14159 * i / len(keys))
        v = scores.get(k, 50) / 100.0
        x = cx + r * v * math.cos(ang)
        y = cy + r * v * math.sin(ang)
        pts.append(f"{x:.1f},{y:.1f}")
    grid_pts = []
    for i in range(len(keys)):
        ang = -1.5708 + (2 * 3.14159 * i / len(keys))
        x = cx + r * math.cos(ang)
        y = cy + r * math.sin(ang)
        grid_pts.append(f"{x:.1f},{y:.1f}")
    label_html = ""
    for i, lab in enumerate(labels):
        ang = -1.5708 + (2 * 3.14159 * i / len(keys))
        x = cx + (r + 16) * math.cos(ang)
        y = cy + (r + 16) * math.sin(ang)
        label_html += f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="middle" class="ra-radar-label">{_esc(lab)}</text>'
    return f"""
<svg class="ra-radar" viewBox="0 0 240 240" xmlns="http://www.w3.org/2000/svg">
  <polygon points="{' '.join(grid_pts)}" class="ra-radar-grid"/>
  <polygon points="{' '.join(pts)}" class="ra-radar-fill"/>
  {label_html}
</svg>"""


def _waveform_svg(peaks: list[float], times: list[float], regions: list[dict[str, Any]]) -> str:
    w, h = 640, 72
    if not peaks:
        return "<div class='ra-wave-empty'>Waveform unavailable</div>"
    bars = []
    n = len(peaks)
    bw = max(1, w // n)
    for i, p in enumerate(peaks):
        bh = max(2, int(p * (h - 8)))
        x = i * bw
        color = "#22c55e"
        for reg in regions:
            t0 = float(reg.get("start", -1))
            t1 = float(reg.get("end", -1))
            if i < len(times) and t0 <= times[i] <= t1:
                sev = reg.get("severity", "low")
                color = "#f59e0b" if sev == "medium" else "#fca5a5"
                break
        bars.append(
            f'<rect x="{x}" y="{h - bh}" width="{max(1, bw - 1)}" height="{bh}" fill="{color}" opacity="0.85" rx="1"/>'
        )
    region_marks = ""
    dur = times[-1] if times else 1.0
    for reg in regions[:6]:
        t0 = float(reg.get("start", 0))
        x0 = int((t0 / max(dur, 0.01)) * w)
        region_marks += (
            f'<line x1="{x0}" y1="0" x2="{x0}" y2="{h}" class="ra-region-line" '
            f'data-label="{_esc(reg.get("label", ""))}"/>'
        )
    return f'<svg class="ra-wave" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">{region_marks}{"".join(bars)}</svg>'


ANALYSIS_CSS = """
<style>
.ra-dashboard {
  font-family: system-ui, -apple-system, Segoe UI, sans-serif;
  color: #0f172a;
  max-width: 100%;
}
.ra-hero {
  border-radius: 16px;
  padding: 18px 20px;
  margin-bottom: 14px;
  background: linear-gradient(135deg, #ecfdf5 0%, #f0f9ff 55%, #faf5ff 100%);
  border: 1px solid rgba(15, 23, 42, 0.1);
}
.ra-hero h2 { margin: 0 0 8px 0; font-size: 1.25rem; }
.ra-hero p { margin: 0; color: #334155; line-height: 1.5; font-size: 0.95rem; }
.ra-pills { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.ra-pill {
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 0.78rem;
  font-weight: 700;
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.12);
}
.ra-pill.issue { border-color: #fbbf24; background: #fffbeb; color: #92400e; }
.ra-pill.focus { border-color: #22c55e; background: #f0fdf4; color: #166534; }
.ra-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 14px;
}
@media (max-width: 900px) { .ra-grid { grid-template-columns: 1fr; } }
.ra-card {
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 14px;
  padding: 14px 16px;
  background: #fff;
}
.ra-card h3 { margin: 0 0 10px 0; font-size: 1.02rem; }
.ra-score-row { display: grid; grid-template-columns: 88px 1fr 36px; gap: 8px; align-items: center; margin-bottom: 8px; }
.ra-score-label { font-size: 0.82rem; font-weight: 700; color: #475569; }
.ra-score-track { height: 10px; border-radius: 999px; background: #e2e8f0; overflow: hidden; }
.ra-score-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #4ade80, #16a34a); }
.ra-score-num { font-weight: 800; font-size: 0.88rem; text-align: right; }
.ra-radar-wrap { display: flex; justify-content: center; }
.ra-radar-grid { fill: none; stroke: #cbd5e1; stroke-width: 1; }
.ra-radar-fill { fill: rgba(34, 197, 94, 0.28); stroke: #16a34a; stroke-width: 2; }
.ra-radar-label { font-size: 9px; fill: #64748b; font-weight: 700; }
.ra-wave-wrap {
  border-radius: 12px;
  background: #0f172a;
  padding: 10px 12px;
  margin-bottom: 10px;
}
.ra-wave { width: 100%; height: auto; display: block; }
.ra-region-line { stroke: rgba(251, 191, 36, 0.7); stroke-width: 2; stroke-dasharray: 4 3; }
.ra-wave-legend { font-size: 0.78rem; color: #94a3b8; margin-top: 6px; }
.ra-section {
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 12px;
  margin-bottom: 10px;
  background: #fafafa;
  overflow: hidden;
}
.ra-section summary {
  cursor: pointer;
  padding: 12px 14px;
  font-weight: 800;
  list-style: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ra-section summary::-webkit-details-marker { display: none; }
.ra-section-body { padding: 0 14px 14px 14px; font-size: 0.92rem; line-height: 1.55; color: #334155; }
.ra-section-body ul { margin: 8px 0 0 0; padding-left: 1.1rem; }
.ra-section-body li { margin-bottom: 6px; }
.ra-badge {
  font-size: 0.75rem;
  font-weight: 800;
  padding: 3px 9px;
  border-radius: 999px;
  background: #dcfce7;
  color: #166534;
}
.ra-plan li { margin-bottom: 8px; }
.ra-muted { color: #64748b; font-size: 0.86rem; }
</style>
"""


def render_analysis_dashboard(result: dict[str, Any]) -> str:
    """Full HTML report for st.markdown(..., unsafe_allow_html=True)."""
    if not result.get("ok"):
        return f"<div class='ra-dashboard'><p>{_esc(result.get('message', 'Analysis failed.'))}</p></div>"

    # Stem-comparison Mix (2+ layers) uses the ensemble dashboard.
    # Layer / single-mix takes that already have full coach categories use the
    # standard report so Step 3 is not an empty findings shell.
    if result.get("multitrack") and not (
        result.get("categories") or result.get("features")
    ):
        return _render_multitrack_dashboard(result)

    features = result.get("features")
    if isinstance(features, dict):
        peaks = list(features.get("waveform_peaks") or [])
        times = list(features.get("waveform_times") or [])
        regions = list(features.get("highlight_regions") or [])
    else:
        peaks = getattr(features, "waveform_peaks", []) if features else []
        times = getattr(features, "waveform_times", []) if features else []
        regions = getattr(features, "highlight_regions", []) if features else []
    scores = result.get("scores") or {}


    ensemble_html = ""
    ens = result.get("ensemble_mix_analysis")
    if isinstance(ens, dict) and ens:
        def _ens_list(key: str) -> str:
            items = ens.get(key) or []
            if not items:
                return "<li class='ra-muted'>No strong evidence for this dimension.</li>"
            return "".join(f"<li>{_esc(x)}</li>" for x in items if str(x).strip())

        ensemble_html = f"""
  <div class="ra-card" style="margin-bottom:14px">
    <h3>Ensemble Mix analysis</h3>
    <p class="ra-muted">{_esc(ens.get("balance_policy") or ens.get("input_mode") or "")}</p>
    <h4>Timing cohesion</h4><ul>{_ens_list("timing_cohesion")}</ul>
    <h4>Groove cohesion</h4><ul>{_ens_list("groove_cohesion")}</ul>
    <h4>Balance</h4><ul>{_ens_list("balance")}</ul>
    <h4>Interaction / space</h4><ul>{_ens_list("interaction_space")}</ul>
    <h4>Musical shape</h4><ul>{_ens_list("musical_shape")}</ul>
  </div>"""

    score_rows = "".join(
        _score_bar(k.title(), scores.get(k, 0))
        for k in ["timing", "pitch", "technique", "groove", "musicality", "confidence", "tone"]
    )

    categories_html = ""
    for key, cat in (result.get("categories") or {}).items():
        findings = "".join(f"<li>{_esc(x)}</li>" for x in cat.get("findings", []))
        tips = "".join(f"<li>{_esc(x)}</li>" for x in cat.get("tips", []))
        sc = cat.get("score", scores.get(key, 0))
        categories_html += f"""
<details class="ra-section" open>
  <summary><span>{_esc(cat.get('title', key))}</span><span class="ra-badge">{sc}/100</span></summary>
  <div class="ra-section-body">
    <strong>Coach observations</strong><ul>{findings}</ul>
    <strong>Practice tips</strong><ul>{tips}</ul>
  </div>
</details>"""

    plan_items = "".join(f"<li>{_esc(p)}</li>" for p in result.get("practice_plan", []))

    mission_html = ""
    if result.get("mission_results"):
        from mission_analysis_ui import render_mission_analysis_html

        mission_html = render_mission_analysis_html(result)
        # Criterion tips already appear in Selected Evaluating Criteria cards — do not
        # duplicate them into Recommended next practice.

    focus_blocks_html = ""
    focus_blocks = (
        result.get("mix_focus_analysis")
        or result.get("practice_focus_analysis")
        or result.get("target_layer_focus_analysis")
        or []
    )
    if isinstance(focus_blocks, list) and focus_blocks:
        rtype_focus = str(result.get("recording_type") or "").strip().lower().replace("_", " ")
        mode_focus = str(result.get("multitrack_mode") or "").strip().lower()
        is_mix_focus = ("mix" in rtype_focus) or mode_focus.startswith("mix")
        target_name = _esc(
            result.get("target_layer") or result.get("instrument") or "Target layer"
        )
        block_parts: list[str] = []
        current_inst = None
        for block in focus_blocks:
            if not isinstance(block, dict):
                continue
            inst = str(block.get("instrument") or block.get("target_layer") or "").strip()
            if is_mix_focus and inst and inst != current_inst:
                current_inst = inst
                block_parts.append(f"<h4 style='margin:12px 0 6px'>{_esc(inst)}</h4>")
            foc = _esc(block.get("focus") or "Focus")
            raw_assessment = str(block.get("assessment") or "")
            mix_limited = (
                str(block.get("attribution_scope") or "").lower() in {"mix_limited", "mix"}
                or bool(block.get("mix_proxy_score") is not None and block.get("display_as_instrument_score") is False)
                or "limited" in raw_assessment.lower()
            )
            # One-file Mix: badge stays qualitative — never show mix proxy as instrument grade.
            if mix_limited and "/100" in raw_assessment:
                badge = "Limited attribution"
            else:
                badge = raw_assessment or "Focus"
            assessment = _esc(badge)
            findings = "".join(
                f"<li>{_esc(x)}</li>" for x in (block.get("findings") or []) if str(x).strip()
            )
            went = _esc(block.get("went_well") or "")
            improve = _esc(block.get("improve_to") or "")
            drill = _esc(block.get("drill") or "")
            proxy_score = block.get("mix_proxy_score")
            proxy_label = str(block.get("mix_proxy_label") or "ensemble mix proxy").strip()
            proxy_html = ""
            if mix_limited and proxy_score is not None:
                try:
                    proxy_html = (
                        "<p><strong>Relevant mix cue:</strong> "
                        + _esc(proxy_label)
                        + f" = {int(proxy_score)}/100 "
                        + "(ensemble evidence, not an isolated instrument grade).</p>"
                    )
                except (TypeError, ValueError):
                    proxy_html = ""
            block_parts.append(
                f"""
<details class="ra-section" open>
  <summary><span>{foc}</span><span class="ra-badge">{assessment}</span></summary>
  <div class="ra-section-body">
    {"<p><strong>Assessment:</strong> " + _esc(raw_assessment) + "</p>" if (mix_limited and raw_assessment) else ""}
    {proxy_html}
    {"<strong>What was detected</strong><ul>" + findings + "</ul>" if findings else ""}
    {("<p><strong>Evidence confidence:</strong> " + _esc(block.get("attribution_confidence") or "") + "</p>") if block.get("attribution_confidence") else ""}
    {"<p><strong>What went well:</strong> " + went + "</p>" if went else ""}
    {"<p><strong>To improve:</strong> " + improve + "</p>" if improve else ""}
    {"<p><strong>Drill:</strong> " + drill + "</p>" if drill else ""}
  </div>
</details>"""
            )
        arrangement = str(result.get("layer_arrangement_context") or "").strip()
        arrangement_html = (
            f"<p class='ra-muted'>{_esc(arrangement)}</p>" if arrangement else ""
        )
        if is_mix_focus:
            _focus_heading = "Practice Focus analysis — Ensemble"
        elif bool(result.get("multitrack") or result.get("target_layer")):
            _focus_heading = f"Practice Focus analysis — {target_name}"
        else:
            _focus_heading = "Practice Focus analysis"
        focus_blocks_html = f"""
  <div class="ra-card" style="margin-bottom:14px">
    <h3>{_focus_heading}</h3>
    {arrangement_html}
    {"".join(block_parts)}
  </div>"""

    tempo_line = ""
    tempo_val = result.get("tempo")
    if tempo_val is not None:
        try:
            tempo_line = (
                f"<span class='ra-pill'>~{_esc(f'{float(tempo_val):.0f}')} BPM detected</span>"
            )
        except (TypeError, ValueError):
            pass
    ref_bpm = result.get("reference_bpm")
    ref_line = ""
    if ref_bpm not in (None, ""):
        try:
            ref_line = (
                f"<span class='ra-pill'>Song reference {int(float(ref_bpm))} BPM</span>"
            )
        except (TypeError, ValueError):
            ref_line = f"<span class='ra-pill'>Song reference {_esc(str(ref_bpm))}</span>"

    _rtype_cap = str(result.get("recording_type") or "").strip().lower().replace("_", " ")
    _mode_cap = str(result.get("multitrack_mode") or "").strip().lower()
    if ("mix" in _rtype_cap) or _mode_cap.startswith("mix"):
        score_caption = (
            "Mix-level estimates from the blended recording — not isolated instrument grades."
        )
    else:
        score_caption = (
            "Scores are coach estimates from rhythm, pitch, dynamics, and articulation — not exam grades."
        )

    duration = float(result.get("duration", 0) or 0)
    duration_text = _esc(f"{duration:.1f}s")
    rtype_meta = str(result.get("recording_type") or "").strip().lower().replace("_", " ")
    mode_meta = str(result.get("multitrack_mode") or "").strip().lower()
    is_mix_meta = ("mix" in rtype_meta) or mode_meta.startswith("mix")
    instruments_meta = [
        str(x).strip() for x in (result.get("instruments") or []) if str(x).strip()
    ]
    if is_mix_meta:
        instrument_text = _esc(
            result.get("instrument_display")
            or (
                ("Multitrack Mix — " + " + ".join(instruments_meta))
                if instruments_meta
                else "Multitrack Mix"
            )
        )
    else:
        instrument_text = _esc(result.get("instrument", ""))
    target_pill = ""
    if is_mix_meta and instruments_meta:
        target_pill = (
            f"<span class='ra-pill focus'>Mix: {_esc(' + '.join(instruments_meta))}</span>"
        )
    elif result.get("target_layer"):
        target_pill = (
            f"<span class='ra-pill focus'>Layer: {_esc(result.get('target_layer'))}</span>"
        )

    song_ctx = result.get("selected_song_analysis_context")
    if not isinstance(song_ctx, dict):
        song_ctx = {}
        snap = result.get("analysis_context_snapshot")
        if isinstance(snap, dict) and isinstance(snap.get("selected_song_analysis_context"), dict):
            song_ctx = dict(snap["selected_song_analysis_context"])
    song_authority_html = ""
    try:
        from recording_analysis_context import format_selected_song_authority_lines

        lines = format_selected_song_authority_lines(song_ctx) if song_ctx else []
        if not lines and result.get("song_source_name"):
            lines = [f"Song: {result.get('song_source_name')}"]
            if result.get("song_source_type"):
                lines.append(f"Source: {result.get('song_source_type')}")
        try:
            from recording_analysis_context import format_recording_key_authority_lines

            lines.extend(format_recording_key_authority_lines(result))
        except Exception:
            if result.get("display_key"):
                lines.append(f"Concert Key: {result.get('display_key')}")
            if result.get("written_key"):
                lines.append(f"Written Key: {result.get('written_key')}")
        if lines:
            pills = "".join(f"<span class='ra-pill'>{_esc(line)}</span>" for line in lines)
            song_authority_html = f"""
  <div class="ra-card" style="margin-bottom:14px">
    <h3>Selected song authority</h3>
    <div class="ra-pills">{pills}</div>
    <p class="ra-muted">Expected musical context for this analysis. Detected audio is scored in concert/sounding pitch; written keys are for musician-facing coaching only.</p>
  </div>"""
    except Exception:
        song_authority_html = ""

    return f"""
{ANALYSIS_CSS}
<div class="ra-dashboard">
  <div class="ra-hero">
    <h2>🎓 AI Coach Summary</h2>
    <p>{_esc(result.get('coach_summary', ''))}</p>
    <div class="ra-pills">
      {tempo_line}
      {ref_line}
      <span class="ra-pill">{duration_text} · {instrument_text}</span>
      {target_pill}
      <span class="ra-pill issue">⚠ {_esc(result.get('biggest_issue', ''))}</span>
      <span class="ra-pill focus">→ {_esc(result.get('next_focus', ''))}</span>
    </div>
  </div>

  {song_authority_html}

  {focus_blocks_html}

  {ensemble_html}

  <div class="ra-card" style="margin-bottom:14px">
    <h3>Playback timeline</h3>
    <div class="ra-wave-wrap">{_waveform_svg(peaks, times, regions)}</div>
    <div class="ra-wave-legend">Green = audio energy · Amber/red markers = coach-flagged moments (rush, drag, pitch drift, low energy)</div>
  </div>

  <div class="ra-grid">
    <div class="ra-card">
      <h3>Performance scores</h3>
      {score_rows}
      <p class="ra-muted">{score_caption}</p>
    </div>
    <div class="ra-card">
      <h3>Skill radar</h3>
      <div class="ra-radar-wrap">{_radar_svg(scores)}</div>
      <p class="ra-muted"><strong>Most improved area:</strong> {_esc(result.get('most_improved', ''))}</p>
    </div>
  </div>

  <div class="ra-card" style="margin-bottom:14px">
    <h3>Deep dive by category</h3>
    {categories_html}
  </div>

  {mission_html}

  <div class="ra-card">
    <h3>Recommended next practice</h3>
    <ul class="ra-plan">{plan_items}</ul>
    {"" if mission_html else (f'<p class="ra-muted">{_esc(result.get("mission_next_recommendation", ""))}</p>' if result.get("mission_next_recommendation") else "")}
  </div>
</div>
"""


def _render_multitrack_dashboard(result: dict[str, Any]) -> str:
    findings = "".join(f"<li>{_esc(x)}</li>" for x in result.get("findings", []))
    tips = "".join(f"<li>{_esc(x)}</li>" for x in result.get("tips", []))
    layers = ", ".join(_esc(x) for x in result.get("layers", []))
    return f"""
{ANALYSIS_CSS}
<div class="ra-dashboard">
  <div class="ra-hero">
    <h2>🎚️ Multitrack ensemble analysis</h2>
    <p>{_esc(result.get('coach_summary', ''))}</p>
    <div class="ra-pills"><span class="ra-pill">Layers: {layers}</span></div>
  </div>
  <div class="ra-card">
    <h3>Ensemble findings</h3>
    <ul>{findings}</ul>
    <h3>Mix &amp; sync tips</h3>
    <ul>{tips}</ul>
  </div>
</div>
"""
