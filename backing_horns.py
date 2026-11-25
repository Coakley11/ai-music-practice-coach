"""Recorded horns - tenor sax, trombone, trumpet - for backgrounds behind the soloist (numpy only).

Off by default: nothing here runs unless ``MUSIC_HORNS`` is switched on (``1`` / ``on`` / ``tenor``)
*and* the pack in ``assets/instruments/tenor_sax`` is present. Then the Jazz quartet's horn is the tenor
(``backing_audio._horn_background``). The trombone and trumpet (``instrument="trombone"`` /
``"trumpet"``, CC0 VSCO 2 CE packs) and the two-horn :func:`render_section_background` are only played
by a caller that asks for them: no ensemble uses them yet.

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

:func:`render_horn_background` puts those together; :func:`render_line` plays any list of notes. Each
takes ``instrument=`` (default ``"tenor"``, whose sound never changes); every horn has its own recorded
range, background register, attack and release (:data:`HORNS`). The brass packs have two sustain layers,
so a held line keeps one layer for a given dynamic instead of the per-note nudge short notes get.

:func:`section_voicing` writes two horns together (e.g. trumpet over tenor): the top horn on a guide-tone
line, the lower one a third or a sixth (or a tenth) under it on another chord tone, each moving as little
as it can, and neither ever on the root or the bass note (the bass has it).
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

_INSTRUMENTS = pathlib.Path(__file__).resolve().parent / "assets" / "instruments"


@dataclass(frozen=True)
class Horn:
    """One recorded horn: where its pack is, what it can play and how a note starts and ends."""

    name: str
    pack: pathlib.Path
    low: int  # recorded concert range (the pack's manifest says the same)
    high: int
    background: tuple[int, int, int]  # low, high and centre of a background line
    attack_sec: dict
    release_sec: dict
    steady_layers: bool = False  # a sustain keeps the layer its velocity names (no per-note nudge)
    aligned_loops: bool = False  # a long sustain's loop starts where its waveform matches the join (see _loop_start)
    label: str = ""
    # Level per articulation, so this horn's backgrounds at their default dynamics (pads 0.6, hits 0.85) sound as
    # loud as the tenor's (measured: RMS of the sounding part over four jazz progressions). None: as recorded.
    level: dict | None = None


HORNS: dict[str, Horn] = {
    "tenor": Horn("tenor", HORN_PACK, TENOR_LOW, TENOR_HIGH, (BACKGROUND_LOW, BACKGROUND_HIGH, BACKGROUND_CENTRE),
                  ATTACK_SEC, RELEASE_SEC, label="tenor sax"),
    # Concert F2-G4 recorded; backgrounds C3-D4, the trombone's singing middle, under a tenor or a trumpet.
    "trombone": Horn("trombone", _INSTRUMENTS / "trombone", 41, 67, (48, 62, 55),
                     {"sustain": 0.02, "staccato": 0.003}, {"sustain": 0.14, "staccato": 0.04},
                     steady_layers=True, aligned_loops=True, label="trombone", level={"sustain": 2.7, "staccato": 0.9}),
    # Concert F3-C6 recorded; backgrounds C4-F5 (written D4-G5), clear of the screech register.
    "trumpet": Horn("trumpet", _INSTRUMENTS / "trumpet", 53, 84, (60, 77, 68),
                    {"sustain": 0.015, "staccato": 0.002}, {"sustain": 0.10, "staccato": 0.035},
                    steady_layers=True, aligned_loops=True, label="trumpet", level={"sustain": 1.45, "staccato": 3.75}),
}


def horn(instrument: "str | Horn" = "tenor") -> Horn:
    if isinstance(instrument, Horn):
        return instrument
    try:
        return HORNS[str(instrument)]
    except KeyError:
        raise ValueError(f"no recorded horn {instrument!r}; known: {', '.join(HORNS)}") from None


def enabled() -> bool:
    """``MUSIC_HORNS`` is on and the tenor pack is present."""
    raw = str(os.environ.get("MUSIC_HORNS") or "").strip().lower()
    return raw in _ON and (HORN_PACK / "manifest.json").is_file()


def available(instrument: str = "tenor") -> bool:
    """``MUSIC_HORNS`` is on and this horn's pack is present: only then can it be offered."""
    return enabled() and (horn(instrument).pack / "manifest.json").is_file()


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


@lru_cache(maxsize=4)
def _pack(instrument: str = "tenor") -> dict[str, SampledInstrument]:
    """The sustained and staccato recordings, each as a SampledInstrument (decoded audio lives in the shared cache)."""
    folder = horn(instrument).pack
    sustain = SampledInstrument(folder)
    staccato = SampledInstrument(folder)
    staccato.zones = sorted(staccato.manifest["articulations"]["staccato"], key=lambda z: z["key"])
    staccato._keys = np.array([z["key"] for z in staccato.zones])
    return {"sustain": sustain, "staccato": staccato}


def pack_range(instrument: str = "tenor") -> tuple[int, int]:
    h = horn(instrument)
    manifest = json.loads((h.pack / "manifest.json").read_text(encoding="utf-8"))
    low, high = manifest.get("range", (h.low, h.high))
    return int(low), int(high)


def _read(x: np.ndarray, first: float, n: int, ratio: float) -> np.ndarray:
    """``n`` output samples from int16 ``x`` starting at source position ``first``, linearly interpolated."""
    pos = first + np.arange(n, dtype=np.float64) * ratio
    i0 = np.minimum(pos.astype(np.int64), len(x) - 2)
    frac = (pos - i0).astype(np.float32)
    a = x[i0].astype(np.float32)
    return (a + (x[i0 + 1].astype(np.float32) - a) * frac) / 32768.0


_LOOP_SEARCH_SEC = 0.03  # how far past the steady point a loop may start: more than one period of the lowest note
_LOOP_STARTS: dict = {}


def _loop_start(x: np.ndarray, key, loop_a: float, loop_b: float, src_sr: int, n: int) -> tuple[float, float]:
    """Where to start the loop so its first ``n`` source samples (the crossfade) match the ``n`` before ``loop_b``
    (a phase-locked recording then joins without a dip), and how well they match (normalised correlation)."""
    key = (key, int(loop_a), int(loop_b), int(n))
    hit = _LOOP_STARTS.get(key)
    if hit is None:
        search = int(_LOOP_SEARCH_SEC * src_sr)
        a, b = int(loop_a), int(loop_b)
        if a + search + n >= b - n or b > len(x):
            hit = (loop_a, 0.0)
        else:
            tail = x[b - n : b].astype(np.float64)
            body = x[a : a + search + n].astype(np.float64)
            dots = np.correlate(body, tail, mode="valid")
            power = np.convolve(body**2, np.ones(n), mode="valid")
            r = dots / np.sqrt(np.maximum(power * float(np.dot(tail, tail)), 1e-12))
            k = int(np.argmax(r))
            hit = (float(a + k), float(r[k]))
        _LOOP_STARTS[key] = hit
    return hit


def _sustained(x: np.ndarray, take: dict, src_sr: int, n: int, ratio: float, sr: int, loop_key=None) -> np.ndarray:
    """The recording resampled to ``n`` samples; past its steady part it continues on a crossfaded loop.

    With ``loop_key`` (a horn whose loops are aligned) the loop starts where its waveform best matches the join,
    and the crossfade is scaled for how well the two ends match, so the join neither dips nor swells."""
    avail = int((len(x) - 2) / ratio)
    if n <= avail:
        return _read(x, 0.0, n, ratio)
    loop_a = (float(take.get("onset_sec", 0.0)) + _LOOP_FROM_SEC) * src_sr
    loop_b = (float(take.get("seconds", len(x) / src_sr)) - _LOOP_BEFORE_END_SEC) * src_sr
    match = 0.0
    xf = int(LOOP_CROSSFADE_SEC * sr)
    if loop_key is not None:
        loop_a, match = _loop_start(x, loop_key, loop_a, loop_b, src_sr, int(xf * ratio))
    loop_n = int((loop_b - loop_a) / ratio)
    if loop_n <= 2 * xf:
        return _read(x, 0.0, min(n, avail), ratio)
    t = np.linspace(0.0, np.pi / 2, xf, dtype=np.float32)
    fade_out, fade_in = np.cos(t), np.sin(t)  # equal power: the two ends are the same note, not the same waveform
    if loop_key is not None:
        # The ends correlate by ``match``: scale the pair so the sum keeps its power through the join.
        norm = np.sqrt(1.0 + 2.0 * float(np.clip(match, -0.9, 0.95)) * fade_out * fade_in).astype(np.float32)
        fade_out, fade_in = fade_out / norm, fade_in / norm
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


def _take(inst: SampledInstrument, zone: dict, velocity: float, seed: str, avoid: dict, steady: bool) -> dict:
    """The take to play. ``steady``: the layer nearest ``velocity`` exactly, so a held line at one dynamic stays
    in one layer (the brass layers differ in tone); its round robins still alternate."""
    if not steady or len(zone["layers"]) < 2:
        return inst._take(zone, velocity, seed, avoid)
    layer = min(zone["layers"], key=lambda la: abs(la["velocity"] - float(velocity)))
    return inst._take({"key": zone["key"], "layers": [layer]}, velocity, seed, avoid)


def _add_note(
    bus: np.ndarray, sr: int, note: HornNote, seed: str, avoid: dict, attack_sec: float | None, h: "Horn | None" = None
) -> None:
    h = h or HORNS["tenor"]
    art = note.articulation or choose_articulation(note.dur_sec)
    inst = _pack(h.name)[art]
    midi = clamp_to_range(note.midi, h.low, h.high)
    start = int(max(0.0, note.start_sec) * sr)
    if start >= len(bus):
        return
    zone = inst._zone(midi)
    take = _take(inst, zone, note.velocity, seed, avoid, h.steady_layers and art == "sustain")
    layer_v = next(la["velocity"] for la in zone["layers"] if take in la["takes"])
    x = inst._audio(take["file"])
    ratio = 2.0 ** ((midi - zone["key"] - float(take.get("cents", 0.0)) / 100.0) / 12.0) * inst.sr / sr
    held_n = max(1, int(max(0.03, note.dur_sec) * sr))
    release_n = max(2, int(h.release_sec[art] * sr))
    n = min(held_n + release_n, len(bus) - start)
    if art == "staccato":
        n = min(n, int((len(x) - 2) / ratio))  # a staccato note dies away inside its recording
        seg = _read(x, 0.0, n, ratio)
    else:
        seg = _sustained(x, take, inst.sr, n, ratio, sr, (h.name, take["file"]) if h.aligned_loops else None)
    n = len(seg)
    if n < 4:
        return
    attack_n = min(n // 2, max(2, int((h.attack_sec[art] if attack_sec is None else attack_sec) * sr)))
    seg[:attack_n] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(attack_n, dtype=np.float32) / attack_n)
    rel_from = min(held_n, n - 2)
    rel_n = n - rel_from
    seg[rel_from:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(1, rel_n + 1, dtype=np.float32) / rel_n)
    if h.level is not None:
        seg *= np.float32(h.level[art])
    bus[start : start + n] += seg * float(take.get("gain", 1.0)) * _velocity_gain(note.velocity, layer_v)


def render_line(
    notes: Sequence[HornNote],
    sr: int = 44100,
    *,
    gain: float = 0.5,
    seconds: float | None = None,
    seed: str = "tenor",
    attack_sec: float | None = None,
    instrument: str = "tenor",
) -> np.ndarray | None:
    """The notes played by ``instrument``, after :func:`breathe`, as mono float32. None while ``MUSIC_HORNS``
    is off or the horn's pack is missing."""
    h = horn(instrument)
    if not available(h.name):
        return None
    played = breathe(notes)
    end = max((n.start_sec + n.dur_sec for n in played), default=0.0) + 0.5
    bus = np.zeros(int((seconds if seconds is not None else end) * sr), dtype=np.float32)
    avoid: dict = {}
    for i, n in enumerate(played):
        _add_note(bus, sr, n, f"{seed}:{i}:{n.voice}:{n.midi}", avoid, attack_sec, h)
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


def guide_tone_line(
    chords: Sequence[str], *, voices: int = 1, start: int | None = None, instrument: str = "tenor"
) -> list[tuple[int, ...]]:
    """For each chord, ``voices`` guide tones, each voice moving to the nearest guide tone of the next chord.

    The top voice stays within the horn's background register (the tenor's: ``BACKGROUND_LOW..BACKGROUND_HIGH``).
    A second voice plays the other guide tone below it (down to the horn's lowest note); the pair that moves
    least in total is chosen, so the voices may trade guide tones. With two voices the top one stays at least
    a sixth above the horn's lowest note, so the lower one always has room.
    """
    h = horn(instrument)
    bg_low, bg_high, centre = h.background
    start = centre if start is None else start
    floor = max(bg_low, h.low + 9) if voices > 1 else bg_low
    lines: list[tuple[int, ...]] = []
    prev: list[int] = []
    for chord in chords:
        pcs = guide_tones(chord)
        tops = _options(pcs if prev else pcs[:1], floor, bg_high)
        if voices < 2 or len(set(pcs)) < 2:
            chosen = [_closest(tops, prev[0] if prev else start)]
        elif not prev:
            top = _closest(tops, start)
            chosen = [top, _closest(_options([p for p in pcs if p != top % 12], h.low, top - 1), top - 4)]
        else:
            pairs = [(t, b) for t in tops for b in _options([p for p in pcs if p != t % 12], h.low, t - 1)]
            chosen = list(min(pairs, key=lambda tb: (abs(tb[0] - prev[0]) + abs(tb[1] - prev[-1]), max(abs(tb[0] - prev[0]), abs(tb[1] - prev[-1])), -tb[0])))
        lines.append(tuple(chosen))
        prev = chosen
    return lines


def sustained_background(
    timeline: Sequence[ChordSpan],
    *,
    voices: int = 1,
    phrase_bars: int = 4,
    beats_per_bar: int = 4,
    velocity: float = 0.6,
    instrument: str = "tenor",
) -> list[HornNote]:
    """Each chord held on its guide tones; the last note of every ``phrase_bars`` bars leaves room to breathe."""
    if not timeline:
        return []
    line = guide_tone_line([s.chord for s in timeline], voices=voices, instrument=instrument)
    return _held_line(timeline, line, phrase_bars, beats_per_bar, velocity)


def _held_line(timeline: Sequence[ChordSpan], line, phrase_bars: int, beats_per_bar: int, velocity: float) -> list[HornNote]:
    """``line``'s pitches (one tuple per chord, top voice first) held for their chords, tied and breathed."""
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
    timeline: Sequence[ChordSpan],
    *,
    voices: int = 1,
    beats: Sequence[float] = (1.5, 3.0),
    velocity: float = 0.85,
    instrument: str = "tenor",
) -> list[HornNote]:
    """Short punches at ``beats`` (from the bar's first beat, 0-based) of every chord, on its guide tones."""
    if not timeline:
        return []
    line = guide_tone_line([s.chord for s in timeline], voices=voices, instrument=instrument)
    return _hit_line(timeline, line, beats, velocity)


def _hit_line(timeline: Sequence[ChordSpan], line, beats: Sequence[float], velocity: float) -> list[HornNote]:
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
    chords: Sequence,
    bars: int,
    bpm: float,
    *,
    part: str = "pads",
    voices: int = 1,
    sr: int = 44100,
    gain: float = 0.5,
    beats_per_bar: int = 4,
    instrument: str = "tenor",
) -> np.ndarray | None:
    """One horn's background (``part`` = ``pads`` or ``hits``) for the chords. None while ``MUSIC_HORNS`` is off."""
    if not available(instrument):
        return None
    timeline = chord_timeline(chords, bars, bpm, beats_per_bar)
    if part == "hits":
        notes = staccato_hits(timeline, voices=voices, instrument=instrument)
    else:
        notes = sustained_background(timeline, voices=voices, beats_per_bar=beats_per_bar, instrument=instrument)
    total = bars * beats_per_bar * 60.0 / float(bpm) + 0.6
    return render_line(notes, sr, gain=gain, seconds=total, seed=f"{instrument}-{part}", instrument=instrument)



# --- Two horns ----------------------------------------------------------------------------------------

SECTION_INTERVALS = (3, 4, 8, 9, 15, 16)  # the lower horn a third, a sixth or a tenth under the top one
_FALLBACK_INTERVALS = (5, 7, 10, 17)  # a fourth, fifth, seventh or eleventh when no third or sixth is a chord tone
LOWER_HORN_LEVEL = 0.85  # the lower horn a touch (-1.4 dB) under the lead


def section_tones(chord: str) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """(guide tones, every tone a horn may play) as pitch classes, neither holding the root or the bass note."""
    import backing_audio
    from backing_pianist import harmony_of

    h = harmony_of(chord, backing_audio.chord_notes, backing_audio.bass_note, colour=True)
    bass = {h.root, h.bass}
    named = (h.third, h.seventh, h.fifth) + tuple(h.written) + tuple(h.extensions)
    tones = tuple(p for p in dict.fromkeys(named) if p is not None and p not in bass)
    # The 3rd and 7th; a triad's 5th stands in for the missing 7th.
    pair = (h.third, h.seventh if h.seventh is not None else h.fifth)
    guides = tuple(p for p in pair if p is not None and p not in bass) or tones[:2]
    return guides, tones


def _section_pairs(chord: str, hi_h: Horn, lo_h: Horn) -> list[tuple[int, int, float]]:
    """Every (top, lower, penalty) the two horns could play on ``chord``."""
    t_low, t_high, _ = hi_h.background
    b_low, b_high, _ = lo_h.background
    guides, tones = section_tones(chord)
    tops = _options(guides, t_low, t_high) or _options(tones, t_low, t_high)
    out: list[tuple[int, int, float]] = []
    for t in tops:
        ceiling = min(b_high, t - 3)
        pairs = [(t, b, 0.0) for b in _options([p for p in tones if p != t % 12], b_low, ceiling) if t - b in SECTION_INTERVALS]
        if not pairs:
            pairs = [(t, b, 3.0) for b in _options(tones, b_low, ceiling) if t - b in _FALLBACK_INTERVALS]
        out.extend(pairs)
    if not out:  # a bare fifth: nothing else to play, so the lower horn takes the top note an octave down
        t = _closest(tops, hi_h.background[2]) or clamp_to_range(hi_h.background[2], t_low, t_high)
        out.append((t, clamp_to_range(t - 12, b_low, b_high), 6.0))
    return out


def _move_cost(a: tuple[int, int, float], b: tuple[int, int, float]) -> float:
    mt, mb = abs(b[0] - a[0]), abs(b[1] - a[1])
    return mt + mb + 0.5 * max(mt, mb) + 2.0 * max(0, mt - 4) + 2.0 * max(0, mb - 4) + b[2]


def section_voicing(chords: Sequence[str], *, top: str = "trumpet", bottom: str = "tenor") -> list[tuple[int, int]]:
    """For each chord, the (top horn, lower horn) concert pitches.

    The top horn plays a guide tone in its background register. The lower horn takes a chord tone a third,
    sixth or tenth under it (a fourth, fifth, seventh or eleventh only when the chord offers none), in its own
    background register. Over the whole progression the pairs that move the two horns least are chosen (no
    leap of more than a major third unless nothing else fits), starting near the middle of each register.
    Neither horn plays the root or the bass note, so they never double the bass.
    """
    hi_h, lo_h = horn(top), horn(bottom)
    if not chords:
        return []
    states = [_section_pairs(c, hi_h, lo_h) for c in chords]
    t_centre, b_centre = hi_h.background[2], lo_h.background[2]
    cost = [abs(s[0] - t_centre) + 0.5 * abs(s[1] - b_centre) + s[2] for s in states[0]]
    back: list[list[int]] = []
    for prev, cur in zip(states, states[1:]):
        step, nxt = [], []
        for s in cur:
            k = min(range(len(prev)), key=lambda i: (cost[i] + _move_cost(prev[i], s), -prev[i][0]))
            step.append(k)
            nxt.append(cost[k] + _move_cost(prev[k], s))
        back.append(step)
        cost = nxt
    k = min(range(len(cost)), key=lambda i: (cost[i], -states[-1][i][0]))
    path = [k]
    for step in reversed(back):
        k = step[k]
        path.append(k)
    path.reverse()
    return [(states[i][j][0], states[i][j][1]) for i, j in enumerate(path)]


def section_background(
    timeline: Sequence[ChordSpan],
    *,
    top: str = "trumpet",
    bottom: str = "tenor",
    part: str = "pads",
    phrase_bars: int = 4,
    beats_per_bar: int = 4,
    velocity: float | None = None,
) -> dict[str, list[HornNote]]:
    """Each horn's notes (its own player, voice 0) for a two-horn background: ``pads`` held, ``hits`` short."""
    if not timeline:
        return {top: [], bottom: []}
    line = section_voicing([s.chord for s in timeline], top=top, bottom=bottom)
    if part == "hits":
        notes = _hit_line(timeline, line, (1.5, 3.0), 0.85 if velocity is None else velocity)
    else:
        notes = _held_line(timeline, line, phrase_bars, beats_per_bar, 0.6 if velocity is None else velocity)
    return {name: [replace(n, voice=0) for n in notes if n.voice == v] for v, name in enumerate((top, bottom))}


def render_section_background(
    chords: Sequence,
    bars: int,
    bpm: float,
    *,
    top: str = "trumpet",
    bottom: str = "tenor",
    part: str = "pads",
    sr: int = 44100,
    gain: float = 0.5,
    beats_per_bar: int = 4,
    velocity: float | None = None,
) -> np.ndarray | None:
    """Two horns together, each levelled to the other (the lower one :data:`LOWER_HORN_LEVEL` under the lead).
    None while ``MUSIC_HORNS`` is off or either pack is missing."""
    if not (available(top) and available(bottom)):
        return None
    timeline = chord_timeline(chords, bars, bpm, beats_per_bar)
    parts = section_background(timeline, top=top, bottom=bottom, part=part, beats_per_bar=beats_per_bar, velocity=velocity)
    total = bars * beats_per_bar * 60.0 / float(bpm) + 0.6
    lines = [render_line(parts[name], sr, gain=1.0, seconds=total, seed=f"{name}-section-{part}", instrument=name) for name in (top, bottom)]
    rms = [float(np.sqrt(np.mean(y.astype(np.float64) ** 2))) for y in lines]
    if min(rms) <= 1e-9:
        return ((lines[0] + lines[1]) * np.float32(gain)).astype(np.float32)
    ref = 0.5 * (rms[0] + rms[1])
    mix = lines[0] * np.float32(ref / rms[0]) + lines[1] * np.float32(LOWER_HORN_LEVEL * ref / rms[1])
    return (mix * np.float32(gain)).astype(np.float32)
