"""A recorded tenor saxophone for backgrounds behind the soloist (numpy only).

Off by default, and not part of any Backing render yet: nothing here runs unless ``MUSIC_HORNS`` is
switched on (``1`` / ``on`` / ``tenor``) *and* the pack in ``assets/instruments/tenor_sax`` is present,
and even then only a caller that asks for a horn part gets one - ``backing_audio`` does not call this
module, and no ensemble lists the horns as available.

The sax plays at concert pitch from the CC0 VCSL tenor (see the pack's README): sustained notes from
the Non-Vibrato recordings, short notes from the Staccato ones, chosen by how long the note is held.
Every note is clamped to the recorded range (concert Ab2-E5, the tenor's normal range), starts with a
short fade-in and ends with a release that reaches silence, so nothing clicks. Velocity picks the
staccato layer and sets the level. One player cannot play two notes at once or play for ever without
breathing, so :func:`breathe` keeps each voice monophonic and opens a breath in a long phrase.

Two parts are written from a chord list, a number of bars and a tempo:

* :func:`sustained_background` - a guide-tone line (3rds and 7ths) moving to the nearest guide tone of
  each new chord, held for the chord, with a breath at each phrase end; ``voices=2`` adds the other
  guide tone a second sax would play (the same recordings, as a duo).
* :func:`staccato_hits` - short punches on the "and" of 2 and on 4, on the same guide tones.

:func:`render_horn_background` puts those together; :func:`render_line` plays any list of notes.
"""

from __future__ import annotations

import json
import os
import pathlib
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Iterable, Sequence

import numpy as np

from backing_sampled_instrument import SampledInstrument

HORN_PACK = pathlib.Path(__file__).resolve().parent / "assets" / "instruments" / "tenor_sax"
# Concert pitch of the recordings (the pack's manifest says the same): Ab2-E5, written Bb3-F#6.
TENOR_LOW = 44
TENOR_HIGH = 76
# Backgrounds sit in the middle of the horn, below a melody: concert D3-Bb4.
BACKGROUND_LOW = 50
BACKGROUND_HIGH = 70
BACKGROUND_CENTRE = 61

STACCATO_MAX_SEC = 0.30  # held this long or less: a staccato recording
ATTACK_SEC = {"sustain": 0.025, "staccato": 0.003}
RELEASE_SEC = {"sustain": 0.12, "staccato": 0.035}
TONGUE_GAP_SEC = 0.04  # the silence a re-tongued note leaves behind the one before it
BREATH_SEC = 0.25  # the silence a breath needs
MAX_PHRASE_SEC = 8.0  # a phrase longer than this gets a breath
LOOP_CROSSFADE_SEC = 0.15  # sustains held longer than the recording continue on a crossfaded loop
_LOOP_FROM_SEC = 0.6  # the steady part of a sustained recording: after the attack ...
_LOOP_BEFORE_END_SEC = 0.36  # ... and before the recording's own fade-out (0.30 s)

_ON = {"1", "true", "yes", "on", "tenor", "recorded"}


def enabled() -> bool:
    """``MUSIC_HORNS`` is on and the tenor pack is present."""
    raw = str(os.environ.get("MUSIC_HORNS") or "").strip().lower()
    return raw in _ON and (HORN_PACK / "manifest.json").is_file()


def horns_renderer_tag() -> str:
    """For saved audio's signature once a render uses the horns; "" while they are off."""
    return "+horns-tenor1" if enabled() else ""


@dataclass(frozen=True)
class HornNote:
    start_sec: float
    dur_sec: float  # how long the note is held, before its release
    midi: int  # concert pitch
    velocity: float = 0.7
    articulation: str | None = None  # "sustain" / "staccato"; None chooses by length
    voice: int = 0  # which player: each voice is monophonic and breathes on its own


def clamp_to_range(midi: int, low: int = TENOR_LOW, high: int = TENOR_HIGH) -> int:
    """The same pitch class moved by octaves into ``low..high``; a range narrower than an octave clips."""
    m = int(midi)
    while m < low:
        m += 12
    while m > high:
        m -= 12
    return min(high, max(low, m))


def choose_articulation(dur_sec: float) -> str:
    return "staccato" if float(dur_sec) <= STACCATO_MAX_SEC else "sustain"


def breathe(notes: Iterable[HornNote]) -> list[HornNote]:
    """What one player per voice can play: no overlaps, a tongued gap between notes, a breath in long phrases."""
    out: list[HornNote] = []
    by_voice: dict[int, list[HornNote]] = {}
    for n in sorted(notes, key=lambda n: (n.voice, n.start_sec)):
        by_voice.setdefault(n.voice, []).append(n)
    for voice_notes in by_voice.values():
        fixed: list[HornNote] = []
        phrase_start = None
        for i, n in enumerate(voice_notes):
            nxt = voice_notes[i + 1].start_sec if i + 1 < len(voice_notes) else None
            dur = float(n.dur_sec)
            if phrase_start is None:
                phrase_start = n.start_sec
            if nxt is not None:
                gap = BREATH_SEC if nxt - phrase_start > MAX_PHRASE_SEC else TONGUE_GAP_SEC
                dur = min(dur, nxt - n.start_sec - gap)
                if nxt - (n.start_sec + dur) >= BREATH_SEC - 1e-9:
                    phrase_start = None  # the player breathed here
            if dur < 0.03:
                continue
            fixed.append(replace(n, dur_sec=dur))
        out.extend(fixed)
    return sorted(out, key=lambda n: (n.start_sec, n.voice))


# --- Playing ------------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _pack() -> dict[str, SampledInstrument]:
    """The sustained and staccato recordings, each as a SampledInstrument (decoded audio lives in the shared cache)."""
    sustain = SampledInstrument(HORN_PACK)
    staccato = SampledInstrument(HORN_PACK)
    staccato.zones = sorted(staccato.manifest["articulations"]["staccato"], key=lambda z: z["key"])
    staccato._keys = np.array([z["key"] for z in staccato.zones])
    return {"sustain": sustain, "staccato": staccato}


def pack_range() -> tuple[int, int]:
    manifest = json.loads((HORN_PACK / "manifest.json").read_text(encoding="utf-8"))
    low, high = manifest.get("range", (TENOR_LOW, TENOR_HIGH))
    return int(low), int(high)


def _read(x: np.ndarray, first: float, n: int, ratio: float) -> np.ndarray:
    """``n`` output samples from int16 ``x`` starting at source position ``first``, linearly interpolated."""
    pos = first + np.arange(n, dtype=np.float64) * ratio
    i0 = np.minimum(pos.astype(np.int64), len(x) - 2)
    frac = (pos - i0).astype(np.float32)
    a = x[i0].astype(np.float32)
    return (a + (x[i0 + 1].astype(np.float32) - a) * frac) / 32768.0


def _sustained(x: np.ndarray, take: dict, src_sr: int, n: int, ratio: float, sr: int) -> np.ndarray:
    """The recording resampled to ``n`` samples; past its steady part it continues on a crossfaded loop."""
    avail = int((len(x) - 2) / ratio)
    if n <= avail:
        return _read(x, 0.0, n, ratio)
    loop_a = (float(take.get("onset_sec", 0.0)) + _LOOP_FROM_SEC) * src_sr
    loop_b = (float(take.get("seconds", len(x) / src_sr)) - _LOOP_BEFORE_END_SEC) * src_sr
    xf = int(LOOP_CROSSFADE_SEC * sr)
    loop_n = int((loop_b - loop_a) / ratio)
    if loop_n <= 2 * xf:
        return _read(x, 0.0, min(n, avail), ratio)
    t = np.linspace(0.0, np.pi / 2, xf, dtype=np.float32)
    fade_out, fade_in = np.cos(t), np.sin(t)  # equal power: the two ends are the same note, not the same waveform
    out = _read(x, 0.0, int(loop_b / ratio), ratio)
    while len(out) < n:
        seg = _read(x, loop_a, loop_n, ratio)
        out[-xf:] = out[-xf:] * fade_out + seg[:xf] * fade_in
        out = np.concatenate([out, seg[xf:]])
    return out[:n]


def _velocity_gain(velocity: float, layer_velocity: float) -> float:
    """Level within a layer: the recorded layer plays at 1.0, softer and louder touches around it."""
    v = min(1.0, max(0.05, float(velocity)))
    return float(min(1.5, max(0.2, (v / max(0.05, float(layer_velocity))) ** 1.2)))


def _add_note(bus: np.ndarray, sr: int, note: HornNote, seed: str, avoid: dict, attack_sec: float | None) -> None:
    art = note.articulation or choose_articulation(note.dur_sec)
    inst = _pack()[art]
    midi = clamp_to_range(note.midi)
    start = int(max(0.0, note.start_sec) * sr)
    if start >= len(bus):
        return
    zone = inst._zone(midi)
    take = inst._take(zone, note.velocity, seed, avoid)
    layer_v = next(la["velocity"] for la in zone["layers"] if take in la["takes"])
    x = inst._audio(take["file"])
    ratio = 2.0 ** ((midi - zone["key"] - float(take.get("cents", 0.0)) / 100.0) / 12.0) * inst.sr / sr
    held_n = max(1, int(max(0.03, note.dur_sec) * sr))
    release_n = max(2, int(RELEASE_SEC[art] * sr))
    n = min(held_n + release_n, len(bus) - start)
    if art == "staccato":
        n = min(n, int((len(x) - 2) / ratio))  # a staccato note dies away inside its recording
        seg = _read(x, 0.0, n, ratio)
    else:
        seg = _sustained(x, take, inst.sr, n, ratio, sr)
    n = len(seg)
    if n < 4:
        return
    attack_n = min(n // 2, max(2, int((ATTACK_SEC[art] if attack_sec is None else attack_sec) * sr)))
    seg[:attack_n] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(attack_n, dtype=np.float32) / attack_n)
    rel_from = min(held_n, n - 2)
    rel_n = n - rel_from
    seg[rel_from:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(1, rel_n + 1, dtype=np.float32) / rel_n)
    bus[start : start + n] += seg * float(take.get("gain", 1.0)) * _velocity_gain(note.velocity, layer_v)


def render_line(
    notes: Sequence[HornNote],
    sr: int = 44100,
    *,
    gain: float = 0.5,
    seconds: float | None = None,
    seed: str = "tenor",
    attack_sec: float | None = None,
) -> np.ndarray | None:
    """The notes played by the tenor, after :func:`breathe`, as mono float32. None while ``MUSIC_HORNS`` is off."""
    if not enabled():
        return None
    played = breathe(notes)
    end = max((n.start_sec + n.dur_sec for n in played), default=0.0) + 0.5
    bus = np.zeros(int((seconds if seconds is not None else end) * sr), dtype=np.float32)
    avoid: dict = {}
    for i, n in enumerate(played):
        _add_note(bus, sr, n, f"{seed}:{i}:{n.voice}:{n.midi}", avoid, attack_sec)
    bus *= float(gain)
    return bus


# --- Writing a part -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class ChordSpan:
    chord: str
    start_sec: float
    dur_sec: float
    beats: float


def chord_timeline(chords: Sequence, bars: int, bpm: float, beats_per_bar: int = 4) -> list[ChordSpan]:
    """``chords`` as symbols (one bar each) or ``(symbol, beats)``, repeated until ``bars`` bars are filled."""
    items = [(c, float(beats_per_bar)) if isinstance(c, str) else (str(c[0]), float(c[1])) for c in chords]
    if not items or bars <= 0 or bpm <= 0:
        return []
    beat = 60.0 / float(bpm)
    total = bars * beats_per_bar
    out: list[ChordSpan] = []
    at = 0.0
    i = 0
    while at < total - 1e-9:
        chord, beats = items[i % len(items)]
        beats = min(beats, total - at)
        out.append(ChordSpan(chord, at * beat, beats * beat, beats))
        at += beats
        i += 1
    return out


def guide_tones(chord: str) -> tuple[int, ...]:
    """The chord's 3rd and 7th as pitch classes (a triad's root stands in for the missing 7th)."""
    import backing_audio
    from backing_pianist import harmony_of

    h = harmony_of(chord, backing_audio.chord_notes, backing_audio.bass_note, colour=False)
    pcs = h.guides
    if len(pcs) < 2:
        pcs = tuple(dict.fromkeys(pcs + ((h.fifth,) if h.fifth is not None else ()) + (h.root,)))[:2]
    return tuple(pcs)


def _options(pcs: Iterable[int], low: int, high: int) -> list[int]:
    wanted = {p % 12 for p in pcs}
    return [m for m in range(low, high + 1) if m % 12 in wanted]


def _closest(options: list[int], near: int) -> int | None:
    """Nearest to ``near``; of two equally near, the higher (guide-tone lines mostly fall, so it leaves room)."""
    return min(options, key=lambda m: (abs(m - near), -m)) if options else None


def guide_tone_line(chords: Sequence[str], *, voices: int = 1, start: int = BACKGROUND_CENTRE) -> list[tuple[int, ...]]:
    """For each chord, ``voices`` guide tones, each voice moving to the nearest guide tone of the next chord.

    The top voice stays within ``BACKGROUND_LOW..BACKGROUND_HIGH``. A second voice plays the other guide
    tone below it (down to the horn's lowest note); the pair that moves least in total is chosen, so the
    voices may trade guide tones. With two voices the top one stays at least a sixth above the horn's
    lowest note, so the lower one always has room.
    """
    floor = max(BACKGROUND_LOW, TENOR_LOW + 9) if voices > 1 else BACKGROUND_LOW
    lines: list[tuple[int, ...]] = []
    prev: list[int] = []
    for chord in chords:
        pcs = guide_tones(chord)
        tops = _options(pcs if prev else pcs[:1], floor, BACKGROUND_HIGH)
        if voices < 2 or len(set(pcs)) < 2:
            chosen = [_closest(tops, prev[0] if prev else start)]
        elif not prev:
            top = _closest(tops, start)
            chosen = [top, _closest(_options([p for p in pcs if p != top % 12], TENOR_LOW, top - 1), top - 4)]
        else:
            pairs = [(t, b) for t in tops for b in _options([p for p in pcs if p != t % 12], TENOR_LOW, t - 1)]
            chosen = list(min(pairs, key=lambda tb: (abs(tb[0] - prev[0]) + abs(tb[1] - prev[-1]), max(abs(tb[0] - prev[0]), abs(tb[1] - prev[-1])), -tb[0])))
        lines.append(tuple(chosen))
        prev = chosen
    return lines


def sustained_background(
    timeline: Sequence[ChordSpan], *, voices: int = 1, phrase_bars: int = 4, beats_per_bar: int = 4, velocity: float = 0.6
) -> list[HornNote]:
    """Each chord held on its guide tones; the last note of every ``phrase_bars`` bars leaves room to breathe."""
    if not timeline:
        return []
    line = guide_tone_line([s.chord for s in timeline], voices=voices)
    beat = timeline[0].dur_sec / timeline[0].beats if timeline[0].beats else 0.5
    phrase_sec = phrase_bars * beats_per_bar * beat
    # A guide tone the next chord keeps is tied over, not re-tongued, unless a phrase ends between them.
    held: list[list] = []  # [start, end, pitches]
    for span, pitches in zip(timeline, line):
        end = span.start_sec + span.dur_sec
        if held and held[-1][2] == pitches and not _ends_phrase(held[-1][1], phrase_sec):
            held[-1][1] = end
        else:
            held.append([span.start_sec, end, pitches])
    notes: list[HornNote] = []
    for start, end, pitches in held:
        dur = end - start - (max(BREATH_SEC, beat * 0.5) if _ends_phrase(end, phrase_sec) else TONGUE_GAP_SEC)
        for v, m in enumerate(pitches):
            notes.append(HornNote(start, dur, m, velocity, "sustain", v))
    return breathe(notes)


def _ends_phrase(t: float, phrase_sec: float) -> bool:
    return phrase_sec > 0 and abs(round(t / phrase_sec) * phrase_sec - t) < 1e-6


def staccato_hits(
    timeline: Sequence[ChordSpan], *, voices: int = 1, beats: Sequence[float] = (1.5, 3.0), velocity: float = 0.85
) -> list[HornNote]:
    """Short punches at ``beats`` (from the bar's first beat, 0-based) of every chord, on its guide tones."""
    if not timeline:
        return []
    line = guide_tone_line([s.chord for s in timeline], voices=voices)
    notes: list[HornNote] = []
    for span, pitches in zip(timeline, line):
        beat = span.dur_sec / span.beats if span.beats else 0.5
        for b in beats:
            if b >= span.beats:
                continue
            for v, m in enumerate(pitches):
                notes.append(HornNote(span.start_sec + b * beat, min(STACCATO_MAX_SEC, beat * 0.4), m, velocity, "staccato", v))
    return breathe(notes)


def render_horn_background(
    chords: Sequence, bars: int, bpm: float, *, part: str = "pads", voices: int = 1, sr: int = 44100, gain: float = 0.5, beats_per_bar: int = 4
) -> np.ndarray | None:
    """A tenor background (``part`` = ``pads`` or ``hits``) for the chords. None while ``MUSIC_HORNS`` is off."""
    if not enabled():
        return None
    timeline = chord_timeline(chords, bars, bpm, beats_per_bar)
    if part == "hits":
        notes = staccato_hits(timeline, voices=voices)
    else:
        notes = sustained_background(timeline, voices=voices, beats_per_bar=beats_per_bar)
    total = bars * beats_per_bar * 60.0 / float(bpm) + 0.6
    return render_line(notes, sr, gain=gain, seconds=total, seed=f"tenor-{part}")
