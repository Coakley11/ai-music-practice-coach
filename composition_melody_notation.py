"""Composition melody events → ABC / staff (reuse music_theory + abcjs path).

Musician-facing section score: chord symbols sit directly above the staff at
their canonical onset/span, then lyrics. Derived from timed chord + melody
events — no separate display state.
"""

from __future__ import annotations

import html
import json
from typing import Any

from music_theory import (
    abc_key_signature_for_reference,
    abc_pitch_for_spelled_note,
    key_is_minor,
    split_key_center,
)


def _duration_to_abc_length(duration_beats: float, *, meter: str = "4/4") -> str:
    """Map beat durations to ABC lengths with L:1/8 base."""
    from composition_hum_transcription import is_compound_meter

    beats = max(0.5, float(duration_beats or 1.0))
    if is_compound_meter(meter):
        # Composition pulse tracks eighths in compound meters (bar length = numerator).
        eighths = int(round(beats))
    else:
        # Pulse ≈ quarter → two eighths per beat.
        eighths = int(round(beats * 2))
    eighths = max(1, eighths)
    return str(eighths) if eighths != 1 else ""


def _pitch_token_to_abc(pitch: str, *, key: str) -> str:
    text = str(pitch or "").strip()
    if not text or text.lower() == "rest":
        return "z"
    # Split trailing octave digits.
    i = len(text) - 1
    while i >= 0 and text[i].isdigit():
        i -= 1
    name = text[: i + 1] or "C"
    try:
        octave = int(text[i + 1 :]) if i + 1 < len(text) else 4
    except ValueError:
        octave = 4
    k_field = composition_abc_key_field(key)
    try:
        return abc_pitch_for_spelled_note(name, octave=octave, k_field=k_field)
    except Exception:
        # Fallback: letter + accidental ASCII.
        from improvisation_motif import _note_name_to_abc_pitch

        return _note_name_to_abc_pitch(name, octave=octave)


def composition_abc_key_field(key: str) -> str:
    tonic, mode = split_key_center(key)
    scale = "minor" if (mode == "minor" or key_is_minor(key)) else "major"
    return abc_key_signature_for_reference(tonic if scale == "major" else key, scale_type=scale)


def beats_per_bar(meter: str) -> float:
    from composition_hum_transcription import parse_meter

    num, _den = parse_meter(meter)
    return float(num)


def chord_span_bars(chords: list[Any] | None) -> int:
    """Declared harmonic length in bars (sum of entry bars, else one per symbol)."""
    total = 0
    for entry in list(chords or []):
        if isinstance(entry, dict):
            if not str(entry.get("chord") or "").strip():
                continue
            try:
                total += max(1, int(entry.get("bars") or 1))
            except (TypeError, ValueError):
                total += 1
        elif str(entry).strip():
            total += 1
    return total


def progression_timing_labels(chords: list[Any] | None) -> list[str]:
    """Ordered chord + duration labels for the full section progression."""
    labels: list[str] = []
    for entry in list(chords or []):
        if isinstance(entry, dict):
            chord = str(entry.get("chord") or "").strip()
            if not chord:
                continue
            try:
                bars = max(1, int(entry.get("bars") or 1))
            except (TypeError, ValueError):
                bars = 1
            unit = "bar" if bars == 1 else "bars"
            labels.append(f"{chord} ({bars} {unit})")
        else:
            chord = str(entry).strip()
            if chord:
                labels.append(f"{chord} (1 bar)")
    return labels


def chord_symbols_by_measure(
    chords: list[Any],
    *,
    meter: str = "4/4",
    measures: int | None = None,
) -> list[str]:
    """Deterministic measure-level chord labels for staff alignment.

    Never drops chords from the selected section. Measure count is at least
    the expanded progression length; shorter melody fragments do not clip it.
    Missing measures reuse the last chord.
    """
    from custom_progression_lab import expand_entries_to_chords

    if chords and isinstance(chords[0], dict):
        symbols = expand_entries_to_chords(list(chords))
    else:
        symbols = [str(c).strip() for c in (chords or []) if str(c).strip()]
    if not symbols:
        return []
    declared = int(measures) if measures and measures > 0 else 0
    n = max(declared, len(symbols), chord_span_bars(chords))
    if len(symbols) >= n:
        return list(symbols)
    return [symbols[i % len(symbols)] for i in range(n)]


def _entry_chord_symbol(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("chord") or "").strip()
    return str(entry or "").strip()


def _entry_duration_beats(entry: Any, *, bar: float) -> float:
    if isinstance(entry, dict):
        raw_beats = entry.get("duration_beats")
        if raw_beats is not None:
            try:
                dur = float(raw_beats)
                if dur > 0:
                    return dur
            except (TypeError, ValueError):
                pass
        try:
            bars = max(1, int(entry.get("bars") or 1))
        except (TypeError, ValueError):
            bars = 1
        return float(bars) * bar
    return float(bar)


def timed_chord_spans(
    chords: list[Any] | None,
    *,
    meter: str = "4/4",
    section_bars: int | None = None,
) -> list[dict[str, Any]]:
    """Canonical onset/span list. Repeated chords stay separate spans."""
    bar = max(1.0, beats_per_bar(meter))
    entries = [e for e in list(chords or []) if _entry_chord_symbol(e)]
    spans: list[dict[str, Any]] = []
    cursor = 0.0
    for entry in entries:
        symbol = _entry_chord_symbol(entry)
        dur = _entry_duration_beats(entry, bar=bar)
        start = None
        if isinstance(entry, dict):
            raw_start = entry.get("start_beat")
            if raw_start is None:
                raw_start = entry.get("beat")
            if raw_start is not None:
                try:
                    start = float(raw_start)
                except (TypeError, ValueError):
                    start = None
        if start is None:
            start = cursor
        end = start + dur
        spans.append(
            {
                "chord": symbol,
                "start_beat": start,
                "duration_beats": dur,
                "end_beat": end,
            }
        )
        cursor = end
    try:
        declared = int(section_bars or 0)
    except (TypeError, ValueError):
        declared = 0
    target = max(cursor, declared * bar) if declared > 0 else cursor
    if entries and target > cursor + 1e-9:
        i = 0
        while cursor < target - 1e-9:
            entry = entries[i % len(entries)]
            symbol = _entry_chord_symbol(entry)
            dur = min(_entry_duration_beats(entry, bar=bar), target - cursor)
            if dur <= 1e-9:
                break
            spans.append(
                {
                    "chord": symbol,
                    "start_beat": cursor,
                    "duration_beats": dur,
                    "end_beat": cursor + dur,
                }
            )
            cursor += dur
            i += 1
    return spans


def span_at_beat(spans: list[dict[str, Any]] | None, beat: float) -> dict[str, Any] | None:
    if not spans:
        return None
    b = float(beat)
    for span in spans:
        start = float(span.get("start_beat") or 0.0)
        end = float(span.get("end_beat") or (start + float(span.get("duration_beats") or 0.0)))
        if start - 1e-9 <= b < end - 1e-9:
            return span
    last = spans[-1]
    if b >= float(last.get("start_beat") or 0.0) - 1e-9:
        return last
    return None


def align_notes_to_chords(
    events: list[dict[str, Any]] | None,
    chords: list[Any] | None,
    *,
    meter: str = "4/4",
    section_bars: int | None = None,
) -> list[dict[str, Any]]:
    """Map each melody event (notes and rests) onto the sounding chord span."""
    if chords and isinstance(chords[0], dict) and "start_beat" in chords[0] and "duration_beats" in chords[0]:
        spans = list(chords)
    else:
        spans = timed_chord_spans(chords, meter=meter, section_bars=section_bars)
    rows: list[dict[str, Any]] = []
    cursor = 0.0
    for ev in list(events or []):
        if not isinstance(ev, dict):
            continue
        onset = float(ev["beat"]) if ev.get("beat") is not None else cursor
        dur = float(ev.get("duration_beats") or 1.0)
        is_rest = bool(ev.get("is_rest")) or str(ev.get("pitch") or "").lower() == "rest"
        span = span_at_beat(spans, onset)
        chord = str((span or {}).get("chord") or ev.get("chord") or "").strip()
        rows.append(
            {
                "beat": onset,
                "duration_beats": dur,
                "pitch": "rest" if is_rest else str(ev.get("pitch") or ""),
                "is_rest": is_rest,
                "chord": chord,
                "span_start": None if span is None else float(span.get("start_beat") or 0.0),
            }
        )
        cursor = onset + dur
    return rows


def pad_events_to_chord_spans(
    events: list[dict[str, Any]] | None,
    spans: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Rest-fill through the last chord span so every change is visible on the staff."""
    evs = [dict(e) for e in list(events or []) if isinstance(e, dict)]
    if not spans:
        return evs
    covered = 0.0
    if evs:
        covered = max(
            float(e.get("beat") or 0.0) + float(e.get("duration_beats") or 0.0) for e in evs
        )
    for span in spans:
        span_end = float(span.get("end_beat") or 0.0)
        if covered >= span_end - 1e-6:
            continue
        start = max(covered, float(span.get("start_beat") or 0.0))
        if span_end > start + 1e-6:
            evs.append(
                {
                    "pitch": "rest",
                    "is_rest": True,
                    "beat": start,
                    "duration_beats": span_end - start,
                    "chord": str(span.get("chord") or ""),
                }
            )
            covered = span_end
    evs.sort(key=lambda e: float(e.get("beat") or 0.0))
    return evs


def _abc_chord_token(symbol: str) -> str:
    text = str(symbol or "").replace('"', "").strip()
    return text


def melody_measure_count(events: list[dict[str, Any]], *, meter: str = "4/4") -> int:
    bar = max(1.0, beats_per_bar(meter))
    total = 0.0
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        total += float(ev.get("duration_beats") or 1.0)
    if total <= 0:
        return 1
    return max(1, int((total + bar - 1e-9) // bar))


def _abc_lyric_line(events: list[dict[str, Any]], syllables: list[str] | None) -> str:
    """One ABC ``w:`` token per event. Extra notes in a syllable use ``-`` / ``*``."""
    if not syllables:
        return ""
    tokens: list[str] = []
    syl_i = 0
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        if ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest":
            tokens.append("*")
            continue
        if syl_i < len(syllables):
            tokens.append(str(syllables[syl_i] or "_"))
            syl_i += 1
        else:
            tokens.append("-")
    return "w: " + " ".join(tokens) if tokens else ""


def build_abc_from_melody_events(
    events: list[dict[str, Any]],
    *,
    key: str = "C",
    meter: str = "4/4",
    bpm: int = 96,
    title: str = "Melody",
    lyric_syllables: list[str] | None = None,
    chords: list[Any] | None = None,
    section_bars: int | None = None,
) -> str:
    """Build ABC from Composition melody events (notes + rests).

    When ``chords`` are supplied, abcjs chord annotations (``"C"``) are placed
    at each span onset so symbols sit on the staff over the sounding notes.
    """
    from composition_hum_transcription import is_compound_meter, parse_meter

    k_field = composition_abc_key_field(key)
    num, den = parse_meter(meter)
    meter_field = f"{num}/{den}"
    tokens: list[str] = []
    beats_in_bar = 0.0
    bar_len = float(num)
    spans = timed_chord_spans(chords, meter=meter, section_bars=section_bars) if chords else []
    last_span_start: float | None = None
    last_measure_announced: int | None = None
    cursor = 0.0
    evs = [e for e in list(events or []) if isinstance(e, dict)]
    evs.sort(key=lambda e: float(e.get("beat") or 0.0))

    for ev in evs:
        dur = float(ev.get("duration_beats") or 1.0)
        onset = float(ev["beat"]) if ev.get("beat") is not None else cursor
        length = _duration_to_abc_length(dur, meter=meter)
        if ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest":
            token = f"z{length}"
        else:
            pitch = _pitch_token_to_abc(str(ev.get("pitch") or "C4"), key=key)
            token = f"{pitch}{length}"
        span = span_at_beat(spans, onset)
        measure_i = int(onset // bar_len + 1e-9)
        symbol = _abc_chord_token(str((span or {}).get("chord") or ""))
        span_start = None if span is None else float(span.get("start_beat") or 0.0)
        announce = False
        if symbol and last_measure_announced != measure_i:
            announce = True
            last_measure_announced = measure_i
            last_span_start = span_start
        elif symbol and span_start is not None and last_span_start != span_start:
            announce = True
            last_span_start = span_start
        if announce:
            token = f'"{symbol}"{token}'
        tokens.append(token)
        beats_in_bar += dur
        cursor = onset + dur
        if beats_in_bar >= bar_len - 1e-6:
            tokens.append("|")
            beats_in_bar = 0.0

    if beats_in_bar > 0 and tokens and tokens[-1] != "|":
        tokens.append("|")
    music = " ".join(tokens) if tokens else "z4 |"
    q_unit = "3/8" if is_compound_meter(meter) else "1/4"
    lyric_line = _abc_lyric_line(evs, lyric_syllables)
    body = f"{music}\n{lyric_line}" if lyric_line else music
    return f"""X:1
T:{title}
M:{meter_field}
L:1/8
Q:{q_unit}={int(bpm)}
K:{k_field}
{body}"""


def measure_aligned_chord_html(
    spans: list[dict[str, Any]] | None,
    *,
    meter: str = "4/4",
    measures: int | None = None,
) -> str:
    """One cell per measure so each chord sits over the bar it governs."""
    bar = max(1.0, beats_per_bar(meter))
    try:
        n = int(measures or 0)
    except (TypeError, ValueError):
        n = 0
    if spans:
        last_end = max(float(s.get("end_beat") or 0.0) for s in spans)
        n = max(n, int((last_end + bar - 1e-9) // bar))
    if n <= 0:
        return ""
    cells: list[str] = []
    for i in range(n):
        start = float(i) * bar
        end = start + bar
        names: list[str] = []
        for span in spans or []:
            s0 = float(span.get("start_beat") or 0.0)
            s1 = float(span.get("end_beat") or (s0 + float(span.get("duration_beats") or 0.0)))
            if s0 < end - 1e-9 and s1 > start + 1e-9:
                name = str(span.get("chord") or "").strip()
                if name and (not names or names[-1] != name):
                    names.append(name)
        label = " ".join(names)
        cells.append(
            f'<div class="composer-score-chord" data-measure="{i + 1}" '
            f'data-onset="{start:g}">{html.escape(label)}</div>'
        )
    return f'<div class="composer-score-measures">{"".join(cells)}</div>'


def timed_chord_strip_html(spans: list[dict[str, Any]] | None) -> str:
    """Proportional chord row: flex width = duration_beats."""
    if not spans:
        return ""
    cells: list[str] = []
    for span in spans:
        symbol = str(span.get("chord") or "").strip()
        if not symbol:
            continue
        dur = max(0.25, float(span.get("duration_beats") or 1.0))
        onset = float(span.get("start_beat") or 0.0)
        cells.append(
            f'<div class="composer-score-chord" data-onset="{onset:g}" '
            f'data-duration="{dur:g}" style="flex:{dur:g} 1 0">'
            f"{html.escape(symbol)}</div>"
        )
    if not cells:
        return ""
    return f'<div class="composer-score-chords composer-score-chords-timed">{"".join(cells)}</div>'


def build_chord_strip_html(
    chords: list[Any],
    *,
    meter: str = "4/4",
    measures: int | None = None,
) -> str:
    """HTML row of chord symbols aligned to timed spans above the staff."""
    spans = timed_chord_spans(chords, meter=meter, section_bars=measures)
    return measure_aligned_chord_html(spans, meter=meter, measures=measures)


def build_live_chord_follow_html(
    spans: list[dict[str, Any]] | None,
    *,
    bpm: int,
    count_in_beats: float = 0.0,
    section_label: str = "",
) -> str:
    """Self-contained follow strip: highlights the sounding chord as time advances."""
    if not spans:
        return ""
    payload = [
        {
            "chord": str(s.get("chord") or ""),
            "start": float(s.get("start_beat") or 0.0),
            "dur": float(s.get("duration_beats") or 0.0),
        }
        for s in spans
        if str(s.get("chord") or "").strip()
    ]
    if not payload:
        return ""
    cells = "".join(
        f'<span class="composer-live-chord" data-start="{row["start"]:g}" '
        f'data-dur="{row["dur"]:g}">{html.escape(row["chord"])}</span>'
        for row in payload
    )
    heading = html.escape(section_label) if section_label else "Now playing"
    data = json.dumps(payload)
    return f"""
<html>
<head>
<style>
  body {{ margin: 0; padding: 0; background: transparent; font-family: ui-sans-serif, system-ui, sans-serif; }}
  .composer-live-follow {{
    border: 1px solid rgba(49, 46, 129, 0.18);
    background: #eef2ff;
    border-radius: 10px;
    padding: 0.45rem 0.55rem 0.55rem;
  }}
  .composer-live-kicker {{
    font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em;
    color: #4338ca; font-weight: 700; margin: 0 0 0.35rem 0;
  }}
  .composer-live-row {{ display: flex; gap: 0.35rem; align-items: stretch; }}
  .composer-live-chord {{
    flex: 1 1 0; text-align: center; font-weight: 800; font-size: 1.05rem;
    color: #312e81; background: #fff; border-radius: 8px; padding: 0.35rem 0.2rem;
    border: 2px solid transparent; opacity: 0.55;
  }}
  .composer-live-chord.is-countin {{ opacity: 0.4; }}
  .composer-live-chord.is-active {{
    opacity: 1; background: #312e81; color: #fff; border-color: #1e1b4b;
    box-shadow: 0 0 0 3px rgba(49, 46, 129, 0.18);
  }}
</style>
</head>
<body>
<div class="composer-live-follow" data-bpm="{int(bpm)}" data-count-in="{float(count_in_beats):g}">
  <div class="composer-live-kicker">{heading}</div>
  <div class="composer-live-row">{cells}</div>
</div>
<script>
(function() {{
  var spans = {data};
  var bpm = {int(max(40, bpm))};
  var countIn = {float(count_in_beats or 0.0)};
  var beatMs = 60000 / bpm;
  var t0 = Date.now();
  var nodes = document.querySelectorAll(".composer-live-chord");
  function tick() {{
    var pos = ((Date.now() - t0) / beatMs) - countIn;
    for (var i = 0; i < nodes.length; i++) {{
      var s = spans[i];
      var active = pos >= s.start && pos < (s.start + s.dur);
      nodes[i].classList.toggle("is-active", active);
      nodes[i].classList.toggle("is-countin", pos < 0);
    }}
  }}
  tick();
  setInterval(tick, 80);
}})();
</script>
</body>
</html>
"""


def build_section_score_model(
    *,
    events: list[dict[str, Any]] | None,
    chords: list[Any] | None,
    key: str,
    meter: str,
    bpm: int,
    title: str = "Melody",
    lyrics_text: str = "",
    lyric_syllables: list[str] | None = None,
    section_bars: int | None = None,
) -> dict[str, Any]:
    """Canonical derived view for section score rendering (no duplicate ownership)."""
    evs = list(events or [])
    chord_list = list(chords or [])
    melody_m = melody_measure_count(evs, meter=meter) if evs else 0
    try:
        declared = int(section_bars or 0)
    except (TypeError, ValueError):
        declared = 0
    measures = max(melody_m, chord_span_bars(chord_list), declared, 1 if (evs or chord_list) else 1)
    chord_labels = chord_symbols_by_measure(chord_list, meter=meter, measures=measures)
    timing = progression_timing_labels(chord_list)
    spans = timed_chord_spans(chord_list, meter=meter, section_bars=measures)
    alignment = align_notes_to_chords(evs, spans, meter=meter, section_bars=measures)
    display_events = pad_events_to_chord_spans(evs, spans) if (evs or spans) else evs
    abc = (
        build_abc_from_melody_events(
            display_events,
            key=key,
            meter=meter,
            bpm=bpm,
            title=title,
            lyric_syllables=lyric_syllables,
            chords=chord_list,
            section_bars=measures,
        )
        if display_events
        else ""
    )
    return {
        "has_melody": bool(evs),
        "has_chords": bool(chord_labels or spans),
        "has_lyrics": bool(str(lyrics_text or "").strip()),
        "abc": abc,
        "chord_labels": chord_labels,
        "timed_spans": spans,
        "note_chord_alignment": alignment,
        "chord_strip_html": measure_aligned_chord_html(spans, meter=meter, measures=measures),
        "progression_line": " → ".join(timing),
        "progression_timing": timing,
        "lyrics_text": str(lyrics_text or "").strip(),
        "measures": measures,
        "key": key,
        "meter": meter,
        "bpm": int(bpm),
        "title": title,
    }


def render_abc_html(abc_text: str, *, height: int = 280) -> str:
    """HTML document for Streamlit components.html abcjs render."""
    escaped = (
        str(abc_text or "")
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("${", "\\${")
    )
    return f"""
    <html>
    <head>
    <style>
      body {{ margin: 0; padding: 8px 4px 12px 4px; overflow: visible; background: #fff; }}
      #paper {{ min-height: 140px; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/abcjs@6.4.4/dist/abcjs-basic-min.js"></script>
    </head>
    <body>
    <div id="paper"></div>
    <script>
    ABCJS.renderAbc("paper", `{escaped}`, {{ responsive: "resize", staffwidth: 520, paddingbottom: 8 }});
    </script>
    </body>
    </html>
    """
