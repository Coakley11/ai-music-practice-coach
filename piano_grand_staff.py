"""Grand-staff ABC for the Practice page's piano exercises.

A pianist reads two staves. Everything else in this app writes one, so the piano exercise
arrived as a single treble staff of block chords - correct harmony, wrong instrument.

This is a *rendering adapter*, not an engine. It consumes the events the existing builders
already produce (``chord_navigation_notation.VoicingEvent``, and plain MIDI lists for
scales and arpeggios) and emits the two-voice ABC that abcjs already understands:

    %%score {1 | 2}
    V:1 clef=treble
    V:2 clef=bass

Harmony, voice leading, level and Practice Focus are all decided upstream and are not
re-litigated here. The only musical judgement this module makes is **which hand plays
what**, which is a question about the keyboard rather than about the chords.

Pure Python: no Streamlit, no abcjs, so the split and the emitted text are unit-testable.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

# Middle C. The conventional reading split: notes below it live on the bass staff.
MIDDLE_C = 60

# A real piano, so an exercise can never ask for a key that does not exist.
PIANO_LOW = 21   # A0
PIANO_HIGH = 108  # C8

# The register a two-handed exercise is written in. The generated line is the RIGHT hand's
# and the left is derived an octave below it, so the window has to leave *both* staves
# readable, not just the treble.
#
# This was G3-C6 (55-84), chosen so the treble staff would not be a bar of rests. It is not
# enough: build_exercise_midis fills toward the top of whatever range it is given, so the
# line landed at G4-C6, which put the left hand at G3-C5 and 79% of its notes above the bass
# staff - four and five ledger lines deep on nearly every note. Unit tests could not see
# that; the browser capture could.
#
# C4-C5 is the register a two-handed scale study is actually written in: the right hand
# between middle C and the C above, the left hand an octave below it in the bass staff where
# it belongs. Measured over parallel and contrary motion at every level, this leaves 2% of
# notes more than two ledger lines off a staff, against 25% before.
PIANO_EXERCISE_LOW = 60   # C4, middle C
PIANO_EXERCISE_HIGH = 72  # C5

# One octave is the right window for a first scale study and the wrong one for the levels
# above it. A C major scale between C4 and C5 has eight rungs, and Advanced plays eight
# notes a bar: the line hits the ceiling and turns round, measured at 21 turnarounds over
# eight bars against 15 in two octaves, with eight distinct pitches against fifteen. That
# is not a two-octave study played small, it is a different and worse exercise.
#
# So the window grows with the level, the way the study does, and the left hand's octave is
# chosen per line (see ``left_hand_octaves``) rather than fixed at one - which is what let
# the one-octave window look necessary in the first place.
PIANO_EXERCISE_REGISTERS: dict[str, tuple[int, int]] = {
    "Beginner": (60, 72),      # C4-C5, one octave, hands an octave apart
    "Intermediate": (60, 84),  # C4-C6, two octaves
    "Advanced": (60, 84),      # C4-C6; Advanced differs in notes per bar and pattern
}

# Where the left hand can be written and still be read on the bass staff. The staff spans
# G2-A3; two ledger lines either side of it is E4 above and C2 below, which is as far as a
# scale study is normally engraved before it changes clef.
LEFT_HAND_CEILING = 64  # E4
LEFT_HAND_FLOOR = 36    # C2

# ``music_theory.abc_pitch_for_spelled_note`` writes scientific C4 (middle C, MIDI 60) as
# ABC ``c``. Real abcjs 6.4.4 decodes a bare ``C`` as MIDI 60 and ``c`` as 72, so a token
# written from a scientific octave sounds and is drawn an octave high. The grand staff is
# the one place that cannot absorb the error: with both hands displaced the same way, the
# left hand climbs above the bass staff and the right runs off the top of the treble.
#
# Composition and the AMI coach each correct the same thing the same way - see
# ``composition_melody_notation.COMPOSITION_ABC_OCTAVE_SHIFT`` and
# ``music_coach_ami.musical_idea_engine.COACH_ABC_OCTAVE_SHIFT``. This is that correction,
# applied once, for the tokens this module writes.
ABC_OCTAVE_SHIFT = -1


def piano_exercise_register(level: str = "Intermediate") -> tuple[int, int]:
    """The right hand's window for a scale or arpeggio study at this level."""
    lvl = str(level or "Intermediate").strip().title()
    return PIANO_EXERCISE_REGISTERS.get(lvl, PIANO_EXERCISE_REGISTERS["Intermediate"])


def left_hand_octaves(midis: Sequence[int]) -> int:
    """How many octaves below the right hand the left hand should answer.

    One octave is the usual answer and the only one a one-octave study needs. A two-octave
    line reaching C6 cannot be answered an octave below without writing the left hand up to
    C5, four ledger lines above the bass staff; two octaves below puts the same notes back
    where they are read. Chosen once for a whole line, never per bar, so the left hand does
    not change octave in the middle of a study.
    """
    notes = [int(m) for m in midis if m is not None]
    if not notes:
        return 1
    for k in (1, 2, 3):
        if max(notes) - 12 * k <= LEFT_HAND_CEILING:
            return k
    return 3

__all__ = [
    "ABC_OCTAVE_SHIFT",
    "CHORD_LABEL_SEPARATOR",
    "LH_OCTAVE",
    "LH_ROLE_FOR_FOCUS",
    "LH_ROOT",
    "LH_ROOT_FIFTH",
    "LH_ROOT_SEVENTH",
    "LH_SHELL_3_7",
    "LH_THIRD_ROOT",
    "MIDDLE_C",
    "PIANO_HIGH",
    "PIANO_EXERCISE_HIGH",
    "PIANO_EXERCISE_LOW",
    "PIANO_EXERCISE_REGISTERS",
    "PIANO_LOW",
    "grand_staff_abc",
    "LEFT_HAND_CEILING",
    "LEFT_HAND_CENTRE",
    "LEFT_HAND_FLOOR",
    "RIGHT_HAND_FLOOR",
    "left_hand_octaves",
    "piano_exercise_register",
    "hands_for_scale",
    "hands_for_voicing",
    "in_piano_range",
    "left_hand_role",
    "scale_motion_for",
    "split_hands",
]


def in_piano_range(midi: int) -> bool:
    return PIANO_LOW <= int(midi) <= PIANO_HIGH


def _clamp_to_piano(midi: int) -> int:
    m = int(midi)
    while m < PIANO_LOW:
        m += 12
    while m > PIANO_HIGH:
        m -= 12
    return m


def split_hands(
    midis: Sequence[int],
    *,
    split_at: int = MIDDLE_C,
    min_left: int = 1,
) -> tuple[list[int], list[int]]:
    """``(left_hand, right_hand)`` for one chord voicing.

    The split point is the reading convention, not a rule about the music: a voicing that
    sits entirely above it would leave the left hand silent, so the lowest note is moved
    down to the bass staff rather than printing an empty bar. A voicing entirely below it
    is left alone - that is a genuine two-hands-low passage, and inventing a treble note
    would be adding music the harmony never asked for.
    """
    notes = sorted(int(m) for m in midis if m is not None)
    if not notes:
        return [], []
    left = [m for m in notes if m < split_at]
    right = [m for m in notes if m >= split_at]
    if not left and len(right) > min_left:
        # Everything landed in the treble: give the bass staff the lowest note(s).
        take = max(min_left, 1)
        left, right = right[:take], right[take:]
    return left, right


# Where each hand lives. These are reading registers, not limits: the left hand plays the
# foundation an octave or two below middle C, the right hand plays the harmony around it.
LEFT_HAND_CENTRE = 45   # A2
RIGHT_HAND_FLOOR = 55   # G3


def _nearest_octave_of(pc: int, near: int) -> int:
    """The octave of pitch class ``pc`` closest to ``near``, kept on the keyboard."""
    base = (int(near) // 12) * 12 + (int(pc) % 12)
    best = min((base - 12, base, base + 12), key=lambda m: abs(m - int(near)))
    return _clamp_to_piano(best)


# What the left hand is doing, as roles rather than note lists, so the names say why.
# Each is read against the chord's own tones: root, 3rd, 5th, 7th.
LH_ROOT = "root"                 # the root alone - the plainest foundation
LH_ROOT_FIFTH = "root_fifth"     # root and fifth - the common two-note foundation
LH_ROOT_SEVENTH = "root_seventh"  # the jazz left hand: root and seventh, 7 falling to 3
LH_SHELL_3_7 = "shell_3_7"       # the guide tones themselves, no root at all
LH_THIRD_ROOT = "third_root"     # the third underneath - a first-inversion bass
LH_OCTAVE = "octave"             # root doubled an octave up - a stride foundation

# Which role each Practice Focus asks the left hand for. Matched as a substring of the focus
# label, so the canonical focus list in practice_setup_controls stays the only list of foci:
# this names no new ones and invents no vocabulary of its own.
#
# Only foci that name a *left-hand* job are here. Improvisation, Soloing, Melody and the like
# are about the line the right hand plays and say nothing about the left, so forcing a role
# from them would be this module inventing an opinion the focus never expressed - and it
# would hide the level progression behind whichever focus happened to be selected. Those, and
# a focus with no opinion at all like Tone or Timing, leave the level's own progression
# alone. "Guide Tones" is kept because the upstream voicing engine already special-cases it.
LH_ROLE_FOR_FOCUS: dict[str, str] = {
    "guide tones": LH_SHELL_3_7,
    "reharmonization": LH_SHELL_3_7,
    "voice leading": LH_ROOT_SEVENTH,
    "left-hand": LH_OCTAVE,
    "inversions": LH_THIRD_ROOT,
    "comping": LH_ROOT_FIFTH,
}


def left_hand_role(level: str = "Intermediate", focus: str = "") -> str:
    """Which role the left hand takes, from the Practice Focus if it asks and the level if not.

    The level progression is the one a pianist actually follows - the root alone, then root
    and fifth, then the root-and-seventh shell - and a focus that names a left-hand job
    outranks it, because that is the exercise the musician chose.
    """
    text = str(focus or "").strip().lower()
    for needle, role in LH_ROLE_FOR_FOCUS.items():
        if needle in text:
            return role
    lvl = str(level or "Intermediate").strip().title()
    if lvl == "Advanced":
        return LH_ROOT_SEVENTH
    if lvl == "Intermediate":
        return LH_ROOT_FIFTH
    return LH_ROOT


def _pcs_for_role(role: str, tones: Sequence[int]) -> tuple[list[int], bool]:
    """``(pitch classes, double_an_octave)`` for a left-hand role, given the chord's tones.

    A role that needs a tone the chord does not have - a seventh on a triad - falls back to
    the nearest role the chord can actually supply rather than borrowing a note from
    somewhere else and changing the harmony.
    """
    root = tones[0]
    has_third = len(tones) >= 2
    has_fifth = len(tones) >= 3
    has_seventh = len(tones) >= 4
    if role == LH_SHELL_3_7 and has_seventh:
        return [tones[1], tones[3]], False
    if role == LH_ROOT_SEVENTH and has_seventh:
        return [root, tones[3]], False
    if role == LH_THIRD_ROOT and has_third:
        return [tones[1], root], False
    if role == LH_OCTAVE:
        return [root], True
    if role == LH_ROOT_FIFTH and has_fifth:
        return [root, tones[2]], False
    if role in (LH_SHELL_3_7, LH_ROOT_SEVENTH) and has_fifth:
        return [root, tones[2]], False      # no seventh to shell: the plain foundation
    return [root], False


def hands_for_voicing(
    voicing_midis: Sequence[int],
    chord: str = "",
    *,
    level: str = "Intermediate",
    focus: str = "",
) -> tuple[list[int], list[int]]:
    """``(left_hand, right_hand)`` with the hands given *roles*, not a midpoint.

    Splitting a close-position voicing at middle C is arbitrary: it can hand the left
    thumb a chord's third while the right plays its root, which is not how anyone voices a
    chord. So the left hand is built for its job - the foundation - and the right hand
    keeps the voice-led voicing the existing engine produced.

    What the left hand plays grows with the level, which is the progression a pianist
    actually follows:

        Beginner      the root alone
        Intermediate  root and fifth
        Advanced      a root-and-seventh shell, the jazz left hand

    A Guide Tones focus overrides that with the 3rd/7th shell at every level, because that
    is precisely the exercise Guide Tones names.
    """
    right = sorted(_clamp_to_piano(int(m)) for m in voicing_midis if m is not None)
    if not right:
        return [], []

    tones: list[int] = []
    if chord:
        try:
            from notation_exercise_patterns import chord_tone_pcs

            tones = [int(p) % 12 for p in chord_tone_pcs(chord)]
        except Exception:
            tones = []
    if not tones:
        tones = sorted({m % 12 for m in right})

    role = left_hand_role(level, focus)
    wanted, double_octave = _pcs_for_role(role, tones)

    left: list[int] = []
    anchor = LEFT_HAND_CENTRE
    for pc in wanted:
        midi = _nearest_octave_of(pc, anchor)
        if midi not in left:
            left.append(midi)
        anchor = midi + 4
    if double_octave and left:
        # The octave goes *below* the root, not above it. Doubling upwards puts the top note
        # at or past middle C for most roots, where it stops being a left hand and starts
        # crowding the right; downwards is where a stride foundation actually lives, and it
        # is always clear of the voicing above.
        lower = _clamp_to_piano(left[0] - 12)
        if lower not in left:
            left.append(lower)
    left.sort()

    # The hands must not collide or cross: lift the right hand clear if the voicing sits
    # low enough to overlap what the left hand just took.
    if left:
        floor = max(max(left) + 1, RIGHT_HAND_FLOOR)
        while right and min(right) < floor:
            right = [m + 12 for m in right]
            if max(right) > PIANO_HIGH:
                right = [m - 12 for m in right]
                break
    return left, sorted(_clamp_to_piano(m) for m in right)


def _abc_token(midi: int, key: str) -> str:
    """One ABC pitch token for *midi*, spelled for *key* by the app's own speller.

    Two things this has to get right, and got wrong.

    ``abc_pitch_for_spelled_note`` takes the octave as a keyword argument; it does not read
    one off the end of the note name. Passing "E3" spelled E at the default octave 4, so
    every note of every piano exercise came out in the same octave - the two staves printed
    identical tokens and the left hand appeared four ledger lines above the bass staff,
    which is what a browser capture showed.

    And ``k_field`` has to be the real key. Left at "C" the token is spelled as if there
    were no key signature, so a natural F in G major would emit a bare "f" that abcjs reads
    as F# - the key signature sharpening a note the harmony wanted natural.

    Then ``ABC_OCTAVE_SHIFT``, which neither of those two covered: getting the octave
    through the keyword argument still wrote it an octave above where it sounds. Proved
    against abcjs itself, which decodes a bare "C" as MIDI 60; the speller writes MIDI 60
    as "c", and abcjs reads that as 72.
    """
    from music_theory import abc_pitch_for_spelled_note, spell_note_in_key

    k = key or "C"
    name = spell_note_in_key(int(midi) % 12, k)
    octave = int(midi) // 12 - 1 + ABC_OCTAVE_SHIFT
    return abc_pitch_for_spelled_note(name, octave=octave, k_field=k)


def _chord_token(midis: Sequence[int], key: str, length: str) -> str:
    notes = [m for m in midis if m is not None]
    if not notes:
        return f"z{length}"
    if len(notes) == 1:
        return f"{_abc_token(notes[0], key)}{length}"
    inner = "".join(_abc_token(m, key) for m in sorted(notes))
    return f"[{inner}]{length}"


def _key_field(key: str) -> str:
    """The full ``K:`` line.

    ``composition_abc_key_field`` returns only the key *value* ("Am"), because its callers
    prepend the field name themselves. Emitting it bare produced a stray "Am" line and ABC
    with no key signature at all.
    """
    try:
        from composition_melody_notation import composition_abc_key_field

        value = composition_abc_key_field(key or "C")
    except Exception:
        value = key or "C"
    value = str(value or "C").strip()
    return value if value.startswith("K:") else f"K:{value}"


def _header(key: str, meter: str, bpm: int, title: str) -> list[str]:
    """The two-voice preamble. ``%%score {1 | 2}`` is what braces the staves together."""
    return [
        "X:1",
        f"T:{title}",
        f"M:{meter}",
        "L:1/8",
        f"Q:1/4={int(bpm)}",
        "%%score {1 | 2}",
        _key_field(key),
        "V:1 clef=treble",
        "V:2 clef=bass",
    ]


# How two harmonies sharing one printed note are joined. The app writes a subdivided bar
# as "Em -> G" wherever it shows one inline, so the score says the same thing.
CHORD_LABEL_SEPARATOR = " → "


def _bar_chord_labels(token: object, hits: int, beats_per_bar: float) -> list[str]:
    """One chord annotation per printed note, each above the note its harmony starts on.

    A chart cell is not a chord symbol. ``"Em:3.5|G:0.5p"`` is two harmonies and their
    timing - a bar of Em with a G pushed onto the last half-beat - and printing the cell
    verbatim put that timing metadata on the staff, where
    ``chord_subdivisions.chord_names_label`` says it must never go. The engraved answer is
    both symbols, each over the note where it begins, which is what the wind and bass
    staves already do through ``composition_melody_notation._chord_onset_beats``.

    The timing itself is untouched: this reads the subdivisions and writes labels. Which
    chord sounds when is decided upstream, by the chart, and the backing plays from the
    same token this only reads.
    """
    slots = max(1, int(hits))
    labels = [""] * slots
    text = str(token or "").strip()
    if not text:
        return labels
    try:
        from chord_subdivisions import (
            hit_underlying_chord,
            is_hit_token,
            parse_subdivisions,
        )

        subs = parse_subdivisions(text, beats_per_bar=float(beats_per_bar))
    except Exception:
        # Better a symbol that is merely unparsed than a bar with no harmony named.
        labels[0] = text
        return labels
    if not subs:
        return labels
    per_hit = float(beats_per_bar) / slots
    cursor = 0.0
    for sub in subs:
        name = str(getattr(sub, "chord", "") or "").strip()
        if name and is_hit_token(name):
            # A ".hit" marker is an instruction to the backing, not part of the name.
            name = hit_underlying_chord(name) or name
        if name:
            # Floor, so a harmony is never announced after the note it starts on, and
            # clamped, so a push landing on the bar line still gets printed.
            j = min(slots - 1, max(0, int(cursor / per_hit + 1e-6)) if per_hit > 0 else 0)
            labels[j] = f"{labels[j]}{CHORD_LABEL_SEPARATOR}{name}" if labels[j] else name
        cursor += float(getattr(sub, "weight", 0.0) or 0.0)
    return labels


def grand_staff_abc(
    bars: Sequence[Sequence[Sequence[int]]],
    *,
    key: str = "C",
    meter: str = "4/4",
    bpm: int = 96,
    title: str = "Piano exercise",
    chords: Sequence[str] = (),
    beats_per_bar: int = 4,
) -> str:
    """Two-staff ABC from ``bars`` of chord voicings.

    ``bars[i]`` is one measure: a sequence of voicings, each a sequence of MIDI notes.
    Every voicing is split into hands, so one call renders a whole exercise.
    """
    lines = _header(key, meter, bpm, title)
    treble: list[str] = []
    bass: list[str] = []

    for i, bar in enumerate(bars):
        hits = [h for h in (bar or []) if h or isinstance(h, tuple)]
        if not hits:
            hits = [[]]
        # Eighths per hit, so the bar always adds up to its meter.
        eighths = max(1, (int(beats_per_bar) * 2) // max(1, len(hits)))
        slot_labels = _bar_chord_labels(
            chords[i] if i < len(chords) else "", len(hits), beats_per_bar
        )
        t_toks, b_toks = [], []
        for j, hit in enumerate(hits):
            # A hit may arrive already assigned to hands as ``(left, right)``. Re-splitting
            # it at middle C would discard that assignment - which is the whole point of
            # giving the hands roles - so a pre-split pair is honoured as given.
            if (
                isinstance(hit, tuple)
                and len(hit) == 2
                and all(isinstance(side, (list, tuple)) for side in hit)
            ):
                left, right = list(hit[0]), list(hit[1])
            else:
                left, right = split_hands(hit)
            # The chord symbol belongs above the top staff only; printing it over both
            # would have abcjs draw the same label twice, once per stave.
            prefix = f'"{slot_labels[j]}"' if j < len(slot_labels) and slot_labels[j] else ""
            t_toks.append(prefix + _chord_token(right, key, str(eighths)))
            b_toks.append(_chord_token(left, key, str(eighths)))
        treble.append(" ".join(t_toks))
        bass.append(" ".join(b_toks))

    lines.append("V:1")
    lines.append(" | ".join(treble) + " |")
    lines.append("V:2")
    lines.append(" | ".join(bass) + " |")
    return "\n".join(lines)


def scale_motion_for(level: str = "Intermediate", focus: str = "") -> str:
    """Which two-hand motion this level and focus should be practising.

    The progression is the one a teacher sets: learn the line in one hand, then play both
    hands together, then split them apart. A Technique focus pulls contrary motion forward
    at any level, because independence is exactly what that focus is asking for.
    """
    lvl = str(level or "Intermediate").strip().title()
    text = str(focus or "").lower()
    if "technique" in text or "independence" in text:
        return "contrary"
    if lvl == "Beginner":
        return "separate"
    if lvl == "Advanced":
        return "contrary"
    return "parallel"


def _descending_from(start: int, pcs: Sequence[int], count: int) -> list[int]:
    """``count`` pitches walking *down* from ``start`` through the scale ``pcs``."""
    allowed = sorted({int(p) % 12 for p in pcs})
    if not allowed:
        return [int(start)] * int(count)
    out = [_clamp_to_piano(int(start))]
    cur = int(start)
    for _ in range(max(0, int(count) - 1)):
        nxt = cur - 1
        while nxt % 12 not in allowed and cur - nxt < 13:
            nxt -= 1
        cur = nxt
        out.append(_clamp_to_piano(cur))
    return out


def _fit_into_bass_staff(notes: Sequence[int]) -> list[int]:
    """Shift a left-hand line by whole octaves until it reads on the bass staff.

    Whole octaves only, so every scale degree the line was given survives the move: this
    decides where the hand sits, never which notes it plays. A descent long enough to reach
    past the floor is placed as high as the ceiling allows, because running off the bottom
    of the keyboard is the worse of the two failures - the engine clamps there and the bass
    turns into a held note.
    """
    line = [int(m) for m in notes]
    if not line:
        return []
    best, best_cost = line, None
    for k in (-2, -1, 0, 1, 2):
        cand = [m + 12 * k for m in line]
        if min(cand) < PIANO_LOW or max(cand) > PIANO_HIGH:
            continue
        cost = (
            max(0, LEFT_HAND_FLOOR - min(cand)) * 2
            + max(0, max(cand) - LEFT_HAND_CEILING)
        )
        if best_cost is None or cost < best_cost:
            best, best_cost = cand, cost
    return best


def hands_for_scale(
    midis: Sequence[int],
    *,
    motion: str = "parallel",
    octaves_apart: int | None = None,
    scale_pcs: Sequence[int] = (),
) -> list[list[int]]:
    """A scale line turned into two hands, one voicing per note.

    ``parallel`` is the pair of hands moving together an octave apart - the first scale
    exercise anyone is given. ``contrary`` sends the left hand down the same scale while the
    right goes up, which is the standard next step. ``separate`` keeps the line in one hand
    so a beginner can learn it before combining.

    Contrary motion needs ``scale_pcs``, and falls back to parallel without it. It used to
    mirror the line arithmetically - ``start - (m - start)`` - which is a reflection in
    semitones, not in scale degrees, and reflecting a scale that way does not give the scale
    back. Over Am6 it had the left hand playing G#, C# and F natural against an A Dorian
    right hand: the exercise contradicting its own harmony. The left hand now walks the very
    pitches the shared engine chose, downward.
    """
    line = [int(m) for m in midis if m is not None]
    if not line:
        return []
    motion = str(motion or "parallel").strip().lower()
    if motion == "contrary" and not scale_pcs:
        motion = "parallel"
    apart = left_hand_octaves(line) if octaves_apart is None else int(octaves_apart)
    out: list[list[int]] = []
    if motion == "contrary":
        # The descent is built first and then placed, because how far it falls depends on
        # the scale and the note count, not on the right hand's octave.
        lefts = _fit_into_bass_staff(
            _descending_from(line[0] - 12, scale_pcs, len(line))
        )
        return [sorted({lefts[i], _clamp_to_piano(m)}) for i, m in enumerate(line)]
    for m in line:
        right = _clamp_to_piano(m)
        if motion == "separate":
            out.append([right])
            continue
        left = _clamp_to_piano(m - 12 * apart)
        out.append(sorted({left, right}))
    return out
