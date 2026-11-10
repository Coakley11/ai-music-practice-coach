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
# and the left is derived an octave below it, so this sits above middle C: G3 to C6 gives
# the right hand a comfortable two octaves and leaves the left hand G2-C5.
PIANO_EXERCISE_LOW = 55   # G3
PIANO_EXERCISE_HIGH = 84  # C6

__all__ = [
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
    "PIANO_LOW",
    "grand_staff_abc",
    "LEFT_HAND_CENTRE",
    "RIGHT_HAND_FLOOR",
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
    """One ABC pitch token for *midi*, spelled for *key* by the app's own speller."""
    from music_theory import abc_pitch_for_spelled_note, spell_note_in_key

    name = spell_note_in_key(int(midi) % 12, key or "C")
    octave = int(midi) // 12 - 1
    return abc_pitch_for_spelled_note(f"{name}{octave}")


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
        label = ""
        if i < len(chords) and str(chords[i] or "").strip():
            label = f'"{str(chords[i]).strip()}"'
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
            prefix = label if j == 0 else ""
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


def hands_for_scale(
    midis: Sequence[int],
    *,
    motion: str = "parallel",
    octaves_apart: int = 1,
) -> list[list[int]]:
    """A scale line turned into two hands, one voicing per note.

    ``parallel`` is the pair of hands moving together an octave apart - the first scale
    exercise anyone is given. ``contrary`` mirrors the left hand around its starting note,
    which is the standard next step and is why it is generated rather than hand-written.
    ``separate`` keeps the line in one hand so a beginner can learn it before combining.
    """
    line = [int(m) for m in midis if m is not None]
    if not line:
        return []
    motion = str(motion or "parallel").strip().lower()
    out: list[list[int]] = []
    start = line[0]
    for m in line:
        right = _clamp_to_piano(m)
        if motion == "separate":
            out.append([right])
            continue
        if motion == "contrary":
            left = _clamp_to_piano(start - (m - start) - 12 * octaves_apart)
        else:
            left = _clamp_to_piano(m - 12 * octaves_apart)
        out.append(sorted({left, right}))
    return out
