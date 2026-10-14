"""MC4 — audio → performed notes for span Mission analysis (transcription only).

Kept apart from alignment and scoring so a beat / bar nudge re-assigns the same notes
without re-running pitch detection. Results are cached by audio fingerprint.

Notes are sounding (concert) pitch — the microphone hears the instrument as it sounds.
"""

from __future__ import annotations

import hashlib
import os
from collections import OrderedDict
from typing import Any

import numpy as np

_CACHE: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
_CACHE_MAX = 16
TRANSCRIPTION_VERSION = 2

# A note needs this many consecutive stable frames (~46 ms at 22.05 kHz / hop 256 … 512).
_MIN_FRAMES = 3


def audio_fingerprint(audio: bytes) -> str:
    return hashlib.sha256(bytes(audio or b"")).hexdigest()


def _load(audio: bytes, filename: str) -> tuple[np.ndarray, int]:
    from recording_analysis import _load_audio

    y, sr, path = _load_audio(bytes(audio), str(filename or "take.wav"))
    try:
        os.unlink(path)
    except OSError:
        pass
    if sr > 22050:
        import librosa

        y = librosa.resample(y, orig_sr=sr, target_sr=22050)
        sr = 22050
    return np.asarray(y, dtype=np.float32), int(sr)


def _segment_notes(
    f0: np.ndarray, voiced: np.ndarray, times: np.ndarray, onset_times: np.ndarray, rms: np.ndarray,
) -> list[dict[str, Any]]:
    """Runs of a stable rounded pitch, also split at detected onsets (repeated notes)."""
    midi = np.full(f0.shape, np.nan)
    ok = voiced & np.isfinite(f0) & (f0 > 0)
    midi[ok] = 69 + 12 * np.log2(f0[ok] / 440.0)
    rounded = np.where(np.isfinite(midi), np.round(midi), np.nan)
    onset_frames = set(int(np.argmin(np.abs(times - t))) for t in onset_times)
    notes: list[dict[str, Any]] = []
    start = None
    cur = None
    loud = float(np.percentile(rms, 90)) if rms.size else 0.0

    def close(end: int) -> None:
        if start is None or cur is None:
            return
        if end - start >= _MIN_FRAMES:
            seg = midi[start:end]
            seg = seg[np.isfinite(seg)]
            level = float(np.mean(rms[start:end])) if rms.size >= end else 0.0
            if seg.size and (loud <= 0 or level >= 0.08 * loud):
                notes.append(
                    {
                        "t": round(float(times[start]), 4),
                        "dur": round(float(times[min(end, len(times) - 1)] - times[start]), 4),
                        "midi": int(round(float(np.median(seg)))),
                        "cents": round(float(np.median(seg) - round(float(np.median(seg)))) * 100, 1),
                    }
                )

    for i in range(len(rounded)):
        r = rounded[i]
        if not np.isfinite(r):
            close(i)
            start, cur = None, None
            continue
        if cur is None:
            start, cur = i, r
            continue
        if r != cur or (i in onset_frames and i - start >= _MIN_FRAMES):
            # A pitch change is real only if it holds (vibrato / glide frames are absorbed).
            hold = rounded[i : i + _MIN_FRAMES]
            if r != cur and not np.all(hold == r):
                continue
            close(i)
            start, cur = i, r
    close(len(rounded))
    return _merge_fragments(notes)


_MIN_NOTE_SEC = 0.07
_GAP_MERGE_SEC = 0.05


def _merge_fragments(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fold onset/release slivers into the neighbouring note of the same pitch; drop the rest."""
    out: list[dict[str, Any]] = []
    for n in notes:
        if out and n["midi"] == out[-1]["midi"]:
            prev = out[-1]
            gap = n["t"] - (prev["t"] + prev["dur"])
            if gap <= _GAP_MERGE_SEC and (n["dur"] < _MIN_NOTE_SEC * 1.5 or prev["dur"] < _MIN_NOTE_SEC * 1.5):
                prev["dur"] = round(n["t"] + n["dur"] - prev["t"], 4)
                continue
        out.append(dict(n))
    return [n for n in out if n["dur"] >= _MIN_NOTE_SEC]


def transcribe(audio: bytes, filename: str = "take.wav") -> dict[str, Any]:
    """Detected notes, onsets (with strengths), beats and tempo of a take (cached)."""
    fp = audio_fingerprint(audio)
    hit = _CACHE.get(fp)
    if hit is not None:
        _CACHE.move_to_end(fp)
        return hit
    import librosa

    y, sr = _load(audio, filename)
    hop = 256
    duration = float(len(y) / sr) if sr else 0.0
    if y.size == 0:
        result = {"fingerprint": fp, "version": TRANSCRIPTION_VERSION, "duration": 0.0, "notes": [],
                  "onsets": [], "onset_strengths": [], "beats": [], "tempo": None}
    else:
        # YIN with an energy gate: fast enough to run once per take (pYIN is ~40x slower here),
        # accurate for a single melodic line, which is what a Mission take is.
        f0 = librosa.yin(y, fmin=librosa.note_to_hz("E2"), fmax=librosa.note_to_hz("C7"), sr=sr,
                         hop_length=hop, frame_length=2048)
        times = librosa.times_like(f0, sr=sr, hop_length=hop)
        rms = librosa.feature.rms(y=y, hop_length=hop, frame_length=2048)[0]
        rms = rms[: len(times)] if rms.size >= len(times) else np.pad(rms, (0, len(times) - rms.size))
        gate = 0.06 * float(np.percentile(rms, 95)) if rms.size else 0.0
        voiced = rms > gate
        env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
        onset_frames = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=hop, backtrack=False)
        onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop)
        strengths = [float(env[min(int(f), len(env) - 1)]) for f in onset_frames]
        notes = _segment_notes(np.asarray(f0), np.asarray(voiced, dtype=bool), times, onset_times, rms)
        try:
            tempo, beat_frames = librosa.beat.beat_track(onset_envelope=env, sr=sr, hop_length=hop)
            tempo_val = float(np.atleast_1d(tempo)[0]) if np.size(tempo) else None
            beats = [round(float(t), 4) for t in librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop)]
        except Exception:
            tempo_val, beats = None, []
        result = {
            "fingerprint": fp,
            "version": TRANSCRIPTION_VERSION,
            "duration": round(duration, 4),
            "notes": notes,
            "onsets": [round(float(t), 4) for t in onset_times],
            "onset_strengths": [round(s, 4) for s in strengths],
            "beats": beats,
            "tempo": round(tempo_val, 2) if tempo_val else None,
        }
    _CACHE[fp] = result
    if len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return result


def session_transcription(session: dict[str, Any], audio: bytes, filename: str = "take.wav") -> dict[str, Any]:
    """Transcription for this take, reusing the session copy when the audio is unchanged."""
    fp = audio_fingerprint(audio)
    stored = session.get("_mission_span_transcription")
    if isinstance(stored, dict) and stored.get("fingerprint") == fp and stored.get("version") == TRANSCRIPTION_VERSION:
        return stored
    result = transcribe(audio, filename)
    session["_mission_span_transcription"] = result
    return result


__all__ = ["audio_fingerprint", "session_transcription", "transcribe"]
