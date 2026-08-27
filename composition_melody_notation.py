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
) -> str:
    """Build ABC from Composition melody events (notes + rests)."""
    from composition_hum_transcription import is_compound_meter, parse_meter

    k_field = composition_abc_key_field(key)
    num, den = parse_meter(meter)
    meter_field = f"{num}/{den}"
    tokens: list[str] = []
    beats_in_bar = 0.0
    bar_len = float(num)

    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        dur = float(ev.get("duration_beats") or 1.0)
        length = _duration_to_abc_length(dur, meter=meter)
        if ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest":
            tokens.append(f"z{length}")
        else:
            pitch = _pitch_token_to_abc(str(ev.get("pitch") or "C4"), key=key)
            tokens.append(f"{pitch}{length}")
        beats_in_bar += dur
        if beats_in_bar >= bar_len - 1e-6:
            tokens.append("|")
            beats_in_bar = 0.0

    if beats_in_bar > 0 and tokens and tokens[-1] != "|":
        tokens.append("|")
    music = " ".join(tokens) if tokens else "z4 |"
    q_unit = "3/8" if is_compound_meter(meter) else "1/4"
    lyric_line = _abc_lyric_line(list(events or []), lyric_syllables)
    body = f"{music}\n{lyric_line}" if lyric_line else music
    return f"""X:1
T:{title}
M:{meter_field}
L:1/8
Q:{q_unit}={int(bpm)}
K:{k_field}
{body}"""


def build_chord_strip_html(
    chords: list[Any],
    *,
    meter: str = "4/4",
    measures: int | None = None,
) -> str:
    """HTML row of chord symbols aligned one-per-measure under the staff."""
    labels = chord_symbols_by_measure(chords, meter=meter, measures=measures)
    if not labels:
        return ""
    cells = "".join(
        f'<div class="composer-score-chord">{html.escape(lab)}</div>' for lab in labels
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
    lyric_syllables: list[str] | None = None,
) -> dict[str, Any]:
    """Canonical derived view for section score rendering (no duplicate ownership)."""
    evs = list(events or [])
    chord_list = list(chords or [])
    measures = melody_measure_count(evs, meter=meter) if evs else max(1, len(chord_list) or 1)
    chord_labels = chord_symbols_by_measure(chord_list, meter=meter, measures=measures)
    abc = (
        build_abc_from_melody_events(
            evs,
            key=key,
            meter=meter,
            bpm=bpm,
            title=title,
            lyric_syllables=lyric_syllables,
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
