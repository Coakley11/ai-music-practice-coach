"""Shared Composition playback timeline + synchronized score highlighting.

One model for Preview/Play across Chords, Melody, combined, and Review:

- Melody events → timed note spans (beat → seconds via current BPM)
- Chord entries → timed chord spans (bar-aligned, shared with sync_transport)
- Combined playback: melody note is the moving cursor; chords shown as static context
- Chord-only: chord chip highlight
- Melody-only / combined: abcjs note highlight via event→DOM index mapping

Rests never become active melody highlights.
"""

from __future__ import annotations

import base64
import html
import json
from typing import Any, Literal

from composition_sync_transport import build_chord_span_timeline, count_in_seconds

HighlightMode = Literal["melody", "chords", "combined", "none"]


def beat_seconds(*, bpm: int) -> float:
    return 60.0 / max(40.0, float(bpm or 96))


def ensure_event_render_ids(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Assign stable ``render_id`` / ``event_index`` for notation↔playback mapping."""
    out: list[dict[str, Any]] = []
    for i, raw in enumerate(list(events or [])):
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        row["event_index"] = i
        if not str(row.get("render_id") or "").strip():
            pass_i = row.get("pass_index")
            if pass_i is None:
                pass_i = row.get("repeat_index")
            rid = f"ev{i}"
            if pass_i is not None:
                rid = f"p{int(pass_i)}_ev{i}"
            row["render_id"] = rid
        out.append(row)
    return out


def build_melody_note_timeline(
    events: list[dict[str, Any]] | None,
    *,
    bpm: int,
    meter: str = "4/4",
    count_in_bars: int = 0,
) -> list[dict[str, Any]]:
    """Timed spans for every melody event (rests included but not highlightable)."""
    del meter  # reserved for future compound-pulse alignment
    evs = ensure_event_render_ids(events)
    if not evs:
        return []
    cin = count_in_seconds(bpm=bpm, meter="4/4", bars=count_in_bars)
    beat_unit = beat_seconds(bpm=bpm)
    spans: list[dict[str, Any]] = []
    cursor_beat = 0.0
    sounding_dom = 0
    for i, ev in enumerate(evs):
        is_rest = bool(ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest")
        try:
            start_beat = float(ev.get("beat")) if ev.get("beat") is not None else cursor_beat
        except (TypeError, ValueError):
            start_beat = cursor_beat
        dur = max(0.05, float(ev.get("duration_beats") or 1.0))
        start_sec = cin + start_beat * beat_unit
        end_sec = start_sec + dur * beat_unit
        dom_idx = None if is_rest else sounding_dom
        if not is_rest:
            sounding_dom += 1
        spans.append(
            {
                "kind": "melody",
                "index": i,
                "event_index": int(ev.get("event_index") if ev.get("event_index") is not None else i),
                "render_id": str(ev.get("render_id") or f"ev{i}"),
                "pitch": str(ev.get("pitch") or ("rest" if is_rest else "?")),
                "is_rest": is_rest,
                "start_sec": float(start_sec),
                "end_sec": float(end_sec),
                "start_beat": float(start_beat),
                "duration_beats": float(dur),
                "dom_note_index": dom_idx,
                "pass_index": ev.get("pass_index", ev.get("repeat_index")),
                "highlightable": not is_rest,
            }
        )
        cursor_beat = max(cursor_beat, start_beat + dur)
    return spans


def build_chord_playback_timeline(
    chord_syms: list[str] | None,
    *,
    bpm: int,
    meter: str = "4/4",
    loops: int = 1,
    count_in_bars: int = 0,
) -> list[dict[str, Any]]:
    """Chord spans — wraps the existing bar-aligned chord timeline."""
    spans = build_chord_span_timeline(
        list(chord_syms or []),
        bpm=bpm,
        meter=meter,
        loops=loops,
        count_in_bars=count_in_bars,
    )
    out: list[dict[str, Any]] = []
    for i, s in enumerate(spans):
        row = dict(s)
        row["kind"] = "chord"
        row["index"] = i
        row["highlightable"] = True
        out.append(row)
    return out


def resolve_highlight_mode(*, has_melody: bool, has_chords: bool) -> HighlightMode:
    if has_melody and has_chords:
        return "combined"
    if has_melody:
        return "melody"
    if has_chords:
        return "chords"
    return "none"


def active_index_at(spans: list[dict[str, Any]], t_sec: float) -> int:
    """Return highlightable span index at time t, or -1."""
    t = float(t_sec)
    found = -1
    for i, s in enumerate(spans):
        if not s.get("highlightable", True):
            continue
        if float(s.get("start_sec") or 0) <= t < float(s.get("end_sec") or 0):
            return i
        if t >= float(s.get("end_sec") or 0):
            found = i
    if spans and t >= float(spans[-1].get("end_sec") or 0):
        for j in range(len(spans) - 1, -1, -1):
            if spans[j].get("highlightable", True):
                return j
    return found if found >= 0 and spans[found].get("highlightable", True) else -1


def build_playback_bundle(
    *,
    events: list[dict[str, Any]] | None = None,
    chord_syms: list[str] | None = None,
    bpm: int,
    meter: str = "4/4",
    loops: int = 1,
    count_in_bars: int = 0,
) -> dict[str, Any]:
    """Canonical timeline bundle for any Preview/Play surface."""
    mel = build_melody_note_timeline(
        events, bpm=bpm, meter=meter, count_in_bars=count_in_bars
    )
    ch = build_chord_playback_timeline(
        chord_syms, bpm=bpm, meter=meter, loops=loops, count_in_bars=count_in_bars
    )
    mode = resolve_highlight_mode(has_melody=bool(mel), has_chords=bool(ch))
    cursor_spans = mel if mode in {"melody", "combined"} else ch
    return {
        "mode": mode,
        "bpm": int(bpm),
        "meter": str(meter or "4/4"),
        "melody_spans": mel,
        "chord_spans": ch,
        "cursor_spans": cursor_spans,
        "primary": "melody"
        if mode in {"melody", "combined"}
        else ("chords" if mode == "chords" else "none"),
    }


def render_synced_score_playback_html(
    *,
    wav_bytes: bytes,
    abc_text: str = "",
    chord_labels: list[str] | None = None,
    bundle: dict[str, Any],
    caption: str = "",
    dom_id: str = "cplay",
    height: int = 220,
) -> str:
    """Self-contained HTML: audio + optional staff + chord strip + synced highlight."""
    if not wav_bytes:
        return ""
    mode = str(bundle.get("mode") or "none")
    melody_spans = list(bundle.get("melody_spans") or [])
    chord_spans = list(bundle.get("chord_spans") or [])
    cursor_spans = list(bundle.get("cursor_spans") or [])
    labels = list(chord_labels or [])
    if not labels and chord_spans:
        seen_loop0 = [s for s in chord_spans if int(s.get("loop") or 0) == 0]
        labels = [str(s.get("chord") or "") for s in (seen_loop0 or chord_spans)]

    safe_id = "".join(
        ch if ch.isalnum() or ch in "-_" else "_" for ch in str(dom_id or "cplay")
    )[:48]
    b64 = base64.b64encode(wav_bytes).decode("ascii")
    escaped_abc = (
        str(abc_text or "")
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("${", "\\${")
    )
    spans_json = json.dumps(cursor_spans)
    chord_spans_json = json.dumps(chord_spans)
    primary = str(bundle.get("primary") or "none")

    chord_strip = ""
    if labels and mode in {"combined", "melody", "chords"}:
        cells = "".join(
            f'<div class="cplay-chord" data-ci="{i}">{html.escape(lab)}</div>'
            for i, lab in enumerate(labels)
        )
        chord_strip = f'<div class="cplay-chords" id="{safe_id}-chords">{cells}</div>'

    staff_block = ""
    if abc_text and mode in {"melody", "combined"}:
        staff_block = f'<div id="{safe_id}-paper" class="cplay-paper"></div>'
    elif mode == "chords":
        chips = "".join(
            f'<button type="button" class="cplay-chord-chip" data-i="{i}" disabled>'
            f"{html.escape(str(s.get('chord') or ''))}</button>"
            for i, s in enumerate(chord_spans)
        )
        staff_block = f'<div class="cplay-chord-chips" id="{safe_id}-chips">{chips}</div>'

    cap = caption or (
        "Follow the highlighted note"
        if primary == "melody"
        else ("Follow the highlighted chord" if primary == "chords" else "Playback")
    )

    abc_script = ""
    if abc_text and mode in {"melody", "combined"}:
        abc_script = f"""
    ABCJS.renderAbc("{safe_id}-paper", `{escaped_abc}`, {{
      responsive: "resize",
      staffwidth: 560,
      paddingbottom: 8,
      add_classes: true
    }});
"""

    return f"""
<html>
<head>
<meta charset="utf-8"/>
<style>
  body {{ margin: 0; padding: 8px 4px 12px; background: #fff; font-family: system-ui, sans-serif; }}
  .cplay-caption {{ margin: 0 0 8px; color: #475569; font-size: 0.9rem; }}
  .cplay-chords {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(3.2rem, 1fr));
    gap: 4px; margin: 0 0 6px; text-align: center;
  }}
  .cplay-chord {{
    font-weight: 700; font-size: 0.95rem; color: #0f172a; padding: 2px 4px;
    border-radius: 6px; border: 1px solid transparent;
  }}
  .cplay-chord.is-soft {{
    background: #e0f2fe; border-color: #7dd3fc; color: #0c4a6e;
  }}
  .cplay-paper {{ min-height: {int(height * 0.55)}px; }}
  .cplay-paper svg .abcjs-note.cplay-active,
  .cplay-paper svg .abcjs-note.cplay-active * {{
    fill: #0284c7 !important; stroke: #0284c7 !important;
  }}
  .cplay-chord-chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }}
  .cplay-chord-chip {{
    border: 1px solid #cbd5e1; background: #f8fafc; color: #0f172a;
    border-radius: 8px; padding: 6px 10px; font-weight: 700; font-size: 0.95rem;
  }}
  .cplay-chord-chip.is-active {{
    background: #0ea5e9; color: #fff; border-color: #0284c7;
    box-shadow: 0 0 0 2px rgba(14,165,233,0.35);
  }}
  .cplay-audio {{ width: 100%; margin-top: 8px; }}
</style>
<script src="https://cdn.jsdelivr.net/npm/abcjs@6.4.4/dist/abcjs-basic-min.js"></script>
</head>
<body>
<div class="cplay-wrap" data-cplay-root="{html.escape(safe_id)}" data-mode="{html.escape(mode)}">
  <p class="cplay-caption">{html.escape(cap)}</p>
  {chord_strip}
  {staff_block}
  <audio id="{safe_id}-audio" class="cplay-audio" controls preload="auto" autoplay>
    <source src="data:audio/wav;base64,{b64}" type="audio/wav"/>
  </audio>
</div>
<script>
(function() {{
  const root = document.querySelector('[data-cplay-root="{safe_id}"]');
  if (!root) return;
  const mode = root.getAttribute("data-mode") || "none";
  const cursorSpans = {spans_json};
  const chordSpans = {chord_spans_json};
  const audio = document.getElementById("{safe_id}-audio");
  {abc_script}
  let last = -1;
  let lastChord = -1;

  function melodyNotes() {{
    return Array.from(root.querySelectorAll("#{safe_id}-paper .abcjs-note"));
  }}
  function chordChips() {{
    return Array.from(root.querySelectorAll("#{safe_id}-chips .cplay-chord-chip"));
  }}
  function chordContext() {{
    return Array.from(root.querySelectorAll("#{safe_id}-chords .cplay-chord"));
  }}

  function clearMelody() {{
    melodyNotes().forEach(n => n.classList.remove("cplay-active"));
  }}
  function setMelodyDom(domIdx) {{
    const notes = melodyNotes();
    notes.forEach((n, i) => n.classList.toggle("cplay-active", i === domIdx));
  }}
  function setChordChip(i) {{
    chordChips().forEach((b, idx) => b.classList.toggle("is-active", idx === i));
  }}
  function softChordAt(t) {{
    // Soft context only — never a competing cursor. Index = sounding chord span.
    let found = -1;
    for (let i = 0; i < chordSpans.length; i++) {{
      const s = chordSpans[i];
      if (t >= s.start_sec && t < s.end_sec) {{ found = i; break; }}
    }}
    if (found === lastChord) return;
    lastChord = found;
    const labels = chordContext();
    if (!labels.length) return;
    const li = found >= 0 ? (found % labels.length) : -1;
    labels.forEach((el, i) => el.classList.toggle("is-soft", found >= 0 && i === li));
  }}

  function tick() {{
    if (!audio) return;
    const t = audio.currentTime || 0;
    if (audio.paused && t <= 0.02) {{
      last = -1;
      clearMelody();
      setChordChip(-1);
      chordContext().forEach(el => el.classList.remove("is-soft"));
      return;
    }}
    if (mode === "chords") {{
      let found = -1;
      for (let i = 0; i < cursorSpans.length; i++) {{
        const s = cursorSpans[i];
        if (t >= s.start_sec && t < s.end_sec) {{ found = i; break; }}
      }}
      if (found < 0 && cursorSpans.length && t >= cursorSpans[cursorSpans.length - 1].end_sec) {{
        found = cursorSpans.length - 1;
      }}
      if (found !== last) {{
        last = found;
        setChordChip(found);
      }}
      return;
    }}
    let found = -1;
    for (let i = 0; i < cursorSpans.length; i++) {{
      const s = cursorSpans[i];
      if (!s.highlightable) continue;
      if (t >= s.start_sec && t < s.end_sec) {{ found = i; break; }}
    }}
    if (found !== last) {{
      last = found;
      clearMelody();
      if (found >= 0) {{
        const domIdx = cursorSpans[found].dom_note_index;
        if (domIdx != null) setMelodyDom(domIdx);
      }}
    }}
    if (mode === "combined") softChordAt(t);
  }}
  if (audio) {{
    audio.addEventListener("timeupdate", tick);
    audio.addEventListener("play", tick);
    audio.addEventListener("seeked", tick);
    audio.addEventListener("pause", tick);
    audio.addEventListener("ended", () => {{ clearMelody(); setChordChip(-1); }});
    setInterval(tick, 80);
  }}
}})();
</script>
</body>
</html>
"""


def mount_synced_score_playback(
    st_module: Any,
    *,
    wav_bytes: bytes,
    abc_text: str = "",
    chord_labels: list[str] | None = None,
    bundle: dict[str, Any],
    caption: str = "",
    dom_id: str = "cplay",
    height: int = 280,
) -> None:
    """Streamlit components.html mount for synced score playback."""
    html_doc = render_synced_score_playback_html(
        wav_bytes=wav_bytes,
        abc_text=abc_text,
        chord_labels=chord_labels,
        bundle=bundle,
        caption=caption,
        dom_id=dom_id,
        height=height,
    )
    if not html_doc:
        return
    try:
        import streamlit.components.v1 as components

        components.html(html_doc, height=height + 120, scrolling=False)
    except Exception:
        st_module.audio(wav_bytes, format="audio/wav")
