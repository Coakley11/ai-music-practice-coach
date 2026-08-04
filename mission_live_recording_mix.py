"""Mix dry live mic capture with mission exact-chord backing for preview."""

from __future__ import annotations

import struct
from typing import Any

import numpy as np

_SAMPLE_RATE = 44100


def _parse_wav_mono(wav: bytes) -> tuple[np.ndarray, int]:
    if not wav or len(wav) < 44:
        return np.zeros(0, dtype=np.float32), _SAMPLE_RATE
    sr = struct.unpack("<I", wav[24:28])[0] or _SAMPLE_RATE
    samples = np.frombuffer(wav[44:], dtype=np.int16).astype(np.float32) / 32768.0
    if samples.size == 0:
        return samples, sr
    return samples, int(sr)


def _resample_linear(samples: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr or samples.size == 0:
        return samples
    duration = samples.size / float(src_sr)
    dst_len = max(1, int(duration * dst_sr))
    x_src = np.linspace(0.0, 1.0, num=samples.size, endpoint=False)
    x_dst = np.linspace(0.0, 1.0, num=dst_len, endpoint=False)
    return np.interp(x_dst, x_src, samples).astype(np.float32)


def _encode_wav_mono(samples: np.ndarray, *, sample_rate: int = _SAMPLE_RATE) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    data = pcm.tobytes()
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(data),
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        sample_rate * 2,
        2,
        16,
        b"data",
        len(data),
    )
    return header + data


def count_in_samples(*, bpm: int, meter: str, bars: int, sample_rate: int = _SAMPLE_RATE) -> int:
    if bars <= 0:
        return 0
    beats_per_bar = 3 if str(meter or "").strip().startswith("3/") else 4
    beat_sec = 60.0 / max(40, int(bpm))
    return int(sample_rate * beat_sec * beats_per_bar * bars)


def mix_dry_mic_with_backing(
    dry_wav: bytes,
    backing_wav: bytes,
    *,
    backing_offset_samples: int = 0,
    backing_gain: float = 0.85,
    mic_gain: float = 1.0,
) -> bytes:
    """Align backing to recording start and sum channels (dry mic unchanged in session)."""
    mic, mic_sr = _parse_wav_mono(dry_wav)
    back, back_sr = _parse_wav_mono(backing_wav)
    if mic.size == 0:
        return dry_wav
    if back.size == 0:
        return dry_wav
    mic = _resample_linear(mic, mic_sr, _SAMPLE_RATE)
    back = _resample_linear(back, back_sr, _SAMPLE_RATE)
    offset = max(0, int(backing_offset_samples))
    out_len = max(mic.size, offset + back.size)
    mixed = np.zeros(out_len, dtype=np.float32)
    mixed[: mic.size] += mic * float(mic_gain)
    end = min(out_len, offset + back.size)
    if end > offset:
        mixed[offset:end] += back[: end - offset] * float(backing_gain)
    return _encode_wav_mono(mixed)


def estimate_backing_offset_samples(session: dict[str, Any], *, bpm: int, meter: str) -> int:
    """Offset backing so mic aligns with performance (count-in + play/recording skew)."""
    ctx = session.get("improv_mission_recording_seal") or session.get("improv_mission_practice_context")
    count_in = 0
    if isinstance(ctx, dict):
        count_in = int(ctx.get("count_in_bars") or 0)
    if session.get("mission_exact_backing_count_in"):
        count_in = max(count_in, 1)
    offset = count_in_samples(bpm=bpm, meter=meter, bars=count_in)
    try:
        rec_start = float(session.get("_mission_live_record_start_mono") or 0)
        play_start = float(session.get("_mission_backing_play_start_mono") or 0)
        if rec_start > 0 and play_start > 0 and rec_start >= play_start:
            offset += int((rec_start - play_start) * _SAMPLE_RATE)
    except (TypeError, ValueError):
        pass
    return max(0, offset)


def build_live_recording_previews(
    session: dict[str, Any],
    dry_wav: bytes,
    *,
    backing_wav: bytes | None,
    bpm: int,
    meter: str,
    backing_gain: float,
) -> dict[str, Any]:
    dry = bytes(dry_wav)
    session["_mission_live_mic_dry"] = dry
    mixed = dry
    if backing_wav:
        offset = estimate_backing_offset_samples(session, bpm=bpm, meter=meter)
        mixed = mix_dry_mic_with_backing(
            dry,
            backing_wav,
            backing_offset_samples=offset,
            backing_gain=backing_gain,
        )
    session["_mission_live_mic_mixed"] = mixed
    return {"dry": dry, "mixed": mixed, "has_backing_mix": backing_wav is not None}
