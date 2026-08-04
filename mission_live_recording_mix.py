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


def _loop_backing_segment(
    back: np.ndarray,
    *,
    out_len: int,
    offset: int,
) -> np.ndarray:
    """Tile backing from offset through out_len (for previews longer than one loop)."""
    if back.size == 0 or out_len <= 0:
        return np.zeros(0, dtype=np.float32)
    out = np.zeros(out_len, dtype=np.float32)
    start = max(0, int(offset))
    pos = start
    while pos < out_len:
        take = min(back.size, out_len - pos)
        out[pos : pos + take] += back[:take]
        pos += back.size
    return out


def mix_dry_mic_with_backing(
    dry_wav: bytes,
    backing_wav: bytes,
    *,
    backing_offset_samples: int = 0,
    backing_gain: float = 0.85,
    mic_gain: float = 1.0,
    loop_backing: bool = True,
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
    out_len = mic.size
    mixed = np.zeros(out_len, dtype=np.float32)
    mixed[: mic.size] += mic * float(mic_gain)
    if loop_backing:
        back_track = _loop_backing_segment(back, out_len=out_len, offset=offset)
        mixed[:out_len] += back_track[:out_len] * float(backing_gain)
    else:
        end = min(out_len, offset + back.size)
        if end > offset:
            mixed[offset:end] += back[: end - offset] * float(backing_gain)
    peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0
    if peak > 1.0:
        mixed = mixed / peak * 0.98
    return _encode_wav_mono(mixed)


def backing_energy_in_mixed(mixed_wav: bytes, dry_wav: bytes) -> float:
    """Rough RMS delta — backing should add energy vs dry alone."""
    mix, _ = _parse_wav_mono(mixed_wav)
    dry, _ = _parse_wav_mono(dry_wav)
    if mix.size == 0 or dry.size == 0 or mix.size != dry.size:
        return 0.0
    diff = mix - dry[: mix.size]
    return float(np.sqrt(np.mean(diff * diff)))


def estimate_backing_offset_samples(session: dict[str, Any], *, bpm: int, meter: str) -> int:
    """Count-in alignment only — avoid monotonic clock skew across Streamlit reruns."""
    ctx = session.get("improv_mission_recording_seal") or session.get("improv_mission_practice_context")
    count_in = 0
    if isinstance(ctx, dict):
        count_in = int(ctx.get("count_in_bars") or 0)
    if session.get("mission_exact_backing_count_in"):
        count_in = max(count_in, 1)
    return count_in_samples(bpm=bpm, meter=meter, bars=count_in)


def wav_duration_sec(wav: bytes, *, default_sr: int = _SAMPLE_RATE) -> float:
    samples, sr = _parse_wav_mono(wav)
    if samples.size == 0:
        return 0.0
    return float(samples.size) / float(sr or default_sr)


def build_live_recording_previews(
    session: dict[str, Any],
    dry_wav: bytes,
    *,
    backing_wav: bytes | None,
    bpm: int,
    meter: str,
    backing_gain: float,
    mic_gain: float = 1.0,
) -> dict[str, Any]:
    dry = bytes(dry_wav)
    session["_mission_live_mic_dry"] = dry
    mixed = dry
    looped = False
    offset = 0
    back_energy = 0.0
    if backing_wav:
        offset = estimate_backing_offset_samples(session, bpm=bpm, meter=meter)
        mixed = mix_dry_mic_with_backing(
            dry,
            backing_wav,
            backing_offset_samples=offset,
            backing_gain=backing_gain,
            mic_gain=mic_gain,
            loop_backing=True,
        )
        looped = True
        back_energy = backing_energy_in_mixed(mixed, dry)
    session["_mission_live_mic_mixed"] = mixed
    session["_mission_live_mix_diag"] = {
        "dry_bytes": len(dry),
        "backing_bytes": len(backing_wav or b""),
        "mixed_bytes": len(mixed),
        "dry_sec": round(wav_duration_sec(dry), 3),
        "backing_sec": round(wav_duration_sec(backing_wav or b""), 3),
        "mixed_sec": round(wav_duration_sec(mixed), 3),
        "offset_samples": offset,
        "backing_gain": backing_gain,
        "mic_gain": mic_gain,
        "backing_looped": looped,
        "backing_residual_rms": round(back_energy, 6),
        "mixed_differs_from_dry": mixed != dry,
    }
    return {
        "dry": dry,
        "mixed": mixed,
        "has_backing_mix": backing_wav is not None and mixed != dry,
        "backing_residual_rms": back_energy,
    }
