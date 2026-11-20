"""Melody-candidate preview helpers: one authoritative timeline for audio, notation and highlight.

Kept separate from the chord-preview helpers so melody-specific behaviour (full-length audio,
timeline/audio reconciliation) does not touch chord refinement code paths.
"""

from __future__ import annotations

import io
import wave
from typing import Any

from composition_playback_sync import beat_seconds, build_playback_bundle

# Audio must outlast the last note by at least this much (release + reverb tail).
MELODY_AUDIO_TAIL_SEC = 0.35


def expanded_section_chords(doc: dict[str, Any], section_id: str) -> list[str]:
    """One symbol per bar, with multi-bar entries and ``%`` repeats resolved.

    The raw ``section['chords']`` list holds *entries* (``{"chord": "Cmaj7", "bars": 2}``);
    previewing them unexpanded produced a backing shorter than the melody, which cut the
    last notes off.  The melody generator already consumes the expanded form.
    """
    from composition_document import chords_for_playback

    return list(chords_for_playback(doc, scope="section", section_id=section_id) or [])


def melody_end_beat(events: list[dict[str, Any]] | None) -> float:
    end = 0.0
    cursor = 0.0
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        try:
            start = float(ev["beat"]) if ev.get("beat") is not None else cursor
        except (TypeError, ValueError):
            start = cursor
        dur = float(ev.get("duration_beats") or 1.0)
        cursor = max(cursor, start + dur)
        end = max(end, start + dur)
    return end


def harmony_covering_melody(
    chords: list[Any] | None,
    events: list[dict[str, Any]] | None,
    *,
    meter: str = "4/4",
) -> list[Any]:
    """The section progression, cycled so it lasts as long as the melody.

    Melody repeats x2-x4 tile the phrase past one pass of the section's chords; the staff,
    the synced chord highlight and the preview backing all used one pass only, so every
    repeated pass showed no chord symbols and played with no harmony underneath. Accepts
    chord entries (``{"chord", "bars"}``) or one symbol per bar; a progression already as
    long as the melody is returned unchanged. The last cycled entry is trimmed to the
    melody's final bar.
    """
    import math

    from composition_melody_notation import beats_per_bar

    seq = [c for c in list(chords or []) if (isinstance(c, dict) or str(c).strip())]
    if not seq or not events:
        return list(chords or [])
    bar = max(1.0, float(beats_per_bar(meter)))
    need = int(math.ceil(melody_end_beat(events) / bar - 1e-6))

    def width(entry: Any) -> int:
        if isinstance(entry, dict):
            try:
                return max(1, int(entry.get("bars") or 1))
            except (TypeError, ValueError):
                return 1
        return 1

    if need <= sum(width(c) for c in seq):
        return list(chords or [])
    out: list[Any] = []
    used = 0
    i = 0
    while used < need:
        entry = seq[i % len(seq)]
        w = width(entry)
        if isinstance(entry, dict):
            entry = dict(entry)
            if used + w > need:
                w = need - used
                entry["bars"] = w
        out.append(entry)
        used += w
        i += 1
    return out


def wav_duration_seconds(wav: bytes | None) -> float:
    if not wav:
        return 0.0
    with wave.open(io.BytesIO(wav), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate() or 1)


def timeline_audio_report(
    wav: bytes | None,
    events: list[dict[str, Any]] | None,
    chord_syms: list[str] | None,
    *,
    bpm: int,
    meter: str = "4/4",
) -> dict[str, Any]:
    """Compare the single event timeline against the rendered audio."""
    bundle = build_playback_bundle(events=events, chord_syms=chord_syms, bpm=bpm, meter=meter)
    spans = [s for s in bundle["melody_spans"] if s.get("highlightable")]
    timeline_end = max((float(s["end_sec"]) for s in bundle["melody_spans"]), default=0.0)
    last_start = max((float(s["start_sec"]) for s in spans), default=0.0)
    audio = wav_duration_seconds(wav)
    return {
        "audio_sec": audio,
        "timeline_end_sec": timeline_end,
        "last_note_start_sec": last_start,
        "chord_end_sec": max((float(s["end_sec"]) for s in bundle["chord_spans"]), default=0.0),
        "audio_covers_timeline": audio + 1e-3 >= timeline_end + MELODY_AUDIO_TAIL_SEC,
        "highlight_sequence": [s["dom_note_index"] for s in spans],
        "bundle": bundle,
        "beat_seconds": beat_seconds(bpm=bpm),
    }
