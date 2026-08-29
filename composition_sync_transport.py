"""Synchronized chord highlighting transport for Composition Hum/Play."""

from __future__ import annotations

import base64
import html
import io
import json
import math
import struct
import wave
from typing import Any

COUNT_IN_OFF = 0
COUNT_IN_ONE_BAR = 1
COUNT_IN_CHOICES: tuple[tuple[int, str], ...] = (
    (COUNT_IN_OFF, "Off"),
    (COUNT_IN_ONE_BAR, "1 bar"),
)


def _beats_per_bar_quarter(meter: str) -> float:
    """Quarter-note-equivalent bar length (legacy fallback)."""
    text = str(meter or "4/4")
    if "/" not in text:
        return 4.0
    try:
        num, den = text.split("/", 1)
        n = float(num)
        d = float(den)
        return n * (4.0 / d)
    except ValueError:
        return 4.0


def bar_seconds(*, bpm: int, meter: str = "4/4") -> float:
    """One chord-bar duration in seconds — matches ``generate_backing_track`` / meter_timing."""
    bpm_i = max(40, int(bpm or 100))
    try:
        from songs.meter import meter_timing

        return float(meter_timing(bpm_i, str(meter or "4/4")).bar_sec)
    except Exception:
        try:
            from backing_audio import meter_timing as _mt

            return float(_mt(bpm_i, str(meter or "4/4")).bar_sec)
        except Exception:
            return _beats_per_bar_quarter(meter) * (60.0 / float(bpm_i))


def pulses_per_bar(meter: str = "4/4") -> int:
    try:
        from songs.meter import meter_timing

        return int(meter_timing(100, str(meter or "4/4")).pulses_per_bar)
    except Exception:
        text = str(meter or "4/4")
        if text.startswith("6/"):
            return 6
        if text.startswith("3/"):
            return 3
        if text.startswith("12/"):
            return 12
        try:
            return max(1, int(text.split("/", 1)[0]))
        except ValueError:
            return 4


def count_in_seconds(*, bpm: int, meter: str = "4/4", bars: int = 1) -> float:
    """Duration of the count-in region (once, before continuous repeats)."""
    n = max(0, int(bars))
    if n <= 0:
        return 0.0
    return bar_seconds(bpm=bpm, meter=meter) * float(n)


def count_in_beats_for_transcription(*, bpm: int, meter: str, bars: int) -> float:
    """
    Count-in length in Composition transcription beat units (60/BPM pulses).

    Used to shift transcribed note starts so section beat 0 = first backing chord.
    """
    sec = count_in_seconds(bpm=bpm, meter=meter, bars=bars)
    if sec <= 0:
        return 0.0
    return sec / (60.0 / max(40.0, float(bpm)))


def prepend_count_in_clicks(
    wav_bytes: bytes,
    *,
    bpm: int,
    meter: str = "4/4",
    bars: int = 1,
) -> bytes:
    """
    Audible click count-in prepended once before the chord body.

    Does not repeat before each loop — caller should prepend after looping the body.
    """
    n_bars = max(0, int(bars))
    if n_bars <= 0 or not wav_bytes or len(wav_bytes) < 44:
        return wav_bytes
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            sr = int(wf.getframerate())
            nframes = wf.getnframes()
            body = wf.readframes(nframes)
        if sampwidth != 2 or sr <= 0:
            return wav_bytes

        bar_sec = bar_seconds(bpm=bpm, meter=meter)
        ppb = max(1, pulses_per_bar(meter))
        pulse_sec = bar_sec / float(ppb)
        total_pulses = ppb * n_bars
        click_len = int(round(sr * bar_sec * n_bars))
        if click_len <= 0:
            return wav_bytes

        clicks = [0.0] * click_len
        for beat in range(total_pulses):
            start = int(round(beat * pulse_sec * sr))
            if start >= click_len:
                break
            end = min(click_len, start + int(0.045 * sr))
            freq = 1200.0 if beat % ppb == 0 else 880.0
            amp = 0.38 if beat % ppb == 0 else 0.22
            for i in range(start, end):
                t = (i - start) / float(sr)
                clicks[i] += amp * math.sin(2.0 * math.pi * freq * t) * math.exp(-t * 42.0)

        # Decode body to mono float then re-encode mono (Composition previews are mono-friendly).
        sample_count = len(body) // 2
        samples = list(struct.unpack("<" + "h" * sample_count, body))
        if channels > 1:
            mono_body = [
                sum(samples[i : i + channels]) / float(channels)
                for i in range(0, len(samples), channels)
            ]
        else:
            mono_body = [float(s) for s in samples]

        merged = [max(-32767, min(32767, int(c * 32767.0 * 0.55))) for c in clicks]
        merged.extend(int(max(-32767, min(32767, s))) for s in mono_body)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(sr)
            out.writeframes(struct.pack("<" + "h" * len(merged), *merged))
        return buf.getvalue()
    except Exception:
        return wav_bytes


def build_chord_span_timeline(
    chords: list[str],
    *,
    bpm: int,
    meter: str = "4/4",
    loops: int = 1,
    count_in_beats: float = 0.0,
    count_in_bars: int | None = None,
    seconds_per_chord_bar: float | None = None,
) -> list[dict[str, Any]]:
    """
    Authoritative timed spans for highlighting.

    Each expanded chord symbol occupies one bar (matches generate_backing_track flattening).
    Count-in shifts the first chord start; no chord is active during the count-in.
    Count-in is applied once — loops tile continuously after it.
    """
    bar_sec = (
        float(seconds_per_chord_bar)
        if seconds_per_chord_bar is not None
        else bar_seconds(bpm=bpm, meter=meter)
    )
    spb = 60.0 / max(40.0, float(bpm))
    if count_in_bars is not None:
        count_in_sec = count_in_seconds(bpm=bpm, meter=meter, bars=int(count_in_bars))
    else:
        count_in_sec = max(0.0, float(count_in_beats)) * spb

    spans: list[dict[str, Any]] = []
    t = count_in_sec
    loop_n = max(1, int(loops))
    seq = [str(c).strip() for c in chords if str(c).strip()]
    if not seq:
        return []
    idx = 0
    for loop_i in range(loop_n):
        for chord in seq:
            start = t
            end = t + bar_sec
            spans.append(
                {
                    "index": idx,
                    "loop": loop_i,
                    "chord": chord,
                    "start_sec": round(start, 4),
                    "end_sec": round(end, 4),
                    "count_in_sec": round(count_in_sec, 4),
                }
            )
            idx += 1
            t = end
    return spans


def active_span_index_at(
    spans: list[dict[str, Any]],
    t_sec: float,
    *,
    stopped_at_start: bool = False,
) -> int:
    """Deterministic highlight index for a playback clock time (seconds)."""
    t = float(t_sec)
    if not spans:
        return -1
    if stopped_at_start and t <= 0.02:
        return -1
    first_start = float(spans[0].get("start_sec") or 0.0)
    # During count-in (before first chord) — no highlight.
    if t < first_start:
        return -1
    for i, s in enumerate(spans):
        start = float(s.get("start_sec") or 0.0)
        end = float(s.get("end_sec") or 0.0)
        if t >= start and t < end:
            return i
    last_end = float(spans[-1].get("end_sec") or 0.0)
    if t >= last_end and last_end > 0:
        return len(spans) - 1
    return -1


def build_synced_transport_html(
    wav_bytes: bytes,
    spans: list[dict[str, Any]],
    *,
    caption: str = "Sing or play — the highlighted chord is sounding now",
    dom_id: str = "csync",
) -> str:
    """Self-contained HTML player: one audio clock drives chord highlight."""
    if not wav_bytes or not spans:
        return ""
    safe_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(dom_id or "csync"))[:48]
    audio_id = f"{safe_id}-audio"
    chords_id = f"{safe_id}-chords"
    b64 = base64.b64encode(wav_bytes).decode("ascii")
    spans_json = json.dumps(spans)
    count_in_sec = float(spans[0].get("count_in_sec") or spans[0].get("start_sec") or 0.0)
    chips = "".join(
        f'<button type="button" class="csync-chord" data-i="{i}" disabled>'
        f"{html.escape(str(s.get('chord') or ''))}</button>"
        for i, s in enumerate(spans)
    )
    count_caption = ""
    if count_in_sec > 0.02:
        count_caption = (
            f'<p class="csync-countin">Count-in {count_in_sec:.2f}s — '
            f"chords highlight when the backing starts</p>"
        )
    return f"""
<div class="csync-wrap" data-csync-root="{html.escape(safe_id)}">
  <p class="csync-caption">{html.escape(caption)}</p>
  {count_caption}
  <div class="csync-chords" id="{chords_id}">{chips}</div>
  <audio id="{audio_id}" class="csync-audio" controls preload="auto" style="width:100%;margin-top:8px;">
    <source src="data:audio/wav;base64,{b64}" type="audio/wav"/>
  </audio>
</div>
<style>
  .csync-wrap {{ font-family: system-ui, sans-serif; }}
  .csync-caption {{ margin: 0 0 8px 0; color: #475569; font-size: 0.9rem; }}
  .csync-countin {{ margin: 0 0 8px 0; color: #64748b; font-size: 0.82rem; }}
  .csync-chords {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .csync-chord {{
    border: 1px solid #cbd5e1; background: #f8fafc; color: #0f172a;
    border-radius: 8px; padding: 6px 10px; font-weight: 700; font-size: 0.95rem;
  }}
  .csync-chord.is-active {{
    background: #0ea5e9; color: #fff; border-color: #0284c7;
    box-shadow: 0 0 0 2px rgba(14,165,233,0.35);
  }}
</style>
<script>
(function() {{
  const spans = {spans_json};
  const root = document.querySelector('[data-csync-root="{safe_id}"]');
  if (!root) return;
  const audio = root.querySelector(".csync-audio") || document.getElementById("{audio_id}");
  const buttons = Array.from(root.querySelectorAll(".csync-chord"));
  let last = -1;
  function setActive(i) {{
    if (i === last) return;
    last = i;
    buttons.forEach((b, idx) => b.classList.toggle("is-active", idx === i));
  }}
  function tick() {{
    if (!audio) return;
    const t = audio.currentTime || 0;
    if (audio.paused && t <= 0.02) {{ setActive(-1); return; }}
    let found = -1;
    for (let i = 0; i < spans.length; i++) {{
      const s = spans[i];
      if (t >= s.start_sec && t < s.end_sec) {{ found = i; break; }}
    }}
    if (found < 0 && spans.length && t >= spans[spans.length - 1].end_sec) {{
      found = spans.length - 1;
    }}
    setActive(found);
  }}
  window.__csyncActiveIndex = function() {{ return last; }};
  window.__csyncTick = tick;
  if (audio) {{
    audio.addEventListener("timeupdate", tick);
    audio.addEventListener("play", tick);
    audio.addEventListener("seeked", tick);
    audio.addEventListener("pause", tick);
    audio.addEventListener("ended", function() {{ setActive(-1); }});
  }}
}})();
</script>
"""


def render_synced_transport(
    st: Any,
    wav_bytes: bytes,
    spans: list[dict[str, Any]],
    *,
    key: str = "",
    caption: str = "Sing or play — the highlighted chord is sounding now",
) -> None:
    """Render via components.html so highlighting shares the audio element's clock."""
    html_doc = build_synced_transport_html(
        wav_bytes,
        spans,
        caption=caption,
        dom_id=key or "csync",
    )
    if not html_doc:
        return
    try:
        import streamlit.components.v1 as components

        components.html(html_doc, height=280, scrolling=False)
    except Exception:
        st.audio(wav_bytes, format="audio/wav")
        st.caption("Synced highlight unavailable — audio only.")
