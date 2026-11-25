"""Composes one section of a Practice Melody: phrases, a motif, the style's rhythms, the focus's material.

User, 2026-11-25: a Practice Melody must feel like something a musician would play on this instrument, in this
style, for this objective. The earlier engine drew an unrelated rhythm for every bar and the style was mostly a
label. Here a section is phrases (a motif stated, answered, varied, then a cadence with a breath), each style has
its own rhythm vocabulary, and the Practice Focus decides what the line is made of.

Everything lies on the eighth-note grid the notation draws, so a bar always fills exactly. Deterministic: the only
randomness is the caller's ``rng``, and markings (articulation, dynamics) never consume it, so an Articulation or
Dynamics focus marks the same notes.
"""

from __future__ import annotations

import math
import random
from dataclasses import replace
from typing import Any, Callable, Sequence

from chord_scale_selection import blue_note_pcs, chord_scale_pcs
from harmonic_spelling import spell_pitch_classes_for_chord
from music_theory import classify_chord_quality, pitch_class_from_spelled_note, spell_chord_tones
from practice_melody_model import MelodyEvent

# --- vocabulary -------------------------------------------------------------------------------------

# One 4/4 bar in eighths: n a note, -n a rest. ("body" bars, cadence bars)
_POP = (((2, 2, 4), (3, 1, 4), (2, 1, 1, 4), (2, 2, 2, 2), (4, 2, -2), (3, 3, 2), (1, 1, 2, 4)), ((6, -2), (4, -4), (2, 4, -2)))
_BALLAD = (((4, 4), (6, 2), (3, 1, 4), (2, 2, 4), (4, 2, 2), (4, 3, 1)), ((6, -2), (4, -4), (2, 4, -2)))
_ROCK = (
    ((2, 1, 1, 2, -2), (1, 1, 2, 1, 1, 2), (3, 1, 2, 2), (2, 2, 1, 1, 2), (-1, 1, 2, 2, 2), (1, 1, 1, 1, 4)),
    ((2, 2, -4), (1, 1, 2, -4), (1, 1, 4, -2)),
)
_SWING = (
    ((1, 1, 1, 1, 2, -2), (-1, 1, 1, 1, 1, 1, 2), (3, 1, 2, -2), (2, 1, 1, 1, 3), (-2, 1, 1, 1, 1, 2), (1, 2, 1, 2, -2), (1, 1, 1, 1, 1, 3), (3, -2, 1, 1, 1), (2, 1, -3, 1, 1)),
    ((1, 3, -4), (3, 1, -4), (1, 1, 2, -4), (2, 1, -5)),
)
_BLUES = (((3, 1, 2, -2), (-2, 1, 1, 2, 2), (1, 1, 1, 1, 2, -2), (2, 1, 3, -2), (1, 2, 1, 4)), ((3, -5), (1, 3, -4), (2, 2, -4)))
_BOSSA = (((3, 3, 2), (3, 5), (2, 3, 3), (-1, 2, 3, 2), (4, 1, 3), (3, 1, 2, -2), (1, 2, 3, 2)), ((3, 5), (6, -2), (3, 3, -2)))
_SAMBA = (
    ((1, 2, 1, 1, 2, 1), (-1, 2, 1, 2, 2), (1, 1, 1, 2, 1, 2), (2, 1, 2, 1, 2), (1, 2, 2, 1, -2), (-1, 1, 1, 2, 1, 2)),
    ((1, 2, -5), (2, 1, 3, -2), (1, 1, 1, -5)),
)
_LATIN = (((3, 3, 2), (1, 2, 2, 1, 2), (-1, 2, 1, 2, 2), (2, 1, 2, 3), (3, 1, 2, 2), (1, 2, 1, 2, 2)), ((3, 3, -2), (1, 2, -5), (2, 1, -5)))
_FUNK = (
    ((1, -1, 1, 1, -2, 2), (-1, 1, 1, -1, 2, -2), (2, -1, 1, 1, -3), (1, 1, -2, 1, 1, -2), (1, 1, -1, 1, 2, -2), (-2, 1, 1, -1, 1, 2)),
    ((1, -7), (1, 1, -6), (1, -1, 1, -5)),
)
_COUNTRY = (((2, 1, 1, 2, 2), (1, 1, 2, 2, 2), (3, 1, 2, 2), (2, 2, 4), (1, 1, 1, 1, 4)), ((4, -4), (2, 4, -2), (6, -2)))
_KLEZMER = (((2, 2, 1, 1, 2), (1, 1, 1, 1, 2, 2), (2, 1, 1, 2, 2), (3, 1, 2, 2), (2, 2, 4)), ((2, 2, -4), (1, 1, 2, -4), (4, -4)))
_STYLES: dict[str, Any] = {
    "pop": _POP, "ballad": _BALLAD, "rock": _ROCK, "swing": _SWING, "blues": _BLUES, "bossa": _BOSSA, "samba": _SAMBA,
    "latin": _LATIN, "funk": _FUNK, "country": _COUNTRY, "klezmer": _KLEZMER,
}
_SIMPLE = ((4, 4), (2, 2, 4), (4, 2, 2), (2, 2, 2, 2), (6, 2), (2, 1, 1, 4))
_LONG = ((8,), (4, 4), (6, 2), (6, -2))
_RHYTHMIC = ((1, 2, 1, 2, 2), (-1, 2, 1, 2, 2), (3, 3, 2), (1, 1, -1, 1, 2, 2), (2, 1, 2, 1, 2), (1, 2, 2, 1, 2))
_RUNS = ((1,) * 8, (1, 1, 1, 1, 2, 2), (2, 1, 1, 1, 1, 2), (1, 1, 1, 1, 1, 1, 2))

# Chromatic approach into the next chord, arpeggio motion and pentatonic lean, by style.
_APPROACH = {"swing": 0.7, "blues": 0.15, "bossa": 0.12, "latin": 0.12, "samba": 0.08, "funk": 0.08}
_ARPEGGIO = {"rock": 0.3, "klezmer": 0.4, "swing": 0.42, "bossa": 0.3, "ballad": 0.3, "pop": 0.3, "samba": 0.35}
_PENTATONIC = {"rock": 0.7, "blues": 0.6, "country": 0.6, "funk": 0.5}
_LEVEL_APPROACH = {"Beginner": 0.0, "Intermediate": 0.6, "Advanced": 1.0}
# Simpler lines outline the chord; richer ones connect it.
_LEVEL_ARPEGGIO = {"Beginner": 0.5, "Intermediate": 0.2, "Advanced": -0.08}
_MAX_LEAP = {"Beginner": 7, "Intermediate": 9, "Advanced": 12}


def style_family(style: str) -> str:
    """The melodic vocabulary a groove / jam style label belongs to (pop when unknown)."""
    s = str(style or "").lower()
    for family, words in (
        ("ballad", ("ballad", "lo-fi", "lofi")),
        ("samba", ("samba",)),
        ("bossa", ("bossa",)),
        ("klezmer", ("klezmer", "hora", "jewish")),
        ("latin", ("latin", "salsa", "mambo", "afro", "cha")),
        ("blues", ("blues",)),
        ("funk", ("funk", "soul", "fusion", "r&b")),
        ("rock", ("rock",)),
        ("country", ("country", "folk")),
        ("swing", ("swing", "jazz", "bebop", "bop", "modal")),
    ):
        if any(w in s for w in words):
            return family
    return "pop"


def focus_intent(focus: str) -> str:
    """What a Practice Focus asks of the notes ("" = nothing in particular)."""
    f = " ".join(str(focus or "").lower().split())
    for intent, words in (
        ("pentatonics", ("pentaton",)),
        ("guide_tones", ("guide tone", "voice leading")),
        ("articulation", ("articulat",)),
        ("dynamics", ("dynamic",)),
        ("phrasing", ("breath", "phrasing", "emotional", "endurance")),
        ("walking", ("walking", "root motion")),
        ("improvisation", ("improvis", "solo", "lead guitar", "bebop", "ear training")),
        ("arpeggios", ("triad", "arpegg", "inversion", "voicing", "barre", "double stop", "harmony", "chord")),
        ("rhythm", ("rhythm", "timing", "syncop", "strum", "groove", "pocket", "comping", "left-hand")),
        ("scales", ("scale", "technique", "range", "fingerstyle")),
        ("tone", ("tone", "vibrato", "pitch accuracy")),
    ):
        if any(w in f for w in words):
            if intent == "phrasing" and ("bebop" in f or "jazz" in f):
                return "improvisation"
            return intent
    return ""


# Focuses that only mark the notes: they never change which notes are played.
MARKING_INTENTS = frozenset({"articulation", "dynamics"})


def note_intent(focus: str) -> str:
    intent = focus_intent(focus)
    return "" if intent in MARKING_INTENTS else intent


# --- rhythm -----------------------------------------------------------------------------------------


def _notes_in(cell: Sequence[int]) -> int:
    return sum(1 for x in cell if x > 0)


def _offbeats(cell: Sequence[int]) -> int:
    """Notes that start off the beat and last longer than the half beat: syncopation."""
    pos = out = 0
    for x in cell:
        out += int(x > 1 and pos % 2 == 1)
        pos += abs(x)
    return out


def _for_length(cells: Sequence[Sequence[int]], n: int, compound: bool) -> list[tuple[int, ...]]:
    """The style's 4/4 cells in another bar length: the same gestures, cut or continued to fill the bar exactly."""
    if n == 8 and not compound:
        return [tuple(c) for c in cells]
    if compound:
        groups = n // 3
        base = ((3,), (2, 1), (1, 1, 1), (1, 2))
        out = []
        for i in range(len(cells) + 2):
            bar: list[int] = []
            for g in range(groups):
                bar.extend(base[(i + g * (1 + i % 3)) % len(base)])
            out.append(tuple(bar))
        out.append(tuple([6] * (groups // 2) + [3] * (groups % 2)))
        return out
    out = []
    for c in cells:
        bar, left = [], n
        source = list(c) * (n // 8 + 1)
        for x in source:
            take = min(abs(x), left)
            if take <= 0:
                break
            bar.append(take if x > 0 else -take)
            left -= take
        if left:
            bar.append(left)
        out.append(tuple(bar))
    return out


def _cadences(cells: Sequence[Sequence[int]], n: int, compound: bool) -> list[tuple[int, ...]]:
    if n == 8 and not compound:
        return [tuple(c) for c in cells]
    if n <= 3:
        return [(n,)]
    rest = 3 if compound and n > 3 else 2 if n > 4 else 1
    return [(n - rest, -rest)]


def _densify(cell: Sequence[int], rng: random.Random, chance: float) -> tuple[int, ...]:
    out: list[int] = []
    for x in cell:
        if x == 2 and rng.random() < chance:
            out.extend((1, 1))
        elif x == 4 and rng.random() < chance * 0.6:
            out.extend((2, 1, 1))
        else:
            out.append(x)
    return tuple(out)


def _section_rhythm(
    bars: int, *, n: int, compound: bool, family: str, level: str, intent: str, tempo: float, rng: random.Random
) -> list[dict[str, Any]]:
    """One plan per bar: its cell, its phrase, and which earlier bar it restates."""
    body, cadence = _STYLES[family]
    if tempo and tempo < 84 and family not in {"ballad", "bossa"} and rng.random() < 0.55:
        body = _BALLAD[0] + body[:2]
    if intent == "tone":
        body, cadence = _LONG, ((8,), (6, -2))
    elif intent == "walking":
        body, cadence = ((2, 2, 2, 2),), ((2, 2, 4),)
    elif intent == "rhythm":
        body = _RHYTHMIC + body
    elif intent == "scales":
        body = _RUNS + body[:2]
    pool = _for_length(body, n, compound)
    ends = _cadences(cadence, n, compound)
    if level == "Beginner":
        simple = _for_length(_SIMPLE, n, compound) if not compound else pool
        easy = [c for c in pool if _notes_in(c) <= 4 and _offbeats(c) <= (1 if family in {"bossa", "samba", "latin", "funk"} else 0)]
        pool = (easy + simple[:3]) if easy else simple
        if intent == "tone":
            pool = [c for c in pool if _notes_in(c) <= 2] or pool
    elif level == "Advanced" and intent not in {"tone", "walking"}:
        pool = sorted(pool, key=lambda c: (-_notes_in(c), c))[: max(2, (len(pool) * 2 + 2) // 3)]
    phrase = 2 if intent == "phrasing" or (level == "Beginner" and tempo and tempo < 84) else 4
    plans: list[dict[str, Any]] = []
    motifs: dict[int, tuple[int, ...]] = {}
    phrases = max(1, math.ceil(bars / phrase))
    for p in range(phrases):
        size = min(phrase, bars - p * phrase)
        motif = (0, 0, 1, 0)[p % 4]
        if motif not in motifs:
            motifs[motif] = rng.choice(pool)
        a = motifs[motif]
        contrast = rng.choice([c for c in pool if c != a] or pool)
        shape = {1: ("end",), 2: ("a", "end"), 3: ("a", "a", "end")}.get(size) or (
            ("a", "a", "b", "end") if p % 2 == 0 else ("a", "b", "a", "end")
        )
        first_a = None
        for k, what in enumerate(shape):
            cell = a if what == "a" else contrast if what == "b" else rng.choice(ends)
            if level == "Advanced" and what == "b" and intent not in {"tone", "walking"}:
                cell = _densify(cell, rng, 0.55)
            elif level == "Advanced" and what == "a" and first_a is not None and intent not in {"tone", "walking"}:
                cell = _densify(cell, rng, 0.4)
            elif level == "Beginner" and what == "end" and intent != "tone":
                cell = _cadences(((6, -2), (4, -4)), n, compound)[0] if rng.random() < 0.7 else cell
            index = len(plans)
            plans.append({
                "cell": cell, "phrase": p, "at": k, "size": size, "motif": motif,
                "restates": first_a if what == "a" and first_a is not None else None, "end": what == "end",
            })
            if what == "a" and first_a is None:
                first_a = index
    return plans


# --- pitch ------------------------------------------------------------------------------------------


def _pcs(chord: str) -> list[int]:
    out: list[int] = []
    for tone in spell_chord_tones(chord):
        pc = pitch_class_from_spelled_note(tone) % 12
        if pc not in out:
            out.append(pc)
    return out or [0]


def pentatonic_pcs(chord: str) -> list[int]:
    root = _pcs(chord)[0]
    minor = classify_chord_quality(chord) in ("minor", "m7", "half-dim", "dim")
    return [(root + s) % 12 for s in ((0, 3, 5, 7, 10) if minor else (0, 2, 4, 7, 9))]


def _guide_pcs(chord: str, pcs: list[int]) -> list[int]:
    tones = [pitch_class_from_spelled_note(t) % 12 for t in spell_chord_tones(chord)]
    return [tones[1], tones[3]] if len(tones) >= 4 else pcs[1:3] or pcs


def _in_window(pcs: Sequence[int], low: int, high: int) -> list[int]:
    wanted = set(pcs)
    return [m for m in range(low, high + 1) if m % 12 in wanted]


def compose_section(
    *,
    chords: Sequence[str],
    key_center: str,
    level: str,
    tempo_bpm: float,
    beats_per_measure: float,
    rng: random.Random,
    start_midi: int,
    style: str = "",
    intent: str = "",
    register: tuple[int, int] = (57, 77),
    compound: bool = False,
    chord_at: Callable[[str, float], str] | None = None,
) -> tuple[list[MelodyEvent], int]:
    """The section's events and the MIDI note it ends on."""
    low, high = register
    family = style_family(style)
    per_beat = 1 if compound else 2
    n = max(1, int(round(beats_per_measure * per_beat)))
    slot = 1.0 / per_beat
    leap = _MAX_LEAP.get(level, 9)
    plans = _section_rhythm(
        len(chords), n=n, compound=compound, family=family, level=level, intent=intent, tempo=float(tempo_bpm or 0), rng=rng
    )
    half = 3 * (n // 6) if compound and n >= 6 else (n // 2 if n >= 8 else 0)

    def sounding_chord(bar: int, at: int) -> str:
        token = str(chords[bar])
        found = chord_at(token, at * slot) if chord_at else token
        return str(found or token)

    # Every attack of the section in order, so a note can see the chord and the beat that follow it.
    attacks: list[dict[str, Any]] = []
    for bar, plan in enumerate(plans):
        pos, ordinal = 0, 0
        for x in plan["cell"]:
            attacks.append({"bar": bar, "pos": pos, "len": abs(x), "rest": x < 0, "ordinal": ordinal if x > 0 else -1})
            ordinal += int(x > 0)
            pos += abs(x)
    notes = [i for i, a in enumerate(attacks) if not a["rest"]]
    last_note = notes[-1] if notes else -1
    following = {a: b for a, b in zip(notes, notes[1:])}

    span = high - low
    centre, height = low + 0.42 * span, 0.34 * span
    if intent == "scales":
        centre, height = low + 0.45 * span, 0.45 * span
    falls = {p: rng.random() < 0.3 for p in range(len(plans) + 1)}
    gestures: dict[int, list[Any]] = {}
    approach_p = _APPROACH.get(family, 0.02) * _LEVEL_APPROACH.get(level, 0.5)
    if intent == "improvisation" and level != "Beginner":
        approach_p = max(approach_p, 0.3)
    arpeggio_p = {"arpeggios": 0.9, "scales": 0.05, "walking": 0.5, "tone": 0.0}.get(intent, _ARPEGGIO.get(family, 0.3) + _LEVEL_ARPEGGIO.get(level, 0.2))
    penta_p = 1.0 if intent == "pentatonics" else 0.0 if intent in {"scales", "guide_tones"} else _PENTATONIC.get(family, 0.0)

    out: list[MelodyEvent] = []
    prev = min(max(int(start_midi), low), high)
    forced: int | None = None
    run = 1
    for i, a in enumerate(attacks):
        bar, plan = a["bar"], plans[a["bar"]]
        chord = sounding_chord(bar, a["pos"])
        base = dict(measure=bar, beat=a["pos"] * slot, duration_beats=a["len"] * slot, chord=chord)
        if a["rest"]:
            out.append(MelodyEvent(is_rest=True, tone_role="rest", **base))
            continue
        pcs = _pcs(chord)
        scale = list(chord_scale_pcs(chord, key_center, style=style) or pcs)
        use_penta = penta_p > 0 and (penta_p >= 1 or rng.random() < penta_p)
        penta = pentatonic_pcs(chord)
        pool = [pc for pc in penta if pc in scale or pc in pcs] if use_penta else scale
        strong_pool = pcs
        if intent == "guide_tones":
            strong_pool = _guide_pcs(chord, pcs)
        elif intent == "pentatonics":
            strong_pool = [pc for pc in pcs if pc in penta] or pcs
        elif intent == "walking" and a["pos"] == 0:
            strong_pool = pcs[:1]
        t = (plan["at"] + a["pos"] / n) / max(1, plan["size"])
        arch = math.sin(math.pi * min(1.0, t * 1.05))
        target = centre + height * (arch if not falls[plan["phrase"]] else 0.55 - arch)
        final = i == last_note
        strong = a["pos"] == 0 or a["pos"] == half or a["len"] >= 3 or final or intent == "walking"
        first_of_chord = bool(notes) and (i == notes[0] or sounding_chord(attacks[_before(notes, i)]["bar"], attacks[_before(notes, i)]["pos"]) != chord)
        remembered = None
        if plan["restates"] is not None:
            saved = gestures.get(plan["restates"], [])
            remembered = saved[a["ordinal"]] if a["ordinal"] < len(saved) else None

        role = "chord_tone"
        if forced is not None:
            midi, forced = forced, None
        elif strong or first_of_chord:
            wanted = strong_pool
            if final:
                wanted = _guide_pcs(chord, pcs) if intent == "guide_tones" else pcs[:2]
            elif plan["end"] and a["pos"] == 0 and intent != "guide_tones":
                wanted = [pc for pc in strong_pool if pc in pcs[:3]] or strong_pool
            candidates = _in_window(wanted, low, high)
            reach = [m for m in candidates if abs(m - prev) <= leap]
            if not reach:
                reach = [m for m in _in_window(pcs, low, high) if abs(m - prev) <= leap and not final] or candidates or _in_window(pcs, low, high)
            degree = remembered[1] if isinstance(remembered, tuple) and remembered[0] == "degree" else None

            def cost(m: int) -> float:
                c = 0.5 * abs(m - target) + 0.8 * abs(m - prev) + rng.random() * 1.4
                if m == prev:
                    c += 2.0 * run
                if degree is not None and m % 12 in pcs and pcs.index(m % 12) == degree:
                    c -= 3.0
                return c

            midi = min(reach, key=cost)
        else:
            midi, role = _connect(
                prev, target, pcs, pool, scale, low, high, leap, rng,
                direction=remembered[1] if isinstance(remembered, tuple) and remembered[0] == "step" else 0,
                arpeggio_p=arpeggio_p, colour=blue_note_pcs(chord, style) if level != "Beginner" and intent != "scales" else [],
                long_run=run,
            )
        # The last note before a new chord may lean into it by a half step (and then it must arrive).
        nxt = following.get(i)
        if (
            forced is None and nxt is not None and not strong and not final and role != "approach"
            and attacks[nxt]["pos"] == 0 and attacks[nxt]["bar"] == bar + 1
            and nxt == i + 1 and approach_p > 0 and rng.random() < approach_p
        ):
            next_chord = sounding_chord(bar + 1, 0)
            if next_chord != chord:
                goals = [m for m in _in_window(_pcs(next_chord), low, high) if 1 <= abs(m - prev) <= 5]
                rng.shuffle(goals)
                for goal in goals:
                    side = -1 if goal > prev else 1
                    lean = goal + side
                    if low <= lean <= high and lean != prev and abs(lean - prev) <= leap:
                        midi, role, forced = lean, "approach", goal
                        break
        run = run + 1 if midi == prev else 1
        gestures.setdefault(bar, []).append(
            ("degree", pcs.index(midi % 12)) if role == "chord_tone" and midi % 12 in pcs and strong
            else ("step", (midi > prev) - (midi < prev))
        )
        spelled = spell_pitch_classes_for_chord([midi % 12], chord, song_display_key=key_center)[0]
        out.append(MelodyEvent(is_rest=False, pitch=spelled, midi=int(midi), tone_role=role, **base))
        prev = int(midi)
    return out, prev


def _before(notes: list[int], i: int) -> int:
    at = notes.index(i)
    return notes[at - 1] if at else i


def _connect(
    prev: int, target: float, pcs: list[int], pool: list[int], scale: list[int], low: int, high: int, leap: int,
    rng: random.Random, *, direction: int, arpeggio_p: float, colour: list[int], long_run: int,
) -> tuple[int, str]:
    """A note between the strong ones: by step along the chord's scale, or through the chord."""
    d = direction or (1 if target > prev + 1 else -1 if target < prev - 1 else rng.choice((-1, 1)))
    if prev + d < low or prev + d > high:
        d = -d

    def step(way: int) -> int | None:
        for size in (1, 2, 3):
            m = prev + way * size
            if low <= m <= high and m % 12 in pool:
                return m
        return None

    if colour and rng.random() < 0.18:
        for way in (d, -d):
            m = prev + way
            if low <= m <= high and m % 12 in colour and m % 12 not in pcs:
                return m, "passing"
    if rng.random() < arpeggio_p:
        ladder = [m for m in _in_window(pcs, low, high) if 0 < (m - prev) * d <= min(leap, 7)]
        if ladder:
            return (min(ladder) if d > 0 else max(ladder)), "chord_tone"
    for way in (d, -d):
        m = step(way)
        if m is not None:
            return m, "chord_tone" if m % 12 in pcs else "passing"
    near = [m for m in _in_window(pcs, low, high) if abs(m - prev) <= leap] or _in_window(pcs, low, high)
    m = min(near, key=lambda x: (abs(x - prev) + (2 if x == prev else 0)))
    return m, "chord_tone"


# --- markings ---------------------------------------------------------------------------------------


def _arc(bars: int) -> dict[int, str]:
    shape = ("mp", "mp", "mf", "f", "f", "mf", "mp", "p")
    if bars <= 1:
        return {0: "mf"}
    return {b: shape[min(len(shape) - 1, int(b / max(1, bars - 1) * (len(shape) - 1)))] for b in range(bars)}


def mark_events(events: list[MelodyEvent], *, level: str, style: str, focus: str, bars: int) -> list[MelodyEvent]:
    """Slurs, accents, staccato, tenuto and dynamics for these notes. Never changes a pitch or a rhythm."""
    intent, family = focus_intent(focus), style_family(style)
    out = [replace(e, slur="", articulation="", dynamic="") for e in events]
    arc = _arc(bars) if intent == "dynamics" else {}
    groups: list[list[int]] = []
    for i, e in enumerate(out):
        if e.is_rest:
            groups.append([])
        elif groups and groups[-1] and out[groups[-1][-1]].measure == e.measure:
            groups[-1].append(i)
        else:
            groups.append([i])

    def slur(idx: list[int]) -> None:
        # Two notes of one pitch under a slur read as a tie: the slur ends before the repeat.
        run: list[int] = []
        for i in idx + [-1]:
            if i >= 0 and (not run or out[run[-1]].midi != out[i].midi):
                run.append(i)
                continue
            if len(run) >= 2:
                out[run[0]] = replace(out[run[0]], slur="start")
                out[run[-1]] = replace(out[run[-1]], slur="end")
            run = [i]

    def art(i: int, name: str) -> None:
        out[i] = replace(out[i], articulation=name)

    seen_measures: set[int] = set()
    for g in groups:
        if not g:
            continue
        bar = out[g[0]].measure
        if bar in arc and bar not in seen_measures:
            out[g[0]] = replace(out[g[0]], dynamic=arc[bar])
        seen_measures.add(bar)
        short = [i for i in g if out[i].duration_beats <= 0.5]
        if intent == "tone":
            continue
        if intent == "articulation":
            pattern = bar % 3
            if pattern == 0:  # slur two, tongue two
                slur(g[:2])
                for k, i in enumerate(g[2:]):
                    art(i, "staccato" if out[i].duration_beats <= 0.5 else "tenuto")
                if len(g) < 3:
                    art(g[0], "accent")
            elif pattern == 1:  # all tongued: accent, tenuto, staccato
                for k, i in enumerate(g):
                    art(i, "accent" if k == 0 else "staccato" if out[i].duration_beats <= 0.5 else "tenuto")
            else:  # legato, the phrase's last note placed
                slur(g)
                if len(g) == 1:
                    art(g[0], "tenuto")
            continue
        if level == "Beginner":
            continue
        if family in {"ballad", "bossa", "pop", "country"} or intent == "phrasing":
            for k in range(0, len(g), 4):
                slur(g[k : k + 4])
        elif family in {"swing", "blues"}:
            # Swing: the off-beat leads into the beat.
            k = 0
            while k + 1 < len(g):
                a, b = g[k], g[k + 1]
                if out[a].beat % 1 and out[a].duration_beats <= 0.5:
                    slur([a, b])
                    k += 2
                else:
                    k += 1
            last = g[-1]
            if out[last].duration_beats <= 0.5:
                art(last, "staccato")
        elif family == "funk":
            for i in short:
                art(i, "staccato")
        elif family in {"samba", "latin"}:
            slur(g[:2])
        if family in {"rock", "funk", "samba", "latin", "swing", "klezmer"}:
            for i in g:
                off = bool(out[i].beat % 1)
                if (off and out[i].duration_beats >= 1.0) or (family == "rock" and out[i].beat == 0):
                    if not out[i].articulation:
                        art(i, "accent")
    return out


__all__ = (
    "MARKING_INTENTS", "compose_section", "focus_intent", "mark_events", "note_intent", "pentatonic_pcs", "style_family",
)
