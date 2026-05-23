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

    if result.get("multitrack"):
        return _render_multitrack_dashboard(result)

    features = result.get("features")
    peaks = getattr(features, "waveform_peaks", []) if features else []
    times = getattr(features, "waveform_times", []) if features else []
    regions = getattr(features, "highlight_regions", []) if features else []
    scores = result.get("scores") or {}

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

    tempo_line = ""
    if result.get("tempo"):
        tempo_line = f"<span class='ra-pill'>~{result['tempo']:.0f} BPM detected</span>"

    return f"""
{ANALYSIS_CSS}
<div class="ra-dashboard">
  <div class="ra-hero">
    <h2>🎓 AI Coach Summary</h2>
    <p>{_esc(result.get('coach_summary', ''))}</p>
    <div class="ra-pills">
      {tempo_line}
      <span class="ra-pill">{_esc(result.get('duration', 0)):.1f}s · {_esc(result.get('instrument', ''))}</span>
      <span class="ra-pill issue">⚠ {_esc(result.get('biggest_issue', ''))}</span>
      <span class="ra-pill focus">→ {_esc(result.get('next_focus', ''))}</span>
    </div>
  </div>

  <div class="ra-card" style="margin-bottom:14px">
    <h3>Playback timeline</h3>
    <div class="ra-wave-wrap">{_waveform_svg(peaks, times, regions)}</div>
    <div class="ra-wave-legend">Green = audio energy · Amber/red markers = coach-flagged moments (rush, drag, pitch drift, low energy)</div>
  </div>

  <div class="ra-grid">
    <div class="ra-card">
      <h3>Performance scores</h3>
      {score_rows}
      <p class="ra-muted">Scores are coach estimates from rhythm, pitch, dynamics, and articulation — not exam grades.</p>
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

  <div class="ra-card">
    <h3>Recommended next practice</h3>
    <ul class="ra-plan">{plan_items}</ul>
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
