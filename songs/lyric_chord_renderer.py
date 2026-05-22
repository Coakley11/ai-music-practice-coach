"""Ultimate Guitar–style lyric + chord sheet renderer.

Section schema (per section)::

    {
        "section": "Verse 1",
        "lines": [{"chords": ["D", "Bm"], "lyrics": "phrase here"}, ...],
    }

Shorthand — repeat a progression block without rewriting chords::

    {
        "section": "Verse 1",
        "progression_block": [
            {"chords": ["D", "Bm", "G", "D"]},
            {"chords": ["A", "Bm", "G", "D"]},
        ],
        "progression_repeat": 4,
        "lyrics": ["line 1", "line 2", ...],
    }

Chord-only rows omit ``lyrics`` or use an empty string.
"""

from __future__ import annotations

import html
import re
from typing import Any

try:
    from music_theory import semitone_distance, transpose_chord
except ImportError:
    semitone_distance = None  # type: ignore[assignment]
    transpose_chord = None  # type: ignore[assignment]

LyricLine = dict[str, Any]
LyricSection = dict[str, Any]


def split_lyrics_for_chords(text: str, chord_count: int) -> list[str]:
    """Split lyric text into *chord_count* segments for pill alignment."""
    text = (text or "").strip()
    n = max(0, int(chord_count))
    if n <= 0:
        return []
    if n == 1:
        return [text]
    if not text:
        return [""] * n
    words = text.split()
    if len(words) <= n:
        parts = list(words) + [""] * (n - len(words))
        return parts[:n]
    base, extra = divmod(len(words), n)
    out: list[str] = []
    idx = 0
    for i in range(n):
        take = base + (1 if i < extra else 0)
        out.append(" ".join(words[idx : idx + take]))
        idx += take
    return out


def normalize_section_lines(section: LyricSection) -> list[LyricLine]:
    """Expand progression_block / legacy parallel arrays into explicit lines."""
    if section.get("lines"):
        return [dict(line) for line in section["lines"]]

    block = section.get("progression_block")
    if block:
        lyrics = [str(x).strip() for x in (section.get("lyrics") or [])]
        repeat = max(1, int(section.get("progression_repeat") or 1))
        lines: list[LyricLine] = []
        for r in range(repeat):
            for bi, row in enumerate(block):
                li = r * len(block) + bi
                text = lyrics[li] if li < len(lyrics) else ""
                lines.append(
                    {
                        "chords": list(row.get("chords") or []),
                        "lyrics": text,
                    }
                )
        return lines

    chords_raw = section.get("chords")
    lyrics_raw = section.get("lyrics")
    if chords_raw and lyrics_raw and isinstance(chords_raw[0], list):
        lines = []
        for cr, lr in zip(chords_raw, lyrics_raw):
            lines.append({"chords": list(cr), "lyrics": str(lr)})
        return lines

    return []


def flatten_section_chords(section: LyricSection) -> list[str]:
    """One bar per chord symbol for backing-track section maps."""
    out: list[str] = []
    for line in normalize_section_lines(section):
        for ch in line.get("chords") or []:
            c = str(ch).strip()
            if c:
                out.append(c)
    return out


def sections_from_lyric_chart(chart: list[LyricSection]) -> dict[str, list[str]]:
    return {str(s["section"]): flatten_section_chords(s) for s in chart if s.get("section")}


def _transpose_chart(chart: list[LyricSection], from_key: str, to_key: str) -> list[LyricSection]:
    if not transpose_chord or not semitone_distance or from_key == to_key:
        return chart
    steps = semitone_distance(from_key, to_key)
    if steps == 0:
        return chart

    def _tx_line(line: LyricLine) -> LyricLine:
        chords = [transpose_chord(str(c), steps) for c in (line.get("chords") or [])]
        return {**line, "chords": chords}

    def _tx_section(sec: LyricSection) -> LyricSection:
        out = dict(sec)
        if sec.get("lines"):
            out["lines"] = [_tx_line(ln) for ln in sec["lines"]]
        if sec.get("progression_block"):
            out["progression_block"] = [
                {"chords": [transpose_chord(str(c), steps) for c in (row.get("chords") or [])]}
                for row in sec["progression_block"]
            ]
        return out

    return [_tx_section(s) for s in chart]


def _section_role(name: str) -> str:
    low = name.lower()
    if "bridge" in low:
        return "bridge"
    if "chorus" in low or "hook" in low:
        return "chorus"
    if "verse" in low:
        return "verse"
    if "intro" in low:
        return "intro"
    if "outro" in low or "final" in low:
        return "outro"
    return "neutral"


def _line_html(line: LyricLine) -> str:
    chords = [str(c).strip() for c in (line.get("chords") or []) if str(c).strip()]
    lyrics = str(line.get("lyrics") or "").strip()
    if not chords:
        return ""
    segments = split_lyrics_for_chords(lyrics, len(chords))
    parts = []
    for chord, text in zip(chords, segments):
        lyric_bit = (
            f'<span class="ug-lyric">{html.escape(text)}</span>'
            if text
            else '<span class="ug-lyric ug-lyric-empty">&nbsp;</span>'
        )
        parts.append(
            f'<span class="ug-segment">'
            f'<span class="ug-chord-pill">{html.escape(chord)}</span>'
            f"{lyric_bit}</span>"
        )
    chord_only = not lyrics
    cls = "ug-line ug-line-chords-only" if chord_only else "ug-line"
    return f'<div class="{cls}"><div class="ug-segments">{"".join(parts)}</div></div>'


def lyric_chord_sheet_css() -> str:
    return """
<style>
.ug-sheet {
  font-family: system-ui, -apple-system, Segoe UI, sans-serif;
  max-width: 100%;
  line-height: 1.45;
}
.ug-sheet .lead-header {
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 14px;
  padding: 12px 14px;
  margin-bottom: 10px;
  background: linear-gradient(180deg, #ffffff, #f8fafc);
}
.ug-sheet .lead-title { font-size: 1.2rem; font-weight: 800; margin-bottom: 4px; }
.ug-sheet .lead-subtitle { color: #475569; margin-bottom: 8px; font-size: 0.9rem; }
.ug-sheet .meta-row { display: flex; gap: 6px; flex-wrap: wrap; }
.ug-sheet .meta-pill {
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 999px;
  padding: 4px 9px;
  background: #fff;
  font-size: 0.8rem;
  color: #334155;
}
.ug-sheet .now-playing {
  border-left: 4px solid #22c55e;
  background: #f0fdf4;
  padding: 8px 10px;
  border-radius: 10px;
  margin: 0 0 10px 0;
  font-weight: 700;
  font-size: 0.9rem;
}
.ug-section {
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 12px;
  padding: 10px 12px 8px 12px;
  margin-bottom: 10px;
  background: #fff;
}
.ug-section.verse { border-left: 5px solid #60a5fa; background: #f8fbff; }
.ug-section.chorus { border-left: 5px solid #22c55e; background: #f6fdf8; }
.ug-section.bridge { border-left: 5px solid #a78bfa; background: #faf8ff; }
.ug-section.intro, .ug-section.outro { border-left: 5px solid #94a3b8; }
.ug-section.current {
  outline: 2px solid rgba(34, 197, 94, 0.35);
  box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.08);
}
.ug-section-label {
  margin: 0 0 6px 0;
  font-size: 1.05rem;
  font-weight: 800;
  letter-spacing: 0.02em;
  color: #0f172a;
  text-transform: none;
}
.ug-line {
  margin: 0 0 6px 0;
  padding: 0;
}
.ug-line-chords-only { margin-bottom: 4px; }
.ug-segments {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0 0.15rem;
  row-gap: 2px;
}
.ug-segment {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  margin-right: 0.55rem;
  margin-bottom: 2px;
  min-width: 1.6rem;
}
.ug-chord-pill {
  display: inline-block;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.72rem;
  font-weight: 800;
  color: #14532d;
  background: linear-gradient(180deg, #dcfce7, #bbf7d0);
  border: 1px solid rgba(22, 163, 74, 0.28);
  border-radius: 999px;
  padding: 2px 9px;
  margin-bottom: 1px;
  white-space: nowrap;
  line-height: 1.25;
}
.ug-lyric {
  font-size: 0.98rem;
  color: #1e293b;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.35;
}
.ug-lyric-empty { opacity: 0; font-size: 0.72rem; }
.ug-progression-hint {
  font-size: 0.78rem;
  color: #64748b;
  margin: 0 0 6px 0;
}
@media (max-width: 760px) {
  .ug-segment { margin-right: 0.4rem; }
  .ug-chord-pill { font-size: 0.68rem; padding: 2px 7px; }
  .ug-lyric { font-size: 0.92rem; }
}
</style>
"""


def render_lyric_chord_section(
    section: LyricSection,
    *,
    is_current: bool = False,
) -> str:
    name = str(section.get("section") or "Section")
    role = _section_role(name)
    lines = normalize_section_lines(section)
    if not lines:
        return ""
    body = "".join(_line_html(ln) for ln in lines if ln.get("chords"))
    cur = " current" if is_current else ""
    return (
        f'<section class="ug-section {role}{cur}">'
        f'<h3 class="ug-section-label">{html.escape(name)}</h3>'
        f"{body}</section>"
    )


def render_lyric_chord_sheet(
    chart: list[LyricSection],
    *,
    song_name: str = "",
    artist: str = "",
    original_key: str = "C",
    display_key: str | None = None,
    current_section: str | None = None,
    meta_bits: list[str] | None = None,
    header_note: str = "",
    now_playing: str = "",
    show_full: bool = True,
) -> str:
    dk = display_key or original_key
    tx_chart = _transpose_chart(chart, original_key, dk)
    show_full = show_full or not current_section
    current_parts = set() if show_full else {str(current_section).strip()}

    meta_html = ""
    if meta_bits:
        meta_html = '<div class="meta-row">' + "".join(
            f'<span class="meta-pill">{html.escape(b)}</span>' for b in meta_bits
        ) + "</div>"

    key_line = f"Key: {html.escape(dk)}"
    if dk != original_key:
        key_line += f" (orig. {html.escape(original_key)})"

    sections_html = []
    for sec in tx_chart:
        name = str(sec.get("section") or "")
        if not show_full and name not in current_parts:
            continue
        sections_html.append(
            render_lyric_chord_section(sec, is_current=name in current_parts)
        )

    note = f'<div class="lead-subtitle">{html.escape(header_note)}</div>' if header_note else ""
    np = (
        f'<div class="now-playing">Now Playing: {html.escape(now_playing)}</div>'
        if now_playing
        else ""
    )

    return f"""
{lyric_chord_sheet_css()}
<div class="lead-sheet ug-lyric-sheet">
  <div class="lead-header">
    <div class="lead-title">{html.escape(song_name)} — Lyric &amp; Chord Chart</div>
    <div class="lead-subtitle">{html.escape(artist)}</div>
    {note}
    <div class="meta-row"><span class="meta-pill">{key_line}</span>{meta_html}</div>
  </div>
  {np}
  {''.join(sections_html)}
</div>
"""
