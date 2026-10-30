"""Song-Aware Coaching (S2) — harmonic facts read from the charted chords only.

Everything here is a *fact about the chart*: which notes each chord contains, how every
other note behaves against it, what two neighbouring chords share, which moves connect
them, and how the selection ends. Coaching text is built on these facts elsewhere
(:mod:`song_coach_plan`); nothing here knows a melody, a recording or a performance.

**Chord reading.** The canonical speller (``music_theory.spell_chord_tones``) is the base.
It drops what some chart symbols state — added notes (``Cadd9``), the 7th of 9/11/13 and
7sus4 chords, the minor 3rd of ``m(maj7)``, a power chord's missing 3rd — and classifies
``add9`` chords as dominant. :func:`chord_facts` therefore *adds* what the symbol states on
top of the canonical tones and records every disagreement (``canonical_agrees`` /
``reading_notes``). It never removes a canonical tone except the documented corrections
(power chord 3rd, minor-major 3rd, sus 3rd). The shared speller is left unchanged.

**Shared-theory discrepancies, documented for a separate repair** (not changed here, because
Missions, Motif and other workflows depend on the current behaviour):

- ``music_theory.spell_chord_tones`` drops added notes (``Cadd9`` → C E G), the 7th of
  9 / 11 / 13 chords and of 7sus4 chords, gives ``Cm(maj7)`` a major 3rd and ``mM7`` a ♭7,
  gives ``C5`` a 3rd, and ignores a slash bass that is not a chord tone (``F/G``, ``G/F``).
- ``music_theory.classify_chord_quality`` classifies ``add9`` / ``add11`` chords as ``dom``.
- ``music_theory.chord_root_for_theory`` returns sharp roots for flat chords (A♭ → G♯).
- The MC1 harmonic-span analyzer and MC2/MC3 engines read chords through the same speller,
  so these affect Missions today (about 8% of catalog bars, 34 songs, for the speller gaps).

**Slash chords.** The bass always sounds: a ♭7 / major 7th bass is the chord's own 7th
(``G/F`` = G7); otherwise it is named as the bass, never the root. A bass a whole step above
the root (``F/G``, ``C/D``) or a 4th above a minor chord (``Gm7/C``) makes the chord function
as a suspended dominant on the bass; ``C/F`` functions as a major chord on F and ``Bb/G`` as a
minor chord on G (:attr:`ChordFacts.fn_root_pc` / :attr:`ChordFacts.fn_family`).

**Note categories** (per chord, never "right / wrong"):

- ``chord_tone`` — stable; land and hold.
- ``extension`` — written in the symbol (the 9 of ``Cadd9``); hold for colour.
- ``colour`` — a consonant unwritten extension (9th, 6th/13th …); can be held, softer.
- ``passing`` — fine while moving (weak beat, step, neighbour); rubs if held on a strong
  beat against a chord tone a half step away (e.g. the 4th over a major chord).
- ``tension`` — context-dependent colour (♭9 / ♯9 / ♯11 / ♭13 on dominants, blue notes in
  a blues): a stylistic choice that wants to resolve.
- ``clash`` — a strong rub if held; use only as a quick chromatic approach into the chord
  tone a half step away.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Sequence

CHORD_TONE = "chord_tone"
EXTENSION = "extension"
COLOUR = "colour"
PASSING = "passing"
TENSION = "tension"
CLASH = "clash"
CATEGORIES = (CHORD_TONE, EXTENSION, COLOUR, PASSING, TENSION, CLASH)
HOLDABLE = frozenset({CHORD_TONE, EXTENSION, COLOUR})

FAMILY_MAJOR = "major"
FAMILY_MINOR = "minor"
FAMILY_DOMINANT = "dominant"
FAMILY_HALF_DIM = "half-diminished"
FAMILY_DIM = "diminished"
FAMILY_AUG = "augmented"
FAMILY_SUS = "suspended"
FAMILY_POWER = "power"

BLUES_STYLES = frozenset({"blues"})
# Styles where an altered tension against the band's chord tone is idiomatic colour.
TENSION_STYLES = frozenset({"jazz", "jazz_ballad", "bossa", "blues", "funk"})

_LETTERS = "CDEFGAB"
_NATURAL_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_MAJOR_SCALE = (0, 2, 4, 5, 7, 9, 11)
_MINOR_SCALE = (0, 2, 3, 5, 7, 8, 10)

# interval → (role label, letter steps from the root)
_ROLE_SPELLING: dict[str, tuple[int, int]] = {
    "root": (0, 0), "♭9": (1, 1), "9th": (2, 1), "2nd": (2, 1), "♯9": (3, 1), "3rd": (4, 2),
    "minor 3rd": (3, 2), "4th": (5, 3), "11th": (5, 3), "♯11": (6, 3), "♭5": (6, 4), "5th": (7, 4),
    "♯5": (8, 4), "♭13": (8, 5), "♭6": (8, 5), "6th": (9, 5), "13th": (9, 5), "°7th": (9, 6),
    "7th": (10, 6), "major 7th": (11, 6),
}
# Engine role names used by span_motif_engine.voice_leading_cost.
ENGINE_ROLE = {"root": "R", "3rd": "3", "minor 3rd": "3", "5th": "5", "♭5": "5", "♯5": "5",
               "7th": "7", "major 7th": "7", "°7th": "7", "6th": "6"}


def _clean(text: Any) -> str:
    return str(text or "").strip()


def pc_of(name: str) -> int:
    from music_theory import pitch_class_from_spelled_note

    return int(pitch_class_from_spelled_note(name)) % 12


def spell_from_root(root: str, semitones: int, letter_steps: int) -> str:
    """Spell the note ``semitones`` above ``root`` on the letter ``letter_steps`` above it."""
    letter = root[0].upper()
    target_letter = _LETTERS[(_LETTERS.index(letter) + letter_steps) % 7]
    target_pc = (pc_of(root) + semitones) % 12
    delta = (target_pc - _NATURAL_PC[target_letter] + 6) % 12 - 6
    if abs(delta) > 1:
        return ""
    return target_letter + {-1: "b", 0: "", 1: "#"}[delta]


def _spell_on_letter(root: str, semitones: int, letter_steps: int) -> str:
    """Like :func:`spell_from_root`, but double accidentals are allowed (Cdim7's 7th is Bbb)."""
    letter = root[0].upper()
    target_letter = _LETTERS[(_LETTERS.index(letter) + letter_steps) % 7]
    delta = ((pc_of(root) + semitones) % 12 - _NATURAL_PC[target_letter] + 6) % 12 - 6
    return target_letter + {-2: "bb", -1: "b", 0: "", 1: "#", 2: "##"}.get(delta, "")


# --------------------------------------------------------------------------- key


@dataclass(frozen=True)
class KeyFacts:
    key: str
    tonic: str
    tonic_pc: int
    minor: bool
    scale_pcs: tuple[int, ...]
    in_key_pcs: frozenset[int]  # minor keys also admit the raised 7th (harmonic-minor V)

    def degree(self, pc: int) -> int:
        return (pc - self.tonic_pc) % 12

    def spell(self, pc: int) -> str:
        from music_theory import spell_note_in_key

        return spell_note_in_key(pc % 12, self.key)


@lru_cache(maxsize=256)
def key_facts(key: str) -> KeyFacts:
    from music_theory import split_key_center

    tonic, mode = split_key_center(_clean(key) or "C")
    minor = mode == "minor"
    tpc = pc_of(tonic)
    scale = tuple((tpc + s) % 12 for s in (_MINOR_SCALE if minor else _MAJOR_SCALE))
    in_key = set(scale)
    if minor:
        in_key.add((tpc + 11) % 12)
    return KeyFacts(_clean(key) or "C", tonic, tpc, minor, scale, frozenset(in_key))


# --------------------------------------------------------------------------- chords


@dataclass(frozen=True)
class Tone:
    pc: int
    name: str
    role: str
    kind: str  # chord_tone | extension

    @property
    def engine_role(self) -> str:
        return ENGINE_ROLE.get(self.role, self.role)


@dataclass(frozen=True)
class ChordFacts:
    symbol: str
    root: str
    root_pc: int
    bass: str
    family: str
    tones: tuple[Tone, ...]
    canonical_pcs: tuple[int, ...]
    canonical_quality: str
    canonical_agrees: bool
    reading_notes: tuple[str, ...] = field(default_factory=tuple)
    function_root_pc: int = -1  # the root the chord functions on (F/G → G); -1 = its own root
    function_family: str = ""

    @property
    def fn_root_pc(self) -> int:
        """Root for harmonic function (degrees, cadences, resolutions) — the bass of F/G."""
        return self.function_root_pc if self.function_root_pc >= 0 else self.root_pc

    @property
    def fn_family(self) -> str:
        return self.function_family or self.family

    @property
    def stable(self) -> tuple[Tone, ...]:
        return tuple(t for t in self.tones if t.kind == CHORD_TONE)

    @property
    def extensions(self) -> tuple[Tone, ...]:
        return tuple(t for t in self.tones if t.kind == EXTENSION)

    @property
    def stable_pcs(self) -> frozenset[int]:
        return frozenset(t.pc for t in self.stable)

    @property
    def charted_pcs(self) -> frozenset[int]:
        return frozenset(t.pc for t in self.tones)

    def tone(self, role: str) -> Tone | None:
        return next((t for t in self.tones if t.role == role), None)

    def tone_for_pc(self, pc: int) -> Tone | None:
        return next((t for t in self.tones if t.pc == pc % 12), None)

    @property
    def third(self) -> Tone | None:
        return self.tone("3rd") or self.tone("minor 3rd")

    @property
    def seventh(self) -> Tone | None:
        return self.tone("7th") or self.tone("major 7th") or self.tone("°7th")

    @property
    def has_third(self) -> bool:
        return self.third is not None


_EXT_RE = re.compile(r"(?<![b#\d])(13|11|9|7)")
_ALT_RE = re.compile(r"([b#])(5|9|11|13)")
_ADD_RE = re.compile(r"add(b|#)?(2|4|6|9|11|13)")


def _body(theory_symbol: str, root: str) -> tuple[str, str]:
    head, bass = theory_symbol, ""
    if "/" in theory_symbol:
        left, right = theory_symbol.rsplit("/", 1)
        if re.fullmatch(r"[A-G][#b]?", right.strip()):
            head, bass = left, right.strip()
    body = head[len(root):] if head.startswith(root) else head[1:].lstrip("#b")
    body = body.replace("♯", "#").replace("♭", "b").replace("Δ", "maj7").replace("ø", "m7b5")
    body = body.replace("°", "dim").replace("(", "").replace(")", "").replace(",", "").replace(" ", "")
    body = re.sub(r"Maj|MAJ", "maj", body)  # "CmMaj7" is a minor-major 7th, not Cmaj7
    body = re.sub(r"M(?=7|9|11|13)", "maj", body)
    body = re.sub(r"^(min|-)", "m", body)
    body = body.replace("mM7", "mmaj7")
    return body, bass


def _read_intervals(body: str) -> tuple[dict[int, str], dict[int, str], list[str]] | None:
    """Stable and extension intervals a symbol body states, or None when unreadable."""
    notes: list[str] = []
    b = body
    adds = _ADD_RE.findall(b)
    b = _ADD_RE.sub("", b)
    alts = _ALT_RE.findall(b)
    b6 = "6/9" in b or "69" in b
    b = _ALT_RE.sub("", b).replace("6/9", "6").replace("69", "6")
    power = b == "5"
    dim = b.startswith("dim") or b.startswith("o")
    half = b.startswith("m7b5") or (b.startswith("m7") and ("b", "5") in alts)
    aug = b.startswith("aug") or b.startswith("+")
    minor = (b.startswith("m") and not b.startswith("maj")) and not dim
    sus2 = "sus2" in b
    sus4 = ("sus" in b) and not sus2
    maj7 = "maj" in b
    alt = "alt" in b
    rest = re.sub(r"^(maj|mmaj|m|dim|o|aug|\+)", "", b).replace("sus4", "").replace("sus2", "").replace("sus", "")
    rest = rest.replace("maj", "").replace("alt", "")
    if re.search(r"[^0-9/]", rest):
        return None
    nums = [int(n) for n in _EXT_RE.findall(rest)]
    six = bool(re.search(r"(?<![b#\d])6", rest)) or b6
    top = max(nums) if nums else 0
    stable: dict[int, str] = {0: "root"}
    ext: dict[int, str] = {}
    if power:
        stable[7] = "5th"
        return stable, ext, ["power chord: root and 5th only"]
    if sus2:
        stable[2] = "2nd"
    elif sus4:
        stable[5] = "4th"
    elif minor or dim or half:
        stable[3] = "minor 3rd"
    else:
        stable[4] = "3rd"
    fifth = 6 if (dim or half) else 8 if aug else 7
    for sign, num in alts:
        if num == "5":
            fifth = 6 if sign == "b" else 8
    stable[fifth] = {6: "♭5", 7: "5th", 8: "♯5"}[fifth]
    if six:
        stable[9] = "6th"
    if dim and ("7" in rest or top >= 7):
        stable[9] = "°7th"
    elif maj7:
        stable[11] = "major 7th"
    elif top >= 7 or alt or (sus4 and top):
        stable[10] = "7th"
    if top >= 9:
        ext[2] = "9th"
    if top >= 11 and (minor or sus4 or top == 11):
        if 4 not in stable:
            ext[5] = "11th"
    if top >= 13:
        ext[9] = "13th"
    if b6 and 2 not in ext:
        ext[2] = "9th"
    for sign, num in alts:
        if num == "9":
            ext[1 if sign == "b" else 3] = "♭9" if sign == "b" else "♯9"
        elif num == "11":
            ext[6 if sign == "#" else 4] = "♯11" if sign == "#" else "11th"
        elif num == "13":
            ext[8 if sign == "b" else 9] = "♭13" if sign == "b" else "13th"
    if alt:
        ext.update({1: "♭9", 3: "♯9", 8: "♭13"})
    for sign, num in adds:
        iv = {"2": 2, "9": 2, "4": 5, "11": 5, "6": 9, "13": 9}[num] + (1 if sign == "#" else -1 if sign == "b" else 0)
        ext[iv % 12] = {2: "9th", 5: "11th", 9: "6th", 1: "♭9", 3: "♯9", 6: "♯11", 8: "♭13"}.get(iv % 12, "added")
    for iv in list(ext):
        if iv in stable:
            ext.pop(iv)
    return stable, ext, notes


def _family(stable: set[int]) -> str:
    if stable == {0, 7}:
        return FAMILY_POWER
    if 4 in stable and 10 in stable:
        return FAMILY_DOMINANT
    if 3 in stable and 6 in stable:
        return FAMILY_HALF_DIM if 10 in stable else FAMILY_DIM
    if 4 in stable and 8 in stable and 7 not in stable:
        return FAMILY_AUG
    if 3 in stable:
        return FAMILY_MINOR
    if 4 in stable:
        return FAMILY_MAJOR
    return FAMILY_SUS


@lru_cache(maxsize=4096)
def chord_facts(symbol: str) -> ChordFacts | None:
    """What the chord symbol contains (concert pitch); None for ``N.C.`` / unreadable roots."""
    from chord_subdivisions import hit_underlying_chord
    from music_theory import (
        chord_root_for_theory,
        classify_chord_quality,
        normalize_chord_for_theory,
        spell_chord_tones,
    )

    theory = normalize_chord_for_theory(hit_underlying_chord(_clean(symbol)))
    if not theory or theory.upper().startswith("N.C") or theory.upper() == "NC":
        return None
    root = chord_root_for_theory(theory)
    if not root or root[0].upper() not in _LETTERS:
        return None
    root_pc = pc_of(root)
    canon_names = [n for n in spell_chord_tones(theory) if n]
    # Keep the chart's own root spelling (Ab, not G#) for every interval spelled from it.
    written = re.match(r"[A-G][#b]?", theory)
    if written and pc_of(written.group(0)) == root_pc:
        root = written.group(0)
    canon = {(pc_of(n) - root_pc) % 12: n for n in canon_names}
    canonical_quality = _clean(classify_chord_quality(theory))
    body, bass = _body(theory, root)
    read = _read_intervals(body)
    notes: list[str] = []
    if read is None:
        stable = {iv: "" for iv in canon}
        ext: dict[int, str] = {}
        notes.append("symbol not fully readable — canonical chord tones used")
    else:
        stable, ext, notes = read[0], read[1], list(read[2])
        for iv in canon:
            if iv not in stable and iv not in ext and not _documented_drop(iv, stable):
                stable[iv] = ""
    fn_root, fn_family = -1, ""
    bass_tone: Tone | None = None
    if bass:
        biv = (pc_of(bass) - root_pc) % 12
        if biv not in stable and biv not in ext:
            # A bass note outside the chord sounds with it. A ♭7 / major 7th in the bass is the
            # chord's own 7th (G/F = G7); otherwise it is named as the bass, never as the root.
            # Named as the 7th only when the chart's bass spelling sits on the 7th's letter
            # (G7/F); a respelled chart (G#/G) keeps its bass name and is called the bass.
            on_letter = spell_from_root(root, biv, 6)[:1] == bass[:1]
            if biv == 10 and 11 not in stable:
                stable[10] = "7th" if on_letter else "bass"
                notes.append(f"bass {bass} is the chord's 7th")
            elif biv == 11 and 10 not in stable:
                stable[11] = "major 7th" if on_letter else "bass"
                notes.append(f"bass {bass} is the chord's major 7th")
            else:
                bass_tone = Tone(pc=pc_of(bass), name=bass, role="bass", kind=CHORD_TONE)
                triad = set(stable)
                if biv == 2 or (biv == 5 and 3 in triad):
                    fn_root, fn_family = pc_of(bass), FAMILY_SUS  # F/G, Gm7/C: a suspended dominant on the bass
                elif biv == 5:
                    fn_root, fn_family = pc_of(bass), FAMILY_MAJOR  # C/F: a major-7th-type chord on the bass
                elif biv == 9:
                    fn_root, fn_family = pc_of(bass), FAMILY_MINOR  # Bb/G: a minor-7th-type chord on the bass
                if fn_root >= 0:
                    notes.append(f"functions on its bass note {bass}")
    tones: list[Tone] = []
    for iv, role in sorted(stable.items()):
        if role == "bass":
            tones.append(Tone(pc=(root_pc + iv) % 12, name=bass, role="bass", kind=CHORD_TONE))
            continue
        tones.append(_tone(root, root_pc, iv, role or _default_role(iv, stable), CHORD_TONE, canon))
    if bass_tone is not None:
        tones.append(bass_tone)
    for iv, role in sorted(ext.items()):
        tones.append(_tone(root, root_pc, iv, role, EXTENSION, canon))
    stable_set = set(stable)
    family = _family(stable_set)
    canon_set = set(canon)
    agrees = canon_set == stable_set and not ext
    if not agrees:
        missing = sorted(stable_set - canon_set) + sorted(ext)
        if missing:
            notes.append("symbol adds " + ", ".join(_tone_label(tones, iv) for iv in missing))
        dropped = sorted(canon_set - stable_set - set(ext))
        if dropped:
            notes.append("corrected " + ", ".join(canon[iv] for iv in dropped))
    if family == FAMILY_MAJOR and canonical_quality == "dom":
        notes.append("not a dominant chord (no ♭7)")
    return ChordFacts(
        symbol=theory,
        root=root,
        root_pc=root_pc,
        bass=bass,
        family=family,
        tones=tuple(tones),
        canonical_pcs=tuple(sorted((root_pc + iv) % 12 for iv in canon)),
        canonical_quality=canonical_quality,
        canonical_agrees=agrees and bass_tone is None,
        reading_notes=tuple(notes),
        function_root_pc=fn_root,
        function_family=fn_family,
    )


def _documented_drop(iv: int, stable: dict[int, str]) -> bool:
    """Canonical tones the symbol explicitly rules out (power / sus / minor-major 3rd)."""
    if iv in (3, 4) and not any(k in stable for k in (3, 4)):
        return True  # power or sus chord: no 3rd
    if iv == 4 and 3 in stable:
        return True  # m(maj7): canonical speller gives a major 3rd
    if iv == 10 and 11 in stable:
        return True  # mM7 / m(M7): canonical speller gives a ♭7 where the symbol writes a major 7th
    return False


def _default_role(iv: int, stable: dict[int, str]) -> str:
    return {0: "root", 3: "minor 3rd", 4: "3rd", 6: "♭5", 7: "5th", 8: "♯5", 9: "6th", 10: "7th", 11: "major 7th",
            2: "2nd", 5: "4th", 1: "♭9"}.get(iv, "added")


def _tone(root: str, root_pc: int, iv: int, role: str, kind: str, canon: dict[int, str]) -> Tone:
    pc = (root_pc + iv) % 12
    name = canon.get(iv) or ""
    steps = _ROLE_SPELLING.get(role, (iv, None))[1]
    if steps is not None:
        # Every tone sits on its own letter. The canonical speller simplifies double
        # accidentals (Cdim7's 7th Bbb -> A); that hides the interval, so respell it.
        on_letter = _spell_on_letter(root, iv, steps)
        if on_letter and (not name or name[0].upper() != on_letter[0]):
            name = on_letter
    if not name:
        from music_theory import spell_pitch_class

        name = spell_pitch_class(pc, mode="flat" if "b" in root[1:] else "sharp")
    return Tone(pc=pc, name=name, role=role, kind=kind)


def _tone_label(tones: Sequence[Tone], iv: int) -> str:
    for t in tones:
        if t.role and t.role not in ("root",) and (t.pc - tones[0].pc) % 12 == iv:
            return f"{t.name} ({t.role})"
    return str(iv)


# --------------------------------------------------------------------------- notes against a chord


@dataclass(frozen=True)
class NoteUse:
    pc: int
    name: str
    role: str
    category: str


def _relative_role(facts: ChordFacts, iv: int) -> tuple[str, int]:
    fam = facts.family
    table = {
        1: ("♭9", 1), 2: ("9th", 1), 3: ("♯9", 1) if fam in (FAMILY_DOMINANT, FAMILY_MAJOR) else ("minor 3rd", 2),
        4: ("3rd", 2), 5: ("11th", 3), 6: ("♭5", 4) if fam in (FAMILY_DIM, FAMILY_HALF_DIM) else ("♯11", 3),
        7: ("5th", 4), 8: ("♭13", 5) if fam == FAMILY_DOMINANT else ("♭6", 5), 9: ("13th", 5) if fam == FAMILY_DOMINANT else ("6th", 5),
        10: ("7th", 6) if fam != FAMILY_MAJOR else ("♭7", 6), 11: ("major 7th", 6), 0: ("root", 0),
    }
    return table[iv]


def note_use(facts: ChordFacts, pc: int, *, key: str, style: str = "default") -> NoteUse:
    """How a pitch class behaves against this chord (see the module docstring)."""
    pc %= 12
    tone = facts.tone_for_pc(pc)
    if tone is not None:
        return NoteUse(pc, tone.name, tone.role, CHORD_TONE if tone.kind == CHORD_TONE else EXTENSION)
    iv = (pc - facts.root_pc) % 12
    role, steps = _relative_role(facts, iv)
    name = spell_from_root(facts.root, iv, steps) or key_facts(key).spell(pc)
    return NoteUse(pc, name, role, _category(facts, iv, pc, key=key, style=style))


def _category(facts: ChordFacts, iv: int, pc: int, *, key: str, style: str) -> str:
    fam = facts.family
    stable = {(t.pc - facts.root_pc) % 12 for t in facts.stable}
    kf = key_facts(key)
    in_key = pc in kf.in_key_pcs
    blues = style in BLUES_STYLES
    near_stable = any((iv - s) % 12 in (1, 11) for s in stable)
    if fam == FAMILY_MAJOR:
        if iv in (2, 9):
            return COLOUR
        if iv == 11:
            return COLOUR if 10 not in stable else CLASH
        if iv == 6:
            return TENSION
        if iv == 5:
            return PASSING
        if iv == 3 and blues:
            return TENSION
        if iv == 10:
            return TENSION if (blues or not in_key) else PASSING
    elif fam == FAMILY_MINOR:
        if iv in (2, 5):
            return COLOUR
        if iv == 10:
            return COLOUR
        if iv == 9:
            return COLOUR if in_key else TENSION
        if iv == 8:
            return PASSING if in_key else CLASH
        if iv == 11:
            return TENSION
        if iv == 6 and blues:
            return TENSION
    elif fam == FAMILY_DOMINANT:
        if iv in (2, 9):
            return COLOUR
        if iv in (1, 3, 6, 8):
            return TENSION
        if iv == 5:
            return PASSING
        if iv == 11:
            return CLASH  # a major 7th against the chord's own ♭7
    elif fam == FAMILY_HALF_DIM:
        if iv in (5, 8):
            return COLOUR
        if iv == 2:
            return TENSION
        if iv == 1:
            return PASSING
    elif fam == FAMILY_DIM:
        if iv in (2, 5, 8, 11):
            return TENSION
    elif fam == FAMILY_AUG:
        if iv == 2:
            return COLOUR
        if iv in (6, 10):
            return TENSION
    elif fam == FAMILY_SUS:
        if iv in (2, 5, 9):
            return COLOUR
        if iv == 10:
            return COLOUR
        if iv == 4:
            return PASSING  # the 3rd the suspension resolves to
    elif fam == FAMILY_POWER:
        if iv in (2, 3, 4, 5, 9, 10):
            return COLOUR
    if in_key and not near_stable:
        return COLOUR
    if in_key:
        return PASSING
    return CLASH


def chord_palette(facts: ChordFacts, *, key: str, style: str = "default") -> tuple[NoteUse, ...]:
    """All twelve pitch classes against the chord, ordered from the root."""
    return tuple(note_use(facts, (facts.root_pc + iv) % 12, key=key, style=style) for iv in range(12))


def outside_tones(facts: ChordFacts, *, key: str) -> tuple[Tone, ...]:
    """Chord tones that are not in the key — what makes an out-of-key chord sound different."""
    kf = key_facts(key)
    return tuple(t for t in facts.stable if t.pc not in kf.in_key_pcs)


# --------------------------------------------------------------------------- collections


@dataclass(frozen=True)
class CollectionFit:
    chord: str
    verdict: str  # fits | fits_with_care | clashes
    clash: tuple[NoteUse, ...]
    passing: tuple[NoteUse, ...]
    tension: tuple[NoteUse, ...]  # a tension a half step from the chord's 3rd
    missing_third: str  # the chord's 3rd when the collection lacks it
    chord_tones_in: int


@dataclass(frozen=True)
class CollectionCheck:
    name: str
    pcs: tuple[int, ...]
    names: tuple[str, ...]
    verdict: str
    fits: tuple[CollectionFit, ...]

    @property
    def usable(self) -> bool:
        return self.verdict in ("fits", "fits_with_care")


def check_collection(
    name: str, pcs: Sequence[int], chords: Sequence[ChordFacts], *, key: str, style: str = "default"
) -> CollectionCheck:
    """Judge one note collection against every chord it is meant to cover.

    ``fits``: no note clashes with any chord and every chord keeps at least two of its
    chord tones. ``fits_with_care``: no clash, but some chord is thinly covered (e.g. its
    3rd is missing — usable, with that chord tone added when the chord arrives).
    ``clashes``: some note rubs strongly against a chord if held. A tension a half step from
    the chord's 3rd (G over E7, against its G♯ — it contradicts the chord's quality) counts as
    a clash outside :data:`TENSION_STYLES`; in those styles it is ``fits_with_care``.
    """
    kf = key_facts(key)
    uniq = tuple(dict.fromkeys(p % 12 for p in pcs))
    fits: list[CollectionFit] = []
    for facts in chords:
        uses = [note_use(facts, p, key=key, style=style) for p in uniq]
        clash = tuple(u for u in uses if u.category == CLASH)
        passing = tuple(u for u in uses if u.category == PASSING)
        third = facts.third
        tension = tuple(
            u for u in uses
            if u.category == TENSION and third is not None and abs(signed_motion(u.pc, third.pc)) == 1
        )
        if tension and style not in TENSION_STYLES:
            clash, tension = clash + tension, ()
        tones_in = sum(1 for u in uses if u.category == CHORD_TONE)
        third = facts.third
        missing_third = third.name if third is not None and third.pc not in uniq else ""
        if clash:
            verdict = "clashes"
        elif tones_in >= 2 and not missing_third and not tension:
            verdict = "fits"
        else:
            verdict = "fits_with_care"
        fits.append(CollectionFit(facts.symbol, verdict, clash, passing, tension, missing_third, tones_in))
    order = {"fits": 0, "fits_with_care": 1, "clashes": 2}
    overall = max((f.verdict for f in fits), key=order.get, default="fits")
    names = tuple(kf.spell(p) for p in uniq)
    return CollectionCheck(name, uniq, names, overall, tuple(fits))


def key_pentatonic(key: str) -> tuple[str, tuple[int, ...]]:
    kf = key_facts(key)
    steps = (0, 3, 5, 7, 10) if kf.minor else (0, 2, 4, 7, 9)
    label = f"{kf.tonic} {'minor' if kf.minor else 'major'} pentatonic"
    return label, tuple((kf.tonic_pc + s) % 12 for s in steps)


def key_scale(key: str) -> tuple[str, tuple[int, ...]]:
    kf = key_facts(key)
    return f"{kf.tonic} {'natural minor' if kf.minor else 'major'} scale", kf.scale_pcs


# --------------------------------------------------------------------------- connections


@dataclass(frozen=True)
class Move:
    from_tone: Tone
    to_tone: Tone
    semitones: int  # signed, smallest motion
    cost: float

    @property
    def common(self) -> bool:
        return self.semitones == 0

    @property
    def guide_resolution(self) -> bool:
        return self.from_tone.engine_role == "7" and self.to_tone.engine_role == "3" and -2 <= self.semitones < 0


@dataclass(frozen=True)
class Change:
    """Facts about moving from one chord to the next."""

    a: ChordFacts
    b: ChordFacts
    at_bar: int
    common: tuple[Move, ...]
    moves: tuple[Move, ...]  # best move for each stable tone of a, smoothest first

    @property
    def best(self) -> tuple[Move, ...]:
        return self.moves[:2]


def signed_motion(a_pc: int, b_pc: int) -> int:
    d = (b_pc - a_pc) % 12
    return d if d <= 6 else d - 12


def move_cost(from_tone: Tone, to_tone: Tone) -> float:
    from span_motif_engine import voice_leading_cost

    prev = 60 + from_tone.pc
    cur = prev + signed_motion(from_tone.pc, to_tone.pc)
    return float(voice_leading_cost(prev, from_tone.engine_role, cur, to_tone.engine_role, None))


def change_facts(a: ChordFacts, b: ChordFacts, *, at_bar: int, roles: Sequence[str] | None = None) -> Change:
    """Common tones and the smoothest stable-tone moves from ``a`` into ``b``."""
    targets = [t for t in b.stable if roles is None or t.engine_role in roles or t.role in roles] or list(b.stable)
    sources = [t for t in a.stable if roles is None or t.engine_role in roles or t.role in roles] or list(a.stable)
    best: list[Move] = []
    for src in sources:
        options = [Move(src, dst, signed_motion(src.pc, dst.pc), move_cost(src, dst)) for dst in targets]
        options.sort(key=lambda m: (m.cost, abs(m.semitones), m.to_tone.pc))
        best.append(options[0])
    best.sort(key=lambda m: (m.cost, abs(m.semitones), m.from_tone.pc))
    common = tuple(m for m in best if m.common)
    return Change(a=a, b=b, at_bar=at_bar, common=common, moves=tuple(best))


def anchor_line(
    chords: Sequence[ChordFacts], *, roles: Sequence[str], end_roles: Sequence[str] | None = None,
    start_roles: Sequence[str] | None = None,
) -> list[Tone]:
    """One landing tone per chord forming the smoothest connected line (voice-leading cost)."""
    if not chords:
        return []

    def candidates(i: int) -> list[Tone]:
        want = roles
        if i == 0 and start_roles:
            want = start_roles
        if i == len(chords) - 1 and end_roles:
            want = end_roles
        pool = [t for t in chords[i].tones if t.engine_role in want or t.role in want]
        return pool or list(chords[i].stable)

    layers = [candidates(i) for i in range(len(chords))]
    best: list[dict[int, tuple[float, list[Tone]]]] = [{k: (0.0, [t]) for k, t in enumerate(layers[0])}]
    for i in range(1, len(layers)):
        cur: dict[int, tuple[float, list[Tone]]] = {}
        for k, tone in enumerate(layers[i]):
            options = [
                (cost + move_cost(path[-1], tone), path + [tone]) for cost, path in best[-1].values()
            ]
            cur[k] = min(options, key=lambda o: (round(o[0], 6), [t.pc for t in o[1]]))
        best.append(cur)
    return min(best[-1].values(), key=lambda o: (round(o[0], 6), [t.pc for t in o[1]]))[1]


# --------------------------------------------------------------------------- endings

ENDING_AUTHENTIC = "authentic_cadence"
ENDING_PLAGAL = "plagal_cadence"
ENDING_HOME = "lands_home"
ENDING_HOME_COLOUR = "home_note_colour"  # on the tonic root, but not the home chord (Dsus2 in D minor)
ENDING_HALF = "open_on_dominant"
ENDING_DECEPTIVE = "deceptive"
ENDING_LEADS_ON = "leads_into_next"
ENDING_LOOPS = "loops_back"
ENDING_MID = "mid_section"
ENDING_OPEN = "open"
CADENCE_ENDINGS = frozenset({ENDING_AUTHENTIC, ENDING_PLAGAL, ENDING_HALF, ENDING_DECEPTIVE})


@dataclass(frozen=True)
class Ending:
    kind: str
    last: str
    previous: str = ""
    following: str = ""

    @property
    def resolves(self) -> bool:
        return self.kind in (ENDING_AUTHENTIC, ENDING_PLAGAL, ENDING_HOME)

    @property
    def is_cadence(self) -> bool:
        return self.kind in CADENCE_ENDINGS


def _is_home(f: ChordFacts, kf: KeyFacts) -> bool:
    if f.fn_root_pc != kf.tonic_pc:
        return False
    if kf.minor:
        return f.fn_family == FAMILY_MINOR
    return f.fn_family == FAMILY_MAJOR


def _resolves_to(dominant: ChordFacts, target: ChordFacts) -> bool:
    """A dominant-family chord moving down a 5th, or a half step (tritone substitute)."""
    if dominant.fn_family != FAMILY_DOMINANT:
        return False
    drop = (dominant.fn_root_pc - target.fn_root_pc) % 12
    return drop in (7, 1)


def classify_ending(
    chords: Sequence[ChordFacts], *, key: str, following: ChordFacts | None, loops: bool, whole_section: bool
) -> Ending:
    """How the selection ends — a cadence only when the chords support it."""
    kf = key_facts(key)
    if not chords:
        return Ending(ENDING_OPEN, "")
    last = chords[-1]
    prev = chords[-2] if len(chords) > 1 else None
    fol = following.symbol if following is not None else ""
    pv = prev.symbol if prev is not None else ""
    if _is_home(last, kf):
        if prev is not None:
            prev_deg = kf.degree(prev.fn_root_pc)
            if prev_deg == 7 and prev.fn_family in (FAMILY_MAJOR, FAMILY_DOMINANT, FAMILY_SUS) or (
                prev_deg == 11 and prev.fn_family in (FAMILY_DIM, FAMILY_HALF_DIM)
            ) or (prev_deg == 1 and prev.fn_family == FAMILY_DOMINANT):
                return Ending(ENDING_AUTHENTIC, last.symbol, pv, fol)
            if prev_deg == 5 and prev.fn_family in (FAMILY_MAJOR, FAMILY_MINOR):
                return Ending(ENDING_PLAGAL, last.symbol, pv, fol)
        return Ending(ENDING_HOME, last.symbol, pv, fol)
    last_deg = kf.degree(last.fn_root_pc)
    if last_deg == 0:
        return Ending(ENDING_HOME_COLOUR, last.symbol, pv, fol)
    if last_deg == 7 and last.fn_family in (FAMILY_MAJOR, FAMILY_DOMINANT, FAMILY_SUS, FAMILY_POWER):
        return Ending(ENDING_HALF, last.symbol, pv, fol)
    if (
        prev is not None
        and prev.fn_family == FAMILY_DOMINANT
        and kf.degree(prev.fn_root_pc) == 7
        and last_deg == (8 if kf.minor else 9)
    ):
        return Ending(ENDING_DECEPTIVE, last.symbol, pv, fol)
    if following is not None and (_resolves_to(last, following) or not whole_section):
        return Ending(ENDING_LEADS_ON if whole_section else ENDING_MID, last.symbol, pv, fol)
    if loops:
        return Ending(ENDING_LOOPS, last.symbol, pv, fol)
    if not whole_section:
        return Ending(ENDING_MID, last.symbol, pv, fol)
    return Ending(ENDING_OPEN, last.symbol, pv, fol)


# --------------------------------------------------------------------------- section profile

RHYTHM_SLOW = "slow"
RHYTHM_STEADY = "steady"
RHYTHM_QUICK = "quick"


@dataclass(frozen=True)
class SectionProfile:
    bars: int
    changes: int
    distinct: int
    harmonic_rhythm: str
    bars_per_change: float
    loops: bool
    cycle: tuple[str, ...]
    ending: Ending
    out_of_key: tuple[str, ...]  # chord symbols with a note outside the key
    has_dominant: bool
    has_sus: bool
    has_no_chord: bool
    exact_timing: bool
    vamp: bool


def section_profile(scope: Any, *, key: str, following: str = "") -> SectionProfile:
    events = [e for e in scope.events if not e.no_chord]
    facts = [chord_facts(e.chord) for e in events]
    facts = [f for f in facts if f is not None]
    bpb = float(scope.beats_per_bar or 4.0)
    per_change = (sum(e.beats for e in events) / len(events) / bpb) if events else 0.0
    rhythm = RHYTHM_SLOW if per_change >= 2 else RHYTHM_STEADY if per_change >= 1 else RHYTHM_QUICK
    distinct = len({f.symbol for f in facts})
    loops = bool(scope.rhythm.cycle)
    fol = chord_facts(following) if following else None
    ending = classify_ending(facts, key=key, following=fol, loops=loops, whole_section=scope.whole_section)
    out = tuple(dict.fromkeys(f.symbol for f in facts if outside_tones(f, key=key)))
    return SectionProfile(
        bars=scope.bar_count,
        changes=len(events),
        distinct=distinct,
        harmonic_rhythm=rhythm,
        bars_per_change=round(per_change, 3),
        loops=loops,
        cycle=tuple(scope.rhythm.cycle),
        ending=ending,
        out_of_key=out,
        has_dominant=any(f.fn_family == FAMILY_DOMINANT for f in facts),
        has_sus=any(f.fn_family == FAMILY_SUS for f in facts),
        has_no_chord=scope.rhythm.has_no_chord,
        exact_timing=all(link.exact_bar_timing for link in scope.chain),
        vamp=distinct == 1,
    )


__all__ = [
    "CADENCE_ENDINGS",
    "CATEGORIES",
    "CHORD_TONE",
    "CLASH",
    "COLOUR",
    "Change",
    "ChordFacts",
    "CollectionCheck",
    "CollectionFit",
    "ENDING_AUTHENTIC",
    "ENDING_DECEPTIVE",
    "ENDING_HALF",
    "ENDING_HOME",
    "ENDING_HOME_COLOUR",
    "ENDING_LEADS_ON",
    "ENDING_LOOPS",
    "ENDING_MID",
    "ENDING_OPEN",
    "ENDING_PLAGAL",
    "EXTENSION",
    "Ending",
    "FAMILY_AUG",
    "FAMILY_DIM",
    "FAMILY_DOMINANT",
    "FAMILY_HALF_DIM",
    "FAMILY_MAJOR",
    "FAMILY_MINOR",
    "FAMILY_POWER",
    "FAMILY_SUS",
    "HOLDABLE",
    "KeyFacts",
    "Move",
    "NoteUse",
    "PASSING",
    "RHYTHM_QUICK",
    "RHYTHM_SLOW",
    "RHYTHM_STEADY",
    "SectionProfile",
    "TENSION",
    "TENSION_STYLES",
    "Tone",
    "anchor_line",
    "change_facts",
    "check_collection",
    "chord_facts",
    "chord_palette",
    "classify_ending",
    "key_facts",
    "key_pentatonic",
    "key_scale",
    "move_cost",
    "note_use",
    "outside_tones",
    "pc_of",
    "section_profile",
    "signed_motion",
    "spell_from_root",
]
