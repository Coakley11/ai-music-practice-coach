"""Generate and cache single-chord backing audio for mission recording workflows."""

from __future__ import annotations

import struct
from typing import Any

import numpy as np

from mission_practice_context import (
    MISSION_BACKING_SOUNDING_CHORD_KEY,
    build_mission_practice_context,
    seal_recording_context,
)

_WAV_CACHE: dict[tuple, bytes] = {}
_CACHE_MAX = 12


def _scale_wav_volume(wav: bytes, volume: float) -> bytes:
    if not wav or abs(volume - 1.0) < 0.02:
        return wav
    try:
        if len(wav) < 44:
            return wav
        data = wav[44:]
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        samples *= max(0.05, min(1.0, float(volume)))
        samples = np.clip(samples, -32767, 32767).astype(np.int16)
        header = bytearray(wav[:44])
        new_len = len(samples) * 2
        struct.pack_into("<I", header, 4, 36 + new_len)
        struct.pack_into("<I", header, 40, new_len)
        return bytes(header) + samples.tobytes()
    except Exception:
        return wav


def _prepend_count_in(wav: bytes, *, bpm: int, meter: str, bars: int = 1) -> bytes:
    if bars <= 0 or not wav or len(wav) < 44:
        return wav
    try:
        beats_per_bar = 4
        if meter.strip().startswith("3/"):
            beats_per_bar = 3
        sr = 44100
        beat_sec = 60.0 / max(40, bpm)
        click_len = int(sr * beat_sec * beats_per_bar * bars)
        clicks = np.zeros(click_len, dtype=np.float32)
        for beat in range(beats_per_bar * bars):
            start = int(beat * beat_sec * sr)
            end = min(start + int(0.04 * sr), click_len)
            t = np.linspace(0, 0.04, max(1, end - start), endpoint=False)
            freq = 1200.0 if beat % beats_per_bar == 0 else 880.0
            pulse = np.sin(2 * np.pi * freq * t) * np.exp(-t * 40)
            clicks[start:end] += pulse[: end - start] * (0.35 if beat % beats_per_bar == 0 else 0.22)
        body = wav[44:]
        tail = np.frombuffer(body, dtype=np.int16).astype(np.float32)
        merged = np.concatenate([clicks * 32767 * 0.5, tail])
        merged = np.clip(merged, -32767, 32767).astype(np.int16)
        header = bytearray(wav[:44])
        new_len = len(merged) * 2
        struct.pack_into("<I", header, 4, 36 + new_len)
        struct.pack_into("<I", header, 40, new_len)
        return bytes(header) + merged.tobytes()
    except Exception:
        return wav


def exact_chord_backing_signature(session: dict[str, Any]) -> tuple:
    ctx = build_mission_practice_context(session)
    chord = ctx.chord.symbol or ""
    return (
        "mission_exact_v1",
        chord,
        ctx.chord.chord_index,
        ctx.chord.section,
        ctx.tempo_bpm,
        ctx.backing_groove or ctx.backing_style,
        ctx.meter,
        ctx.loops if ctx.loop else 1,
        round(ctx.volume, 2),
        ctx.count_in_bars,
        ctx.mission_type,
    )


def generate_exact_chord_backing_wav(session: dict[str, Any]) -> tuple[bytes | None, str]:
    ctx = build_mission_practice_context(session)
    chord = ctx.chord.symbol
    if not chord:
        return None, ""
    sig = exact_chord_backing_signature(session)
    cached = _WAV_CACHE.get(sig)
    if cached is None:
        from backing_audio import generate_backing_track

        style = ctx.backing_groove or ctx.backing_style or "Pop groove"
        loops = max(1, ctx.loops if ctx.loop else 1)
        wav = generate_backing_track(
            [chord],
            bpm=ctx.tempo_bpm,
            loops=loops,
            style=style,
            level=str(session.get("level") or "Intermediate"),
            song_title=ctx.song_title or "Mission chord",
            song_artist="",
            time_signature=ctx.meter,
            mood=str(session.get("improv_mood") or ""),
            intensity=str(session.get("improv_difficulty") or ""),
        )
        if not wav:
            return None, ""
        wav = _scale_wav_volume(wav, ctx.volume)
        if ctx.count_in_bars:
            wav = _prepend_count_in(wav, bpm=ctx.tempo_bpm, meter=ctx.meter, bars=ctx.count_in_bars)
        _WAV_CACHE[sig] = wav
        if len(_WAV_CACHE) > _CACHE_MAX:
            first = next(iter(_WAV_CACHE))
            _WAV_CACHE.pop(first, None)
        cached = wav
    session[MISSION_BACKING_SOUNDING_CHORD_KEY] = chord
    session["mission_exact_backing_wav"] = cached
    session["mission_exact_backing_signature"] = sig
    seal_recording_context(session, association="exact_chord_backing_play")
    return cached, chord


def invalidate_exact_chord_backing_cache(session: dict[str, Any]) -> None:
    session.pop("mission_exact_backing_wav", None)
    session.pop("mission_exact_backing_signature", None)
    session.pop(MISSION_BACKING_SOUNDING_CHORD_KEY, None)
