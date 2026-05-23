"""Pitch detection, tuning feedback, and tone-development analysis (future-ready core)."""

from __future__ import annotations

import io
import math
import tempfile
from dataclasses import dataclass, field
from typing import Any

import numpy as np

try:
    import librosa
except ImportError:
    librosa = None  # type: ignore[assignment]

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


@dataclass
class PitchReading:
    """Single detected pitch snapshot — extensible for live graphs."""

    note_name: str
    octave: int
    frequency_hz: float
    cents_offset: float
    target_note: str | None = None
    in_tune: bool = False


@dataclass
class TonePracticeResult:
    """Sustain / tone consistency analysis from a recorded clip."""

    duration_sec: float
    median_note: str
    target_note: str | None
    mean_cents: float
    max_cents_drift: float
    pitch_stability_score: float  # 0–100
    volume_stability_score: float
    sustain_seconds: float
    feedback: list[str] = field(default_factory=list)
    pitch_trace_hz: list[float] = field(default_factory=list)
    time_trace_sec: list[float] = field(default_factory=list)


@dataclass
class InstrumentTunerProfile:
    instrument: str
    mode: str  # strings | wind | voice | chromatic
    string_targets: list[str] = field(default_factory=list)
    hint: str = ""
    tone_focus: list[str] = field(default_factory=list)


def _profile_for_instrument(instrument: str, *, sax_type: str = "") -> InstrumentTunerProfile:
    inst = str(instrument or "Piano").strip()
    if inst == "Guitar":
        return InstrumentTunerProfile(
            instrument=inst,
            mode="strings",
            string_targets=["E2", "A2", "D3", "G3", "B3", "E4"],
            hint="Tune low E → high E. Pluck one string at a time near the 12th fret for stability.",
            tone_focus=["Even attack", "Clean decay", "No buzzing"],
        )
    if inst == "Bass":
        return InstrumentTunerProfile(
            instrument=inst,
            mode="strings",
            string_targets=["E1", "A1", "D2", "G2"],
            hint="Tune thickest to thinnest. Check 12th-fret harmonics if open strings waver.",
            tone_focus=["Round attack", "Even note length"],
        )
    if inst == "Saxophone":
        low = sax_type.lower()
        if "tenor" in low or "soprano" in low:
            hint = "Bb instrument — match written fingerings; long tones help intonation."
        else:
            hint = "Eb instrument (Alto/Baritone) — concert pitch differs from written chart."
        return InstrumentTunerProfile(
            instrument=inst,
            mode="wind",
            hint=hint,
            tone_focus=[
                "Long-tone sustain",
                "Steady pitch center",
                "Consistent air support",
                "Smooth attacks",
            ],
        )
    if inst in ("Flute", "Trumpet", "Clarinet"):
        return InstrumentTunerProfile(
            instrument=inst,
            mode="wind",
            hint="Center pitch with steady air. Start soft, then add volume once pitch locks.",
            tone_focus=["Pitch center", "Even tone color", "Controlled vibrato later"],
        )
    if inst == "Voice":
        return InstrumentTunerProfile(
            instrument=inst,
            mode="voice",
            hint="Hum or sing one vowel. Focus on breath support and steady pitch.",
            tone_focus=["Pitch center", "Sustain", "Volume consistency"],
        )
    if inst == "Violin":
        return InstrumentTunerProfile(
            instrument=inst,
            mode="strings",
            string_targets=["G3", "D4", "A4", "E5"],
            hint="Tune G → E. Use light bow pressure for tuning checks.",
            tone_focus=["Straight tone", "Even bow speed"],
        )
    return InstrumentTunerProfile(
        instrument=inst,
        mode="chromatic",
        hint="Play a clear single note. Reduce background noise for best detection.",
        tone_focus=["Steady pitch", "Even tone"],
    )


def hz_to_note_parts(hz: float) -> tuple[str, int, float]:
    if hz <= 0 or not math.isfinite(hz):
        return ("—", 0, 0.0)
    midi = 69 + 12 * math.log2(hz / 440.0)
    midi_round = int(round(midi))
    cents = (midi - midi_round) * 100
    name = NOTE_NAMES[midi_round % 12]
    octave = midi_round // 12 - 1
    return name, octave, float(cents)


def note_label(name: str, octave: int) -> str:
    if name == "—":
        return "—"
    return f"{name}{octave}"


def parse_note_token(token: str) -> int | None:
    """Parse like E2, A#3, Bb4 to MIDI."""
    t = str(token or "").strip().replace("♯", "#").replace("♭", "b")
    if not t:
        return None
    name = t[0].upper()
    if name not in "ABCDEFG":
        return None
    rest = t[1:]
    base = NOTE_NAMES.index(name)
    if rest.startswith("#"):
        base = (base + 1) % 12
        rest = rest[1:]
    elif rest.startswith("b"):
        base = (base - 1) % 12
        rest = rest[1:]
    try:
        octave = int(rest)
    except ValueError:
        return None
    return (octave + 1) * 12 + base


def cents_to_target(hz: float, target_token: str) -> float:
    target_midi = parse_note_token(target_token)
    if target_midi is None or hz <= 0:
        return 0.0
    midi = 69 + 12 * math.log2(hz / 440.0)
    return (midi - target_midi) * 100


def load_audio_mono(audio_bytes: bytes, *, sr: int = 22050) -> tuple[np.ndarray, int]:
    if not audio_bytes:
        raise ValueError("No audio data.")
    if librosa is None:
        raise RuntimeError("Pitch tools need librosa and soundfile (see requirements.txt).")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        path = tmp.name
    try:
        y, out_sr = librosa.load(path, sr=sr, mono=True)
    finally:
        import os

        try:
            os.unlink(path)
        except OSError:
            pass
    return y, out_sr


def detect_pitch_from_audio(
    audio_bytes: bytes,
    *,
    target_note: str | None = None,
    sr: int = 22050,
) -> PitchReading | None:
    """Detect dominant pitch from a short microphone clip."""
    y, out_sr = load_audio_mono(audio_bytes, sr=sr)
    if len(y) < out_sr * 0.15:
        return None
    y = y / (np.max(np.abs(y)) + 1e-9)
    if librosa is None:
        return None
    f0, voiced_flag, _ = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("E1"),
        fmax=librosa.note_to_hz("C7"),
        sr=out_sr,
    )
    voiced = f0[voiced_flag] if voiced_flag is not None else f0[~np.isnan(f0)]
    voiced = voiced[np.isfinite(voiced)]
    if len(voiced) < 3:
        return None
    hz = float(np.median(voiced))
    name, octave, cents = hz_to_note_parts(hz)
    if target_note:
        cents = cents_to_target(hz, target_note)
    in_tune = abs(cents) <= 8
    return PitchReading(
        note_name=note_label(name, octave),
        octave=octave,
        frequency_hz=hz,
        cents_offset=float(cents),
        target_note=target_note,
        in_tune=in_tune,
    )


def analyze_tone_practice(
    audio_bytes: bytes,
    *,
    target_note: str | None = None,
    min_sustain_sec: float = 3.0,
    sr: int = 22050,
) -> TonePracticeResult | None:
    """Analyze sustain, pitch drift, and volume consistency."""
    y, out_sr = load_audio_mono(audio_bytes, sr=sr)
    dur = len(y) / out_sr
    if dur < 0.5 or librosa is None:
        return None
    y = y / (np.max(np.abs(y)) + 1e-9)
    f0, voiced_flag, _ = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("E2"),
        fmax=librosa.note_to_hz("C7"),
        sr=out_sr,
    )
    times = librosa.times_like(f0, sr=out_sr)
    mask = voiced_flag if voiced_flag is not None else ~np.isnan(f0)
    hz_series = f0[mask]
    t_series = times[mask]
    if len(hz_series) < 5:
        return None

    midi_series = 69 + 12 * np.log2(hz_series / 440.0)
    if target_note:
        tm = parse_note_token(target_note)
        if tm is not None:
            cents_series = (midi_series - tm) * 100
        else:
            cents_series = (midi_series - np.round(midi_series)) * 100
    else:
        cents_series = (midi_series - np.round(midi_series)) * 100

    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    rms_t = librosa.frames_to_time(np.arange(len(rms)), sr=out_sr, hop_length=512)

    mean_cents = float(np.mean(cents_series))
    max_drift = float(np.max(np.abs(cents_series - mean_cents)))
    pitch_std = float(np.std(cents_series))
    pitch_score = max(0.0, min(100.0, 100.0 - pitch_std * 4.5))

    vol_std = float(np.std(rms))
    vol_mean = float(np.mean(rms)) + 1e-9
    vol_score = max(0.0, min(100.0, 100.0 - (vol_std / vol_mean) * 120))

    median_hz = float(np.median(hz_series))
    n_name, n_oct, _ = hz_to_note_parts(median_hz)
    median_note = note_label(n_name, n_oct)

    # voiced duration estimate
    hop = 512
    sustain = float(np.sum(mask)) * hop / out_sr

    feedback: list[str] = []
    tail = cents_series[int(len(cents_series) * 0.65) :]
    if len(tail) > 2 and float(np.mean(tail)) < -12:
        feedback.append("Pitch drifted **flat** near the end — check air support or embouchure.")
    elif len(tail) > 2 and float(np.mean(tail)) > 12:
        feedback.append("Pitch drifted **sharp** near the end — relax jaw/throat tension.")

    if pitch_score >= 78:
        feedback.append("Good **sustain stability** — pitch center held well.")
    elif pitch_score >= 55:
        feedback.append("Moderate pitch movement — try a slower, steadier long tone.")
    else:
        feedback.append("Pitch was **unstable** — shorten the note and reset breath support.")

    if vol_score < 50 and len(rms) > 4:
        late = rms[int(len(rms) * 0.55) :]
        if len(late) and float(np.mean(late)) < float(np.mean(rms[: max(1, len(rms) // 3)])) * 0.65:
            feedback.append("**Air support weakened** after the first few seconds.")

    attack_frames = rms[: max(2, len(rms) // 10)]
    if len(attack_frames) >= 2 and float(np.max(attack_frames)) > vol_mean * 2.2:
        feedback.append("**Tone attack** was aggressive — start softer, then bloom into the note.")

    if sustain >= min_sustain_sec and pitch_score >= 70 and vol_score >= 60:
        feedback.append(f"Strong **{min_sustain_sec:.0f}s+ hold** — ready to apply this to the song.")

    if not feedback:
        feedback.append("Keep practicing steady long tones before jumping into fast passages.")

    return TonePracticeResult(
        duration_sec=dur,
        median_note=median_note,
        target_note=target_note,
        mean_cents=mean_cents,
        max_cents_drift=max_drift,
        pitch_stability_score=pitch_score,
        volume_stability_score=vol_score,
        sustain_seconds=sustain,
        feedback=feedback,
        pitch_trace_hz=[float(x) for x in hz_series[:: max(1, len(hz_series) // 80)]],
        time_trace_sec=[float(x) for x in t_series[:: max(1, len(t_series) // 80)]],
    )


def cents_meter_html(cents: float, *, width_pct: float | None = None) -> str:
    """HTML tuning meter: flat ← center → sharp."""
    clamped = max(-50.0, min(50.0, float(cents)))
    if width_pct is None:
        width_pct = 50 + (clamped / 50.0) * 45
    in_tune = abs(clamped) <= 8
    color = "#22c55e" if in_tune else ("#f59e0b" if abs(clamped) <= 20 else "#ef4444")
    label = "In tune ✓" if in_tune else (
        f"{abs(clamped):.0f}¢ sharp" if clamped > 0 else f"{abs(clamped):.0f}¢ flat"
    )
    return f"""
    <div style="font-family:system-ui,sans-serif;margin:0.5rem 0;">
      <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:#64748b;margin-bottom:4px;">
        <span>Too flat</span><span style="color:{color};font-weight:600;">{label}</span><span>Too sharp</span>
      </div>
      <div style="position:relative;height:12px;background:linear-gradient(90deg,#3b82f6,#e2e8f0 48%,#e2e8f0 52%,#f97316);border-radius:6px;">
        <div style="position:absolute;left:50%;top:0;width:2px;height:100%;background:#334155;transform:translateX(-50%);"></div>
        <div style="position:absolute;left:{width_pct:.1f}%;top:-3px;width:14px;height:18px;background:{color};border-radius:3px;transform:translateX(-50%);box-shadow:0 1px 4px rgba(0,0,0,.25);"></div>
      </div>
    </div>
    """


def pitch_trace_svg(
    times: list[float],
    hz_values: list[float],
    *,
    target_hz: float | None = None,
    width: int = 400,
    height: int = 80,
) -> str:
    if len(times) < 2 or len(hz_values) < 2:
        return ""
    t0, t1 = min(times), max(times) or 1.0
    hz_arr = np.array(hz_values, dtype=float)
    lo, hi = float(np.min(hz_arr)), float(np.max(hz_arr))
    if hi - lo < 1:
        hi += 20
        lo -= 20
    pts = []
    for t, h in zip(times, hz_values):
        x = 8 + (t - t0) / (t1 - t0 + 1e-9) * (width - 16)
        y = height - 8 - (h - lo) / (hi - lo + 1e-9) * (height - 16)
        pts.append(f"{x:.1f},{y:.1f}")
    target_line = ""
    if target_hz and lo <= target_hz <= hi:
        ty = height - 8 - (target_hz - lo) / (hi - lo + 1e-9) * (height - 16)
        target_line = f'<line x1="8" y1="{ty:.1f}" x2="{width-8}" y2="{ty:.1f}" stroke="#94a3b8" stroke-dasharray="4"/>'
    return (
        f'<svg width="{width}" height="{height}" style="max-width:100%;">'
        f'<polyline fill="none" stroke="#6366f1" stroke-width="2" points="{" ".join(pts)}"/>'
        f"{target_line}</svg>"
    )


def librosa_available() -> bool:
    return librosa is not None
