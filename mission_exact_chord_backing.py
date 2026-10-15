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


def _prepend_metered_count_in(wav: bytes, *, bpm: int, meter: str, bars: int = 1) -> bytes:
    """Count-in lasting exactly ``bars`` bars of ``meter`` (the analyzer's count_in_sec)."""
    if bars <= 0 or not wav or len(wav) < 44:
        return wav
    try:
        from songs.meter import meter_timing

        timing = meter_timing(int(bpm or 100), meter)
        sr = struct.unpack_from("<I", wav, 24)[0] or 44100
        click_len = int(round(sr * timing.bar_sec * bars))
        clicks = np.zeros(click_len, dtype=np.float32)
        for pulse in range(timing.pulses_per_bar * bars):
            start = int(round(pulse * timing.pulse_sec * sr))
            end = min(start + int(0.04 * sr), click_len)
            t = np.linspace(0, 0.04, max(1, end - start), endpoint=False)
            down = pulse % timing.pulses_per_bar == 0
            tone = np.sin(2 * np.pi * (1200.0 if down else 880.0) * t) * np.exp(-t * 40)
            clicks[start:end] += tone[: end - start] * (0.35 if down else 0.22)
        tail = np.frombuffer(wav[44:], dtype=np.int16).astype(np.float32)
        merged = np.clip(np.concatenate([clicks * 32767 * 0.5, tail]), -32767, 32767).astype(np.int16)
        header = bytearray(wav[:44])
        struct.pack_into("<I", header, 4, 36 + len(merged) * 2)
        struct.pack_into("<I", header, 40, len(merged) * 2)
        return bytes(header) + merged.tobytes()
    except Exception:
        return wav


def exact_chord_backing_signature(session: dict[str, Any]) -> tuple:
    ctx = build_mission_practice_context(session)
    chord = ctx.chord.symbol or ""
    if ctx.span:
        from mission_practice_context import span_backing_identity

        return (
            "mission_span_v1",
            span_backing_identity(ctx.span),
            ctx.backing_groove or ctx.backing_style,
            ctx.loops if ctx.loop else 1,
            round(ctx.volume, 2),
            ctx.count_in_bars,
            ctx.mission_type,
        )
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


def _generate_span_backing_wav(session: dict[str, Any], ctx: Any) -> tuple[bytes | None, str]:
    """2/3-chord Mission: loop the span exactly as charted (repeats, unequal durations, meter)."""
    from mission_practice_context import MISSION_BACKING_SOUNDING_SPAN_KEY
    from mission_span_recording_context import per_bar_chords, sounding_claim, span_chart_label

    span = ctx.span
    chords = per_bar_chords(span.get("timeline") or [])
    if not chords:
        return None, ""
    bpm = int(span.get("bpm") or ctx.tempo_bpm)
    meter = str(span.get("meter") or ctx.meter)
    sig = exact_chord_backing_signature(session)
    cached = _WAV_CACHE.get(sig)
    if cached is None:
        from backing_audio import generate_backing_track

        style = ctx.backing_groove or ctx.backing_style or "Pop groove"
        wav = generate_backing_track(
            chords,
            bpm=bpm,
            loops=max(1, ctx.loops if ctx.loop else 1),
            style=style,
            level=str(session.get("level") or "Intermediate"),
            song_title=ctx.song_title or "Mission span",
            song_artist="",
            time_signature=meter,
            mood=str(session.get("improv_mood") or ""),
            intensity=str(session.get("improv_difficulty") or ""),
        )
        if not wav:
            return None, ""
        wav = _scale_wav_volume(wav, ctx.volume)
        if ctx.count_in_bars:
            # Exactly one count-in, before bar 1 of the first loop.
            wav = _prepend_metered_count_in(wav, bpm=bpm, meter=meter, bars=ctx.count_in_bars)
        _WAV_CACHE[sig] = wav
        if len(_WAV_CACHE) > _CACHE_MAX:
            _WAV_CACHE.pop(next(iter(_WAV_CACHE)), None)
        cached = wav
    # The claim describes this WAV; it is removed together with it (Stop / invalidation).
    session[MISSION_BACKING_SOUNDING_SPAN_KEY] = sounding_claim(span)
    session["mission_exact_backing_wav"] = cached
    session["mission_exact_backing_signature"] = sig
    seal_recording_context(session, association="exact_span_backing_play")
    return cached, span_chart_label(span)


def generate_exact_chord_backing_wav(session: dict[str, Any]) -> tuple[bytes | None, str]:
    ctx = build_mission_practice_context(session)
    if ctx.span:
        return _generate_span_backing_wav(session, ctx)
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
    from mission_practice_context import MISSION_BACKING_SOUNDING_SPAN_KEY

    session.pop("mission_exact_backing_wav", None)
    session.pop("mission_exact_backing_signature", None)
    session.pop(MISSION_BACKING_SOUNDING_CHORD_KEY, None)
    # No WAV → nothing is sounding from the recorder (a span claim must not outlive it).
    session.pop(MISSION_BACKING_SOUNDING_SPAN_KEY, None)
