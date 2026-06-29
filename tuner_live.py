"""Browser-based real-time tuner (Web Audio + pitch detection in JavaScript)."""

from __future__ import annotations

import html
import json
import re
from typing import Any

from tuner_tone import NOTE_NAMES, parse_note_token

NOTE_NAMES_JS = list(NOTE_NAMES)


def _safe_dom_id(key_prefix: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(key_prefix or "tuner").strip())
    return f"live_tuner_{slug[:64] or 'default'}"


def live_tuner_config(
    *,
    key_prefix: str = "practice_tuner",
    target_note: str | None = None,
    expected_note: str | None = None,
    string_targets: list[str] | None = None,
    reference_hz: float = 440.0,
    in_tune_cents: float = 5.0,
    yellow_cents: float = 15.0,
    display_mode: str = "concert",
    concert_to_written_semitones: int = 0,
    instrument_label: str = "",
) -> dict[str, Any]:
    """Build config passed into the embedded live tuner component."""
    target_midi = parse_note_token(target_note) if target_note else None
    expected_midi = parse_note_token(expected_note) if expected_note else None
    strings = list(string_targets or [])
    string_midis: dict[str, int | None] = {
        s: parse_note_token(s) for s in strings
    }
    return {
        "domId": _safe_dom_id(key_prefix),
        "storageKey": _safe_dom_id(key_prefix) + "_target",
        "targetNote": target_note or "",
        "expectedNote": expected_note or "",
        "targetMidi": target_midi,
        "expectedMidi": expected_midi,
        "stringTargets": strings,
        "stringTargetMidis": string_midis,
        "referenceHz": float(reference_hz),
        "inTuneCents": float(in_tune_cents),
        "yellowCents": float(yellow_cents),
        "noteNames": NOTE_NAMES_JS,
        "displayMode": str(display_mode or "concert"),
        "concertToWrittenSemitones": int(concert_to_written_semitones or 0),
        "instrumentLabel": str(instrument_label or ""),
    }


def build_live_tuner_html(config: dict[str, Any]) -> str:
    """Self-contained HTML/JS tuner widget for ``components.html``."""
    cfg_json = json.dumps(config)
    dom_id = html.escape(str(config.get("domId", "live_tuner_default")))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<style>
  #{dom_id} {{
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    border: 1px solid #cbd5e1;
    border-radius: 14px;
    padding: 16px;
    max-width: 520px;
    margin: 0 auto;
    background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
    box-sizing: border-box;
  }}
  #{dom_id} * {{ box-sizing: border-box; }}
  #{dom_id} .lt-toolbar {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
    margin-bottom: 12px;
  }}
  #{dom_id} .lt-btn {{
    padding: 9px 16px;
    border-radius: 8px;
    border: 1px solid #94a3b8;
    background: #fff;
    font-weight: 600;
    cursor: pointer;
    font-size: 14px;
  }}
  #{dom_id} .lt-btn.primary {{
    background: #0f766e;
    color: #fff;
    border-color: #0f766e;
  }}
  #{dom_id} .lt-btn.primary:disabled {{
    opacity: 0.55;
    cursor: not-allowed;
  }}
  #{dom_id} .lt-btn.danger {{
    background: #fef2f2;
    border-color: #fca5a5;
    color: #b91c1c;
  }}
  #{dom_id} .lt-status {{
    font-size: 13px;
    color: #64748b;
    flex: 1;
    min-width: 140px;
  }}
  #{dom_id} .lt-note {{
    text-align: center;
    font-size: 3.2rem;
    font-weight: 800;
    line-height: 1;
    letter-spacing: -0.02em;
    color: #0f172a;
    min-height: 3.4rem;
  }}
  #{dom_id} .lt-note.idle {{ color: #94a3b8; font-size: 1.4rem; font-weight: 600; }}
  #{dom_id} .lt-meta {{
    text-align: center;
    font-size: 0.95rem;
    color: #475569;
    margin: 6px 0 10px;
  }}
  #{dom_id} .lt-direction {{
    text-align: center;
    font-size: 1.05rem;
    font-weight: 650;
    margin-bottom: 10px;
    min-height: 1.4rem;
  }}
  #{dom_id} .lt-meter-labels {{
    display: flex;
    justify-content: space-between;
    font-size: 0.72rem;
    color: #64748b;
    margin-bottom: 4px;
  }}
  #{dom_id} .lt-meter-track {{
    position: relative;
    height: 22px;
    border-radius: 11px;
    overflow: hidden;
    background: linear-gradient(
      90deg,
      #3b82f6 0%,
      #fde68a 38%,
      #86efac 48%,
      #86efac 52%,
      #fde68a 62%,
      #f97316 100%
    );
    box-shadow: inset 0 1px 3px rgba(0,0,0,0.12);
  }}
  #{dom_id} .lt-meter-center {{
    position: absolute;
    left: 50%;
    top: 0;
    width: 3px;
    height: 100%;
    background: #334155;
    transform: translateX(-50%);
    z-index: 2;
  }}
  #{dom_id} .lt-needle {{
    position: absolute;
    top: -4px;
    width: 16px;
    height: 30px;
    border-radius: 4px;
    transform: translateX(-50%);
    z-index: 3;
    box-shadow: 0 2px 6px rgba(0,0,0,0.25);
    transition: left 45ms linear, background 120ms ease;
  }}
  #{dom_id} .lt-signal {{
    margin-top: 12px;
    height: 8px;
    border-radius: 4px;
    background: #e2e8f0;
    overflow: hidden;
  }}
  #{dom_id} .lt-signal-fill {{
    height: 100%;
    width: 0%;
    background: #6366f1;
    transition: width 60ms linear;
  }}
  #{dom_id} .lt-target {{
    margin-top: 12px;
    padding: 10px 12px;
    border-radius: 8px;
    background: #fff;
    border: 1px solid #e2e8f0;
    font-size: 13px;
    color: #334155;
  }}
  #{dom_id} .lt-target strong {{ color: #0f172a; }}
  #{dom_id} .lt-strings {{
    margin-bottom: 12px;
  }}
  #{dom_id} .lt-strings-label {{
    font-size: 0.82rem;
    font-weight: 700;
    color: #334155;
    margin-bottom: 8px;
  }}
  #{dom_id} .lt-strings-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }}
  #{dom_id} .lt-str-btn {{
    padding: 8px 14px;
    border-radius: 8px;
    border: 1px solid #cbd5e1;
    background: #fff;
    color: #0f172a;
    font-weight: 700;
    font-size: 0.88rem;
    cursor: pointer;
    transition: background 0.12s ease, color 0.12s ease, border-color 0.12s ease, box-shadow 0.12s ease;
  }}
  #{dom_id} .lt-str-btn:hover {{
    border-color: #f87171;
    box-shadow: 0 2px 8px rgba(220, 38, 38, 0.15);
  }}
  #{dom_id} .lt-str-btn.active {{
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 55%, #b91c1c 100%);
    border-color: #b91c1c;
    color: #fff;
    box-shadow: 0 0 0 1px rgba(255,255,255,0.12) inset, 0 4px 14px rgba(220, 38, 38, 0.35);
  }}
  #{dom_id} .lt-feedback {{
    margin-top: 12px;
    padding: 12px 14px;
    border-radius: 10px;
    background: #fff;
    border: 1px solid #e2e8f0;
    font-size: 0.88rem;
    line-height: 1.55;
    color: #334155;
  }}
  #{dom_id} .lt-feedback .lt-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px 16px;
    margin: 2px 0;
  }}
  #{dom_id} .lt-feedback .lt-k {{
    color: #64748b;
    font-weight: 600;
    min-width: 72px;
  }}
  #{dom_id} .lt-feedback .lt-v {{
    color: #0f172a;
    font-weight: 700;
  }}
  #{dom_id} .lt-feedback .lt-v.ok {{ color: #15803d; }}
  #{dom_id} .lt-feedback .lt-v.warn {{ color: #c2410c; }}
  #{dom_id} .lt-feedback .lt-v.bad {{ color: #b91c1c; }}
  #{dom_id} .lt-feedback-idle {{
    color: #64748b;
    font-style: italic;
  }}
</style>
</head>
<body>
<div id="{dom_id}">
  <div class="lt-strings" id="{dom_id}-strings" style="display:none;">
    <div class="lt-strings-label">String targets (tap to set target)</div>
    <div class="lt-strings-row" id="{dom_id}-strings-row"></div>
  </div>
  <div class="lt-toolbar">
    <button type="button" class="lt-btn primary" id="{dom_id}-start">Start Tuner</button>
    <button type="button" class="lt-btn danger" id="{dom_id}-stop" disabled>Stop Tuner</button>
    <div class="lt-status" id="{dom_id}-status">Press Start — your browser will ask for microphone access.</div>
  </div>
  <div class="lt-note idle" id="{dom_id}-note">—</div>
  <div class="lt-meta" id="{dom_id}-meta">Play or sing a single note</div>
  <div class="lt-direction" id="{dom_id}-direction"></div>
  <div class="lt-meter-labels">
    <span>Too flat</span><span>In tune</span><span>Too sharp</span>
  </div>
  <div class="lt-meter-track">
    <div class="lt-meter-center"></div>
    <div class="lt-needle" id="{dom_id}-needle" style="left:50%;background:#94a3b8;"></div>
  </div>
  <div class="lt-signal"><div class="lt-signal-fill" id="{dom_id}-signal"></div></div>
  <div class="lt-feedback" id="{dom_id}-feedback">
    <div class="lt-feedback-idle" id="{dom_id}-feedback-body">Select a string target or press Start Tuner.</div>
  </div>
</div>
<script>
(() => {{
  const CFG = {cfg_json};
  const DOM_ID = {json.dumps(config.get("domId", "live_tuner_default"))};
  const STORAGE_KEY = CFG.storageKey || (DOM_ID + "_target");
  const NOTE_NAMES = CFG.noteNames || ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];
  const REF = CFG.referenceHz || 440;
  const IN_TUNE = CFG.inTuneCents ?? 5;
  const YELLOW = CFG.yellowCents ?? 15;
  let targetMidi = CFG.targetMidi;
  const EXPECTED_MIDI = CFG.expectedMidi;
  const STRING_MIDIS = CFG.stringTargetMidis || {{}};

  const el = (suffix) => document.getElementById(DOM_ID + suffix);
  const noteEl = el("-note");
  const metaEl = el("-meta");
  const dirEl = el("-direction");
  const needleEl = el("-needle");
  const statusEl = el("-status");
  const signalEl = el("-signal");
  const feedbackEl = el("-feedback-body");
  const stringsWrap = el("-strings");
  const stringsRow = el("-strings-row");
  const startBtn = el("-start");
  const stopBtn = el("-stop");

  let audioCtx = null;
  let mediaStream = null;
  let analyser = null;
  let source = null;
  let rafId = null;
  let buf = null;

  function hasTarget() {{
    return targetMidi != null && targetMidi !== undefined && !Number.isNaN(targetMidi);
  }}

  function targetLabel() {{
    return CFG.targetNote || (hasTarget() ? midiToLabel(targetMidi) : "");
  }}

  function isTransposingDisplay() {{
    return CFG.displayMode === "transposing_written";
  }}

  function pitchClassFromMidi(midi) {{
    const midiRound = Math.round(midi);
    return NOTE_NAMES[((midiRound % 12) + 12) % 12];
  }}

  function writtenDisplayFromConcert(parts) {{
    const writtenMidi = parts.midi + (CFG.concertToWrittenSemitones || 0);
    return {{
      writtenLabel: midiToLabel(writtenMidi),
      writtenPc: pitchClassFromMidi(writtenMidi),
      concertPc: pitchClassFromMidi(parts.midi),
      writtenMidi,
    }};
  }}

  function midiToLabel(midi) {{
    const midiRound = Math.round(midi);
    const name = NOTE_NAMES[((midiRound % 12) + 12) % 12];
    const octave = Math.floor(midiRound / 12) - 1;
    return name + octave;
  }}

  function persistTarget(note, midi) {{
    try {{
      sessionStorage.setItem(STORAGE_KEY, note || "");
    }} catch (e) {{}}
    CFG.targetNote = note || "";
    targetMidi = midi;
    CFG.targetMidi = midi;
  }}

  function setActiveStringButton(note) {{
    if (!stringsRow) return;
    stringsRow.querySelectorAll(".lt-str-btn").forEach((btn) => {{
      btn.classList.toggle("active", btn.dataset.note === note);
    }});
  }}

  function selectTarget(note, midi) {{
    if (!note || midi == null || midi === undefined) return;
    persistTarget(note, midi);
    setActiveStringButton(note);
    renderFeedbackIdle();
  }}

  function initStringButtons() {{
    const targets = CFG.stringTargets || [];
    if (!targets.length || !stringsWrap || !stringsRow) return;
    stringsWrap.style.display = "block";
    stringsRow.innerHTML = "";
    targets.forEach((note) => {{
      const midi = STRING_MIDIS[note];
      if (midi == null || midi === undefined) return;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "lt-str-btn";
      btn.dataset.note = note;
      btn.textContent = note;
      btn.addEventListener("click", () => selectTarget(note, midi));
      stringsRow.appendChild(btn);
    }});
    let initial = CFG.targetNote || "";
    try {{
      const stored = sessionStorage.getItem(STORAGE_KEY);
      if (stored && STRING_MIDIS[stored] != null) initial = stored;
    }} catch (e) {{}}
    if (initial && STRING_MIDIS[initial] != null) {{
      selectTarget(initial, STRING_MIDIS[initial]);
    }} else if (CFG.targetNote && STRING_MIDIS[CFG.targetNote] != null) {{
      selectTarget(CFG.targetNote, STRING_MIDIS[CFG.targetNote]);
    }}
  }}

  function hzToNoteParts(hz) {{
    if (!hz || hz <= 0 || !isFinite(hz)) return null;
    const midi = 69 + 12 * Math.log2(hz / REF);
    const midiRound = Math.round(midi);
    const name = NOTE_NAMES[((midiRound % 12) + 12) % 12];
    const octave = Math.floor(midiRound / 12) - 1;
    const nearestCents = (midi - midiRound) * 100;
    const label = name + octave;
    let cents = nearestCents;
    if (hasTarget()) {{
      cents = (midi - targetMidi) * 100;
    }}
    const wrongNote = hasTarget() && Math.round(midi) !== Math.round(targetMidi);
    return {{
      name,
      octave,
      label,
      midi,
      cents,
      nearestCents,
      hz,
      wrongNote,
    }};
  }}

  function autoCorrelate(samples, sampleRate) {{
    const SIZE = samples.length;
    let rms = 0;
    for (let i = 0; i < SIZE; i++) {{
      const v = samples[i];
      rms += v * v;
    }}
    rms = Math.sqrt(rms / SIZE);
    if (rms < 0.008) return {{ hz: -1, rms }};

    let r1 = 0;
    let r2 = SIZE - 1;
    const thres = 0.15;
    for (let i = 0; i < SIZE / 2; i++) {{
      if (Math.abs(samples[i]) < thres) {{ r1 = i; break; }}
    }}
    for (let i = 1; i < SIZE / 2; i++) {{
      if (Math.abs(samples[SIZE - i]) < thres) {{ r2 = SIZE - i; break; }}
    }}

    const trim = samples.subarray(r1, r2);
    const trimSize = trim.length;
    if (trimSize < 64) return {{ hz: -1, rms }};

    const c = new Float32Array(trimSize);
    for (let lag = 0; lag < trimSize; lag++) {{
      let sum = 0;
      for (let i = 0; i < trimSize - lag; i++) {{
        sum += trim[i] * trim[i + lag];
      }}
      c[lag] = sum;
    }}

    let d = 0;
    while (d + 1 < trimSize && c[d] > c[d + 1]) d++;
    let maxVal = -1;
    let maxPos = -1;
    const minLag = Math.floor(sampleRate / 2200);
    const maxLag = Math.floor(sampleRate / 38);
    for (let i = Math.max(d, minLag); i < Math.min(trimSize, maxLag); i++) {{
      if (c[i] > maxVal) {{
        maxVal = c[i];
        maxPos = i;
      }}
    }}
    if (maxPos < 0) return {{ hz: -1, rms }};

    let T0 = maxPos;
    if (T0 > 0 && T0 < trimSize - 1) {{
      const s0 = c[T0 - 1];
      const s1 = c[T0];
      const s2 = c[T0 + 1];
      const adj = (s2 - s0) / (2 * (2 * s1 - s2 - s0));
      if (isFinite(adj)) T0 += adj;
    }}
    const hz = sampleRate / T0;
    if (hz < 38 || hz > 2200) return {{ hz: -1, rms }};
    return {{ hz, rms }};
  }}

  function needleColor(cents) {{
    const a = Math.abs(cents);
    if (a <= IN_TUNE) return "#22c55e";
    if (a <= YELLOW) return "#f59e0b";
    return "#ef4444";
  }}

  function feedbackLine(key, value, cls) {{
    return '<div class="lt-row"><span class="lt-k">' + key + '</span><span class="lt-v' + (cls ? ' ' + cls : '') + '">' + value + '</span></div>';
  }}

  function renderFeedbackIdle() {{
    if (!feedbackEl) return;
    if (hasTarget()) {{
      feedbackEl.className = "";
      feedbackEl.innerHTML =
        feedbackLine("Target", targetLabel(), "") +
        feedbackLine("Mode", "Fixed target — needle centered on " + targetLabel(), "") +
        '<div class="lt-row"><span class="lt-k">Status</span><span class="lt-v">Press Start and play this string</span></div>';
    }} else if (isTransposingDisplay()) {{
      feedbackEl.className = "lt-feedback-idle";
      feedbackEl.textContent =
        "Free tuning — written note shown first, concert pitch secondary. Press Start and play.";
    }} else {{
      feedbackEl.className = "lt-feedback-idle";
      feedbackEl.textContent =
        "No fixed target — chromatic mode (nearest note). Showing concert pitch. Press Start and play.";
    }}
  }}

  function tuningFeedback(parts) {{
    if (parts.wrongNote) {{
      return {{ text: "Wrong note — play " + targetLabel(), cls: "bad" }};
    }}
    if (Math.abs(parts.cents) <= IN_TUNE) {{
      return {{ text: "In tune", cls: "ok" }};
    }}
    if (parts.cents > 0) {{
      return {{ text: "Sharp — tune down", cls: "warn" }};
    }}
    return {{ text: "Flat — tune up", cls: "warn" }};
  }}

  function updateFeedbackPanel(parts) {{
    if (!feedbackEl) return;
    if (!parts) {{
      renderFeedbackIdle();
      return;
    }}
    const cents = parts.cents;
    const fb = tuningFeedback(parts);
    const centsLabel = (cents >= 0 ? "+" : "") + cents.toFixed(0) + (hasTarget() ? "" : " (nearest)");
    let html = "";
    if (hasTarget()) {{
      html += feedbackLine("Target", targetLabel(), "");
    }} else {{
      html += feedbackLine("Target", "None (chromatic)", "");
    }}
    if (isTransposingDisplay()) {{
      const wd = writtenDisplayFromConcert(parts);
      html += feedbackLine("Written note", wd.writtenPc, "");
      html += feedbackLine("Concert pitch", wd.concertPc, "");
      html += feedbackLine("Detected (concert)", parts.label, parts.wrongNote ? "bad" : "");
    }} else {{
      html += feedbackLine("Detected note", parts.label, parts.wrongNote ? "bad" : "");
      html += feedbackLine("Mode", "Showing concert pitch", "");
    }}
    html += feedbackLine("Frequency", parts.hz.toFixed(1) + " Hz", "");
    html += feedbackLine("Cents", centsLabel, fb.cls);
    html += feedbackLine("Feedback", fb.text, fb.cls);
    if (CFG.expectedNote) {{
      const match = Math.round(parts.midi) === Math.round(EXPECTED_MIDI);
      html += feedbackLine(
        "Practice",
        match ? "Expected " + CFG.expectedNote : "Expected " + CFG.expectedNote + " (mismatch)",
        match ? "ok" : "bad"
      );
    }}
    feedbackEl.className = "";
    feedbackEl.innerHTML = html;
  }}

  function renderIdle(msg) {{
    noteEl.textContent = "—";
    noteEl.className = "lt-note idle";
    metaEl.textContent = msg || (hasTarget()
      ? "Listening for " + targetLabel()
      : (isTransposingDisplay()
        ? "Showing " + (CFG.instrumentLabel || "instrument") + " written note"
        : "Showing concert pitch — play a single note"));
    dirEl.textContent = hasTarget() ? "Target: " + targetLabel() : "No fixed target";
    dirEl.style.color = "#64748b";
    needleEl.style.left = "50%";
    needleEl.style.background = "#94a3b8";
    signalEl.style.width = "0%";
    renderFeedbackIdle();
  }}

  function renderPitch(hz, rms) {{
    const parts = hzToNoteParts(hz);
    if (!parts) {{
      renderIdle("Listening… play a clear single note");
      statusEl.textContent = "Listening — no stable pitch yet";
      return;
    }}
    const cents = parts.cents;
    let displayNote = hasTarget() && !parts.wrongNote ? targetLabel() : parts.label;
    if (!hasTarget() && isTransposingDisplay()) {{
      displayNote = writtenDisplayFromConcert(parts).writtenPc;
    }} else if (!hasTarget() && !isTransposingDisplay()) {{
      displayNote = pitchClassFromMidi(parts.midi);
    }}
    noteEl.textContent = displayNote;
    noteEl.className = "lt-note";
    if (hasTarget()) {{
      metaEl.textContent =
        "Detected " + parts.label + " · " + parts.hz.toFixed(1) + " Hz · " +
        (cents >= 0 ? "+" : "") + cents.toFixed(0) + "¢ vs " + targetLabel();
    }} else if (isTransposingDisplay()) {{
      const wd = writtenDisplayFromConcert(parts);
      metaEl.textContent =
        "Written note: " + wd.writtenPc + " · Concert pitch: " + wd.concertPc + " · " +
        parts.hz.toFixed(1) + " Hz · " +
        (parts.nearestCents >= 0 ? "+" : "") + parts.nearestCents.toFixed(0) + "¢ from nearest";
    }} else {{
      metaEl.textContent =
        "Showing concert pitch · " + parts.hz.toFixed(1) + " Hz · " +
        (parts.nearestCents >= 0 ? "+" : "") + parts.nearestCents.toFixed(0) + "¢ from nearest pitch";
    }}
    const clamped = Math.max(-50, Math.min(50, cents));
    const leftPct = 50 + (clamped / 50) * 45;
    needleEl.style.left = leftPct.toFixed(1) + "%";
    needleEl.style.background = needleColor(cents);

    const conf = Math.min(100, Math.round(rms * 400));
    signalEl.style.width = conf + "%";

    if (parts.wrongNote) {{
      dirEl.textContent = "Wrong note";
      dirEl.style.color = "#b91c1c";
      statusEl.textContent = "Expected " + targetLabel() + " · heard " + parts.label;
    }} else if (Math.abs(cents) <= IN_TUNE) {{
      dirEl.textContent = "In tune";
      dirEl.style.color = "#15803d";
      statusEl.textContent = "In tune · signal " + conf + "%";
    }} else if (cents > 0) {{
      dirEl.textContent = "Tune down ↓";
      dirEl.style.color = "#c2410c";
      statusEl.textContent = Math.abs(cents).toFixed(0) + "¢ sharp · signal " + conf + "%";
    }} else {{
      dirEl.textContent = "Tune up ↑";
      dirEl.style.color = "#1d4ed8";
      statusEl.textContent = Math.abs(cents).toFixed(0) + "¢ flat · signal " + conf + "%";
    }}
    updateFeedbackPanel(parts);
  }}

  function tick() {{
    if (!analyser || !buf) return;
    analyser.getFloatTimeDomainData(buf);
    const {{ hz, rms }} = autoCorrelate(buf, audioCtx.sampleRate);
    if (hz > 0) renderPitch(hz, rms);
    else renderIdle("Listening…");
    rafId = requestAnimationFrame(tick);
  }}

  async function startTuner() {{
    try {{
      statusEl.textContent = "Requesting microphone…";
      mediaStream = await navigator.mediaDevices.getUserMedia({{
        audio: {{
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        }},
        video: false,
      }});
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === "suspended") await audioCtx.resume();
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 4096;
      analyser.smoothingTimeConstant = 0.72;
      buf = new Float32Array(analyser.fftSize);
      source = audioCtx.createMediaStreamSource(mediaStream);
      source.connect(analyser);
      startBtn.disabled = true;
      stopBtn.disabled = false;
      statusEl.textContent = "Listening — play a note";
      tick();
    }} catch (err) {{
      statusEl.textContent = "Mic blocked or unavailable: " + (err.message || err);
      renderIdle("Allow microphone access to use the tuner");
    }}
  }}

  function stopTuner() {{
    if (rafId) cancelAnimationFrame(rafId);
    rafId = null;
    if (source) {{
      try {{ source.disconnect(); }} catch (e) {{}}
      source = null;
    }}
    if (mediaStream) {{
      mediaStream.getTracks().forEach((t) => t.stop());
      mediaStream = null;
    }}
    if (audioCtx) {{
      audioCtx.close().catch(() => {{}});
      audioCtx = null;
    }}
    analyser = null;
    buf = null;
    startBtn.disabled = false;
    stopBtn.disabled = true;
    statusEl.textContent = "Stopped — press Start Tuner to listen again";
    renderIdle("Tuner stopped");
  }}

  startBtn.addEventListener("click", startTuner);
  stopBtn.addEventListener("click", stopTuner);
  initStringButtons();
  renderFeedbackIdle();
}})();
</script>
</body>
</html>"""


def render_live_tuner(
    st_module: Any,
    *,
    key_prefix: str = "practice_tuner",
    target_note: str | None = None,
    expected_note: str | None = None,
    string_targets: list[str] | None = None,
    height: int = 520,
    display_mode: str = "concert",
    concert_to_written_semitones: int = 0,
    instrument_label: str = "",
) -> None:
    """Embed the real-time tuner via Streamlit ``components.html``."""
    import streamlit.components.v1 as components

    config = live_tuner_config(
        key_prefix=key_prefix,
        target_note=target_note,
        expected_note=expected_note,
        string_targets=string_targets,
        display_mode=display_mode,
        concert_to_written_semitones=concert_to_written_semitones,
        instrument_label=instrument_label,
    )
    widget_html = build_live_tuner_html(config)
    components.html(widget_html, height=height, scrolling=False)
