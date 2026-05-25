"""Unified block chord chart for backing-track follow-along (all songs)."""

from __future__ import annotations

import html
from typing import Any

from chord_subdivisions import (
    is_subdivided_bar as _sub_is_subdivided_bar,
    subdivisions as _sub_subdivisions,
)

BACKING_CHART_CSS = """
<style>
.backing-chart-sheet { font-family: system-ui, -apple-system, Segoe UI, sans-serif; }
.backing-chart-sheet .lead-header {
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 16px;
  padding: 14px 16px;
  margin-bottom: 12px;
  background: linear-gradient(180deg, #ffffff, #f8fafc);
}
.backing-chart-sheet .lead-title { font-size: 1.28rem; font-weight: 800; margin-bottom: 4px; }
.backing-chart-sheet .lead-subtitle { color: #475569; margin-bottom: 10px; font-size: 0.9rem; }
.backing-chart-sheet .meta-row { display: flex; gap: 8px; flex-wrap: wrap; }
.backing-chart-sheet .meta-pill {
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 999px;
  padding: 4px 10px;
  background: #fff;
  font-size: 0.82rem;
  color: #334155;
}
.backing-chart-sheet .now-playing {
  border-left: 5px solid #22c55e;
  background: #f0fdf4;
  padding: 9px 12px;
  border-radius: 12px;
  margin: 10px 0 12px 0;
  font-weight: 750;
  font-size: 0.95rem;
}
.backing-chart-sheet .section-card {
  border: 1px solid rgba(15, 23, 42, 0.13);
  border-left-width: 7px;
  border-radius: 16px;
  padding: 12px 14px;
  margin-bottom: 12px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
  scroll-margin-top: 4.5rem;
}
.backing-chart-sheet .section-card.gray { border-left-color: #94a3b8; background: #f5f6f8; }
.backing-chart-sheet .section-card.verse { border-left-color: #60a5fa; background: #eef6ff; }
.backing-chart-sheet .section-card.pre { border-left-color: #2dd4bf; background: #eafaf7; }
.backing-chart-sheet .section-card.chorus { border-left-color: #22c55e; background: #eefaf0; }
.backing-chart-sheet .section-card.bridge { border-left-color: #a78bfa; background: #f5f0ff; }
.backing-chart-sheet .section-card.solo { border-left-color: #fb923c; background: #fff4e6; }
.backing-chart-sheet .section-card.neutral { border-left-color: #cbd5e1; }
.backing-chart-sheet .section-card.current {
  outline: 3px solid rgba(34, 197, 94, 0.28);
  box-shadow: 0 0 0 5px rgba(34, 197, 94, 0.08);
}
.backing-chart-sheet .section-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
  margin-bottom: 8px;
}
.backing-chart-sheet .section-title { font-size: 1.08rem; font-weight: 800; color: #0f172a; }
.backing-chart-sheet .section-meta { color: #475569; font-size: 0.86rem; }
.backing-chart-sheet .lead-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(92px, 1fr));
  gap: 10px 12px;
  margin: 8px 0 4px 0;
}
.backing-chart-sheet .chord-cell {
  min-height: 72px;
  border: 1.5px solid rgba(15, 23, 42, 0.22);
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff, #f8fafc);
  padding: 7px 9px;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.backing-chart-sheet .chord-cell.current-chord {
  background: linear-gradient(180deg, #bbf7d0, #dcfce7);
  border-color: #15803d;
  box-shadow: 0 0 0 4px rgba(22, 163, 74, 0.22), 0 8px 18px rgba(22, 163, 74, 0.18);
  transform: translateY(-1px);
}
.backing-chart-sheet .bar-num { color: #64748b; font-size: 0.68rem; font-weight: 700; margin-bottom: 4px; }
.backing-chart-sheet .chord-symbol {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 1.3rem;
  font-weight: 900;
  letter-spacing: -0.03em;
  color: #0f172a;
}
.backing-chart-sheet .duration {
  display: inline-block;
  margin-top: 3px;
  color: #64748b;
  font-size: 0.70rem;
  font-weight: 700;
}
.backing-chart-sheet .chord-cell.subdivided .chord-symbol {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  flex-wrap: wrap;
  font-size: 0.96rem;
  letter-spacing: -0.02em;
  line-height: 1.05;
}
.backing-chart-sheet .chord-cell.subdivided .sub-chord {
  padding: 2px 5px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(15, 23, 42, 0.10);
  transition: background 0.12s ease, color 0.12s ease;
}
.backing-chart-sheet .chord-cell.subdivided .sub-sep {
  color: #94a3b8;
  font-weight: 700;
  font-size: 0.82rem;
  margin: 0 1px;
}
.backing-chart-sheet .chord-cell.subdivided.current-chord .sub-chord {
  background: rgba(255, 255, 255, 0.55);
  color: #14532d;
}
.backing-chart-sheet .chord-cell.subdivided .sub-chord.active-sub {
  background: #15803d;
  color: #f0fdf4;
  border-color: #14532d;
  box-shadow: 0 0 0 2px rgba(22, 163, 74, 0.45);
}
.backing-chart-sheet .chord-cell.subdivided .subdivided-tag {
  display: block;
  margin-top: 4px;
  color: #15803d;
  font-size: 0.66rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.backing-chart-sheet .lyric-preview {
  margin-top: 6px;
  padding: 6px 8px;
  border-radius: 8px;
  background: rgba(241, 245, 249, 0.9);
  color: #475569;
  font-size: 0.84rem;
  font-style: italic;
}
.backing-chart-sheet .empty-chart { color: #64748b; font-size: 0.9rem; }
@media (max-width: 760px) {
  .backing-chart-sheet .lead-grid { grid-template-columns: repeat(2, minmax(100px, 1fr)); }
}
</style>
"""


def chart_section_role(section_name: str) -> str:
    name = str(section_name).lower()
    if "chorus" in name and "pre" not in name:
        return "chorus"
    if "pre" in name:
        return "pre"
    if "verse" in name or "main loop" in name:
        return "verse"
    if "bridge" in name:
        return "bridge"
    if "solo" in name:
        return "solo"
    if "intro" in name or "outro" in name or "final" in name or "ending" in name:
        return "gray"
    return "neutral"


def chart_feel_label(style: str | None) -> str:
    return {
        "Pop groove": "Pop 8th-note feel",
        "Rock groove": "Rock 8th-note feel",
        "Jazz swing": "Swing feel",
        "Bossa nova": "Bossa feel",
        "Funk groove": "Funk syncopation",
        "Ballad": "Ballad feel",
    }.get(style or "Pop groove", style or "Pop groove")


def _render_chord_symbol_html(token: str) -> tuple[str, bool]:
    """Return ``(symbol_html, is_subdivided)`` for a chart cell."""
    if _sub_is_subdivided_bar(token):
        parts = _sub_subdivisions(token)
        spans: list[str] = []
        for sub_idx, part in enumerate(parts):
            if sub_idx > 0:
                spans.append("<span class='sub-sep'>&rarr;</span>")
            spans.append(
                f"<span class='sub-chord' data-sub='{sub_idx}'>{html.escape(str(part))}</span>"
            )
        return "".join(spans), True
    return html.escape(str(token)), False


def chart_grid_html(
    chords: list[str],
    *,
    section_name: str = "",
    current_bar: int | None = None,
    shape_chords: list[str] | None = None,
) -> str:
    """Block chord cells with ``live-chart-cell`` markers for JS follow-along."""
    if not chords:
        return "<div class='empty-chart'>No chords entered for this section.</div>"
    cells = []
    safe_section_attr = html.escape(str(section_name), quote=True)
    for idx, chord in enumerate(chords):
        previous = chords[idx - 1] if idx else None
        same_as_prev = bool(previous and chord == previous)
        is_subdivided = _sub_is_subdivided_bar(chord)
        # Don't compress subdivided bars with a "%" repeat marker - each
        # subdivided bar is its own distinct passing-harmony event.
        if same_as_prev and not is_subdivided:
            display_token = "%"
            symbol_html = "%"
            subdivided_cell = False
        else:
            display_token = str(chord)
            symbol_html, subdivided_cell = _render_chord_symbol_html(display_token)
        current_class = " current-chord" if current_bar == idx + 1 else ""
        sub_class = " subdivided" if subdivided_cell else ""
        repeat_count = 1
        if display_token != "%" and not subdivided_cell:
            for nxt in chords[idx + 1:]:
                if nxt != chord:
                    break
                repeat_count += 1
        duration = (
            f"<span class='duration'>{repeat_count} bars</span>" if repeat_count > 1 else ""
        )
        if subdivided_cell:
            duration = (
                f"{duration}<span class='subdivided-tag'>Passing &middot; subdivided bar</span>"
            )
        shape_hint = ""
        if (
            shape_chords
            and idx < len(shape_chords)
            and display_token != "%"
            and not subdivided_cell
            and shape_chords[idx] != display_token
        ):
            shape_hint = (
                f"<div class='chord-shape-hint' style='font-size:0.72rem;color:#64748b;"
                f"margin-top:2px;'>{html.escape(str(shape_chords[idx]))} shape</div>"
            )
        cells.append(
            f"<div class='chord-cell live-chart-cell{current_class}{sub_class}' "
            f"data-section='{safe_section_attr}' data-bar='{idx + 1}'>"
            f"<div class='bar-num'>Bar {idx + 1}</div>"
            f"<div class='chord-symbol'>{symbol_html}</div>"
            f"{shape_hint}{duration}</div>"
        )
    return "<div class='lead-grid'>" + "".join(cells) + "</div>"


def user_lyric_preview_html(section_name: str, section_lyrics: dict[str, str] | None) -> str:
    """Optional first-line preview — only when the user entered custom lyrics."""
    user_text = (section_lyrics or {}).get(section_name, "")
    lines = [ln.strip() for ln in str(user_text).splitlines() if ln.strip()]
    if not lines:
        return ""
    first = html.escape(lines[0])
    if len(lines) > 1:
        first += " …"
    return f'<div class="lyric-preview"><strong>Your lyric:</strong> {first}</div>'


def render_backing_chord_chart(
    song_name: str,
    song_data: dict[str, Any],
    sections: dict[str, list[str]],
    *,
    display_key: str | None = None,
    level: str = "Intermediate",
    groove_style: str = "Pop groove",
    bpm: int = 100,
    time_signature: str = "4/4",
    current_section: str | None = None,
    current_bar: int | None = None,
    section_lyrics: dict[str, str] | None = None,
    selected_section_names: list[str] | None = None,
    show_user_lyric_preview: bool = False,
    shape_sections: dict[str, list[str]] | None = None,
    capo_fret: int = 0,
    capo_shape_key: str = "",
) -> str:
    """Section-based block chart for backing playback (no auto lyric dump)."""
    dk = display_key or song_data.get("key", "C")
    show_full = not current_section or str(current_section).strip().lower() in (
        "full song",
        "full form",
        "",
    )
    now_playing = "Full song" if show_full else str(current_section)
    ext = song_data.get("extensions") or {}
    total_bars = sum(len(chords) for chords in sections.values())
    selected = set(selected_section_names or [])

    key_text = f"Key: {html.escape(str(dk))}"
    if dk != song_data.get("key"):
        key_text += f" (orig. {html.escape(str(song_data.get('key', '')))})"
    meta_bits = [
        key_text,
    ]
    if shape_sections and capo_shape_key:
        meta_bits.append(
            f"Guitar shape: {html.escape(capo_shape_key)}"
            + (f" · capo {capo_fret}" if capo_fret else "")
        )
    meta_bits.extend([
        f"Level: {html.escape(str(level))}",
        f"Form: {total_bars} bars",
        f"Tempo: {int(bpm)} BPM",
        f"Time: {html.escape(str(time_signature))}",
        f"Feel: {html.escape(chart_feel_label(groove_style))}",
        "Drums/Bass/Comping: active",
    ])
    meta = "".join(f"<span class='meta-pill'>{bit}</span>" for bit in meta_bits)
    header_note = (
        f"<div class='lead-subtitle'>{html.escape(str(ext['arrangement_notes']))}</div>"
        if ext.get("arrangement_notes")
        else ""
    )

    current_parts = set() if show_full else {str(current_section).strip()}
    section_cards = []
    for section_name, chords in sections.items():
        if not chords:
            continue
        if selected and section_name not in selected:
            continue
        if not show_full and section_name not in current_parts:
            continue
        role = chart_section_role(section_name)
        is_current = section_name in current_parts
        now_label = "Now Playing" if is_current else ""
        current_bar_for_section = current_bar if is_current else None
        preview = (
            user_lyric_preview_html(section_name, section_lyrics)
            if show_user_lyric_preview
            else ""
        )
        shape_row = (shape_sections or {}).get(section_name) if shape_sections else None
        section_cards.append(
            f"""
<section class="section-card {role}{' current' if is_current else ''}">
  <div class="section-head">
    <div>
      <div class="section-title">{html.escape(section_name)} — {len(chords)} bars</div>
      <div class="section-meta">{html.escape(chart_feel_label(groove_style))}</div>
    </div>
    <div class="section-meta">{now_label}</div>
  </div>
  {chart_grid_html(chords, section_name=section_name, current_bar=current_bar_for_section, shape_chords=shape_row)}
  {preview}
</section>
"""
        )

    return f"""
{BACKING_CHART_CSS}
<div class="lead-sheet backing-chart-sheet">
  <div class="lead-header">
    <div class="lead-title">{html.escape(song_name)} — Backing chart</div>
    <div class="lead-subtitle">{html.escape(str(song_data.get('artist', '')))} | {html.escape(str(song_data.get('genre', '')))}</div>
    {header_note}
    <div class="meta-row">{meta}</div>
  </div>
  <div class="now-playing">Now Playing: {html.escape(str(now_playing))}</div>
  {''.join(section_cards)}
</div>
"""
