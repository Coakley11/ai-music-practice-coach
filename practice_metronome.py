"""Shared Practice page metronome widget (Streamlit HTML component)."""

from __future__ import annotations

import html
import json
from typing import Any

import streamlit.components.v1 as components

from music_feature_icons import FEATURE_ICONS
from songs.meter import meter_timing, metronome_accents


def build_metronome_widget_html(
    *,
    default_bpm: int = 100,
    default_signature: str = "4/4",
    section_bars: int = 0,
    section_label: str = "",
    loop_section: bool = False,
    compact: bool = False,
) -> str:
    """Build inline HTML/JS for the practice metronome."""
    bpm = int(default_bpm)
    signature = str(default_signature or "4/4")
    timing = meter_timing(bpm, signature)
    config = json.dumps(
        {
            "bpm": bpm,
            "signature": signature,
            "pulseIntervalMs": int(timing.pulse_sec * 1000),
            "beatsPerMeasure": timing.pulses_per_bar,
            "accentBeats": metronome_accents(signature),
            "sectionBars": int(section_bars) if loop_section and section_bars > 0 else 0,
            "sectionLabel": section_label or "",
        }
    )

    metro_icon = FEATURE_ICONS["timing_tempo_metronome"]
    title = f"{metro_icon} Metronome" if compact else f"{metro_icon} Practice Metronome"
    loop_note = ""
    if loop_section and section_bars > 0 and section_label:
        loop_note = (
            f"<p style='margin:0 0 8px 0;color:#166534;font-weight:650;font-size:13px;'>"
            f"Section loop: <strong>{html.escape(section_label)}</strong> "
            f"({section_bars} bar{'s' if section_bars != 1 else ''})</p>"
        )
    help_line = ""
    if not compact:
        help_line = (
            "<p style='margin:10px 0 0 0; color:#666; font-size:13px;'>"
            "First beat is accented higher/louder; other beats are softer/lower. "
            "Audio starts after pressing Start.</p>"
        )

    sig_options = ["2/4", "3/4", "4/4", "6/8", "3/8", "5/4", "7/8"]
    sig_select_html = "".join(
        f'<option{" selected" if sig == signature else ""}>{sig}</option>' for sig in sig_options
    )

    return f"""
    <div id="metro-root" style="font-family: system-ui, -apple-system, Segoe UI, sans-serif; border:1px solid #ddd; border-radius:12px; padding:{"10" if compact else "14"}px; max-width:760px;">
      <h4 style="margin:0 0 {"6" if compact else "10"}px 0;">{html.escape(title)}</h4>
      {loop_note}
      <div style="display:flex; gap:12px; flex-wrap:wrap; align-items:end;">
        <label>BPM<br><input id="metro-bpm" type="range" min="40" max="240" value="{bpm}" style="width:{"180" if compact else "220"}px;"></label>
        <div><strong id="metro-bpm-label">{bpm}</strong> BPM</div>
        <label>Time signature<br>
          <select id="metro-sig">{sig_select_html}</select>
        </label>
        <button id="metro-start" style="padding:6px 12px;">Start</button>
        <button id="metro-stop" style="padding:6px 12px;">Stop</button>
      </div>
      <div style="margin-top:{"8" if compact else "12"}px;">
        <div style="font-size:{"13" if compact else "14"}px;">Beat: <strong id="metro-beat">-</strong> / <span id="metro-beats-per-measure">{timing.pulses_per_bar}</span> | Measure: <strong id="metro-measure">0</strong></div>
        <div id="metro-dots" style="display:flex; gap:8px; margin-top:8px;"></div>
      </div>
      {help_line}
    </div>
    <script>
    (() => {{
      const cfg = {config};
      const bpmInput = document.getElementById("metro-bpm");
      const bpmLabel = document.getElementById("metro-bpm-label");
      const sigSelect = document.getElementById("metro-sig");
      const beatEl = document.getElementById("metro-beat");
      const measureEl = document.getElementById("metro-measure");
      const beatsPerEl = document.getElementById("metro-beats-per-measure");
      const dotsEl = document.getElementById("metro-dots");
      let ctx = null;
      let timer = null;
      let beat = 0;
      let measure = 0;

      bpmInput.value = cfg.bpm;
      bpmLabel.textContent = cfg.bpm;
      sigSelect.value = cfg.signature;

      function beatsPerMeasure() {{
        if (cfg.beatsPerMeasure) return cfg.beatsPerMeasure;
        return parseInt(sigSelect.value.split("/")[0], 10);
      }}

      function recomputePulseTiming() {{
        const sig = sigSelect.value;
        const num = parseInt(sig.split("/")[0], 10) || 4;
        const den = parseInt(sig.split("/")[1], 10) || 4;
        const bpmVal = Math.max(1, parseInt(bpmInput.value, 10) || cfg.bpm || 100);
        cfg.bpm = bpmVal;
        cfg.signature = sig;
        if (den === 8 && num % 3 === 0 && num >= 6) {{
          cfg.pulseIntervalMs = Math.round((2 * (60000 / bpmVal)) / num);
          cfg.beatsPerMeasure = num;
          cfg.accentBeats = num === 6 ? [1, 4] : [1, 4, 7, 10];
        }} else {{
          cfg.pulseIntervalMs = Math.round((60000 / bpmVal) * (4 / den));
          cfg.beatsPerMeasure = num;
          cfg.accentBeats = [1];
        }}
      }}

      function tickIntervalMs() {{
        return Math.max(1, cfg.pulseIntervalMs || Math.round(60000 / Math.max(1, parseInt(bpmInput.value, 10) || 100)));
      }}

      function isAccentBeat(n) {{
        const accents = cfg.accentBeats || [1];
        return accents.includes(n);
      }}

      function drawDots(activeBeat) {{
        const beats = beatsPerMeasure();
        beatsPerEl.textContent = beats;
        dotsEl.innerHTML = "";
        for (let i = 1; i <= beats; i++) {{
          const dot = document.createElement("div");
          dot.textContent = i;
          dot.style.width = "30px";
          dot.style.height = "30px";
          dot.style.borderRadius = "50%";
          dot.style.display = "flex";
          dot.style.alignItems = "center";
          dot.style.justifyContent = "center";
          dot.style.border = "1px solid #aaa";
          dot.style.background = i === activeBeat ? (i === 1 ? "#ffcc66" : "#b7e4ff") : "#f5f5f5";
          dot.style.fontWeight = i === activeBeat ? "700" : "400";
          dotsEl.appendChild(dot);
        }}
      }}

      function click(accent) {{
        if (!ctx) return;
        const now = ctx.currentTime;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.frequency.value = accent ? 1180 : 760;
        gain.gain.setValueAtTime(accent ? 0.42 : 0.20, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.07);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.08);
      }}

      function tick() {{
        const beats = beatsPerMeasure();
        beat += 1;
        if (beat > beats) {{
          beat = 1;
          measure += 1;
          if (cfg.sectionBars > 0 && measure > cfg.sectionBars) {{
            measure = 1;
          }}
        }}
        click(isAccentBeat(beat));
        beatEl.textContent = beat;
        measureEl.textContent = measure;
        drawDots(beat);
      }}

      function start() {{
        stop();
        ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
        recomputePulseTiming();
        beat = 0;
        measure = 1;
        tick();
        timer = setInterval(tick, tickIntervalMs());
      }}

      function stop() {{
        if (timer) clearInterval(timer);
        timer = null;
        beat = 0;
        measure = 0;
        beatEl.textContent = "-";
        measureEl.textContent = "0";
        drawDots(0);
      }}

      bpmInput.addEventListener("input", () => {{
        bpmLabel.textContent = bpmInput.value;
        recomputePulseTiming();
        if (timer) start();
      }});
      sigSelect.addEventListener("change", () => {{
        recomputePulseTiming();
        if (timer) start();
        else drawDots(0);
      }});
      document.getElementById("metro-start").addEventListener("click", start);
      document.getElementById("metro-stop").addEventListener("click", stop);
      recomputePulseTiming();
      drawDots(0);
    }})();
    </script>
    """


def render_metronome_widget(
    st_module: Any,
    default_bpm: int = 100,
    default_signature: str = "4/4",
    *,
    section_bars: int = 0,
    section_label: str = "",
    loop_section: bool = False,
    compact: bool = False,
) -> None:
    """Render the practice metronome inside a Streamlit page or expander."""
    widget_html = build_metronome_widget_html(
        default_bpm=int(default_bpm),
        default_signature=default_signature,
        section_bars=section_bars,
        section_label=section_label,
        loop_section=loop_section,
        compact=compact,
    )
    height = 190 if compact else 230
    components.html(widget_html, height=height)
