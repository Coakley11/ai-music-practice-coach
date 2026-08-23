"""Composition melody events → ABC / staff (reuse music_theory + abcjs path)."""

from __future__ import annotations

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


def build_abc_from_melody_events(
    events: list[dict[str, Any]],
    *,
    key: str = "C",
    meter: str = "4/4",
    bpm: int = 96,
    title: str = "Melody",
) -> str:
    """Build ABC from Composition melody events (notes + rests)."""
    from composition_hum_transcription import is_compound_meter, parse_meter

    k_field = composition_abc_key_field(key)
    num, den = parse_meter(meter)
    meter_field = f"{num}/{den}"
    tokens: list[str] = []
    beats_in_bar = 0.0
    # Match composition_preview / hum quantization: bar length = meter numerator pulses.
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
    return f"""X:1
T:{title}
M:{meter_field}
L:1/8
Q:{q_unit}={int(bpm)}
K:{k_field}
{music}"""


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
      #paper {{ min-height: 160px; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/abcjs@6.4.4/dist/abcjs-basic-min.js"></script>
    </head>
    <body>
    <div id="paper"></div>
    <script>
    ABCJS.renderAbc("paper", `{escaped}`, {{ responsive: "resize", staffwidth: 520, paddingbottom: 12 }});
    </script>
    </body>
    </html>
    """
