"""Song-Aware Coaching (S5) — practice loops played by the app's shared backing arranger.

A loop is the selected bars of the coached song, rendered by ``backing_audio`` (the same
arranger Backing Studio uses: style grooves, bass, comping, drums, 6/8 feels, split bars, slash
basses, N.C. bars) and cut so it repeats seamlessly. This module is pure: it never reads or
writes session state, never uses Backing Studio's caches or transport, and never changes the
shared arranger.

- **Bars as charted.** The arranger receives the selection's own bar tokens (``"C:2|G:2"``,
  pushes, hits, ``N.C.``), parsed by the same ``chord_subdivisions`` code as the coaching
  scope, so the audio and the coaching text agree on every chord change.
- **Never wrong harmony.** The shared arranger reads some chord qualities lossily (it voices
  ``sus2`` as ``sus4``, gives ``m(maj7)`` a major 3rd, adds a 3rd to ``5`` chords …). Every
  pitch it would voice — comp and bass — is checked against the coaching chord reader first;
  if any would be a wrong note, the loop is refused and the chord is named
  (:func:`voicing_problems`).
- **Mid-bar changes are refused.** In a split bar (``"C:2|G:2"``, pushes) the shared arranger's
  comping follows the second chord but its bass keeps its usual beat-3 approach into the next
  bar (an A♭ under the G of ``C:2|G:2``) — a wrong bass note. Until the arranger follows
  mid-bar changes, such bars are not looped (:func:`timing_problems`).
- **Seamless loop.** The arranger is asked for several passes; the loop is the middle pass
  (it starts with the previous pass's ring-over and is clear of any count-in, first-bar crash
  or programmed outro fade). The last milliseconds of the loop — the release of its final
  bar — are cross-faded into what preceded the middle pass in the full render, so the final
  sample flows straight into the untouched first downbeat (its attack is never blended).
- **Identity.** A loop's signature covers the song identity, chart fingerprint, concert key,
  meter, bars, tempo, style and level: any change there is a different loop — stale audio is
  never reused.

Shared-arranger defects found in S5 (left unchanged — for a separately approved "Shared Backing
Harmony Accuracy" repair; reproduced in ``tests/test_song_coach_backing.py::TestSharedArrangerDefects``):

1. **Split-bar bass** — ``backing_audio._bass_motion_pitch``: the last bass slot of every bar is
   a half-step approach to the *next bar's* chord (``target - 1``), even when that slot is the
   only bass note of a chord that starts mid-bar. ``"C:2|G:2", "Am"`` (Pop groove, bass on
   beats 1 and 3) plays A♭ where G belongs; ``"Fmaj7|Am7"`` → C♯ under Am7; 6/8 ``"G:3|D:3"``
   → E♭ under D. ``_pulse_chord`` / ``_pulse_next_chord`` already know the sub-chord; the
   approach rule doesn't check that its slot starts a new chord. Side effect in whole bars:
   two-slot styles (Pop, Ballad) always put a chromatic approach on beat 3. Affects 12 of 119
   catalog songs (183 bars, 2.2 %: Say, The Scientist, Piano Man, Satin Doll, I'm Yours …),
   Custom progressions with split bars or pushes. Coaching: refused (:func:`timing_problems`).
2. **Chord qualities** — ``backing_audio.chord_notes`` (substring tests in a fixed order;
   ``_voicing_for_comp`` and the bass build on it): ``sus2`` → sus4 (the ``"sus"`` branch),
   ``aug`` / ``+`` → no ♯5 (no branch), ``5`` → adds a 3rd, ``m(maj7)`` → major 3rd (``"maj7"``
   matched before ``"m"``), ``9sus4`` → adds a 3rd (``"9"`` before ``"sus"``), ``7b9`` / ``7#9``
   → natural 9 added (``"9"`` branch, then the alteration appended), ``7b13`` → natural 9 and
   13, ``69`` → ♭7, ``maj13`` → ♭7 (``"13"`` branch is dominant). Affects 13 catalog songs
   (Dsus2, Csus2, D7b9, E9sus4, Faug, B5, Dbmaj13, A7#9 … in Wave, Corcovado, So Nice, Vienna,
   The Scientist …). Coaching: refused, naming the chord (:func:`voicing_problems`).
3. **Blues walking line** — ``_bass_motion_pitch`` "Blues groove": ``flat7 = fifth - 2`` is the
   4th (F under C7), not the ♭7. Musically a passing tone, so not refused; worth fixing.
"""

from __future__ import annotations

import hashlib
import io
import json
import wave
from collections import OrderedDict
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np

LOOP_VERSION = "s5.2"
LOOP_SAMPLE_RATE = 22050  # mono 16-bit: small enough to hand to the in-page player
CROSSFADE_SEC = 0.012
TEMPO_MIN, TEMPO_MAX = 40, 220
DEFAULT_BPM = 90
CACHE_MAX = 8

STYLE_TO_ARRANGER = {
    "ballad": "Ballad",
    "jazz_ballad": "Ballad",
    "bossa": "Bossa nova",
    "samba": "Bossa nova",
    "latin": "Bossa nova",
    "jazz": "Jazz swing",
    "swing": "Jazz swing",
    "blues": "Blues groove",
    "rock": "Rock groove",
    "funk": "Funk groove",
    "soul": "Funk groove",
    "pop": "Pop groove",
    "folk": "Pop groove",
    "default": "Pop groove",
}

REFUSAL_VOICING = "voicing"
REFUSAL_EMPTY = "empty"
REFUSAL_SPLIT_BAR = "split_bar"


@dataclass(frozen=True)
class LoopRequest:
    identity: str
    fingerprint: str
    concert_key: str
    meter: str
    section_label: str
    start_bar: int
    end_bar: int
    bars: tuple[str, ...]  # the chart's own bar tokens, concert pitch
    bpm: int
    style: str  # arranger style ("Ballad", "Bossa nova" …)
    level: str = "Intermediate"
    song_title: str = ""
    artist: str = ""

    @property
    def bar_count(self) -> int:
        return len(self.bars)

    def signature(self) -> str:
        payload = json.dumps({"v": LOOP_VERSION, **asdict(self)}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]

    def range_key(self) -> str:
        """Identity of *what* is looped, independent of tempo (the player resumes across a
        tempo change, never across a change of song, chart, key or bars)."""
        payload = json.dumps([self.identity, self.fingerprint, self.concert_key, self.meter,
                              self.start_bar, self.end_bar, list(self.bars)], ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class LoopEvent:
    start: float  # seconds from the loop start
    end: float
    chord: str  # "" for N.C.
    bass_pc: int  # sounding bass pitch class (slash bass); -1 for N.C.
    root_pc: int  # chord root pitch class; -1 for N.C.
    bar: int  # section bar the chord starts in


@dataclass(frozen=True)
class PracticeLoop:
    request: LoopRequest
    wav: bytes
    sample_rate: int
    bar_seconds: float
    loop_seconds: float
    events: tuple[LoopEvent, ...]
    passes: int

    @property
    def signature(self) -> str:
        return self.request.signature()


@dataclass(frozen=True)
class LoopRefusal:
    kind: str
    message: str
    chords: tuple[str, ...] = ()


# --------------------------------------------------------------------------- request


def arranger_style(style: str = "", record: Mapping[str, Any] | None = None) -> str:
    """The arranger groove for the song: a catalog song's own groove (``infer_groove_style``,
    the same choice Backing Studio makes on "Auto"), else the coaching style mapped."""
    from backing_audio import infer_groove_style

    if record:
        try:
            return str(infer_groove_style(dict(record), "Auto") or "Pop groove")
        except Exception:
            pass
    return STYLE_TO_ARRANGER.get(str(style or "default").strip().lower(), "Pop groove")


def clamp_bpm(bpm: Any, default: int = DEFAULT_BPM) -> int:
    try:
        value = int(bpm)
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        value = int(default or DEFAULT_BPM)
    return max(TEMPO_MIN, min(TEMPO_MAX, value))


def loop_request(
    ctx: Any,
    scope: Any,
    *,
    start_bar: int,
    end_bar: int,
    bpm: int,
    style: str,
    level: str = "Intermediate",
) -> LoopRequest:
    """The loop for bars ``start_bar``–``end_bar`` (section bars) of the plan's ``scope``."""
    first = max(scope.start_bar, int(start_bar))
    last = min(scope.end_bar, max(first, int(end_bar)))
    bars = tuple(scope.bars[first - scope.start_bar: last - scope.start_bar + 1])
    return LoopRequest(
        identity=str(ctx.identity), fingerprint=str(ctx.fingerprint), concert_key=str(scope.key_center),
        meter=str(scope.meter or "4/4"), section_label=str(scope.section_label or "Practice Loop"),
        start_bar=first, end_bar=last, bars=bars, bpm=clamp_bpm(bpm), style=str(style or "Pop groove"),
        level=str(level or "Intermediate"), song_title=str(getattr(ctx, "song_title", "") or ""),
        artist=str(getattr(ctx, "artist", "") or ""),
    )


# --------------------------------------------------------------------------- harmony check


def _bar_chords(token: str, meter: str) -> list[str]:
    """The sounding chord symbols charted in one bar (hits keep their chord, N.C. is dropped)."""
    from chord_subdivisions import hit_underlying_chord, parse_subdivisions
    from music_theory import is_no_chord_token

    from song_coach_scope import _beats_per_bar

    out = []
    for sub in parse_subdivisions(str(token), beats_per_bar=_beats_per_bar(meter)) or []:
        raw = hit_underlying_chord(str(sub.chord or "").strip())
        if raw and not is_no_chord_token(raw):
            out.append(raw)
    return out


def voicing_problems(request: LoopRequest) -> list[str]:
    """Chords the shared arranger would voice with a wrong note, described for the musician.

    Against the coaching chord reader: the arranger's chord tones must be the chart's own
    tones (so ``Dsus2`` voiced as a sus4, ``C7b9`` with a natural 9th or ``C5`` with a 3rd are
    caught), any note its style voicing adds on top must be a holdable colour, and its bass
    must be the chord's (slash) bass."""
    from backing_audio import _voicing_for_comp, bass_note, chord_notes
    from music_theory import normalize_chord_for_theory
    from songs.meter import meter_timing

    from song_coach_harmony import HOLDABLE, chord_facts, key_facts, note_use, pc_of

    pulses = int(meter_timing(max(1, request.bpm), request.meter).pulses_per_bar)
    spell = key_facts(request.concert_key).spell
    problems: list[str] = []
    seen: set[str] = set()
    for token in request.bars:
        for raw in _bar_chords(token, request.meter):
            if raw in seen:
                continue
            seen.add(raw)
            facts = chord_facts(normalize_chord_for_theory(raw))
            if facts is None:
                problems.append(f"{raw} (the backing can't read this chord)")
                continue
            tones = {int(n) % 12 for n in chord_notes(raw)}
            added: set[int] = set()
            for beat in range(max(1, pulses)):
                added |= {int(n) % 12 for n in _voicing_for_comp(raw, request.level, request.style, beat)}
            bass = int(bass_note(raw)) % 12
            wrong = sorted(
                {pc for pc in tones if pc not in facts.charted_pcs}
                | {pc for pc in added - tones if note_use(facts, pc, key=request.concert_key).category not in HOLDABLE}
            )
            if facts.bass and pc_of(facts.bass) != bass:
                problems.append(f"{raw} (the backing would put {spell(bass)} in the bass)")
            elif wrong:
                names = ", ".join(spell(pc) for pc in wrong)
                problems.append(f"{raw} (the backing would add {names})")
    return problems


def timing_problems(request: LoopRequest) -> list[int]:
    """Section bars where a chord changes after the downbeat (split bars, pushes)."""
    from song_coach_scope import _beats_per_bar, harmony_events

    bpb = _beats_per_bar(request.meter)
    bars = []
    for ev in harmony_events(list(request.bars), meter=request.meter, first_bar=request.start_bar):
        if ev.chord and abs(ev.start_beat / bpb - round(ev.start_beat / bpb)) > 1e-6:
            bars.append(int(ev.start_bar))
    return sorted(set(bars))


def check_loop(request: LoopRequest) -> LoopRefusal | None:
    """Why these bars can't be looped faithfully, or ``None`` when they can."""
    events = loop_events(request)
    if not any(ev.chord for ev in events):
        return LoopRefusal(REFUSAL_EMPTY, "These bars have no chords to play (N.C.).")
    split = timing_problems(request)
    if split:
        where = ", ".join(str(b) for b in split)
        return LoopRefusal(
            REFUSAL_SPLIT_BAR,
            f"Bar{'s' if len(split) > 1 else ''} {where} change{'' if len(split) > 1 else 's'} chord in the middle of the bar, "
            "and the backing's bass doesn't follow mid-bar changes yet — so these bars aren't looped rather "
            "than play a wrong bass note. Choose bars without a split chord to practise with the loop.",
        )
    wrong = voicing_problems(request)
    if wrong:
        return LoopRefusal(
            REFUSAL_VOICING,
            "The backing can't voice these chords correctly yet, so the loop is off for these bars rather "
            "than play wrong notes: " + "; ".join(wrong) + ".",
            tuple(w.split(" ")[0] for w in wrong),
        )
    return None


# --------------------------------------------------------------------------- timeline


def loop_events(request: LoopRequest) -> tuple[LoopEvent, ...]:
    """Expected chord changes in seconds, from the coaching scope's own harmony events."""
    from music_theory import normalize_chord_for_theory
    from songs.meter import meter_timing

    from song_coach_harmony import chord_facts, pc_of
    from song_coach_scope import _beats_per_bar, harmony_events

    bar_sec = float(meter_timing(request.bpm, request.meter).bar_sec)
    bpb = _beats_per_bar(request.meter)
    out: list[LoopEvent] = []
    for ev in harmony_events(list(request.bars), meter=request.meter, first_bar=request.start_bar):
        start = ev.start_beat / bpb * bar_sec
        end = (ev.start_beat + ev.beats) / bpb * bar_sec
        facts = chord_facts(normalize_chord_for_theory(ev.chord)) if ev.chord else None
        bass = pc_of(facts.bass) if facts is not None and facts.bass else (facts.root_pc if facts else -1)
        out.append(LoopEvent(round(start, 6), round(end, 6), ev.chord or "", bass, facts.root_pc if facts else -1,
                             ev.start_bar))
    return tuple(out)


# --------------------------------------------------------------------------- rendering


_CACHE: "OrderedDict[str, PracticeLoop]" = OrderedDict()


def _passes(request: LoopRequest) -> int:
    """Enough passes that the middle one is clear of any programmed outro fade."""
    try:
        from backing_audio import _song_backing_profile

        fade = int(_song_backing_profile(request.song_title, request.artist, request.style, bpm=request.bpm)
                   .get("outro_fade_bars", 0) or 0)
    except Exception:
        fade = 0
    n = max(1, request.bar_count)
    return 3 + (fade + n - 1) // n


def _wav(audio: np.ndarray, sr: int) -> bytes:
    pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)
    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return out.getvalue()


def decode_wav(wav: bytes) -> tuple[np.ndarray, int]:
    """Mono float samples and the sample rate of a loop's WAV."""
    with wave.open(io.BytesIO(wav), "rb") as wf:
        sr = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767.0, sr


def render_loop(request: LoopRequest) -> PracticeLoop:
    """Render (or reuse) the seamless loop for ``request``."""
    sig = request.signature()
    cached = _CACHE.get(sig)
    if cached is not None:
        _CACHE.move_to_end(sig)
        return cached
    from backing_audio import synthesize_chords_to_numpy
    from songs.meter import meter_timing

    n = request.bar_count
    if n <= 0:
        raise ValueError("a practice loop needs at least one bar")
    passes = _passes(request)
    events = [
        {"chord": token, "section": request.section_label, "bar_in_section": i, "section_bars": n}
        for i, token in enumerate(request.bars)
    ]
    sr = LOOP_SAMPLE_RATE
    audio, sr = synthesize_chords_to_numpy(
        events, bpm=request.bpm, loops=passes, sr=sr, style=request.style, level=request.level,
        song_title=request.song_title, song_artist=request.artist, time_signature=request.meter,
    )
    bar_sec = float(meter_timing(request.bpm, request.meter).bar_sec)
    length = int(round(n * bar_sec * sr))
    start = length  # the second pass
    fade = int(CROSSFADE_SEC * sr)
    audio = np.asarray(audio, dtype=np.float64)
    segment = audio[start: start + length].copy()
    before = audio[start - fade: start]
    if len(segment) == length and len(before) == fade and 0 < fade < length:
        ramp = np.linspace(0.0, 1.0, fade + 1)[1:]
        # Playback wraps from segment[-1] to segment[0] (the middle pass's own first downbeat).
        # The true predecessor of that downbeat is the end of the previous pass, so the loop's
        # final ``fade`` samples blend into it: segment[-1] == audio[start - 1].
        segment[-fade:] = segment[-fade:] * (1.0 - ramp) + before * ramp
    loop = PracticeLoop(request, _wav(segment, sr), sr, bar_sec, length / sr, loop_events(request), passes)
    _CACHE[sig] = loop
    while len(_CACHE) > CACHE_MAX:
        _CACHE.popitem(last=False)
    return loop


def cached_loop(signature: str) -> PracticeLoop | None:
    return _CACHE.get(signature)


def clear_loop_cache() -> None:
    _CACHE.clear()


__all__ = [
    "CACHE_MAX",
    "DEFAULT_BPM",
    "LOOP_SAMPLE_RATE",
    "LOOP_VERSION",
    "LoopEvent",
    "LoopRefusal",
    "LoopRequest",
    "PracticeLoop",
    "REFUSAL_EMPTY",
    "REFUSAL_SPLIT_BAR",
    "REFUSAL_VOICING",
    "STYLE_TO_ARRANGER",
    "TEMPO_MAX",
    "TEMPO_MIN",
    "arranger_style",
    "cached_loop",
    "check_loop",
    "clamp_bpm",
    "clear_loop_cache",
    "decode_wav",
    "loop_events",
    "loop_request",
    "render_loop",
    "timing_problems",
    "voicing_problems",
]
