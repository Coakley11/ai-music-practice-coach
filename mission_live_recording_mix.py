"""Mix dry live mic capture with mission exact-chord backing for preview."""

from __future__ import annotations

import struct
from typing import Any

import numpy as np

_SAMPLE_RATE = 44100

# Audible backing in mixed preview: post-gain backing RMS vs mic RMS (not merely nonzero).
BACKING_AUDIBLE_RMS_RATIO_MIN = 0.08


def _read_fmt(wav: bytes) -> tuple[int, int, int]:
    """Return (channels, sample_rate, data_offset) or mono 44100 defaults."""
    if not wav or len(wav) < 44:
        return 1, _SAMPLE_RATE, 44
    if wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
        return 1, _SAMPLE_RATE, 44
    pos = 12
    channels = 1
    sr = _SAMPLE_RATE
    data_off = 44
    while pos + 8 <= len(wav):
        chunk_id = wav[pos : pos + 4]
        chunk_sz = struct.unpack("<I", wav[pos + 4 : pos + 8])[0]
        chunk_data = pos + 8
        if chunk_id == b"fmt " and chunk_sz >= 16:
            channels = struct.unpack("<H", wav[chunk_data + 2 : chunk_data + 4])[0] or 1
            sr = struct.unpack("<I", wav[chunk_data + 4 : chunk_data + 8])[0] or _SAMPLE_RATE
        elif chunk_id == b"data":
            data_off = chunk_data
            break
        pos = chunk_data + chunk_sz + (chunk_sz % 2)
    return int(channels), int(sr), int(data_off)


def _parse_wav_mono(wav: bytes) -> tuple[np.ndarray, int]:
    if not wav or len(wav) < 44:
        return np.zeros(0, dtype=np.float32), _SAMPLE_RATE
    channels, sr, data_off = _read_fmt(wav)
    raw = np.frombuffer(wav[data_off:], dtype=np.int16)
    if raw.size == 0:
        return np.zeros(0, dtype=np.float32), sr
    if channels > 1:
        usable = (raw.size // channels) * channels
        raw = raw[:usable].reshape(-1, channels)
        samples = raw.mean(axis=1).astype(np.float32) / 32768.0
    else:
        samples = raw.astype(np.float32) / 32768.0
    return samples, int(sr or _SAMPLE_RATE)


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


def _rms_peak(samples: np.ndarray) -> tuple[float, float]:
    if samples.size == 0:
        return 0.0, 0.0
    peak = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(samples * samples)))
    return rms, peak


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


def _strip_leading_silence_and_count_in(
    back: np.ndarray,
    *,
    count_in_samples: int,
) -> np.ndarray:
    """Use musical body for mix — WAV may already include count-in clicks at the head."""
    skip = max(0, int(count_in_samples))
    if skip > 0 and back.size > skip:
        return back[skip:].astype(np.float32, copy=False)
    return back


def _apply_preview_limiter(mixed: np.ndarray, *, ceiling: float = 0.98) -> np.ndarray:
    peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0
    if peak <= ceiling or peak <= 1e-9:
        return mixed
    return (mixed * (ceiling / peak)).astype(np.float32)


def mix_dry_mic_with_backing(
    dry_wav: bytes,
    backing_wav: bytes,
    *,
    backing_offset_samples: int = 0,
    backing_gain: float = 0.65,
    mic_gain: float = 1.0,
    loop_backing: bool = True,
    backing_skip_head_samples: int = 0,
) -> tuple[bytes, dict[str, Any]]:
    """Align backing to recording start and sum channels (dry mic unchanged in session)."""
    mic, mic_sr = _parse_wav_mono(dry_wav)
    back, back_sr = _parse_wav_mono(backing_wav)
    diag: dict[str, Any] = {
        "mic_samples": int(mic.size),
        "back_samples_raw": int(back.size),
        "backing_skip_head_samples": int(backing_skip_head_samples),
    }
    if mic.size == 0:
        return dry_wav, {**diag, "mix_aborted": "empty_mic"}
    if back.size == 0:
        return dry_wav, {**diag, "mix_aborted": "empty_backing"}

    dry_rms, dry_peak = _rms_peak(mic)
    back_rms_raw, back_peak_raw = _rms_peak(back)
    diag["dry_rms"] = round(dry_rms, 6)
    diag["dry_peak"] = round(dry_peak, 6)
    diag["backing_rms_raw"] = round(back_rms_raw, 6)
    diag["backing_peak_raw"] = round(back_peak_raw, 6)

    mic = _resample_linear(mic, mic_sr, _SAMPLE_RATE)
    back = _resample_linear(back, back_sr, _SAMPLE_RATE)
    back = _strip_leading_silence_and_count_in(
        back, count_in_samples=backing_skip_head_samples
    )
    back_rms_body, back_peak_body = _rms_peak(back)
    diag["backing_rms_body"] = round(back_rms_body, 6)
    diag["backing_peak_body"] = round(back_peak_body, 6)

    offset = max(0, int(backing_offset_samples))
    out_len = mic.size
    mic_track = mic * float(mic_gain)
    if loop_backing:
        back_track = _loop_backing_segment(back, out_len=out_len, offset=offset)
    else:
        back_track = np.zeros(out_len, dtype=np.float32)
        end = min(out_len, offset + back.size)
        if end > offset:
            back_track[offset:end] = back[: end - offset]
    back_scaled = back_track * float(backing_gain)
    back_rms_gain, back_peak_gain = _rms_peak(back_scaled)
    diag["backing_gain"] = float(backing_gain)
    diag["mic_gain"] = float(mic_gain)
    diag["backing_rms_after_gain"] = round(back_rms_gain, 6)
    diag["backing_peak_after_gain"] = round(back_peak_gain, 6)
    diag["offset_samples"] = offset
    diag["backing_looped_sec"] = round(float(back_track.size) / _SAMPLE_RATE, 3)

    mixed = mic_track + back_scaled
    mixed = _apply_preview_limiter(mixed)
    mix_rms, mix_peak = _rms_peak(mixed)
    diag["mixed_rms"] = round(mix_rms, 6)
    diag["mixed_peak"] = round(mix_peak, 6)
    mic_rms, _ = _rms_peak(mic_track)
    ratio = (back_rms_gain / mic_rms) if mic_rms > 1e-9 else 0.0
    diag["backing_to_mic_rms_ratio"] = round(ratio, 4)
    diag["backing_clearly_audible"] = bool(
        back_rms_body > 1e-5 and ratio >= BACKING_AUDIBLE_RMS_RATIO_MIN
    )
    return _encode_wav_mono(mixed), diag


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


def resolve_backing_wav_for_live_mix(session: dict[str, Any]) -> tuple[bytes | None, str]:
    """Prefer the same WAV armed by Play; regenerate only if missing."""
    stored = session.get("mission_exact_backing_wav")
    if isinstance(stored, (bytes, bytearray)) and len(stored) > 44:
        return bytes(stored), "session_play"
    from mission_exact_chord_backing import generate_exact_chord_backing_wav

    wav, _chord = generate_exact_chord_backing_wav(session)
    if wav:
        return wav, "regenerated"
    return None, "none"


def build_looped_backing_preview_wav(
    backing_wav: bytes,
    *,
    dry_wav: bytes,
    bpm: int,
    meter: str,
    session: dict[str, Any],
    backing_gain: float,
) -> bytes:
    """Dev preview: backing track as used in the mix (looped to dry length)."""
    dry, _ = _parse_wav_mono(dry_wav)
    back, back_sr = _parse_wav_mono(backing_wav)
    if dry.size == 0 or back.size == 0:
        return b""
    back = _resample_linear(back, back_sr, _SAMPLE_RATE)
    skip = estimate_backing_offset_samples(session, bpm=bpm, meter=meter)
    back = _strip_leading_silence_and_count_in(back, count_in_samples=skip)
    offset = estimate_backing_offset_samples(session, bpm=bpm, meter=meter)
    track = _loop_backing_segment(back, out_len=dry.size, offset=offset)
    track = _apply_preview_limiter(track * float(backing_gain))
    return _encode_wav_mono(track)


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
    mix_diag: dict[str, Any] = {}
    looped = False
    offset = 0
    back_energy = 0.0
    backing_source = "none"
    if backing_wav:
        offset = estimate_backing_offset_samples(session, bpm=bpm, meter=meter)
        mixed, mix_diag = mix_dry_mic_with_backing(
            dry,
            backing_wav,
            backing_offset_samples=offset,
            backing_gain=backing_gain,
            mic_gain=mic_gain,
            loop_backing=True,
            backing_skip_head_samples=offset,
        )
        looped = True
        back_energy = backing_energy_in_mixed(mixed, dry)
        backing_source = str(session.get("_mission_live_backing_source") or "unknown")
    session["_mission_live_mic_mixed"] = mixed
    if backing_wav and len(dry) > 44:
        session["_mission_live_backing_looped_preview"] = build_looped_backing_preview_wav(
            backing_wav,
            dry_wav=dry,
            bpm=bpm,
            meter=meter,
            session=session,
            backing_gain=backing_gain,
        )
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
        "backing_source": backing_source,
        "mixed_source_key": "_mission_live_mic_mixed",
        **mix_diag,
    }
    return {
        "dry": dry,
        "mixed": mixed,
        "has_backing_mix": backing_wav is not None and mixed != dry,
        "backing_residual_rms": back_energy,
    }
