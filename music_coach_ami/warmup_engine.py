"""AMI adaptive warmups, Slice 1: the deterministic music behind each warmup exercise.

Four exercise families, every one written directly in the pitch the player READS (the written domain), so range, transposition and notation
are decided in one place and verified before anything is shown:

* ``long_tones``   - sustained whole notes on scale degrees of the written key, a breath bar after every pair.
* ``scale``        - the key's scale up and down (as many octaves as the instrument's level window holds).
* ``intervals``    - diatonic seconds, thirds, fourths, fifths, sixths, sevenths or octaves, ascending then descending.
* ``articulation`` - repeated-note tonguing, two-note slurred/tongued pairs, slur-tongue groups and an articulation-style contrast.

The notation is produced by the same writer every other AMI exercise uses (``composition_to_abc``: bar-long accidentals and the stored-octave
staff are fixed there), the transposition comes from the app's own tables (``scale_pattern_harmony`` offsets and ranges, the written-music
context for the written key), and the player's global instrument selection is never read for a *named* instrument or written to.

Nothing here knows about songs or chords: Slice 1 warmups are key- and instrument-based, and say so.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Any

from music_coach_ami import scale_pattern_harmony as sph

LEVELS = ("Beginner", "Intermediate", "Advanced")
FAMILIES = ("long_tones", "scale", "intervals", "articulation")
FAMILY_LABEL = {"long_tones": "Long tones", "scale": "Scale", "intervals": "Intervals", "articulation": "Articulation", "guide_tones": "Guide tones"}
INTERVALS = {"seconds": 1, "thirds": 2, "fourths": 3, "fifths": 4, "sixths": 5, "sevenths": 6, "octaves": 7}   # scale steps
INTERVAL_SINGULAR = {"seconds": "second", "thirds": "third", "fourths": "fourth", "fifths": "fifth", "sixths": "sixth", "sevenths": "seventh",
                     "octaves": "octave"}
ARTIC_PATTERNS = ("repeated", "two_note", "slur_tongue", "contrast")
ARTIC_LABEL = {"repeated": "Tonguing on one note", "two_note": "Two-note slurs and tongued pairs", "slur_tongue": "Slur two, tongue two",
               "contrast": "Articulation styles"}

METER = "4/4"
BEATS_PER_BAR = Fraction(4)
_DUR_BEATS = {"whole": Fraction(4), "half": Fraction(2), "quarter": Fraction(1), "eighth": Fraction(1, 2), "sixteenth": Fraction(1, 4)}
_REST_PIECES = (("whole", Fraction(4)), ("half", Fraction(2)), ("quarter", Fraction(1)), ("eighth", Fraction(1, 2)), ("sixteenth", Fraction(1, 4)))

# Written MIDI window a line is built inside, per instrument family and level, then clamped to what the horn can play. Comfort windows, not
# limits: a Beginner is kept in the easy middle of the instrument, an Advanced player gets the whole of it.
_WINDOWS: dict[str, dict[str, tuple[int, int]]] = {
    "flute": {"Beginner": (67, 84), "Intermediate": (62, 91), "Advanced": (60, 96)},
    "sax": {"Beginner": (62, 79), "Intermediate": (60, 84), "Advanced": (58, 89)},
    "trumpet": {"Beginner": (58, 74), "Intermediate": (55, 79), "Advanced": (54, 84)},
    "clarinet": {"Beginner": (55, 76), "Intermediate": (52, 86), "Advanced": (52, 91)},
    "piano": {"Beginner": (60, 76), "Intermediate": (55, 84), "Advanced": (52, 88)},
}

GAP_SECONDS = 8            # rest between two plays of the same exercise
TRANSITION_SECONDS = 10    # to turn to the next exercise


class WarmupUnavailable(ValueError):
    """The warmup (or one exercise of it) cannot be built correctly for this player; the message says why."""


@dataclass(frozen=True)
class Player:
    key: str                # exercise_adapt.SPECS key ("alto")
    label: str              # "Alto Saxophone"
    notation: str           # notation / transposition table name
    family: str             # window family: flute | sax | trumpet | clarinet | piano
    ttype: str
    offset: int             # written minus sounding semitones, octave included
    play_low: int           # lowest / highest WRITTEN note the instrument can play
    play_high: int
    written_key: str        # "A", "Am", "Bb" ... the key the player reads
    concert_key: str
    semitones: int          # the app's written-minus-concert transposition (mod 12)
    clef: str

    def window(self, level: str) -> tuple[int, int]:
        lo, hi = _WINDOWS[self.family][level if level in LEVELS else "Intermediate"]
        return max(lo, self.play_low), min(hi, self.play_high)


def window_family(spec_key: str) -> str:
    return {"flute": "flute", "piano": "piano", "trumpet": "trumpet", "clarinet": "clarinet"}.get(spec_key, "sax")


def supports(player: Player, family: str) -> str:
    """'' when the family suits the instrument, otherwise the reason it does not."""
    if family == "long_tones" and player.family == "piano":
        return "long tones train breath and tone, which don't apply to piano"
    return ""


# ---------------------------------------------------------------- keys and scales


_MAJOR_NAMES = {0: "C", 1: "Db", 2: "D", 3: "Eb", 4: "E", 5: "F", 6: "Gb", 7: "G", 8: "Ab", 9: "A", 10: "Bb", 11: "B"}
_MINOR_NAMES = {0: "C", 1: "C#", 2: "D", 3: "Eb", 4: "E", 5: "F", 6: "F#", 7: "G", 8: "G#", 9: "A", 10: "Bb", 11: "B"}


def split_key(token: str) -> tuple[str, str]:
    """('A', 'major') / ('A', 'natural minor') from 'A', 'Am', 'A minor', 'Bb', 'F#m' ..."""
    parts = sph._token_parts(token)
    if not parts:
        return "C", "major"
    return parts[0], parts[1]


def key_token(tonic: str, tonality: str) -> str:
    return tonic + ("m" if tonality == "natural minor" else "")


def key_text(tonic: str, tonality: str) -> str:
    return f"{tonic} {'minor' if tonality == 'natural minor' else 'major'}"


def related_key(tonic: str, tonality: str, semitones: int) -> tuple[str, str]:
    """The same mode ``semitones`` up, spelled with the fewest accidentals."""
    pc = (sph.pc_of(tonic) + semitones) % 12
    return (_MINOR_NAMES if tonality == "natural minor" else _MAJOR_NAMES)[pc], tonality


def practical_key(tonic: str, tonality: str) -> tuple[str, str]:
    """The key a warmup is written in: the requested one unless its signature needs double accidentals or more than six sharps/flats
    (a concert F# for an alto reads as D# major), in which case the enharmonic key with the fewest accidentals."""
    try:
        names = scale_spelling(tonic, tonality)
    except ValueError:                       # the scale needs a double accidental the spelling tables do not write
        return related_key(tonic, tonality, 0)
    if any(len(x) > 2 for x in names) or sum(1 for x in names if len(x) > 1) > 6:
        return related_key(tonic, tonality, 0)
    return tonic, tonality


def scale_spelling(tonic: str, tonality: str) -> list[str]:
    return sph.spell_scale(tonic, "aeolian" if tonality == "natural minor" else "ionian")


_STEPS = {"major": (0, 2, 4, 5, 7, 9, 11), "natural minor": (0, 2, 3, 5, 7, 8, 10)}


@dataclass(frozen=True)
class Run:
    """A scale laid out over the window: ``notes[i]`` is scale step ``i`` above the run's tonic (step 7 is the octave)."""
    notes: tuple[tuple[str, int, int], ...]     # (spelled, octave, midi)

    def __len__(self) -> int:
        return len(self.notes)


def build_run(tonic: str, tonality: str, lo: int, hi: int, *, steps: int, start_octave_from_low: bool = True, anchor: float = 0.0) -> Run:
    """The scale from a tonic placed near ``lo + anchor*(hi-lo)``, ``steps`` scale steps up if they fit (fewer if not).
    ``anchor`` 0 sits the tonic at the bottom of the window, 0.5 in the middle."""
    names = scale_spelling(tonic, tonality)
    semis = _STEPS[tonality]
    tonic_pc = sph.pc_of(tonic)
    target = lo + anchor * (hi - lo)
    # candidate tonic midis: every midi with the tonic's pitch class inside the window
    cands = [m for m in range(lo, hi + 1) if m % 12 == tonic_pc]
    if not cands:
        raise WarmupUnavailable(f"{tonic} doesn't sit inside this instrument's window")
    best: tuple[float, int] | None = None
    for base in cands:
        top = base + 12 * (steps // 7) + semis[steps % 7]
        fits = top <= hi
        score = (0 if fits else 1000) + abs(base - target)
        if best is None or score < best[0]:
            best = (score, base)
    base = best[1]                                          # type: ignore[index]
    out: list[tuple[str, int, int]] = []
    for i in range(steps + 1):
        midi = base + 12 * (i // 7) + semis[i % 7]
        if midi > hi:
            break
        spelled = names[i % 7]
        out.append((spelled, sph.octave_for(spelled, midi), midi))
    return Run(tuple(out))


def fit_steps(tonic: str, tonality: str, lo: int, hi: int, want: int) -> int:
    """The most scale steps (up to ``want``) that fit above some tonic inside the window."""
    for steps in range(want, 0, -1):
        try:
            if len(build_run(tonic, tonality, lo, hi, steps=steps)) == steps + 1:
                return steps
        except WarmupUnavailable:
            return 0
    return 0


def fit_window(player: "Player", level: str, tonic: str, tonality: str, need_steps: int) -> tuple[int, int, int]:
    """(low, high, steps): the level's comfort window, or that window widened a little (never past what the instrument can play) when this key
    would not otherwise hold ``need_steps`` scale steps. ``steps`` is what actually fits (``need_steps`` or fewer)."""
    lo0, hi0 = player.window(level)
    best = (lo0, hi0, fit_steps(tonic, tonality, lo0, hi0, need_steps))
    if best[2] >= need_steps:
        return best
    for widen in (2, 4, 6, 8):
        lo, hi = max(player.play_low, lo0 - widen), min(player.play_high, hi0 + widen)
        steps = fit_steps(tonic, tonality, lo, hi, need_steps)
        if steps >= need_steps:
            return lo, hi, steps
        if steps > best[2]:
            best = (lo, hi, steps)
    return best


# ---------------------------------------------------------------- an exercise as a flat list of notes


@dataclass
class Note:
    spelled: str            # '' for a rest
    octave: int
    dur: str                # whole | half | quarter | eighth | sixteenth
    art: str = ""           # '', 'staccato', 'accent', 'tenuto' (a slur is carried by ``slur``)
    slur: int = 0
    chord: str = ""         # the chord symbol printed above this note (song-aware exercises); '' for none

    @property
    def rest(self) -> bool:
        return not self.spelled

    @property
    def beats(self) -> Fraction:
        return _DUR_BEATS[self.dur]

    @property
    def midi(self) -> int:
        return sph.midi_of(self.spelled, self.octave)


def n_(run: Run, step: int, dur: str, art: str = "", slur: int = 0) -> Note:
    spelled, octave, _m = run.notes[step]
    return Note(spelled, octave, dur, art, slur)


def rests(beats: Fraction) -> list[Note]:
    out: list[Note] = []
    rest_left = Fraction(beats)
    for name, value in _REST_PIECES:
        while rest_left >= value:
            out.append(Note("", 0, name))
            rest_left -= value
    return out


def total_beats(notes: list[Note]) -> Fraction:
    return sum((n.beats for n in notes), Fraction(0))


def finish(notes: list[Note], run: Run, step: int = 0) -> list[Note]:
    """End on ``step`` of the run (the tonic) and fill the last bar: the closing note takes up to a half note, rests make up the rest."""
    used = total_beats(notes) % BEATS_PER_BAR
    room = BEATS_PER_BAR - used if used else BEATS_PER_BAR
    closing = Fraction(4) if room >= 4 else Fraction(2) if room >= 2 else Fraction(1) if room >= 1 else Fraction(1, 2)
    name = next(k for k, v in _DUR_BEATS.items() if v == closing)
    notes = notes + [n_(run, step, name)]
    notes = notes + rests(room - closing) if room > closing else notes
    return notes


# ---------------------------------------------------------------- the four families


@dataclass
class Built:
    notes: list[Note]
    bpm: int
    title: str
    how: list[str]              # how to practice it (shown to the player)
    listen: list[str]
    meta: dict[str, Any]


def _level_index(level: str) -> int:
    return LEVELS.index(level) if level in LEVELS else 1


def build_long_tones(player: Player, level: str, tonic: str, tonality: str, *, variant: int = 0, size: str = "full") -> Built:
    lv = _level_index(level)
    # which scale steps to hold: a settled shape for each level, nudged to a different part of the window for each variant
    shapes = [[0, 2, 4, 2], [0, 1, 2, 3, 4, 2], [0, 2, 4, 7, 4, 2]]
    steps_ = shapes[lv][:4] if size == "short" else shapes[lv]
    anchors = (0.25, 0.0, 0.55, 0.3)
    anchor = anchors[variant % len(anchors)]
    top_step = max(steps_)
    lo, hi, fitted = fit_window(player, level, tonic, tonality, max(top_step, 7))
    if fitted < top_step:
        raise WarmupUnavailable("the long-tone shape does not fit this instrument's range")
    run = build_run(tonic, tonality, lo, hi, steps=max(top_step, 7), anchor=anchor)
    if len(run) <= top_step:
        raise WarmupUnavailable("the long-tone shape does not fit this instrument's range")
    notes: list[Note] = []
    for i, s in enumerate(steps_):
        notes.append(n_(run, s, "whole"))
        if i % 2 == 1:
            notes.append(Note("", 0, "whole"))
    if steps_ and len(steps_) % 2 == 1:
        notes.append(Note("", 0, "whole"))
    bpm = (60, 50, 40)[lv]
    seconds = float(4 * 60 / bpm)
    reg = {0: "middle", 1: "low", 2: "upper", 3: "middle"}[variant % 4]
    names = " · ".join(run.notes[s][0] for s in steps_)
    how = [f"Breathe in, then hold each note for all 4 beats at ♩ = {bpm} (about {seconds:g} seconds). The rest bar is your calm breath.",
           "Start each note softly and in tune, keep the pitch and the tone steady the whole way, and release without letting the pitch sag."]
    if lv >= 1:
        how.append("Once it is steady, shape each note: soft → a little louder → soft again, with the pitch staying put.")
    if lv >= 2:
        how.append("Check the second note of each pair against the first: the interval you hear should stay in tune as the air changes.")
    return Built(notes, bpm, f"Long tones ({reg} register) — {names}", how,
                 ["An even, centered tone from the first to the last beat.", "Pitch that doesn't drift as the note runs out of air."],
                 {"variant": variant, "register": reg, "hold_seconds": round(seconds, 2), "window": [lo, hi]})


def build_scale(player: Player, level: str, tonic: str, tonality: str, *, variant: int = 0, size: str = "full") -> Built:
    lv = _level_index(level)
    want_oct = (1, 2, 2)[lv] if size == "full" else 1
    lo, hi, steps = fit_window(player, level, tonic, tonality, 7 * want_oct)
    if steps >= 7 and steps < 14 and want_oct == 2:
        steps = 7
    if steps < 7:
        raise WarmupUnavailable(f"a full {key_text(tonic, tonality)} scale does not fit this instrument's range")
    run = build_run(tonic, tonality, lo, hi, steps=steps)
    bpm = (66, 72, 76)[lv]
    # a ladder of passes over the same scale, each on its own bars: tongued first, then slurred, then faster
    ladder = [[("quarter", False), ("quarter", True)], [("quarter", False), ("eighth", True)],
              [("eighth", False), ("eighth", True), ("sixteenth", True)]][lv]
    if size == "short":
        ladder = ladder[:2] if lv == 2 else ladder[:1]
    notes: list[Note] = []
    group = 0
    up = list(range(0, steps + 1))
    down = list(range(steps - 1, 0, -1))
    for unit, slurred in ladder:
        part: list[Note] = []
        for i, s_ in enumerate(up):
            sl = 0
            if slurred:
                if i % 4 == 0:
                    group += 1
                sl = group          # slur the way up in fours, tongue the way down
            part.append(n_(run, s_, unit, "", sl))
        for s_ in down:
            part.append(n_(run, s_, unit))
        notes += finish(_unslur_singletons(part), run)
    names = ", then ".join(f"{u} notes{' (slurred going up)' if sl else ''}" for u, sl in ladder)
    octaves = f"{steps // 7} octave{'s' if steps > 7 else ''}"
    how = [f"Play the {key_text(tonic, tonality)} scale (the written key for your instrument) up and down at ♩ = {bpm}, {octaves}. "
           f"{len(ladder)} pass{'es' if len(ladder) != 1 else ''}, each starting on a new bar: {names}.",
           "Slurred passes: slur each group of four notes going up, tongue every note coming down. Tongued passes: every note lightly tongued.",
           "Keep the tempo steady — if you stumble, slow down rather than rushing the next notes."]
    return Built(notes, bpm, f"{key_text(tonic, tonality)} scale — {octaves}, {len(ladder)} pass{'es' if len(ladder) != 1 else ''}", how,
                 ["Even fingers: every note the same length.", "The same tone quality in every register."],
                 {"variant": variant, "octaves": steps // 7, "passes": [u for u, _ in ladder], "window": [lo, hi]})


def build_intervals(player: Player, level: str, tonic: str, tonality: str, *, interval: str = "thirds", variant: int = 0, size: str = "full") -> Built:
    if interval not in INTERVALS:
        raise WarmupUnavailable(f"I don't have an exercise for “{interval}”")
    n = INTERVALS[interval]
    lv = _level_index(level)
    want_oct = (1, 1, 2)[lv] if size == "full" else 1
    lo, hi, steps = fit_window(player, level, tonic, tonality, 7 * want_oct + n)
    if steps < n + 3:
        raise WarmupUnavailable(f"{interval} don't fit in this instrument's range")
    run = build_run(tonic, tonality, lo, hi, steps=steps)
    unit = ("quarter", "eighth", "eighth")[lv]
    bpm = (60, 72, 84)[lv]
    last = steps - n
    notes: list[Note] = []
    group = 0
    cell4 = lv >= 2
    firsts = list(range(0, last + 1))
    if variant % 2 == 1:
        firsts = list(reversed(firsts))
    first_dir = "up" if variant % 2 == 0 else "down"
    if cell4:
        for i in firsts:
            if i + 1 > last:
                continue
            group += 1
            notes += [n_(run, i, unit, "", group), n_(run, i + n, unit, "", group), n_(run, i + 1, unit, "", group), n_(run, i + 1 + n, unit, "", group)]
    else:
        for i in firsts:
            group += 1
            notes += [n_(run, i, unit, "", group), n_(run, i + n, unit, "", group)]
    for i in reversed(firsts):                       # and back, the interval turned over
        if cell4 and i + 1 > last:
            continue
        group += 1
        if cell4:
            notes += [n_(run, i + 1 + n, unit, "", group), n_(run, i + 1, unit, "", group), n_(run, i + n, unit, "", group), n_(run, i, unit, "", group)]
        else:
            notes += [n_(run, i + n, unit, "", group), n_(run, i, unit, "", group)]
    notes = finish(notes, run)
    how = [f"Play {interval} through the {key_text(tonic, tonality)} scale (written key): each pair is a scale step and the note {n} steps above it.",
           f"Slur each {'group of four' if cell4 else 'pair'}, then take a quick breath-free restart on the next. Start {first_dir}ward, then come back the other way.",
           f"Keep ♩ = {bpm} steady; the {INTERVAL_SINGULAR[interval]} changes size from step to step because the notes stay in the key — listen for it."]
    return Built(notes, bpm, f"Diatonic {interval} — {key_text(tonic, tonality)}{' (starting downward)' if variant % 2 else ''}", how,
                 [f"Each {INTERVAL_SINGULAR[interval]} in tune and the same length.", "Smooth finger changes, no accent on the second note of a slur."],
                 {"variant": variant, "interval": interval, "steps": n, "cell": 4 if cell4 else 2, "unit": unit, "window": [lo, hi]})


_PAIR_SPANS = (1, 2, 3, 1, 4, 2)           # two-note exercises: neighbouring notes, thirds, fourths ... (variants 3 and 5 start downward)
_PAIR_NAMES = {1: "stepwise", 2: "in thirds", 3: "in fourths", 4: "in fifths"}


def build_articulation(player: Player, level: str, tonic: str, tonality: str, *, pattern: str = "repeated", variant: int = 0, size: str = "full") -> Built:
    if pattern not in ARTIC_PATTERNS:
        raise WarmupUnavailable(f"I don't have an articulation pattern called “{pattern}”")
    lv = _level_index(level)
    lo, hi, fitted = fit_window(player, level, tonic, tonality, 7)
    run = build_run(tonic, tonality, lo, hi, steps=7, anchor=0.3)
    if len(run) < 8:
        raise WarmupUnavailable("the articulation pattern does not fit this instrument's range")
    notes: list[Note] = []
    group = 0
    bpm = (60, 72, 80)[lv]
    meta_extra: dict[str, Any] = {}
    if pattern == "repeated":
        pitches = [4, 2] if size == "full" else [4]             # the fifth of the scale, then the third: comfortable, resonant notes
        for step in pitches:
            bars = [("quarter", 4, "")] + [("eighth", 8, "")] + ([("sixteenth", 16, "")] if lv >= 2 else [("quarter", 4, "accent")])
            if size == "short":
                bars = bars[:2]
            for dur, count, art in bars:
                for _ in range(count):
                    notes.append(n_(run, step, dur, art))
        how = [f"Repeat the same note, tonguing every note: quarters, then eighths{', then sixteenths' if lv >= 2 else ', then accented quarters'}, at ♩ = {bpm}. "
               f"Then do it again on the next note.",
               "Keep the air moving steadily between the notes — the tongue only interrupts it, it never stops it.",
               "Make every note start the same way; if the notes get hard or uneven, slow the tempo rather than pushing."]
        title = "Tonguing on one note"
    elif pattern == "two_note":
        which = variant % len(_PAIR_SPANS)
        span = _PAIR_SPANS[which]
        down = which in (3, 5)
        starts = [i for i in range(0, len(run) - span)][: (4 if size == "short" else 6)]
        pairs = [(i + span, i) if down else (i, i + span) for i in starts]
        forms = [("slurred", lambda k: (True, "")), ("tongued", lambda k: (False, "staccato")),
                 ("alternating", lambda k: (k % 2 == 0, "" if k % 2 == 0 else "staccato"))]
        for _name, rule in forms:
            for k, (a_, b_) in enumerate(pairs):
                slurred, art = rule(k)
                if slurred:
                    group += 1
                    notes += [n_(run, a_, "eighth", "", group), n_(run, b_, "eighth", "", group)]
                else:
                    notes += [n_(run, a_, "eighth", art), n_(run, b_, "eighth", art)]
            notes = _fill_bar(notes)
        shape = _PAIR_NAMES.get(span, "stepwise")
        how = [f"Each pair is two notes {shape}{', starting from the top' if down else ''}, at ♩ = {bpm}. First play all the pairs slurred: tongue only the first note of each pair.",
               "Second line: the same pairs tongued short and light on both notes. Third line: alternate — a slurred pair, a tongued pair.",
               "Notice how the second note of a slur arrives without a tongue stroke. Keep all three lines the same speed."]
        title = f"Two-note slurs and tongued pairs ({shape}{', downward' if down else ''})"
        meta_extra = {"span": span, "down": down}
    elif pattern == "slur_tongue":
        seq = list(range(0, min(len(run), 8)))
        for offset in ([0, 1] if size == "full" else [0]):
            s_ = [x + offset for x in seq if x + offset < len(run)]
            for i in range(0, len(s_) - 3, 2):
                group += 1
                notes += [n_(run, s_[i], "eighth", "", group), n_(run, s_[i + 1], "eighth", "", group), n_(run, s_[i + 2], "eighth", "staccato"),
                          n_(run, s_[i + 3], "eighth", "staccato")]
            back = list(reversed(s_))
            for i in range(0, len(back) - 3, 2):
                group += 1
                notes += [n_(run, back[i], "eighth", "", group), n_(run, back[i + 1], "eighth", "", group), n_(run, back[i + 2], "eighth", "staccato"),
                          n_(run, back[i + 3], "eighth", "staccato")]
            notes = _fill_bar(notes)
        how = [f"In each group of four: slur the first two notes, then tongue the last two short, at ♩ = {bpm}. Up the scale, then back down; then once more starting a step higher.",
               "The change from smooth to detached should be clear but the tempo and the air stay even.",
               "If the grouping slips, play it once more slowly with a steady foot tap."]
        title = "Slur two, tongue two"
    else:  # contrast
        styles = [("legato", ""), ("staccato", "staccato"), ("accent", "accent"), ("tenuto", "tenuto")]
        for name, art in styles[: (2 if size == "short" else 4)]:
            seq = list(range(0, 5)) + [3, 2, 1]
            group += 1
            for s_ in seq:
                notes.append(n_(run, s_, "quarter", art, group if name == "legato" else 0))
        how = [f"Four lines of the same melody at ♩ = {bpm}, each with its own character: smooth (legato), short (staccato), accented, and sustained (tenuto).",
               "Make the difference between the lines obvious in length and in how each note starts — without changing the tempo.",
               "Listen for the same pitch and tone in every line."]
        title = "Articulation styles"
    notes = _unslur_singletons(notes)
    notes = finish(notes, run) if pattern in ("repeated", "slur_tongue") else _fill_bar(notes)
    return Built(notes, bpm, title, how, ["Every note starting cleanly, with an even air stream.", "The same pitch and tone whichever articulation you use."],
                 {"variant": variant, "pattern": pattern, "window": [lo, hi], **meta_extra})


def _fill_bar(notes: list[Note]) -> list[Note]:
    used = total_beats(notes) % BEATS_PER_BAR
    return notes + rests(BEATS_PER_BAR - used) if used else notes


def _unslur_singletons(notes: list[Note]) -> list[Note]:
    """A slur needs two notes: a group with only one pitched note is written plain (a lone slur mark would be an ABC error)."""
    counts: dict[int, int] = {}
    for n in notes:
        if n.slur and not n.rest:
            counts[n.slur] = counts.get(n.slur, 0) + 1
    return [replace(n, slur=0) if n.slur and counts.get(n.slur, 0) < 2 else n for n in notes]


BUILDERS = {"long_tones": build_long_tones, "scale": build_scale, "intervals": build_intervals, "articulation": build_articulation}


# ---------------------------------------------------------------- notation and verification


def to_events(notes: list[Note]) -> tuple[Any, int]:
    """(``MusicalEvent`` tuple in the written domain, bar count). Every bar is checked to add up to the meter."""
    from music_coach_ami.musical_idea_engine import MusicalEvent

    events: list[Any] = []
    bar, pos = 0, Fraction(0)
    for n in notes:
        if pos + n.beats > BEATS_PER_BAR:
            raise WarmupUnavailable("a note crosses a bar line")
        art = n.art
        events.append(MusicalEvent(
            spelled=n.spelled, octave=n.octave, duration=f"rest_{n.dur}" if n.rest else n.dur, bar_index=bar, beat=float(pos) + 1.0,
            articulation="" if n.rest else art, domain="written", slur_group=0 if n.rest else n.slur,
            pitch_class=None if n.rest else sph.pc_of(n.spelled), chord=n.chord))
        pos += n.beats
        if pos == BEATS_PER_BAR:
            bar, pos = bar + 1, Fraction(0)
    if pos != 0:
        raise WarmupUnavailable("the last bar does not add up")
    return tuple(events), bar


def render(player: Player, built: Built, tonic: str, tonality: str, *, title: str, bpm: int | None = None) -> tuple[str, dict[str, Any]]:
    from music_coach_ami.musical_idea_engine import MusicalIdeaComposition, composition_to_abc
    from music_coach_ami.notation_profile import notation_profile_for_instrument

    events, bars = to_events(built.notes)
    profile = notation_profile_for_instrument(player.notation)
    if player.family == "piano":
        profile = replace(profile, clef="treble", midi_low=55, midi_high=88)
    comp = MusicalIdeaComposition(events=events, reference_key=key_token(tonic, tonality), meter=METER, bars=bars, object_type="pattern", style="warmup",
                                  notation_profile=profile, strategy="warmup", tonic=tonic, tonality=tonality,
                                  scale_spelling=tuple(scale_spelling(tonic, tonality)))
    abc, diag = composition_to_abc(comp, title=title, bpm=int(bpm or built.bpm))
    return abc, diag


def verify(player: Player, level: str, built: Built, tonic: str, tonality: str, diag: dict[str, Any]) -> list[dict[str, Any]]:
    """The checks every exercise passes before it is shown. Raises ``WarmupUnavailable`` listing any that fail."""
    pitched = [n for n in built.notes if not n.rest]
    lo, hi = (built.meta.get("window") or list(player.window(level)))[:2]
    pcs = {sph.pc_of(x) for x in scale_spelling(tonic, tonality)}
    midi = [n.midi for n in pitched]
    checks = [
        {"name": "bars_add_up", "ok": total_beats(built.notes) % BEATS_PER_BAR == 0, "detail": f"{total_beats(built.notes) / BEATS_PER_BAR} bars of 4"},
        {"name": "written_inside_level_window", "ok": all(lo <= m <= hi for m in midi), "detail": f"{lo}-{hi}, notes {min(midi)}-{max(midi)}"},
        {"name": "written_inside_playable_range", "ok": all(player.play_low <= m <= player.play_high for m in midi), "detail": f"{player.play_low}-{player.play_high}"},
        {"name": "inside_the_key", "ok": all(sph.pc_of(n.spelled) in pcs for n in pitched), "detail": key_text(tonic, tonality)},
        # the sounding line is the written one minus the instrument's exact offset: its pitch classes must be the written ones minus the app's own
        # transposition (two separate tables agreeing, not one number subtracted from itself)
        {"name": "sounding_equals_written_minus_offset",
         "ok": all(((m - player.offset) % 12) == ((sph.pc_of(n.spelled) - player.semitones) % 12) for m, n in zip(midi, pitched)),
         "detail": f"written − {player.offset} semitones, octave included"},
        {"name": "notation_validation", "ok": bool(diag.get("notation_validation_ok")), "detail": "; ".join(diag.get("notation_validation_errors") or []) or "passed"},
    ]
    bad = [c for c in checks if not c["ok"]]
    if bad:
        raise WarmupUnavailable("; ".join(f"{c['name']}: {c['detail']}" for c in bad))
    return checks


def pass_seconds(built: Built, bpm: int | None = None) -> float:
    return float(total_beats(built.notes)) * 60.0 / float(bpm or built.bpm)


# ---------------------------------------------------------------- the player


def make_player(spec_key: str, concert_key: str) -> Player:
    """The player for one of the verified instruments (``exercise_adapt.SPECS``) in a concert Practice Key.

    The written key comes from the app's own written-music context, resolved from an isolated mapping, so the global instrument and
    saxophone-type selections are neither read nor changed. Raises ``WarmupUnavailable`` if the pitch table can't be verified."""
    from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY
    from music_coach_ami.exercise_adapt import SPECS
    from music_coach_ami.written_music_context import build_written_music_context

    spec = SPECS.get(spec_key)
    if spec is None:
        raise WarmupUnavailable(f"I don't have a verified pitch table for “{spec_key}”")
    iso = {SELECTED_TRANSPOSING_INSTRUMENT_KEY: spec.ttype} if spec.ttype else {}
    concert = (concert_key or "C").strip() or "C"
    ctx = build_written_music_context(instrument=spec.family, practice_concert_key=concert, original_song_key=concert, concert_chords=[],
                                      session_state=iso, register="", chart_already_in_practice_key=True)
    semis = int(ctx.transposition_semitones or 0)
    offset = sph.exact_offset(spec.notation, semis)
    rng = sph.playable_written_range(spec.notation)
    if offset is None or rng is None:
        raise WarmupUnavailable(f"the written/sounding pitch relationship for {spec.label} can't be verified")
    return Player(key=spec.key, label=spec.label, notation=spec.notation, family=window_family(spec.key), ttype=spec.ttype, offset=int(offset),
                  play_low=int(rng[0]), play_high=int(rng[1]), written_key=str(ctx.written_key or concert), concert_key=concert, semitones=semis,
                  clef="treble")
