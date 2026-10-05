"""Composition melody events → ABC / staff (reuse music_theory + abcjs path).

Also builds the musician-facing section score: staff above, chord symbols
aligned by measure, optional lyrics beneath — derived from canonical events
+ section chords (no separate display state).
"""

from __future__ import annotations

import html
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


def chord_symbols_by_measure(
    chords: list[Any],
    *,
    meter: str = "4/4",
    measures: int | None = None,
) -> list[str]:
    """Deterministic measure-level chord labels for staff alignment.

    One chord symbol per measure when possible. Extra chords beyond measure
    count are appended; missing measures reuse the last chord or stay blank.
    """
    from custom_progression_lab import expand_entries_to_chords

    if chords and isinstance(chords[0], dict):
        symbols = expand_entries_to_chords(list(chords))
    else:
        symbols = [str(c).strip() for c in (chords or []) if str(c).strip()]
    if not symbols:
        return []
    bar = max(1.0, beats_per_bar(meter))
    n = int(measures) if measures and measures > 0 else max(1, len(symbols))
    # Prefer 1:1 chord→measure when lengths match; otherwise stretch/cycle.
    if len(symbols) == n:
        return list(symbols)
    if len(symbols) > n:
        return list(symbols[:n])
    out: list[str] = []
    for i in range(n):
        out.append(symbols[min(i, len(symbols) - 1)])
    return out


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


def _chord_onset_beats(
    chords: list[Any] | None,
    *,
    meter: str = "4/4",
) -> list[tuple[float, str]]:
    """Absolute 0-based beat onsets with chord symbols for score alignment."""
    if not chords:
        return []
    bar = max(1.0, beats_per_bar(meter))
    if isinstance(chords[0], dict):
        try:
            from composition_chord_manual_editor import chord_timeline

            rows = chord_timeline(list(chords), meter=meter)
        except Exception:
            rows = []
        out: list[tuple[float, str]] = []
        for row in rows:
            sym = str(row.get("chord") or "").strip()
            if not sym:
                continue
            measure = max(1, int(row.get("measure") or 1))
            beat_in_bar = float(row.get("beat") or 1.0)
            abs_beat = (measure - 1) * bar + max(0.0, beat_in_bar - 1.0)
            out.append((abs_beat, sym))
        return out
    symbols = [str(c).strip() for c in chords if str(c).strip()]
    return [(i * bar, sym) for i, sym in enumerate(symbols)]


def _chord_span_cells(
    chords: list[Any] | None,
    *,
    meter: str = "4/4",
    measures: int | None = None,
) -> list[tuple[str, float]]:
    """(symbol, duration_beats) cells for proportional chord-strip flex widths."""
    if not chords:
        return []
    bar = max(1.0, beats_per_bar(meter))
    if isinstance(chords[0], dict):
        try:
            from composition_chord_manual_editor import chord_timeline

            rows = chord_timeline(list(chords), meter=meter)
        except Exception:
            rows = []
        cells = [
            (str(r.get("chord") or "").strip(), float(r.get("duration_beats") or bar))
            for r in rows
            if str(r.get("chord") or "").strip()
        ]
        if cells:
            return cells
    labels = chord_symbols_by_measure(list(chords), meter=meter, measures=measures)
    return [(lab, bar) for lab in labels]


def build_abc_from_melody_events(
    events: list[dict[str, Any]],
    *,
    key: str = "C",
    meter: str = "4/4",
    bpm: int = 96,
    title: str = "Melody",
    chords: list[Any] | None = None,
    clef: str = "treble",
) -> str:
    """Build ABC from Composition melody events (notes + rests).

    When ``chords`` is provided, ABC chord annotations are placed at chord
    onsets so abcjs draws symbols above the corresponding note positions.
    """
    from composition_hum_transcription import is_compound_meter, parse_meter

    k_field = composition_abc_key_field(key)
    num, den = parse_meter(meter)
    meter_field = f"{num}/{den}"
    tokens: list[str] = []
    beats_in_bar = 0.0
    bar_len = float(num)
    abs_beat = 0.0
    onsets = _chord_onset_beats(chords, meter=meter)
    onset_i = 0

    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        dur = float(ev.get("duration_beats") or 1.0)
        length = _duration_to_abc_length(dur, meter=meter)
        chord_prefix = ""
        while onset_i < len(onsets) and onsets[onset_i][0] <= abs_beat + 1e-6:
            # Keep the latest onset at/before this note (handles tied bar starts).
            chord_prefix = f'"{onsets[onset_i][1]}"'
            onset_i += 1
        if ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest":
            tokens.append(f"{chord_prefix}z{length}" if chord_prefix else f"z{length}")
        else:
            pitch = _pitch_token_to_abc(str(ev.get("pitch") or "C4"), key=key)
            # ABC decoration syntax: "!>!" renders an accent mark above the
            # note, a leading "." renders staccato -- both abcjs-native, no
            # custom rendering needed.
            articulation = str(ev.get("articulation") or "").strip().lower()
            deco = "!>!" if articulation == "accent" else ("." if articulation == "staccato" else "")
            # ABC slur syntax: "(" immediately precedes the first note of a
            # slurred group, ")" immediately follows the last -- both
            # attach directly to the note token with no space, same as the
            # decoration prefix above.
            slur = str(ev.get("slur") or "").strip().lower()
            slur_open = "(" if slur in ("start", "both") else ""
            slur_close = ")" if slur in ("end", "both") else ""
            tokens.append(f"{chord_prefix}{slur_open}{deco}{pitch}{length}{slur_close}")
        abs_beat += dur
        beats_in_bar += dur
        if beats_in_bar >= bar_len - 1e-6:
            tokens.append("|")
            beats_in_bar = 0.0

    if beats_in_bar > 0 and tokens and tokens[-1] != "|":
        tokens.append("|")
    music = " ".join(tokens) if tokens else "z4 |"
    q_unit = "3/8" if is_compound_meter(meter) else "1/4"
    k_line = f"K:{k_field}" if clef == "treble" else f"K:{k_field} clef={clef}"
    return f"""X:1
T:{title}
M:{meter_field}
L:1/8
Q:{q_unit}={int(bpm)}
{k_line}
{music}"""


def build_chord_strip_html(
    chords: list[Any],
    *,
    meter: str = "4/4",
    measures: int | None = None,
) -> str:
    """HTML row of chord symbols with widths proportional to onset spans."""
    cells_data = _chord_span_cells(chords, meter=meter, measures=measures)
    if not cells_data:
        return ""
    cells = "".join(
        f'<div class="composer-score-chord" style="flex:{max(0.5, float(dur)):g} 1 0" '
        f'data-duration-beats="{max(0.5, float(dur)):g}">{html.escape(lab)}</div>'
        for lab, dur in cells_data
    )
    return f'<div class="composer-score-chords">{cells}</div>'


def build_section_score_model(
    *,
    events: list[dict[str, Any]] | None,
    chords: list[Any] | None,
    key: str,
    meter: str,
    bpm: int,
    title: str = "Melody",
    lyrics_text: str = "",
) -> dict[str, Any]:
    """Canonical derived view for section score rendering (no duplicate ownership)."""
    evs = list(events or [])
    chord_list = list(chords or [])
    from custom_progression_lab import expand_entries_to_chords

    n_chords = len(expand_entries_to_chords(chord_list)) if chord_list and isinstance(chord_list[0], dict) else len(
        [c for c in chord_list if str(c).strip()]
    )
    measures = melody_measure_count(evs, meter=meter) if evs else max(1, n_chords or 1)
    # Always surface the full accepted progression when it is longer than the melody span.
    if n_chords > 0:
        measures = max(measures, n_chords)
    chord_labels = chord_symbols_by_measure(chord_list, meter=meter, measures=measures)
    abc = (
        build_abc_from_melody_events(
            evs, key=key, meter=meter, bpm=bpm, title=title, chords=chord_list
        )
        if evs
        else ""
    )
    return {
        "has_melody": bool(evs),
        "has_chords": bool(chord_labels),
        "has_lyrics": bool(str(lyrics_text or "").strip()),
        "abc": abc,
        "chord_labels": chord_labels,
        "chord_strip_html": build_chord_strip_html(chord_list, meter=meter, measures=measures),
        "lyrics_text": str(lyrics_text or "").strip(),
        "measures": measures,
        "key": key,
        "meter": meter,
        "bpm": int(bpm),
        "title": title,
    }


def render_abc_html(abc_text: str, *, height: int = 280, add_classes: bool = True) -> str:
    """HTML document for Streamlit components.html abcjs render."""
    escaped = (
        str(abc_text or "")
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("${", "\\${")
    )
    add_cls = "true" if add_classes else "false"
    return f"""
    <html>
    <head>
    <style>
      html, body {{ margin: 0; padding: 0; background: #fff; overflow-x: auto; overflow-y: hidden; }}
      body {{ padding: 6px 2px 10px 2px; max-width: 100%; box-sizing: border-box; }}
      #paper {{ min-height: 120px; max-width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }}
      #paper svg {{ max-width: 100%; height: auto; }}
      #paper svg .abcjs-note.cplay-active,
      #paper svg .abcjs-note.cplay-active * {{
        fill: #0284c7 !important; stroke: #0284c7 !important;
      }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/abcjs@6.4.4/dist/abcjs-basic-min.js"></script>
    </head>
    <body>
    <div id="paper"></div>
    <script>
    (function () {{
      var w = Math.max(240, Math.min(520, (window.innerWidth || 360) - 16));
      ABCJS.renderAbc("paper", `{escaped}`, {{
        responsive: "resize",
        staffwidth: w,
        paddingbottom: 8,
        add_classes: {add_cls}
      }});
    }})();
    </script>
    </body>
    </html>
    """
