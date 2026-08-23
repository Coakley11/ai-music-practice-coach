"""Audition backing (and optional melody) audio for Composition Studio."""

from __future__ import annotations

import io
import math
import struct
import wave
from typing import Any

from composition_document import chords_for_playback, playback_globals, section_by_id, section_melody_events


def preview_signature(
    doc: dict[str, Any],
    *,
    scope: str = "section",
    section_id: str | None = None,
    loops: int = 2,
    chord_override: list[str] | None = None,
    include_melody: bool = False,
    melody_override: list[dict[str, Any]] | None = None,
) -> tuple:
    pg = playback_globals(doc)
    if chord_override is not None:
        chords = [str(c) for c in chord_override if str(c).strip()]
    else:
        chords = chords_for_playback(doc, scope=scope, section_id=section_id)
    mel_sig: tuple = ()
    if include_melody:
        events = melody_override if melody_override is not None else _resolve_melody_events(doc, section_id)
        mel_sig = tuple(
            (str(e.get("pitch") or ""), float(e.get("duration_beats") or 1.0), float(e.get("beat") or 0.0))
            for e in events
        )
    return (
        str(doc.get("id") or ""),
        scope,
        section_id or "",
        tuple(chords),
        pg["bpm"],
        pg["time_signature"],
        pg["style"],
        pg["groove"],
        int(loops),
        bool(include_melody),
        mel_sig,
    )


def _resolve_melody_events(doc: dict[str, Any], section_id: str | None) -> list[dict[str, Any]]:
    if not section_id:
        return []
    sec = section_by_id(doc, section_id)
    return section_melody_events(sec)


def _beats_per_bar(time_signature: str) -> float:
    text = str(time_signature or "4/4").strip()
    if "/" in text:
        try:
            num, _den = text.split("/", 1)
            return float(int(num))
        except ValueError:
            return 4.0
    return 4.0


def _midi_to_hz(midi: int) -> float:
    return 440.0 * (2.0 ** ((int(midi) - 69) / 12.0))


def _pitch_to_midi(pitch: str, fallback: int = 60) -> int:
    from music_theory import NOTE_TO_MIDI, split_chord

    text = str(pitch or "").strip()
    if not text:
        return fallback
    # Optional octave digit: C4, Eb5
    if text[-1].isdigit():
        octv = int(text[-1])
        name = text[:-1]
        root, _ = split_chord(name)
        base = NOTE_TO_MIDI.get(root) or NOTE_TO_MIDI.get(root.replace("b", ""))
        if base is None:
            return fallback
        # NOTE_TO_MIDI is around octave 4 (C=60). Adjust relative octave.
        return int(base + (octv - 4) * 12)
    root, _ = split_chord(text)
    return int(NOTE_TO_MIDI.get(root) or NOTE_TO_MIDI.get(root.replace("b", "")) or fallback)


def _wav_to_mono_floats(wav_bytes: bytes) -> tuple[list[float], int]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        sr = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    if sampwidth != 2:
        # Only PCM16 expected from backing_audio.
        return [], sr
    count = len(frames) // 2
    samples = list(struct.unpack("<" + "h" * count, frames))
    if channels > 1:
        mono = [
            sum(samples[i : i + channels]) / float(channels)
            for i in range(0, len(samples), channels)
        ]
    else:
        mono = [float(s) for s in samples]
    return [s / 32768.0 for s in mono], sr


def _floats_to_wav_bytes(samples: list[float], sr: int) -> bytes:
    clipped = [max(-1.0, min(1.0, float(s))) for s in samples]
    pcm = [int(s * 32767.0) for s in clipped]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sr))
        wf.writeframes(struct.pack("<" + "h" * len(pcm), *pcm))
    return buf.getvalue()


def _mix_melody_onto_backing(
    wav_bytes: bytes,
    events: list[dict[str, Any]],
    *,
    bpm: int,
    time_signature: str = "4/4",
    loops: int = 1,
) -> bytes:
    if not events or not wav_bytes:
        return wav_bytes
    mono, sr = _wav_to_mono_floats(wav_bytes)
    if not mono:
        return wav_bytes
    seconds_per_beat = 60.0 / max(40.0, float(bpm))
    bpb = _beats_per_bar(time_signature)
    # Melody may be shorter than looped backing — repeat softly to fill.
    total_beats = len(mono) / float(sr) / seconds_per_beat
    out = list(mono)
    gain = 0.22
    for loop_i in range(max(1, int(loops))):
        loop_offset = loop_i * max(bpb, sum(float(e.get("duration_beats") or 1.0) for e in events))
        if loop_offset > total_beats + 0.5:
            break
        for ev in events:
            if ev.get("is_rest") or str(ev.get("pitch") or "").strip().lower() == "rest":
                continue
            midi = ev.get("midi")
            try:
                midi_i = int(midi) if midi is not None else _pitch_to_midi(str(ev.get("pitch") or ""))
            except (TypeError, ValueError):
                midi_i = _pitch_to_midi(str(ev.get("pitch") or ""))
            start_beat = float(ev.get("beat") or 0.0) + loop_offset
            dur_beats = float(ev.get("duration_beats") or 1.0)
            start = int(start_beat * seconds_per_beat * sr)
            length = int(dur_beats * seconds_per_beat * sr)
            if start >= len(out) or length <= 0:
                continue
            end = min(len(out), start + length)
            hz = _midi_to_hz(midi_i)
            for i in range(start, end):
                t = (i - start) / float(sr)
                # Soft attack / release envelope
                env = 1.0
                attack = min(0.02, (end - start) / float(sr) * 0.2)
                release = min(0.05, (end - start) / float(sr) * 0.3)
                local_t = t
                local_end = (end - start) / float(sr)
                if attack > 0 and local_t < attack:
                    env = local_t / attack
                elif release > 0 and local_t > local_end - release:
                    env = max(0.0, (local_end - local_t) / release)
                out[i] += gain * env * math.sin(2.0 * math.pi * hz * t)
    # Prevent clipping
    peak = max(abs(s) for s in out) if out else 1.0
    if peak > 0.98:
        scale = 0.98 / peak
        out = [s * scale for s in out]
    return _floats_to_wav_bytes(out, sr)


def generate_preview_wav(
    doc: dict[str, Any],
    *,
    scope: str = "section",
    section_id: str | None = None,
    loops: int = 2,
    level: str = "Intermediate",
    chord_override: list[str] | None = None,
    include_melody: bool = False,
    melody_override: list[dict[str, Any]] | None = None,
) -> bytes | None:
    if chord_override is not None:
        chords = [str(c) for c in chord_override if str(c).strip()]
    else:
        chords = chords_for_playback(doc, scope=scope, section_id=section_id)
    if not chords:
        return None
    pg = playback_globals(doc)
    from backing_audio import generate_backing_track

    wav = generate_backing_track(
        chords,
        bpm=pg["bpm"],
        loops=max(1, int(loops)),
        style=pg["groove"],
        level=level,
        song_title=str(doc.get("title") or "Composition"),
        song_artist="",
        time_signature=pg["time_signature"],
        mood=pg.get("mood") or "",
    )
    if not wav:
        return None
    if include_melody:
        events = (
            list(melody_override)
            if melody_override is not None
            else _resolve_melody_events(doc, section_id)
        )
        if events:
            wav = _mix_melody_onto_backing(
                wav,
                events,
                bpm=int(pg["bpm"]),
                time_signature=str(pg["time_signature"]),
                loops=max(1, int(loops)),
            )
    return wav


def set_composer_preview(
    session_state: dict,
    wav: bytes | None,
    signature: tuple | None = None,
) -> None:
    """Replace the active Composition preview (single owner — no stacked mystery audio)."""
    if not wav:
        invalidate_composer_preview(session_state)
        return
    session_state["composer_preview_wav"] = wav
    if signature is not None:
        session_state["composer_preview_signature"] = signature


def invalidate_composer_preview(session_state: dict) -> None:
    session_state.pop("composer_preview_wav", None)
    session_state.pop("composer_preview_signature", None)
