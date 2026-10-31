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


def _duration_to_abc_eighths(duration_beats: float, *, meter: str = "4/4") -> int:
    """How many L:1/8 units a duration occupies in the rendered ABC."""
    from composition_hum_transcription import is_compound_meter

    beats = max(0.5, float(duration_beats or 1.0))
    if is_compound_meter(meter):
        # Composition pulse tracks eighths in compound meters (bar length = numerator).
        eighths = int(round(beats))
    else:
        # Pulse ≈ quarter → two eighths per beat.
        eighths = int(round(beats * 2))
    return max(1, eighths)


def _duration_to_abc_length(duration_beats: float, *, meter: str = "4/4") -> str:
    """Map beat durations to ABC lengths with L:1/8 base."""
    eighths = _duration_to_abc_eighths(duration_beats, meter=meter)
    return str(eighths) if eighths != 1 else ""


def abc_beat_group_eighths(meter: str) -> int:
    """Eighths per beaming group: a quarter beat, or a dotted quarter in compound.

    Measured in L:1/8 units -- the same units the rendered ABC uses -- so this
    is independent of whatever beat unit a particular generator counts in.
    """
    from composition_hum_transcription import is_compound_meter

    return 3 if is_compound_meter(meter) else 2


def join_abc_tokens_with_beams(entries: list[tuple[str, bool, Any, bool]]) -> str:
    """Join ABC tokens, beaming eighth notes within each beat group.

    ABC uses whitespace as the beam separator: tokens written adjacently are
    beamed under one beam, space-separated tokens each get their own flag.
    Space-joining everything -- what both builders used to do -- is why every
    eighth note rendered individually flagged.

    Each entry is ``(text, beamable, group_key, break_before)``. Two tokens are
    beamed only when both are beamable, they share a ``group_key`` (same bar,
    same beat group) and the later one does not demand a break. Rests, notes a
    quarter or longer, bar lines and chord-annotated notes therefore end a
    beam, which keeps the result musical rather than beaming every consecutive
    eighth in sight.
    """
    out: list[str] = []
    prev_beamable = False
    prev_group: Any = None
    for text, beamable, group_key, break_before in entries:
        if not out:
            out.append(text)
        elif (
            beamable
            and prev_beamable
            and not break_before
            and group_key is not None
            and group_key == prev_group
        ):
            out.append(text)
        else:
            out.append(" ")
            out.append(text)
        prev_beamable = beamable
        prev_group = group_key
    return "".join(out)


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


from chord_subdivisions import chord_names_label, parse_subdivisions  # noqa: E402


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
    symbols = [lab for lab in (chord_names_label(sym) for sym in symbols) if lab]
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
            sym = chord_names_label(row.get("chord"))
            if not sym:
                continue
            measure = max(1, int(row.get("measure") or 1))
            beat_in_bar = float(row.get("beat") or 1.0)
            abs_beat = (measure - 1) * bar + max(0.0, beat_in_bar - 1.0)
            out.append((abs_beat, sym))
        return out
    out_s: list[tuple[float, str]] = []
    for bar_index, token in enumerate(str(c).strip() for c in chords if str(c).strip()):
        cursor = 0.0
        for sub in parse_subdivisions(token, beats_per_bar=bar):
            out_s.append((bar_index * bar + cursor, sub.chord))
            cursor += float(sub.weight)
    return out_s


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
            (chord_names_label(r.get("chord")), float(r.get("duration_beats") or bar))
            for r in rows
            if chord_names_label(r.get("chord"))
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
    # (text, beamable, group_key, break_before) -- see join_abc_tokens_with_beams.
    entries: list[tuple[str, bool, Any, bool]] = []
    beats_in_bar = 0.0
    bar_len = float(num)
    abs_beat = 0.0
    onsets = _chord_onset_beats(chords, meter=meter)
    onset_i = 0
    group_eighths = abc_beat_group_eighths(meter)
    bar_index = 0
    eighths_in_bar = 0

    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        start_eighths_in_bar = eighths_in_bar
        dur = float(ev.get("duration_beats") or 1.0)
        length = _duration_to_abc_length(dur, meter=meter)
        eighths_in_bar += _duration_to_abc_eighths(dur, meter=meter)
        chord_prefix = ""
        while onset_i < len(onsets) and onsets[onset_i][0] <= abs_beat + 1e-6:
            # Keep the latest onset at/before this note (handles tied bar starts).
            chord_prefix = f'"{onsets[onset_i][1]}"'
            onset_i += 1
        # Only a lone eighth (empty length field under L:1/8) can carry a beam;
        # rests and anything a quarter or longer end the group.
        is_rest = bool(ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest")
        beamable = (not is_rest) and length == ""
        group_key = (bar_index, start_eighths_in_bar // group_eighths)
        if is_rest:
            entries.append(
                (f"{chord_prefix}z{length}" if chord_prefix else f"z{length}", False, None, True)
            )
        else:
            pitch = _pitch_token_to_abc(str(ev.get("pitch") or "C4"), key=key)
            # ABC decoration syntax: "!>!" renders an accent mark above the
            # note, a leading "." renders staccato, "!tenuto!" renders a
            # tenuto dash -- all abcjs-native, no custom rendering needed.
            articulation = str(ev.get("articulation") or "").strip().lower()
            deco = (
                "!>!" if articulation == "accent"
                else "." if articulation == "staccato"
                else "!tenuto!" if articulation == "tenuto"
                else ""
            )
            # Dynamics/hairpins: abcjs renders "!p!"/"!mf!"/etc. and
            # "!crescendo(!"/"!crescendo)!" as standard decorations attached
            # to the note they precede.
            dyn_token = str(ev.get("dynamic") or "").strip().lower()
            dyn_deco = {
                "p": "!p!", "mp": "!mp!", "mf": "!mf!", "f": "!f!",
                "cresc_start": "!crescendo(!", "cresc_end": "!crescendo)!",
                "dim_start": "!diminuendo(!", "dim_end": "!diminuendo)!",
            }.get(dyn_token, "")
            # ABC slur syntax: "(" immediately precedes the first note of a
            # slurred group, ")" immediately follows the last -- both
            # attach directly to the note token with no space, same as the
            # decoration prefix above.
            slur = str(ev.get("slur") or "").strip().lower()
            slur_open = "(" if slur in ("start", "both") else ""
            slur_close = ")" if slur in ("end", "both") else ""
            entries.append(
                (
                    f"{chord_prefix}{slur_open}{dyn_deco}{deco}{pitch}{length}{slur_close}",
                    beamable,
                    group_key,
                    # A chord symbol anchors the start of its own beam group.
                    bool(chord_prefix),
                )
            )
        abs_beat += dur
        beats_in_bar += dur
        if beats_in_bar >= bar_len - 1e-6:
            entries.append(("|", False, None, True))
            beats_in_bar = 0.0
            eighths_in_bar = 0
            bar_index += 1

    if beats_in_bar > 0 and entries and entries[-1][0] != "|":
        entries.append(("|", False, None, True))
    music = join_abc_tokens_with_beams(entries) if entries else "z4 |"
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
    lyrics_alignment: dict[str, Any] | None = None,
    clef: str = "treble",
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
            evs, key=key, meter=meter, bpm=bpm, title=title, chords=chord_list, clef=clef
        )
        if evs
        else ""
    )
    alignment = lyrics_alignment if isinstance(lyrics_alignment, dict) else {}
    alignment_status = str(alignment.get("status") or "unaligned")
    lyrics_aligned = bool(
        abc
        and str(lyrics_text or "").strip()
        and alignment_status in {"provisional", "confirmed"}
        and alignment.get("event_assignments")
    )
    if lyrics_aligned:
        from composition_lyrics_alignment import build_abc_with_lyrics

        abc = build_abc_with_lyrics(abc, alignment, evs, meter=meter)
    return {
        "has_melody": bool(evs),
        "has_chords": bool(chord_labels),
        "has_lyrics": bool(str(lyrics_text or "").strip()),
        "abc": abc,
        "chord_labels": chord_labels,
        "chord_strip_html": build_chord_strip_html(chord_list, meter=meter, measures=measures),
        "lyrics_text": str(lyrics_text or "").strip(),
        "lyrics_aligned": lyrics_aligned,
        "alignment_status": alignment_status,
        "alignment_warnings": [str(w) for w in (alignment.get("warnings") or [])],
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
      html, body {{ margin: 0; padding: 0; background: #fff; overflow-x: auto; overflow-y: auto; }}
      body {{ padding: 6px 2px 14px 2px; max-width: 100%; box-sizing: border-box; }}
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
        paddingtop: 6,
        paddingbottom: 14,
        wrap: {{ minSpacing: 1.8, maxSpacing: 2.7, preferredMeasuresPerLine: 4 }},
        add_classes: {add_cls}
      }});
    }})();
    </script>
    </body>
    </html>
    """
