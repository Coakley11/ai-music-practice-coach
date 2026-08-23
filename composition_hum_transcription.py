"""Composition Studio — monophonic hum/sing → melody-event transcription.

Reuses librosa/pyin patterns from Practice pitch tools without modifying shared
Upload/Metrics analysis contracts. Composition-owned: concert pitch only,
BPM/meter quantization, key-aware spelling (not forced diatonic).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

try:
    import librosa
except ImportError:  # pragma: no cover
    librosa = None  # type: ignore[assignment]

from music_theory import spell_note_in_key

# Tunable segmentation (conservative — favor fewer, clearer notes).
_MIN_NOTE_SEC = 0.09
_MERGE_GAP_SEC = 0.08
_REST_GAP_SEC = 0.18
_CENTS_MERGE = 55.0  # vibrato / wobble within one note
_OCTAVE_JUMP_CENTS = 900.0  # ~7.5 semitones — keep legitimate leaps, filter wild spikes
_MIN_VOICED_RATIO = 0.12
_MIN_EVENTS = 1

# Duration grid in beats (1.0 = one BPM pulse).
_DURATION_GRID_SIMPLE = (0.5, 1.0, 1.5, 2.0, 3.0, 4.0)
_DURATION_GRID_COMPOUND = (0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0)


def hum_analysis_available() -> bool:
    return librosa is not None


def parse_meter(meter: str) -> tuple[int, int]:
    text = str(meter or "4/4").strip().replace(" ", "")
    if "/" not in text:
        return 4, 4
    try:
        num_s, den_s = text.split("/", 1)
        return max(1, int(num_s)), max(1, int(den_s))
    except ValueError:
        return 4, 4


def is_compound_meter(meter: str) -> bool:
    num, den = parse_meter(meter)
    return den == 8 and num % 3 == 0 and num >= 6


def duration_grid_for_meter(meter: str) -> tuple[float, ...]:
    return _DURATION_GRID_COMPOUND if is_compound_meter(meter) else _DURATION_GRID_SIMPLE


def quantize_beats(value: float, *, meter: str = "4/4") -> float:
    grid = duration_grid_for_meter(meter)
    v = max(0.25, float(value))
    return float(min(grid, key=lambda g: abs(g - v)))


def midi_from_hz(hz: float) -> float:
    if hz <= 0 or not math.isfinite(hz):
        return float("nan")
    return 69.0 + 12.0 * math.log2(hz / 440.0)


def spell_midi_in_key(midi: int, key: str) -> str:
    """Concert pitch name with octave, spelled for Composition key (Db vs C#)."""
    m = int(midi)
    pc = m % 12
    name = spell_note_in_key(pc, key)
    octave = m // 12 - 1
    return f"{name}{octave}"


def load_hum_audio_mono(audio_bytes: bytes, *, sr: int = 22050) -> tuple[np.ndarray, int]:
    """Decode/normalize hum audio. Raises RuntimeError if librosa missing."""
    if librosa is None:
        raise RuntimeError("Hum transcription needs librosa (see requirements.txt).")
    if not audio_bytes:
        raise ValueError("No audio data.")
    # Prefer tuner_tone loader when available (same decode path as Practice pitch tools).
    try:
        from tuner_tone import load_audio_mono

        y, out_sr = load_audio_mono(audio_bytes, sr=sr)
    except Exception:
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            path = tmp.name
        try:
            y, out_sr = librosa.load(path, sr=sr, mono=True)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
    y = np.asarray(y, dtype=float)
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    if peak > 1e-9:
        y = y / peak
    return y, int(out_sr)


def extract_f0_track(y: np.ndarray, sr: int) -> dict[str, Any]:
    """Return pyin F0 + times. Uses the same backend family as Practice pitch tools."""
    if librosa is None:
        return {"f0": np.array([]), "times": np.array([]), "voiced_ratio": 0.0, "available": False}
    try:
        f0, voiced_flag, _ = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
        )
        f0 = np.asarray(f0, dtype=float)
        times = librosa.times_like(f0, sr=sr)
        if voiced_flag is not None:
            voiced_mask = np.asarray(voiced_flag, dtype=bool)
            f0 = np.where(voiced_mask, f0, np.nan)
        voiced = f0[~np.isnan(f0)]
        ratio = float(len(voiced) / max(1, len(f0)))
        return {
            "f0": f0,
            "times": np.asarray(times, dtype=float),
            "voiced_ratio": ratio,
            "available": True,
        }
    except Exception:
        return {"f0": np.array([]), "times": np.array([]), "voiced_ratio": 0.0, "available": False}


def _cents_delta(a_midi: float, b_midi: float) -> float:
    return abs(float(a_midi) - float(b_midi)) * 100.0


def segment_f0_track(
    f0: np.ndarray,
    times: np.ndarray,
    *,
    min_note_sec: float = _MIN_NOTE_SEC,
    cents_merge: float = _CENTS_MERGE,
    merge_gap_sec: float = _MERGE_GAP_SEC,
    rest_gap_sec: float = _REST_GAP_SEC,
) -> list[dict[str, Any]]:
    """Convert continuous F0 into discrete note/rest segments (synthetic-testable)."""
    f0 = np.asarray(f0, dtype=float)
    times = np.asarray(times, dtype=float)
    if len(f0) == 0 or len(times) == 0:
        return []

    # Median-smooth voiced MIDI to reduce vibrato micro-notes.
    midi = np.array([midi_from_hz(hz) if not np.isnan(hz) else np.nan for hz in f0], dtype=float)
    voiced_idx = np.where(~np.isnan(midi))[0]
    if len(voiced_idx) >= 5:
        smoothed = midi.copy()
        for i in voiced_idx:
            lo = max(0, i - 2)
            hi = min(len(midi), i + 3)
            window = midi[lo:hi]
            window = window[~np.isnan(window)]
            if len(window):
                smoothed[i] = float(np.median(window))
        midi = smoothed

    raw: list[dict[str, Any]] = []
    i = 0
    n = len(midi)
    while i < n:
        if np.isnan(midi[i]):
            i += 1
            continue
        start_i = i
        vals = [float(midi[i])]
        i += 1
        while i < n and not np.isnan(midi[i]):
            # Octave-spike filter: skip single-frame wild jumps, keep legitimate leaps.
            if _cents_delta(midi[i], vals[-1]) > _OCTAVE_JUMP_CENTS and i + 1 < n:
                nxt = midi[i + 1]
                if not np.isnan(nxt) and _cents_delta(nxt, vals[-1]) < cents_merge:
                    i += 1
                    continue
            if _cents_delta(midi[i], float(np.median(vals))) <= cents_merge:
                vals.append(float(midi[i]))
                i += 1
            else:
                break
        end_i = i - 1
        t0 = float(times[start_i])
        t1 = float(times[min(end_i + 1, len(times) - 1)])
        if end_i + 1 < len(times):
            t1 = float(times[end_i + 1])
        dur = max(0.0, t1 - t0)
        if dur < min_note_sec:
            continue
        med = float(np.median(vals))
        std_cents = float(np.std([(v - med) * 100.0 for v in vals])) if len(vals) > 1 else 0.0
        conf = max(0.15, min(1.0, 1.0 - (std_cents / 80.0)))
        raw.append(
            {
                "kind": "note",
                "midi_f": med,
                "midi": int(round(med)),
                "start_sec": t0,
                "end_sec": t1,
                "duration_sec": dur,
                "confidence": conf,
            }
        )

    # Merge adjacent same-pitch notes separated by tiny gaps (re-attack vs wobble).
    merged: list[dict[str, Any]] = []
    for seg in raw:
        if (
            merged
            and merged[-1]["kind"] == "note"
            and seg["kind"] == "note"
            and merged[-1]["midi"] == seg["midi"]
            and (seg["start_sec"] - merged[-1]["end_sec"]) <= merge_gap_sec
        ):
            merged[-1]["end_sec"] = seg["end_sec"]
            merged[-1]["duration_sec"] = merged[-1]["end_sec"] - merged[-1]["start_sec"]
            merged[-1]["confidence"] = min(float(merged[-1]["confidence"]), float(seg["confidence"]))
        else:
            # Insert rest for meaningful silence.
            if merged and (seg["start_sec"] - merged[-1]["end_sec"]) >= rest_gap_sec:
                gap0 = float(merged[-1]["end_sec"])
                gap1 = float(seg["start_sec"])
                merged.append(
                    {
                        "kind": "rest",
                        "midi_f": None,
                        "midi": None,
                        "start_sec": gap0,
                        "end_sec": gap1,
                        "duration_sec": gap1 - gap0,
                        "confidence": 1.0,
                    }
                )
            merged.append(seg)
    return merged


def segments_to_melody_events(
    segments: list[dict[str, Any]],
    *,
    bpm: int,
    meter: str,
    key: str,
) -> list[dict[str, Any]]:
    """Quantize segments into Composition melody events (beats at Composition BPM)."""
    bpm_f = max(40.0, float(bpm or 96))
    sec_per_beat = 60.0 / bpm_f
    events: list[dict[str, Any]] = []
    cursor_beat = 0.0
    for seg in segments:
        dur_sec = float(seg.get("duration_sec") or 0.0)
        dur_beats = quantize_beats(dur_sec / sec_per_beat, meter=meter)
        if dur_beats < 0.5 and seg.get("kind") == "rest":
            # Tiny rests collapse into timing; keep note starts honest via beat cursor.
            cursor_beat += dur_beats
            continue
        start_beat = quantize_beats(
            float(seg.get("start_sec") or 0.0) / sec_per_beat,
            meter=meter,
        ) if events else cursor_beat
        # Prefer sequential packing for editable phrases.
        start_beat = cursor_beat
        if seg.get("kind") == "rest":
            events.append(
                {
                    "pitch": "rest",
                    "midi": None,
                    "duration_beats": dur_beats,
                    "beat": start_beat,
                    "measure": int(start_beat // _beats_per_bar(meter)) + 1,
                    "is_rest": True,
                    "confidence": float(seg.get("confidence") or 1.0),
                    "uncertain": False,
                }
            )
        else:
            midi_i = int(seg.get("midi") or round(float(seg.get("midi_f") or 60)))
            conf = float(seg.get("confidence") or 0.5)
            pitch = spell_midi_in_key(midi_i, key)
            events.append(
                {
                    "pitch": pitch,
                    "midi": midi_i,
                    "duration_beats": dur_beats,
                    "beat": start_beat,
                    "measure": int(start_beat // _beats_per_bar(meter)) + 1,
                    "is_rest": False,
                    "confidence": conf,
                    "uncertain": conf < 0.45,
                }
            )
        cursor_beat = start_beat + dur_beats
    return events


def _beats_per_bar(meter: str) -> float:
    """Bar length in Composition BPM pulses — matches composition_preview (numerator)."""
    num, _den = parse_meter(meter)
    return float(num)


def transcribe_hum_audio(
    audio_bytes: bytes,
    *,
    bpm: int,
    meter: str,
    key: str,
    sr: int = 22050,
) -> dict[str, Any]:
    """Full hum → proposal events. Never mutates a Composition document."""
    result: dict[str, Any] = {
        "status": "unclear",
        "message": "",
        "events": [],
        "confidence": 0.0,
        "voiced_ratio": 0.0,
        "available": hum_analysis_available(),
        "monophonic": True,
    }
    if not hum_analysis_available():
        result["status"] = "unavailable"
        result["message"] = (
            "Hum transcription needs librosa on this server. "
            "You can still explore melody concepts or write notes manually."
        )
        return result
    if not audio_bytes:
        result["message"] = "No recording found — hum or sing a short melody, then analyze."
        return result

    try:
        y, out_sr = load_hum_audio_mono(audio_bytes, sr=sr)
    except Exception as exc:
        result["status"] = "unclear"
        result["message"] = f"Could not read that recording ({exc}). Try again with a short clear hum."
        return result

    duration = float(len(y) / max(1, out_sr))
    if duration < 0.35:
        result["message"] = "Recording is too short — try humming at least half a second."
        return result

    track = extract_f0_track(y, out_sr)
    if not track.get("available"):
        result["status"] = "unavailable"
        result["message"] = "Pitch detection could not run for this recording."
        return result

    voiced_ratio = float(track.get("voiced_ratio") or 0.0)
    result["voiced_ratio"] = voiced_ratio
    if voiced_ratio < _MIN_VOICED_RATIO:
        result["message"] = (
            "We could not hear a clear single melodic line. "
            "Try humming one note at a time in a quieter space."
        )
        return result

    segments = segment_f0_track(track["f0"], track["times"])
    note_segs = [s for s in segments if s.get("kind") == "note"]
    if len(note_segs) < _MIN_EVENTS:
        result["message"] = "No stable notes detected — try a clearer, more sustained hum."
        return result

    events = segments_to_melody_events(segments, bpm=int(bpm), meter=str(meter), key=str(key))
    pitched = [e for e in events if not e.get("is_rest")]
    if not pitched:
        result["message"] = "No pitched notes after quantization — try again with longer tones."
        return result

    conf = float(np.mean([float(e.get("confidence") or 0.5) for e in pitched]))
    uncertain = any(bool(e.get("uncertain")) for e in pitched)
    result["events"] = events
    result["confidence"] = conf
    if uncertain or conf < 0.55:
        result["status"] = "uncertain"
        result["message"] = (
            "We heard a melody, but some notes look uncertain — check them before using this."
        )
    else:
        result["status"] = "usable"
        result["message"] = "We heard this melody — check the notes below before using it."
    return result


def empty_hum_proposal() -> dict[str, Any]:
    return {
        "status": "",
        "message": "",
        "events": [],
        "confidence": 0.0,
        "voiced_ratio": 0.0,
        "available": hum_analysis_available(),
    }


def duration_choice_labels(meter: str = "4/4") -> list[tuple[float, str]]:
    """Musician-facing duration options for the event editor."""
    if is_compound_meter(meter):
        return [
            (0.5, "short"),
            (1.0, "eighth pulse"),
            (1.5, "dotted grouping"),
            (2.0, "two pulses"),
            (3.0, "dotted quarter group"),
            (6.0, "full bar (6/8)"),
        ]
    return [
        (0.5, "eighth"),
        (1.0, "quarter"),
        (1.5, "dotted quarter"),
        (2.0, "half"),
        (3.0, "dotted half"),
        (4.0, "whole"),
    ]


def nudge_event_pitch(events: list[dict[str, Any]], index: int, *, semitones: int, key: str) -> list[dict[str, Any]]:
    out = [dict(e) for e in events]
    if index < 0 or index >= len(out):
        return out
    ev = out[index]
    if ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest":
        return out
    midi = ev.get("midi")
    try:
        midi_i = int(midi) if midi is not None else 60
    except (TypeError, ValueError):
        midi_i = 60
    midi_i = max(36, min(84, midi_i + int(semitones)))
    ev["midi"] = midi_i
    ev["pitch"] = spell_midi_in_key(midi_i, key)
    ev["uncertain"] = False
    out[index] = ev
    return out


def set_event_duration(
    events: list[dict[str, Any]],
    index: int,
    duration_beats: float,
    *,
    meter: str = "4/4",
) -> list[dict[str, Any]]:
    out = [dict(e) for e in events]
    if index < 0 or index >= len(out):
        return out
    dur = quantize_beats(float(duration_beats), meter=meter)
    out[index]["duration_beats"] = dur
    # Re-pack beat positions sequentially.
    cursor = 0.0
    bpb = _beats_per_bar(meter)
    for ev in out:
        ev["beat"] = cursor
        ev["measure"] = int(cursor // bpb) + 1
        cursor += float(ev.get("duration_beats") or 1.0)
    return out


def delete_melody_event(events: list[dict[str, Any]], index: int, *, meter: str = "4/4") -> list[dict[str, Any]]:
    out = [dict(e) for i, e in enumerate(events) if i != index]
    cursor = 0.0
    bpb = _beats_per_bar(meter)
    for ev in out:
        ev["beat"] = cursor
        ev["measure"] = int(cursor // bpb) + 1
        cursor += float(ev.get("duration_beats") or 1.0)
    return out


def insert_melody_event(
    events: list[dict[str, Any]],
    index: int,
    *,
    pitch_midi: int = 60,
    duration_beats: float = 1.0,
    key: str = "C",
    meter: str = "4/4",
    is_rest: bool = False,
) -> list[dict[str, Any]]:
    out = [dict(e) for e in events]
    idx = max(0, min(len(out), index))
    dur = quantize_beats(duration_beats, meter=meter)
    if is_rest:
        new_ev: dict[str, Any] = {
            "pitch": "rest",
            "midi": None,
            "duration_beats": dur,
            "beat": 0.0,
            "measure": 1,
            "is_rest": True,
            "confidence": 1.0,
            "uncertain": False,
        }
    else:
        midi_i = int(pitch_midi)
        new_ev = {
            "pitch": spell_midi_in_key(midi_i, key),
            "midi": midi_i,
            "duration_beats": dur,
            "beat": 0.0,
            "measure": 1,
            "is_rest": False,
            "confidence": 1.0,
            "uncertain": False,
        }
    out.insert(idx, new_ev)
    cursor = 0.0
    bpb = _beats_per_bar(meter)
    for ev in out:
        ev["beat"] = cursor
        ev["measure"] = int(cursor // bpb) + 1
        cursor += float(ev.get("duration_beats") or 1.0)
    return out


def format_heard_line(events: list[dict[str, Any]], *, meter: str = "4/4") -> str:
    """Compact musician-facing summary: G4 eighth · A4 quarter …"""
    labels = {d: name for d, name in duration_choice_labels(meter)}
    parts: list[str] = []
    for ev in events:
        dur = float(ev.get("duration_beats") or 1.0)
        dur_label = labels.get(dur) or f"{dur:g} beat"
        if ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest":
            parts.append(f"rest {dur_label}")
        else:
            flag = " ?" if ev.get("uncertain") else ""
            parts.append(f"{ev.get('pitch') or '?'} {dur_label}{flag}")
    return "   ".join(parts)

