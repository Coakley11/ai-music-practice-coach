"""Deterministic coaching brief: steers each Claude note toward a different practice angle per exercise, instrument, focus and level.

The brief contains only practice-method guidance, never musical facts. Facts still come exclusively from the chart FactSheet.
"""

from __future__ import annotations

import hashlib
from typing import Any

# angle id -> instruction. Two angles allow tempo/recording talk; every other note must not mention them.
ANGLES: dict[str, str] = {
    "pair_drill": "Isolate the single hardest chord pair and drill it as a two-chord loop before joining the rest.",
    "anticipate": "Prepare each change early: hear or name the next chord before it arrives.",
    "common_tones": "Find what stays the same between neighbouring chords and keep that part still while the rest moves (do not name pitches).",
    "rhythm_placement": "Work on where the first beat of each chord lands: play the changes on beat one only, then add anticipations.",
    "chunking": "Split the section into short phrases, practice each, then join them with an overlapping chord.",
    "listen_first": "Listen to or sing the harmonic movement before playing it, then match it.",
    "reverse_order": "Practice the chord order backwards, then forwards, so no change relies on momentum.",
    "tempo_ladder": "Use a tempo ladder: start slower than the target and step up only after clean repeats.",
    "self_check": "Record one pass and check specific change points on playback.",
}
TEMPO_ANGLES = frozenset({"tempo_ladder"})
RECORDING_ANGLES = frozenset({"self_check"})

_FOCUS_ANGLES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("rhythm", "groove", "timing", "strum"), ("rhythm_placement", "chunking", "tempo_ladder", "pair_drill")),
    (("pitch", "intonation", "tune"), ("listen_first", "common_tones", "pair_drill", "self_check")),
    (("improv", "solo", "lick"), ("anticipate", "chunking", "listen_first", "rhythm_placement")),
    (("chord", "change", "voicing", "harmony"), ("pair_drill", "common_tones", "anticipate", "chunking", "reverse_order")),
)
_DEFAULT_ANGLES = ("pair_drill", "anticipate", "chunking", "common_tones", "reverse_order", "listen_first")

_INSTRUMENT_CUES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("sax", "clarinet", "trumpet", "flute", "oboe", "horn", "trombone", "recorder"),
     ("air support and breath planning at phrase ends", "fingering or slide changes between chords", "articulation at the start of each chord")),
    (("guitar", "ukulele", "banjo", "mandolin"),
     ("fretting-hand economy and anchor fingers", "keeping the strumming or picking hand steady", "clean ringing on the first strum after a change")),
    (("voice", "vocal", "sing"),
     ("breath before the entry", "vowel shape and pitch centre on held sounds", "hearing each chord as a reference for pitch")),
    (("piano", "keys", "keyboard", "organ"),
     ("hand shape and smallest movement between voicings", "left hand and right hand independence", "even touch on repeated chords")),
    (("bass",), ("root movement and rhythmic placement", "left-hand shifts and string crossings")),
    (("drum", "percussion"), ("keeping time while marking the chord changes", "fills that end on the downbeat")),
)

_LEVEL_SCOPE = {
    "beginner": {"items": "2", "style": "one small idea at a time, very slow, plain wording, no jargon"},
    "intermediate": {"items": "3", "style": "targeted drills on the trickiest changes, light musical terms"},
    "advanced": {"items": "3 to 4", "style": "specific musical targets per chord, voice-leading and phrase-shape ideas, concise"},
}


def _pick(pool: tuple[str, ...], seed: str, offset: int = 0) -> str:
    digest = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16)
    return pool[(digest + offset) % len(pool)]


def _angle_pool(focus: str) -> tuple[str, ...]:
    low = focus.lower()
    for words, pool in _FOCUS_ANGLES:
        if any(w in low for w in words):
            return pool
    return _DEFAULT_ANGLES


def _instrument_cues(instrument: str) -> tuple[str, ...]:
    low = instrument.lower()
    for words, cues in _INSTRUMENT_CUES:
        if any(w in low for w in words):
            return cues
    return ()


def build_brief(
    *, song_title: str, section: str, instrument: str, level: str, practice_focus: str, chords: tuple[str, ...]
) -> dict[str, Any]:
    """Pure function of its inputs, so the same exercise always gets the same brief (stable cache fingerprint)."""
    seed = "|".join([song_title, section, instrument, level, practice_focus, ",".join(chords)])
    pool = _angle_pool(practice_focus)
    primary = _pick(pool, seed)
    secondary = _pick(tuple(a for a in pool if a != primary) or pool, seed, 1)
    level_key = level.strip().lower()
    scope = _LEVEL_SCOPE.get(level_key, _LEVEL_SCOPE["intermediate"])
    cues = _instrument_cues(instrument)
    chosen_cues = list(cues)
    if len(cues) > 2:
        skip = int(hashlib.sha256(("cue" + seed).encode("utf-8")).hexdigest()[:8], 16) % len(cues)
        chosen_cues = [c for i, c in enumerate(cues) if i != skip]
    chosen = {primary, secondary}
    return {
        "primary_angle": ANGLES[primary],
        "secondary_angle": ANGLES[secondary],
        "angle_ids": [primary, secondary],
        "instrument_cues": chosen_cues,
        "level_scope": scope,
        "may_mention_tempo": bool(chosen & TEMPO_ANGLES),
        "may_suggest_recording": bool(chosen & RECORDING_ANGLES),
    }
