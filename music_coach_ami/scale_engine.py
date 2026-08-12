"""Deterministic scale spelling, interval exercises, and ABC notation for AMI coach."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Tonic patterns — longer spellings first (weak fallback only)
_TONIC_RE = re.compile(
    r"\b(Eb|Ab|Bb|Db|Gb|F#|C#|G#|D#|A#|[A-Ga-g])(?![A-Za-z#])"
)

_TONIC_SPELLING = (
    r"(?:Eb|Ab|Bb|Db|Gb|F#|C#|G#|D#|A#|[A-G](?:#|b|♭|♯)?)"
)

_SCALE_TYPE_PHRASE = (
    r"(?:(?:natural|harmonic|melodic)\s+)?(?:major|minor)"
)

# `[tonic] major/minor` with optional English article/determiner (not pitch A)
_SCALE_PHRASE_RE = re.compile(
    rf"(?:\b(?:give|show|write|play)\s+me\s+)?(?:the\s+|an?\s+)?"
    rf"({_TONIC_SPELLING})\s+{_SCALE_TYPE_PHRASE}\b",
    re.I,
)

_SCALE_PHRASE_WITH_SCALE_WORD_RE = re.compile(
    rf"\b({_TONIC_SPELLING})\s+{_SCALE_TYPE_PHRASE}\s+scale\b",
    re.I,
)

_OCTAVES_OF_RE = re.compile(
    rf"\b(?:one|two|three|\d+)\s+octaves?\s+of\s+({_TONIC_SPELLING})\s+{_SCALE_TYPE_PHRASE}\b",
    re.I,
)

_BARE_SCALE_PHRASE_RE = re.compile(
    rf"\b({_TONIC_SPELLING})\s+{_SCALE_TYPE_PHRASE}\b",
    re.I,
)

_TONIC_MULTIWORD = r"[A-Ga-g]\s+(?:flat|b|♭|sharp|#|♯)"

_MODE_NAMES = r"(?:dorian|mixolydian|lydian|locrian|phrygian)"

_MODE_SCALE_PHRASE_RE = re.compile(
    rf"\b(?P<tonic>{_TONIC_SPELLING}|{_TONIC_MULTIWORD})\s+"
    rf"(?:(?:natural|harmonic|melodic)\s+)?(?:minor\s+)?"
    rf"(?P<mode>{_MODE_NAMES})(?:\s+scale)?\b",
    re.I,
)

_MODE_OCTAVES_OF_RE = re.compile(
    rf"\b(?:one|two|three|\d+)\s+octaves?\s+of\s+"
    rf"(?P<tonic>{_TONIC_SPELLING}|{_TONIC_MULTIWORD})\s+"
    rf"(?:(?:natural|harmonic|melodic)\s+)?(?:minor\s+)?"
    rf"(?P<mode>{_MODE_NAMES})\b",
    re.I,
)

_INTERVAL_STEPS: dict[str, int] = {
    "unison": 0,
    "straight": 0,
    "scale": 0,
    "thirds": 2,
    "third": 2,
    "fourths": 3,
    "fourth": 3,
    "fifths": 4,
    "fifth": 4,
    "sixths": 5,
    "sixth": 5,
    "sevenths": 6,
    "seventh": 6,
}

_ALL_INTERVAL_LABELS = ("thirds", "fourths", "fifths", "sixths", "sevenths")


@dataclass
class ScalePracticeSpec:
    tonic: str = "C"
    preferred_spelling: str = ""
    scale_type: str = "major"
    interval_patterns: tuple[str, ...] = ("straight",)
    octave_count: int = 2
    octave_count_explicit: bool = False
    direction: str = "ascending"  # ascending | descending | both
    note_value: str = "quarter"
    note_value_explicit: bool = False
    rhythm_triplet: bool = False
    meter: str = "4/4"
    meter_explicit: bool = False
    articulation: str = ""
    instrument: str = ""
    tempo_bpm: int | None = None
    start_octave: int | None = None
    wants_measures: bool = False
    tonic_provenance: str = ""
    exercise_pattern: str = "straight"
    pattern_id: str = ""
    pattern_degree_formula: str = ""
    requested_difficulty: bool = False
    resolved_difficulty: str = ""
    player_level: str = ""
    practice_focus: str = ""
    pedagogical_goal: str = ""
    wants_structured_exercise: bool = False
    selection_reason: str = ""


@dataclass
class ScalePracticeResult:
    label: str
    display_label: str
    tonic: str
    scale_type: str
    reference_key: str
    scale_degrees: list[str]
    scale_notes: list[str]
    practice_sequence: list[str]
    exercise_note_names: list[str]
    abc_key: str = ""
    interval_pairs: list[tuple[str, str]] = field(default_factory=list)
    abc: str = ""
    notation_sections: list[str] = field(default_factory=list)
    written_sequence: str = ""
    scale_reference: str = ""
    scale_reference_descending: str = ""
    interval_pairs_display: str = ""
    interval_pairs_display_descending: str = ""
    key_signature_hint: str = ""
    practice_guidance: list[str] = field(default_factory=list)
    what_to_listen_for: list[str] = field(default_factory=list)
    chosen_start_octave: int = 4


def _normalize_tonic(raw: str) -> str:
    t = str(raw or "C").strip()
    if len(t) == 1:
        return t.upper()
    head = t[0].upper()
    tail = t[1:]
    if tail in ("#", "b"):
        return head + tail
    return head


def _preferred_tonic_spelling(raw: str, tonic_ascii: str) -> str:
    """Preserve Unicode ♭/♯ in display when the user typed them (same pitch as ASCII)."""
    letter = tonic_ascii[0].upper() if tonic_ascii else "C"
    raw_s = str(raw or "")
    if re.search(rf"{letter}\s+flat", raw_s, re.I) or re.search(rf"{letter}\s*♭", raw_s, re.I):
        return f"{letter}♭"
    if re.search(rf"{letter}\s+sharp", raw_s, re.I) or re.search(rf"{letter}\s*♯", raw_s, re.I):
        return f"{letter}♯"
    if len(tonic_ascii) > 1 and tonic_ascii[1] == "b" and "♭" in raw_s:
        return f"{letter}♭"
    if len(tonic_ascii) > 1 and tonic_ascii[1] == "#" and "♯" in raw_s:
        return f"{letter}♯"
    return tonic_ascii


def _parse_scale_type(text: str) -> str:
    low = text.lower()
    if "harmonic minor" in low:
        return "harmonic minor"
    if "melodic minor" in low:
        return "melodic minor"
    if "natural minor" in low:
        return "natural minor"
    if "major pentatonic" in low:
        return "major pentatonic"
    if "minor pentatonic" in low:
        return "minor pentatonic"
    if "blues" in low:
        return "blues"
    if "dorian" in low:
        return "dorian"
    if "mixolydian" in low:
        return "mixolydian"
    if "lydian" in low:
        return "lydian"
    if "phrygian" in low:
        return "locrian"
    if "locrian" in low:
        return "locrian"
    if re.search(r"\bminor\b", low) and "pentatonic" not in low:
        return "natural minor"
    return "major"


def _tonic_from_phrase_group(raw: str, full_text: str) -> str:
    token = str(raw or "").strip()
    if re.fullmatch(_TONIC_MULTIWORD, token, flags=re.I):
        letter = token[0].upper()
        if re.search(r"flat|b|♭", token, re.I):
            return f"{letter}b"
        if re.search(r"sharp|#|♯", token, re.I):
            return f"{letter}#"
    return _normalize_tonic(token)


def _wants_structured_exercise(text: str) -> bool:
    low = str(text or "").lower()
    if re.search(r"\b(pattern|exercise)\b", low):
        return True
    if re.search(r"\b(easy|medium|beginner|intermediate|difficult|hard|advanced)\b", low) and re.search(
        r"\b(dorian|mixolydian|lydian|locrian|phrygian|major|minor|scale|mode)\b", low
    ):
        return True
    if any(p in low for p in ("build tone", "for tone", "articulation", "finger technique", "short notes")):
        return True
    return False


def _parse_interval_patterns(text: str) -> tuple[str, ...]:
    low = text.lower()
    if any(p in low for p in ("all the interval", "interval exercises", "thirds, fourths", "thirds fourths")):
        return _ALL_INTERVAL_LABELS
    found: list[str] = []
    for label in _ALL_INTERVAL_LABELS:
        if label in low or label.rstrip("s") + "s" in low:
            found.append(label)
    if found:
        return tuple(found)
    if any(p in low for p in ("in thirds", "in 3rds")):
        return ("thirds",)
    if re.search(r"\bscale pattern\b", low):
        return ("four_note_sequence",)
    if re.search(r"\b(difficult|challenging|hard|advanced|hardest)\b", low) and re.search(
        r"\bexercise\b", low
    ):
        return ("four_note_sequence",)
    if re.search(r"\bpattern\b", low) and re.search(
        r"\b(difficult|challenging|hard|advanced)\b|\bexercise\b", low
    ):
        return ("four_note_sequence",)
    if "sheet music" in low or "scale" in low or "show me" in low or "give me" in low:
        return ("straight",)
    return ("straight",)


def _parse_octave_count(text: str) -> tuple[int, bool]:
    low = text.lower()
    if re.search(r"\b(one|1)\s+octave", low) or "just one octave" in low:
        return 1, True
    if re.search(r"\btwo\s+octaves?\b", low) or re.search(r"\b2\s+octaves?\b", low) or "over two octaves" in low:
        return 2, True
    if re.search(r"\bthree\s+octaves?\b", low) or re.search(r"\b3\s+octaves?\b", low):
        return 3, True
    return 2, False


def _parse_direction(text: str) -> str:
    low = text.lower()
    if any(
        p in low
        for p in (
            "ascending and descending",
            "ascending & descending",
            "up and down",
            "both directions",
        )
    ):
        return "both"
    if re.search(r"\bdescending only\b", low) or (
        "descending" in low and "ascending" not in low
    ):
        return "descending"
    return "ascending"


def _parse_note_value(text: str) -> tuple[str, bool, bool]:
    low = text.lower()
    triplet = any(p in low for p in ("triplet", "triplets", "triplet eighth", "eighth-note triplet"))
    explicit = False
    if any(p in low for p in ("sixteenth", "16th", "1/16")):
        explicit = True
        return "sixteenth", triplet, explicit
    if any(p in low for p in ("eighth", "8th", "1/8")) or "two notes per beat" in low:
        explicit = True
        return "eighth", triplet, explicit
    if any(p in low for p in ("half note", "half notes", "1/2")) or "one note per beat" in low and "two" not in low:
        explicit = True
        return "half", triplet, explicit
    if "four notes per beat" in low:
        explicit = True
        return "sixteenth", triplet, explicit
    if "quarter" in low or "1/4" in low:
        explicit = True
        return "quarter", triplet, explicit
    return "quarter", False, False


def _parse_meter(text: str) -> tuple[str, bool]:
    low = text.lower()
    m = re.search(r"\b(4/4|3/4|6/8|2/4|5/4)\b", low)
    if m:
        return m.group(1), True
    if "in 3/4" in low or "3/4 time" in low:
        return "3/4", True
    if "in 6/8" in low or "6/8 time" in low:
        return "6/8", True
    return "4/4", False


def _parse_wants_measures(text: str) -> bool:
    low = text.lower()
    return any(p in low for p in ("with measures", "with measure", "in measures", "barlines"))


def _parse_tonic(text: str, cleaned: str) -> tuple[str, str]:
    """Extract tonic from scale noun phrases before weak letter fallback."""
    blob = cleaned or text or ""
    for pattern, prov in (
        (_MODE_OCTAVES_OF_RE, "octaves_of_mode_phrase"),
        (_MODE_SCALE_PHRASE_RE, "mode_scale_phrase"),
        (_OCTAVES_OF_RE, "octaves_of_scale_phrase"),
        (_SCALE_PHRASE_WITH_SCALE_WORD_RE, "scale_phrase_with_scale_word"),
        (_SCALE_PHRASE_RE, "scale_phrase"),
    ):
        m = pattern.search(blob)
        if m:
            tonic_raw = m.groupdict().get("tonic") or m.group(1)
            return _tonic_from_phrase_group(tonic_raw, text), prov
    m = _BARE_SCALE_PHRASE_RE.search(blob)
    if m and not re.search(_MODE_NAMES, blob, re.I):
        return _tonic_from_phrase_group(m.group(1), text), "bare_scale_phrase"
    m = _TONIC_RE.search(blob)
    if m:
        return _normalize_tonic(m.group(1)), "standalone_letter_fallback"
    return "C", "default"


def _parse_articulation(text: str) -> str:
    low = text.lower()
    if re.search(r"\bmix\b", low) and ("slur" in low or "slurred" in low) and any(
        p in low for p in ("short", "staccato", "tongued", "articulated")
    ):
        return "slur2_short2"
    if "staccato" in low or "short notes" in low:
        if "slur" in low or "slurred" in low:
            return "slur2_short2"
    if "staccato" in low:
        return "staccato"
    if "two slurred two tongued" in low or "alternate slurred" in low:
        return "alternate_slur_tongue"
    if re.search(r"\bslur two\b", low) or re.search(r"\btwo slurred\b", low):
        if "two tongued" not in low:
            return "slur_two"
    if "slurred" in low or "legato" in low or re.search(r"\bslur(?:red)?\b", low):
        return "slurred"
    if any(p in low for p in ("tongued", "articulated", "tonguing")):
        return "tongued"
    return ""


def _parse_tempo_bpm(text: str) -> int | None:
    low = text.lower()
    tm = re.search(r"\b(\d{2,3})\s*bpm\b", low)
    if tm:
        return int(tm.group(1))
    tm2 = re.search(r"\bat\s+(\d{2,3})\b", low)
    if tm2:
        return int(tm2.group(1))
    return None


def spec_to_dev_dict(spec: ScalePracticeSpec, result: ScalePracticeResult | None = None) -> dict[str, object]:
    out: dict[str, object] = {
        "tonic": spec.tonic,
        "preferred_spelling": spec.preferred_spelling,
        "scale_type": spec.scale_type,
        "interval_patterns": list(spec.interval_patterns),
        "octave_count": spec.octave_count,
        "octave_count_explicit": spec.octave_count_explicit,
        "direction": spec.direction,
        "note_value": spec.note_value,
        "rhythm_triplet": spec.rhythm_triplet,
        "meter": spec.meter,
        "articulation": spec.articulation,
        "tempo_bpm": spec.tempo_bpm,
        "instrument": spec.instrument,
        "start_octave": spec.start_octave,
        "tonic_provenance": spec.tonic_provenance,
        "pattern_id": spec.pattern_id,
        "pattern_degree_formula": spec.pattern_degree_formula,
        "requested_difficulty": spec.requested_difficulty,
        "resolved_difficulty": spec.resolved_difficulty,
        "player_level": spec.player_level,
        "practice_focus": spec.practice_focus,
        "pedagogical_goal": spec.pedagogical_goal,
    }
    if result is not None:
        out["chosen_start_octave"] = result.chosen_start_octave
        out["abc_key"] = result.abc_key
    return out


def parse_scale_practice_question(text: str, *, instrument: str = "") -> ScalePracticeSpec:
    raw_text = str(text or "")
    cleaned = raw_text
    try:
        from music_coach_ami.entities import normalize_musical_accidentals

        cleaned = normalize_musical_accidentals(cleaned)
    except ImportError:
        cleaned = cleaned.replace("♭", "b").replace("♯", "#")
    low = cleaned.lower()
    tonic, tonic_prov = _parse_tonic(text, cleaned)
    preferred = _preferred_tonic_spelling(raw_text, tonic)
    scale_type = _parse_scale_type(text)
    patterns = _parse_interval_patterns(text)
    exercise_pattern = "four_note_sequence" if "four_note_sequence" in patterns else "straight"
    if exercise_pattern == "four_note_sequence":
        patterns = ("straight",)
    requested_difficulty = bool(
        re.search(r"\b(difficult|challenging|hard|advanced|hardest)\b", low)
    )
    if requested_difficulty and re.search(r"\bexercise\b", low):
        exercise_pattern = "four_note_sequence"
    octaves, oct_explicit = _parse_octave_count(text)
    direction = _parse_direction(text)
    note_value, triplet, note_explicit = _parse_note_value(text)
    meter, meter_explicit = _parse_meter(text)
    articulation = _parse_articulation(text)
    tempo = _parse_tempo_bpm(text)
    wants_measures = _parse_wants_measures(text)
    wants_structured = _wants_structured_exercise(text)
    if wants_structured and exercise_pattern == "straight":
        exercise_pattern = "four_note_sequence"
    return ScalePracticeSpec(
        tonic=tonic,
        preferred_spelling=preferred,
        scale_type=scale_type,
        interval_patterns=patterns,
        octave_count=max(1, min(3, octaves)),
        octave_count_explicit=oct_explicit,
        direction=direction,
        note_value=note_value,
        note_value_explicit=note_explicit,
        rhythm_triplet=triplet,
        meter=meter,
        meter_explicit=meter_explicit,
        articulation=articulation,
        instrument=str(instrument or "").strip(),
        tempo_bpm=tempo,
        wants_measures=wants_measures,
        tonic_provenance=tonic_prov,
        exercise_pattern=exercise_pattern,
        requested_difficulty=requested_difficulty,
        wants_structured_exercise=wants_structured,
    )


_MELODIC_MINOR_ASC_SEMITONES = (0, 2, 3, 5, 7, 9, 11)
_MELODIC_MINOR_DESC_SEMITONES = (0, 2, 3, 5, 7, 8, 10)


def format_spelled_note_display(note: str) -> str:
    """Unicode display from an already-correct spelled note (no enharmonic respell)."""
    text = str(note or "C").strip() or "C"
    head = text[0].upper()
    tail = text[1:]
    if tail.startswith("#") or tail.startswith("♯"):
        return f"{head}♯"
    if tail.startswith("b") or tail.startswith("♭"):
        return f"{head}♭"
    return head


def spell_scale_degrees_for_direction(tonic: str, scale_type: str, direction: str) -> list[str]:
    from music_theory import spell_diatonic_scale_from_root

    if scale_type == "melodic minor":
        semis = _MELODIC_MINOR_DESC_SEMITONES if direction == "descending" else _MELODIC_MINOR_ASC_SEMITONES
        return spell_diatonic_scale_from_root(tonic, semis)
    from improvisation_intelligence import spell_scale_notes

    ref = tonic
    if scale_type in ("natural minor", "harmonic minor", "melodic minor") and not str(tonic).endswith("m"):
        ref = f"{tonic}m"
    return spell_scale_notes(tonic, scale_type, ref)


def spell_scale(tonic: str, scale_type: str) -> tuple[list[str], str, str]:
    """Return scale degrees (ascending form for reference), human label, reference key."""
    notes = spell_scale_degrees_for_direction(tonic, scale_type, "ascending")
    label = f"{tonic} {_scale_type_label(scale_type)}"
    ref = tonic
    if scale_type in ("natural minor", "harmonic minor", "melodic minor") and not str(tonic).endswith("m"):
        ref = f"{tonic}m"
    return notes, label, ref


def _scale_type_label(scale_type: str) -> str:
    st = scale_type.lower()
    if st == "major":
        return "major"
    if st == "natural minor":
        return "natural minor"
    if st == "harmonic minor":
        return "harmonic minor"
    if st == "melodic minor":
        return "melodic minor"
    return scale_type.replace("_", " ")


def _midi_for_spelled(note: str, octave: int = 4) -> int:
    from music_theory import midi_from_spelled_note

    return midi_from_spelled_note(note, octave=octave)


def _octave_for_sequence(notes: list[str], start_octave: int = 4) -> list[tuple[str, int]]:
    """Assign octaves so each pitch is >= previous (when ascending)."""
    if not notes:
        return []
    out: list[tuple[str, int]] = []
    prev_midi = _midi_for_spelled(notes[0], start_octave) - 1
    octave = start_octave
    for n in notes:
        midi = _midi_for_spelled(n, octave)
        while midi <= prev_midi:
            octave += 1
            midi = _midi_for_spelled(n, octave)
        out.append((n, octave))
        prev_midi = midi
    return out


def extend_scale_octaves(scale: list[str], octave_count: int) -> list[str]:
    """Endpoint-inclusive heptatonic run: N octaves => N*7 + 1 sounding degrees."""
    if not scale or octave_count < 1:
        return list(scale)
    out: list[str] = []
    for _ in range(octave_count):
        out.extend(scale)
    out.append(scale[0])
    return out


def straight_scale_degree_count(octave_count: int, degree_count: int = 7) -> int:
    return max(0, octave_count) * degree_count + 1


def _octave_for_sequence_descending(notes: list[str], start_octave: int = 4) -> list[tuple[str, int]]:
    """Assign octaves so each pitch is strictly lower than the previous (by MIDI)."""
    if not notes:
        return []
    out: list[tuple[str, int]] = []
    prev_midi = _midi_for_spelled(notes[0], start_octave) + 1
    octave = start_octave
    for n in notes:
        midi = _midi_for_spelled(n, octave)
        while midi >= prev_midi:
            octave -= 1
            midi = _midi_for_spelled(n, octave)
        out.append((n, octave))
        prev_midi = midi
    return out


def _melodic_descending_note_sequence(desc_degrees: list[str], octave_count: int) -> list[str]:
    n = len(desc_degrees)
    if n < 2:
        return list(desc_degrees)
    one_oct = [desc_degrees[0]] + [desc_degrees[(n - k) % n] for k in range(1, n)] + [desc_degrees[0]]
    if octave_count <= 1:
        return one_oct
    out = list(one_oct)
    for _ in range(octave_count - 1):
        out.extend(one_oct[1:])
    return out


def build_four_note_sequence(
    scale: list[str],
    *,
    octave_count: int,
    start_octave: int = 4,
) -> list[str]:
    from music_coach_ami.exercise_patterns import build_degree_pattern_sequence

    n = len(scale)
    if n < 4:
        return build_straight_sequence(scale, direction="ascending", octave_count=octave_count, start_octave=start_octave)
    return build_degree_pattern_sequence(
        scale, (0, 1, 2, 3), octave_count=octave_count, start_octave=start_octave
    )


def build_straight_sequence(
    scale: list[str],
    *,
    direction: str,
    octave_count: int,
    start_octave: int = 4,
    scale_type: str = "",
    tonic: str = "",
) -> list[str]:
    if not scale:
        return []
    if scale_type == "melodic minor" and tonic:
        asc_deg = spell_scale_degrees_for_direction(tonic, scale_type, "ascending")
        desc_deg = spell_scale_degrees_for_direction(tonic, scale_type, "descending")
        if direction == "ascending":
            return _names_for_degree_run(asc_deg, octave_count, start_octave, ascending=True)
        if direction == "descending":
            seq = _melodic_descending_note_sequence(desc_deg, octave_count)
            return [n for n, _ in _octave_for_sequence_descending(seq, start_octave + octave_count)]
        up = _names_for_degree_run(asc_deg, octave_count, start_octave, ascending=True)
        asc_seq = extend_scale_octaves(asc_deg, octave_count)
        up_pitched = _octave_for_sequence(asc_seq, start_octave)
        last_o = up_pitched[-1][1]
        desc_seq = _melodic_descending_note_sequence(desc_deg, octave_count)
        down_pitched = _octave_for_sequence_descending(desc_seq, last_o)
        return [n for n, _ in up_pitched] + [n for n, _ in down_pitched[1:]]
    seq = extend_scale_octaves(scale, octave_count)
    if direction == "descending":
        pitched = _octave_for_sequence_descending(list(reversed(seq)), start_octave + octave_count)
        return [n for n, _ in reversed(pitched)]
    pitched = _octave_for_sequence(seq, start_octave)
    names = [n for n, _ in pitched]
    if direction == "both":
        top_n, top_o = pitched[-1]
        rev_notes = list(reversed([n for n, _ in pitched[:-1]])) + [top_n]
        down_pitched = _octave_for_sequence_descending(rev_notes, top_o)
        names = names + [n for n, _ in down_pitched[1:]]
    return names


def _names_for_degree_run(degrees: list[str], octave_count: int, start_octave: int, *, ascending: bool) -> list[str]:
    seq = extend_scale_octaves(degrees, octave_count)
    if ascending:
        return [n for n, _ in _octave_for_sequence(seq, start_octave)]
    return [n for n, _ in _octave_for_sequence_descending(list(reversed(seq)), start_octave + octave_count)]


def build_interval_pairs(scale: list[str], step: int) -> list[tuple[str, str]]:
    """Diatonic interval pairs for one pass through the scale (seven sources in major)."""
    if step <= 0 or len(scale) < 2:
        return []
    n = len(scale)
    pairs: list[tuple[str, str]] = []
    for i in range(n):
        a = scale[i % n]
        b = scale[(i + step) % n]
        pairs.append((a, b))
    return pairs


def build_interval_pairs_over_octaves(scale: list[str], step: int, octave_count: int) -> list[tuple[str, str]]:
    """Interval pairs for each scale-degree source across ``octave_count`` octave spans."""
    if step <= 0 or not scale or octave_count < 1:
        return []
    n = len(scale)
    pairs: list[tuple[str, str]] = []
    for _ in range(octave_count):
        for i in range(n):
            a = scale[i]
            b = scale[(i + step) % n]
            pairs.append((a, b))
    return pairs


_DIATONIC_LETTERS = "CDEFGAB"


def _octave_for_diatonic_spellings(notes: list[str], start_octave: int = 4) -> list[tuple[str, int]]:
    """Assign octaves by ascending letter spellings (B♯ stays in-register before C wraps)."""
    if not notes:
        return []
    out: list[tuple[str, int]] = []
    octave = start_octave
    prev_li: int | None = None
    for n in notes:
        letter = str(n)[0].upper()
        li = _DIATONIC_LETTERS.index(letter)
        if prev_li is not None and li <= prev_li:
            octave += 1
        out.append((n, octave))
        prev_li = li
    return out


def _octave_for_diatonic_spellings_descending(notes: list[str], start_octave: int = 4) -> list[tuple[str, int]]:
    if not notes:
        return []
    out: list[tuple[str, int]] = []
    octave = start_octave
    prev_li: int | None = None
    for n in notes:
        letter = str(n)[0].upper()
        li = _DIATONIC_LETTERS.index(letter)
        if prev_li is not None and li >= prev_li:
            octave -= 1
        out.append((n, octave))
        prev_li = li
    return out


def _default_start_octave(instrument: str) -> int:
    low = str(instrument or "").lower()
    if "flute" in low or "piccolo" in low:
        return 5
    if "clarinet" in low or "trumpet" in low or "violin" in low:
        return 4
    return 4


def _assign_interval_pair_octaves(
    pairs: list[tuple[str, str]],
    *,
    start_octave: int = 4,
    ascending: bool = True,
) -> list[tuple[str, int]]:
    """Broken-interval register: sources follow the scale; targets sit above/below each source."""
    if not pairs:
        return []
    sources = [a for a, _ in pairs]
    if ascending:
        source_pitched = _octave_for_diatonic_spellings(sources, start_octave)
    else:
        source_pitched = _octave_for_diatonic_spellings_descending(sources, start_octave)

    out: list[tuple[str, int]] = []
    for (a, a_oct), (_, b) in zip(source_pitched, pairs, strict=True):
        a_midi = _midi_for_spelled(a, a_oct)
        b_oct = a_oct
        b_midi = _midi_for_spelled(b, b_oct)
        if ascending:
            while b_midi <= a_midi:
                b_oct += 1
                b_midi = _midi_for_spelled(b, b_oct)
        else:
            while b_midi >= a_midi:
                b_oct -= 1
                b_midi = _midi_for_spelled(b, b_oct)
        out.append((a, a_oct))
        out.append((b, b_oct))
    return out


def build_interval_pairs_descending_over_octaves(
    scale: list[str], step: int, octave_count: int
) -> list[tuple[str, str]]:
    """Descending interval pairs: sources follow the scale downward from the tonic (F→E→D♭…)."""
    if step <= 0 or not scale or octave_count < 1:
        return []
    n = len(scale)
    degree_order = [0] + [(n - k) % n for k in range(1, n)]
    pairs: list[tuple[str, str]] = []
    for _ in range(octave_count):
        for i in degree_order:
            a = scale[i]
            b = scale[(i - step) % n]
            pairs.append((a, b))
    return pairs


def interval_pairs_for_direction(
    scale: list[str],
    step: int,
    octave_count: int,
    direction: str,
) -> list[tuple[str, str]]:
    if direction == "descending":
        return build_interval_pairs_descending_over_octaves(scale, step, octave_count)
    return build_interval_pairs_over_octaves(scale, step, octave_count)


def pairs_to_pitched_notes(
    pairs: list[tuple[str, str]],
    *,
    direction: str,
    start_octave: int = 4,
    scale: list[str] | None = None,
    step: int = 2,
    octave_count: int = 1,
) -> list[tuple[str, int]]:
    if scale and step > 0:
        if direction == "both":
            up_pairs = build_interval_pairs_over_octaves(scale, step, octave_count)
            up = _assign_interval_pair_octaves(up_pairs, start_octave=start_octave, ascending=True)
            top_oct = max((o for _, o in up), default=start_octave)
            down_pairs = build_interval_pairs_descending_over_octaves(scale, step, octave_count)
            down = _assign_interval_pair_octaves(
                down_pairs,
                start_octave=top_oct,
                ascending=False,
            )
            return up + down
        if direction == "descending":
            pairs = build_interval_pairs_descending_over_octaves(scale, step, octave_count)
            high_start = start_octave + max(0, octave_count)
            return _assign_interval_pair_octaves(pairs, start_octave=high_start, ascending=False)
    if not pairs:
        return []
    asc = direction != "descending"
    return _assign_interval_pair_octaves(pairs, start_octave=start_octave, ascending=asc)


def _abc_key_field(tonic: str, scale_type: str) -> str:
    from music_theory import abc_key_signature_for_mode, abc_key_signature_for_reference

    st = str(scale_type or "major").lower()
    if st in ("dorian", "mixolydian", "lydian", "locrian"):
        return abc_key_signature_for_mode(tonic, st)
    ref = tonic
    if "minor" in scale_type and "major" not in scale_type and not str(tonic).endswith("m"):
        ref = f"{tonic}m"
    return abc_key_signature_for_reference(ref, scale_type=scale_type)


def _note_to_abc(note: str, octave: int, *, key_field: str = "C") -> str:
    from music_theory import abc_pitch_for_spelled_note

    return abc_pitch_for_spelled_note(note, octave=octave, k_field=key_field)


def _display_tonic(spec: ScalePracticeSpec, reference_key: str) -> str:
    from music_theory import format_musician_note_name

    if spec.preferred_spelling and ("♭" in spec.preferred_spelling or "♯" in spec.preferred_spelling):
        return spec.preferred_spelling.rstrip("mM")
    return format_musician_note_name(spec.tonic, reference_key)


def _format_notes_display(notes: list[str], reference_key: str, *, preserve_spelling: bool = True) -> list[str]:
    if preserve_spelling:
        return [format_spelled_note_display(n) for n in notes]
    from music_theory import format_musician_note_name

    return [format_musician_note_name(n, reference_key) for n in notes]


def _straight_scale_only(patterns: tuple[str, ...]) -> bool:
    return bool(patterns) and all(p in ("straight", "unison", "scale") for p in patterns)


def _build_practice_guidance(spec: ScalePracticeSpec, *, straight: bool) -> list[str]:
    from music_coach_ami.request_resolution import display_coach_instrument

    inst = display_coach_instrument(spec.instrument)
    guidance: list[str] = []
    guidance.append(f"Use a comfortable register on **{inst}**.")

    tempo_line = (
        f"Practice at **{spec.tempo_bpm} BPM**."
        if spec.tempo_bpm
        else "Start around **60–72 BPM** with a metronome."
    )
    rhythm_hint = ""
    if spec.note_value == "eighth":
        if spec.rhythm_triplet:
            rhythm_hint = "Keep the **three-note triplet** subdivision even."
        else:
            rhythm_hint = "Keep **eighth notes** even in tone and time."
    elif spec.note_value == "sixteenth":
        rhythm_hint = "Keep **sixteenth notes** clean and even."
    elif spec.note_value == "half":
        rhythm_hint = " sustain each **half note** with steady tone."

    if straight:
        if spec.direction == "descending":
            guidance.extend(
                [
                    tempo_line,
                    rhythm_hint or "Keep every note even as you move **down** the scale.",
                    "Connect each scale degree smoothly on the way down.",
                    "Increase tempo after **three accurate repetitions**.",
                ]
            )
        elif spec.direction == "both":
            guidance.extend(
                [
                    tempo_line,
                    rhythm_hint or "Keep tone and time even ascending and descending.",
                    "Turn around cleanly at the top and bottom.",
                    "Increase tempo after **three accurate repetitions**.",
                ]
            )
        else:
            guidance.extend(
                [
                    tempo_line,
                    rhythm_hint or "Keep every note even in tone and time.",
                    "Connect each scale degree smoothly.",
                    "Increase tempo after **three accurate repetitions**.",
                ]
            )
        if spec.octave_count_explicit and spec.octave_count == 1:
            pass
        elif spec.octave_count >= 2 and not spec.octave_count_explicit:
            pass
    else:
        guidance.extend(
            [
                tempo_line,
                rhythm_hint or "Keep each pair rhythmically even.",
                "Match tone between the two notes of each interval.",
                "Increase tempo after **three accurate repetitions**.",
            ]
        )
    if spec.articulation == "slurred":
        if straight:
            guidance.append("Keep the notes smoothly connected under the slur.")
        else:
            guidance.append(
                "Keep **slurred** interval pairs connected; do not retongue between the two notes of a pair."
            )
    elif spec.articulation == "slur_two":
        guidance.append("Use **two-note slurs** consistently through the pattern.")
    elif spec.articulation == "alternate_slur_tongue":
        guidance.append("Alternate **two slurred** and **two tongued** notes as marked.")
    elif spec.articulation == "slur2_short2":
        guidance.append("Use **two-note slurs** then **two short/tongued** notes in each cell.")
    elif spec.articulation == "staccato":
        guidance.append("Keep **staccato** attacks light and rhythm steady.")
    elif spec.articulation == "tongued":
        guidance.append("Use a clear, consistent **articulation** on each note.")
    return [g for g in guidance if g]


def _scale_accidental_display_names(scale: list[str], reference_key: str) -> list[str]:
    seen: list[str] = []
    for note in scale:
        disp = format_spelled_note_display(note)
        if ("♭" in disp or "♯" in disp) and disp not in seen:
            seen.append(disp)
    return seen


def _listen_for_intonation_line(scale: list[str], reference_key: str) -> str:
    names = _scale_accidental_display_names(scale, reference_key)
    if not names:
        return "Secure intonation on every degree"
    if len(names) == 1:
        return f"Keep {names[0]} secure and in tune."
    if len(names) == 2:
        return f"Keep {names[0]} and {names[1]} secure and in tune."
    return f"Keep {', '.join(names[:-1])}, and {names[-1]} secure and in tune."


def _melodic_minor_directional_listen(tonic: str) -> str:
    asc = spell_scale_degrees_for_direction(tonic, "melodic minor", "ascending")
    desc = spell_scale_degrees_for_direction(tonic, "melodic minor", "descending")
    up_parts: list[str] = []
    down_parts: list[str] = []
    for i, a in enumerate(asc):
        d = desc[i] if i < len(desc) else ""
        if a != d:
            up_parts.append(format_spelled_note_display(a))
            down_parts.append(format_spelled_note_display(d))
    if not up_parts:
        return _listen_for_intonation_line(asc, f"{tonic}m")
    up_txt = " and ".join(up_parts[:2]) if len(up_parts) <= 2 else ", ".join(up_parts[:-1]) + f", and {up_parts[-1]}"
    down_txt = (
        " and ".join(down_parts[:2])
        if len(down_parts) <= 2
        else ", ".join(down_parts[:-1]) + f", and {down_parts[-1]}"
    )
    return (
        f"Keep {up_txt} clear on the way up; "
        f"return securely to {down_txt} on the way down."
    )


def _build_listen_for(
    *,
    straight: bool,
    scale: list[str],
    reference_key: str,
    spec: ScalePracticeSpec | None = None,
    tonic: str = "",
) -> list[str]:
    if straight:
        intonation = _listen_for_intonation_line(scale, reference_key)
        if (
            spec
            and spec.scale_type == "melodic minor"
            and spec.direction == "both"
            and tonic
        ):
            intonation = _melodic_minor_directional_listen(tonic)
        return [
            "Steady tone across the scale",
            "Smooth transitions between degrees",
            intonation,
        ]
    return [
        "Matching tone between the two notes of each pair",
        "Clean landing on the second note of each interval",
        "Even rhythm through the full pattern",
    ]


def _interval_pattern_title(pattern: str) -> str:
    label = pattern.rstrip("s")
    return f"Diatonic {pattern}" if pattern.endswith("s") else f"Diatonic {pattern}s"


def _format_scale_reference(scale: list[str], reference_key: str) -> str:
    degrees = _format_notes_display(scale, reference_key)
    upper = format_spelled_note_display(scale[0]) if scale else ""
    if upper and (not degrees or degrees[-1] != upper):
        degrees = degrees + [upper]
    return " ".join(degrees)


def _format_interval_pairs_line(pairs: list[tuple[str, str]], reference_key: str) -> str:
    chunks: list[str] = []
    for a, b in pairs:
        chunks.append(f"{format_spelled_note_display(a)}–{format_spelled_note_display(b)}")
    return " · ".join(chunks)


def format_scale_request_summary(spec: ScalePracticeSpec) -> list[str]:
    lines: list[str] = []
    if spec.octave_count_explicit:
        label = {1: "One octave", 2: "Two octaves", 3: "Three octaves"}.get(
            spec.octave_count, f"{spec.octave_count} octaves"
        )
        lines.append(f"**Range:** {label}")
    elif spec.octave_count >= 2:
        lines.append("**Range:** Two octaves")
    if spec.note_value_explicit or spec.note_value != "quarter" or spec.rhythm_triplet:
        rv = spec.note_value.capitalize() + " notes"
        if spec.rhythm_triplet:
            rv = "Triplet " + rv.lower()
        lines.append(f"**Rhythm:** {rv}")
    if spec.direction == "descending":
        lines.append("**Direction:** Descending")
    elif spec.direction == "both":
        lines.append("**Direction:** Ascending and descending")
    if spec.tempo_bpm:
        lines.append(f"**Tempo:** {spec.tempo_bpm} BPM")
    if spec.articulation:
        label = {
            "slur2_short2": "2 slurred, 2 short",
            "alternate_slur_tongue": "Alternate slur/tongue groups",
            "slur_two": "Two-note slurs",
            "slurred": "Slurred",
            "staccato": "Staccato",
            "tongued": "Tongued",
        }.get(spec.articulation, spec.articulation.replace("_", " ").title())
        lines.append(f"**Articulation:** {label}")
    if spec.meter_explicit or spec.wants_measures:
        lines.append(f"**Meter:** {spec.meter}")
    if spec.pattern_id:
        from music_coach_ami.exercise_patterns import PATTERN_LIBRARY

        pat = PATTERN_LIBRARY.get(spec.pattern_id)
        if pat:
            lines.append(f"**Pattern:** {pat.display_name}")
    elif spec.exercise_pattern == "four_note_sequence":
        lines.append("**Pattern:** Four-note ascending sequence")
    return lines


def _abc_default_length(note_value: str) -> str:
    return {
        "quarter": "1/4",
        "eighth": "1/8",
        "half": "1/2",
        "sixteenth": "1/16",
    }.get(note_value, "1/4")


def _rhythmic_unit_count(note_value: str, *, triplet: bool) -> float:
    """Units of the default L: length consumed by one written note (before tuplet grouping)."""
    if triplet:
        return 1.0
    if note_value == "half":
        return 2.0
    if note_value == "sixteenth":
        return 0.25
    return 1.0


def _units_per_measure(meter: str, default_len: str) -> int:
    if meter == "6/8" and default_len == "1/8":
        return 6
    if meter == "3/4" and default_len == "1/4":
        return 3
    if meter == "2/4" and default_len == "1/4":
        return 2
    if meter == "4/4" and default_len == "1/4":
        return 4
    if meter == "4/4" and default_len == "1/8":
        return 8
    if meter == "4/4" and default_len == "1/16":
        return 16
    return 4


def _abc_tempo_line(meter: str, bpm: int) -> str:
    if meter == "6/8":
        return f"Q:3/8={bpm}"
    return f"Q:1/4={bpm}"


def _abc_duration_suffix(note_value: str, *, triplet: bool) -> str:
    """Duration multipliers only when L: differs from the written note value."""
    if triplet:
        return ""
    return ""


def _l_unit_quarters(default_len: str) -> float:
    return {"1/4": 1.0, "1/8": 0.5, "1/2": 2.0, "1/16": 0.25}.get(default_len, 1.0)


def _note_quarter_duration(note_value: str, *, rhythm_triplet: bool) -> float:
    if rhythm_triplet:
        return 2.0 / 3.0
    return {"quarter": 1.0, "half": 2.0, "eighth": 0.5, "sixteenth": 0.25}.get(note_value, 1.0)


def _meter_capacity_quarters(meter: str) -> float:
    num, den = meter.split("/")
    n, d = int(num), int(den)
    if d == 8:
        return n * 0.5
    return n * 4.0 / d


def _abc_mult_for_quarters(quarters: float, default_len: str) -> str:
    unit = _l_unit_quarters(default_len)
    mult = quarters / unit
    if abs(mult - 1.0) < 1e-6:
        return ""
    if abs(mult - round(mult)) < 1e-6:
        return str(int(round(mult)))
    if abs(mult - 0.5) < 1e-6:
        return "/2"
    if abs(mult - 2.0) < 1e-6:
        return "2"
    return str(round(mult, 3)).rstrip("0").rstrip(".")


def _expand_slur_token(tok: str) -> list[str]:
    if tok.startswith("(") and tok.endswith(")") and not tok.startswith("(3"):
        inner = tok[1:-1].strip()
        if inner:
            return inner.split()
    return [tok]


def _abc_apply_triplet_groups(tokens: list[str]) -> list[str]:
    if not tokens:
        return []
    out: list[str] = []
    i = 0
    while i < len(tokens):
        if i + 2 < len(tokens):
            out.append(f"(3:2:2{tokens[i]}{tokens[i + 1]}{tokens[i + 2]}")
            i += 3
        elif i + 1 < len(tokens):
            out.append(f"(3:2:2{tokens[i]}{tokens[i + 1]}z")
            i += 2
        else:
            out.append(f"(3:2:2{tokens[i]}zz")
            i += 1
    return out


def _abc_beam_within_measure(chunk: list[str], meter: str, default_len: str) -> str:
    if meter == "6/8" and default_len == "1/8":
        parts: list[str] = []
        j = 0
        while j < len(chunk):
            group = chunk[j : j + 3]
            if len(group) == 3:
                merged = []
                for g in group:
                    if g.startswith("(3") and g.endswith(")"):
                        merged.append(g)
                    else:
                        merged.append(g)
                if all(not g.startswith("(3") for g in group):
                    parts.append("".join(group))
                else:
                    parts.append(" ".join(group))
            else:
                parts.append(" ".join(group))
            j += 3
        return " ".join(parts)
    return " ".join(chunk)


def _abc_pack_measures(
    tokens: list[str],
    *,
    meter: str,
    note_value: str,
    rhythm_triplet: bool,
    pack_measures: bool,
    default_len: str,
) -> list[str]:
    if not tokens or not pack_measures:
        return [" ".join(tokens)] if tokens else []
    bar_cap = _meter_capacity_quarters(meter)
    note_q = _note_quarter_duration(note_value, rhythm_triplet=rhythm_triplet)
    expanded: list[str] = []
    for tok in tokens:
        expanded.extend(_expand_slur_token(tok))
    lines: list[str] = []
    measure_parts: list[str] = []
    bar_used = 0.0

    def flush_bar() -> None:
        nonlocal measure_parts, bar_used
        if measure_parts:
            lines.append(_abc_beam_within_measure(measure_parts, meter, default_len) + " |")
            measure_parts = []
            bar_used = 0.0

    for tok in expanded:
        if tok.startswith("(3"):
            group_q = 1.0
            if bar_used + group_q > bar_cap + 1e-6 and bar_used > 0:
                flush_bar()
            measure_parts.append(tok)
            bar_used += group_q
            if bar_used >= bar_cap - 1e-6:
                flush_bar()
            continue
        remaining_q = note_q
        first = True
        while remaining_q > 1e-6:
            space = bar_cap - bar_used
            if space <= 1e-6 and measure_parts:
                flush_bar()
                space = bar_cap
            take = min(remaining_q, space)
            suffix = _abc_mult_for_quarters(take, default_len)
            tie = ""
            if take < remaining_q - 1e-6:
                tie = "-"
            elif not first and remaining_q > take:
                tie = ""
            measure_parts.append(f"{tok}{suffix}{tie}")
            bar_used += take
            remaining_q -= take
            first = False
            if bar_used >= bar_cap - 1e-6:
                flush_bar()
    flush_bar()
    return lines


def _abc_layout_systems_from_lines(
    measure_lines: list[str],
    *,
    lines_per_system: int = 4,
) -> str:
    """Join measures onto shared systems (space-separated), wrapping every N bars."""
    if not measure_lines:
        return " |"
    cleaned = [str(m).strip() for m in measure_lines if str(m).strip()]
    out: list[str] = []
    for i in range(0, len(cleaned), max(1, lines_per_system)):
        chunk = cleaned[i : i + lines_per_system]
        # Keep trailing bar line on the last measure of the system only once
        joined = " ".join(chunk)
        out.append(joined if joined.endswith("|") else joined + " |")
    return "\n".join(out)


def build_abc_from_chord_bass_line(
    composition: Any,
    *,
    title: str = "Bass line",
    bpm: int = 84,
    tune_number: int = 1,
    measures_per_system: int = 4,
) -> str:
    """Serialize a BassLineComposition to ABC with chord symbols, clef, and bar lines."""
    from music_theory import abc_key_signature_for_reference

    from music_coach_ami.notation_validate import validate_notation_structure

    ref = str(getattr(composition, "reference_key", "") or "C")
    meter = str(getattr(composition, "meter", "") or "4/4")
    profile = getattr(composition, "notation_profile")
    clef = str(getattr(profile, "clef", "") or "")
    fallback_octave = int(getattr(profile, "written_octave", getattr(profile, "default_octave", 3)) or 3)
    key_field = abc_key_signature_for_reference(ref, scale_type="major")
    measure_lines: list[str] = []
    for bar in getattr(composition, "bars", ()) or ():
        parts: list[str] = []
        chord_label = str(getattr(bar, "chord", "") or "").replace('"', "'")
        for idx, item in enumerate(getattr(bar, "notes", ()) or ()):
            if hasattr(item, "note"):
                note = str(item.note)
                dur = str(item.duration)
                octave = int(getattr(item, "written_octave", fallback_octave) or fallback_octave)
            else:
                note, dur = item
                octave = fallback_octave
            tok = _note_to_abc(str(note), octave, key_field=key_field)
            # L:1/4 → quarter has empty suffix; half=2; eighth=/2
            dur_l = str(dur).lower()
            if dur_l in ("half", "minim"):
                suffix = "2"
            elif dur_l in ("eighth", "quaver"):
                suffix = "/2"
            elif dur_l in ("whole", "semibreve"):
                suffix = "4"
            elif dur_l in ("sixteenth",):
                suffix = "/4"
            else:
                suffix = ""
            if idx == 0:
                parts.append(f'"{chord_label}"{tok}{suffix}')
            else:
                parts.append(f"{tok}{suffix}")
        measure_lines.append(_abc_beam_within_measure(parts, meter, _abc_default_length("quarter")) + " |")
    music = _abc_layout_systems_from_lines(measure_lines, lines_per_system=measures_per_system)
    abc = _abc_tune_block(
        tune_number=tune_number,
        title=title,
        key_field=key_field,
        bpm=bpm,
        meter=meter,
        note_value="quarter",
        music=music,
        clef=clef,
    )
    validate_notation_structure(
        abc,
        meter=meter,
        clef=clef,
        profile=profile,
        raise_on_error=False,
    )
    return abc


def pairs_to_playable_notes(
    pairs: list[tuple[str, str]],
    *,
    direction: str,
    start_octave: int = 4,
    scale: list[str] | None = None,
    step: int = 2,
    octave_count: int = 1,
) -> list[str]:
    pitched = pairs_to_pitched_notes(
        pairs,
        direction=direction,
        start_octave=start_octave,
        scale=scale,
        step=step,
        octave_count=octave_count,
    )
    return [n for n, _ in pitched]


def _abc_slur_tokens(tokens: list[str], articulation: str, *, pair_mode: bool) -> list[str]:
    if not tokens:
        return []
    if articulation == "slur2_short2":
        out: list[str] = []
        i = 0
        while i < len(tokens):
            if i + 3 < len(tokens):
                a, b, c, d = tokens[i], tokens[i + 1], tokens[i + 2], tokens[i + 3]
                out.append(f"({a}{b})")
                out.append(c if c.endswith(".") else f"{c}.")
                out.append(d if d.endswith(".") else f"{d}.")
                i += 4
            elif i + 1 < len(tokens):
                out.append(f"({tokens[i]}{tokens[i + 1]})")
                i += 2
            else:
                out.append(tokens[i] if tokens[i].endswith(".") else f"{tokens[i]}.")
                i += 1
        return out
    if articulation not in ("slurred", "slur_two", "alternate_slur_tongue"):
        return list(tokens)
    if articulation in ("slur_two", "alternate_slur_tongue") or (articulation == "slurred" and pair_mode):
        chunks: list[str] = []
        i = 0
        while i < len(tokens):
            if i + 1 < len(tokens):
                chunks.append(f"({tokens[i]}{tokens[i + 1]})")
                i += 2
            else:
                chunks.append(tokens[i])
                i += 1
        return chunks
    if len(tokens) <= 8:
        return [f"({' '.join(tokens)})"]
    phrase = 4
    chunks = []
    for i in range(0, len(tokens), phrase):
        group = tokens[i : i + phrase]
        if len(group) > 1:
            chunks.append(f"({' '.join(group)})")
        else:
            chunks.append(group[0])
    return chunks


def _abc_layout_systems(
    body: str,
    *,
    tokens_per_system: int = 12,
    phase_break_token_index: int | None = None,
    pair_mode: bool = False,
) -> str:
    """Legacy token wrap when measure packing is disabled."""
    parts = body.split()
    if not parts:
        return " |"
    safe_per_system = tokens_per_system if not pair_mode else max(2, tokens_per_system - (tokens_per_system % 2))
    lines: list[str] = []
    buf: list[str] = []
    token_i = 0
    for part in parts:
        buf.append(part)
        token_i += 1
        if len(buf) >= safe_per_system:
            lines.append(" ".join(buf) + " |")
            buf = []
    if buf:
        lines.append(" ".join(buf) + " |")
    return "\n".join(lines)


def _build_abc_body(
    pitch_tokens: list[str],
    *,
    articulation: str,
    pair_mode: bool,
    meter: str,
    note_value: str,
    rhythm_triplet: bool,
    pack_measures: bool,
    tokens_per_system: int,
) -> str:
    default_len = _abc_default_length(note_value)
    if rhythm_triplet:
        pitch_tokens = _abc_apply_triplet_groups(pitch_tokens)
    slurred = _abc_slur_tokens(pitch_tokens, articulation, pair_mode=pair_mode)
    if pack_measures:
        measure_lines = _abc_pack_measures(
            slurred,
            meter=meter,
            note_value=note_value,
            rhythm_triplet=rhythm_triplet,
            pack_measures=True,
            default_len=default_len,
        )
        return _abc_layout_systems_from_lines(measure_lines, lines_per_system=4)
    flat = " ".join(slurred)
    per_sys = tokens_per_system
    if len(slurred) > 14:
        per_sys = min(per_sys, 10)
    return _abc_layout_systems(flat, tokens_per_system=per_sys, pair_mode=pair_mode)


def _abc_tune_block(
    *,
    tune_number: int,
    title: str,
    key_field: str,
    bpm: int,
    meter: str,
    note_value: str,
    music: str,
    clef: str = "",
) -> str:
    default_len = _abc_default_length(note_value)
    tempo = _abc_tempo_line(meter, bpm)
    key_line = f"K:{key_field}"
    if clef:
        key_line = f"{key_line} clef={clef}"
    return f"""X:{tune_number}
T:{title}
M:{meter}
L:{default_len}
{tempo}
{key_line}
{music}"""


def build_abc_from_note_names(
    note_names: list[str],
    *,
    title: str,
    key_field: str,
    bpm: int = 72,
    pitched: list[tuple[str, int]] | None = None,
    note_value: str = "quarter",
    rhythm_triplet: bool = False,
    meter: str = "4/4",
    articulation: str = "",
    pair_mode: bool = False,
    pack_measures: bool = True,
    tokens_per_system: int = 12,
    tune_number: int = 1,
) -> str:
    if not note_names and not pitched:
        return ""
    if pitched is None:
        pitched = _octave_for_sequence(note_names)
    dur = _abc_duration_suffix(note_value, triplet=rhythm_triplet)
    staccato = articulation == "staccato"
    pair_slur = pair_mode

    pitch_tokens: list[str] = []
    for name, octv in pitched:
        tok = _note_to_abc(name, octv, key_field=key_field)
        if staccato:
            tok = tok + "."
        if dur:
            tok = tok + dur
        pitch_tokens.append(tok)

    music = _build_abc_body(
        pitch_tokens,
        articulation=articulation,
        pair_mode=pair_slur,
        meter=meter,
        note_value=note_value,
        rhythm_triplet=rhythm_triplet,
        pack_measures=pack_measures,
        tokens_per_system=tokens_per_system,
    )
    return _abc_tune_block(
        tune_number=tune_number,
        title=title,
        key_field=key_field,
        bpm=bpm,
        meter=meter,
        note_value=note_value,
        music=music,
    )


def generate_scale_practice(spec: ScalePracticeSpec) -> ScalePracticeResult:
    scale, label, ref = spell_scale(spec.tonic, spec.scale_type)
    key_field = _abc_key_field(spec.tonic, spec.scale_type)
    display_tonic = _display_tonic(spec, ref)
    display_label = f"{display_tonic} {_scale_type_label(spec.scale_type)}"
    straight = _straight_scale_only(spec.interval_patterns)
    key_signature_hint = ref
    start_oct = spec.start_octave if spec.start_octave is not None else _default_start_octave(spec.instrument)
    spec.start_octave = start_oct
    bpm = spec.tempo_bpm or 72
    pack_measures = spec.wants_measures or spec.meter_explicit
    abc_kw = dict(
        key_field=key_field,
        bpm=bpm,
        note_value=spec.note_value,
        rhythm_triplet=spec.rhythm_triplet,
        meter=spec.meter,
        articulation=spec.articulation,
        pack_measures=pack_measures,
    )

    all_pairs: list[tuple[str, str]] = []
    exercise_names: list[str] = []
    abc_sections: list[str] = []
    practice_seq: list[str] = []
    interval_line = ""
    interval_line_desc = ""
    scale_reference = _format_scale_reference(scale, ref)
    scale_ref_desc = ""

    for pattern in spec.interval_patterns:
        if pattern in ("straight", "unison", "scale"):
            from music_coach_ami.exercise_patterns import PATTERN_LIBRARY, build_degree_pattern_pitched

            pat_key = spec.pattern_id or (
                spec.exercise_pattern if spec.exercise_pattern in PATTERN_LIBRARY else ""
            )
            pattern_exercise = bool(
                spec.wants_structured_exercise
                or pat_key
                or spec.exercise_pattern == "four_note_sequence"
            )
            if pattern_exercise and (
                pat_key in PATTERN_LIBRARY
                or spec.exercise_pattern == "four_note_sequence"
                or spec.pattern_id
            ):
                if pat_key in PATTERN_LIBRARY:
                    offsets = PATTERN_LIBRARY[pat_key].degree_offsets
                    pat_title = PATTERN_LIBRARY[pat_key].display_name
                else:
                    offsets = (0, 1, 2, 3)
                    pat_title = "Four-note ascending sequence"
                pitched = build_degree_pattern_pitched(
                    scale,
                    offsets,
                    octave_count=spec.octave_count,
                    start_octave=start_oct,
                )
                seq = [n for n, _ in pitched]
                practice_seq = list(seq)
                exercise_names.extend(seq)
                per_system = 12 if len(seq) <= 28 else 10
                abc_sections.append(
                    build_abc_from_note_names(
                        seq,
                        title=f"{display_label} — {pat_title}",
                        pitched=pitched,
                        pair_mode=False,
                        tokens_per_system=per_system,
                        **abc_kw,
                    )
                )
                continue
            seq = build_straight_sequence(
                scale,
                direction=spec.direction,
                octave_count=spec.octave_count,
                start_octave=start_oct,
                scale_type=spec.scale_type,
                tonic=spec.tonic,
            )
            practice_seq = list(seq)
            exercise_names.extend(seq)
            if spec.scale_type == "melodic minor" and spec.direction == "both":
                asc_deg = spell_scale_degrees_for_direction(spec.tonic, spec.scale_type, "ascending")
                desc_deg = spell_scale_degrees_for_direction(spec.tonic, spec.scale_type, "descending")
                scale_reference = _format_scale_reference(asc_deg, ref)
                scale_ref_desc = _format_scale_reference(
                    [desc_deg[0]]
                    + [desc_deg[(len(desc_deg) - k) % len(desc_deg)] for k in range(1, len(desc_deg))],
                    ref,
                )
                asc_seq = extend_scale_octaves(asc_deg, spec.octave_count)
                up_pitched = _octave_for_sequence(asc_seq, start_oct)
                desc_seq = _melodic_descending_note_sequence(desc_deg, spec.octave_count)
                down_pitched = _octave_for_sequence_descending(desc_seq, up_pitched[-1][1])
                abc_sections.append(
                    build_abc_from_note_names(
                        [n for n, _ in up_pitched],
                        title=f"{display_label} scale (ascending)",
                        pitched=up_pitched,
                        pair_mode=False,
                        tokens_per_system=12,
                        tune_number=1,
                        **abc_kw,
                    )
                )
                abc_sections.append(
                    build_abc_from_note_names(
                        [n for n, _ in down_pitched],
                        title=f"{display_label} scale (descending)",
                        pitched=down_pitched,
                        pair_mode=False,
                        tokens_per_system=12,
                        tune_number=1,
                        **abc_kw,
                    )
                )
            else:
                if spec.scale_type == "melodic minor":
                    asc_deg = spell_scale_degrees_for_direction(spec.tonic, spec.scale_type, "ascending")
                    desc_deg = spell_scale_degrees_for_direction(spec.tonic, spec.scale_type, "descending")
                    scale_reference = _format_scale_reference(asc_deg, ref)
                    if spec.direction == "descending":
                        scale_ref_desc = _format_scale_reference(
                            [desc_deg[0]]
                            + [desc_deg[(len(desc_deg) - k) % len(desc_deg)] for k in range(1, len(desc_deg))],
                            ref,
                        )
                abc_sections.append(
                    build_abc_from_note_names(
                        seq,
                        title=f"{display_label} scale",
                        pair_mode=False,
                        tokens_per_system=14 if len(seq) <= 16 else 10,
                        **abc_kw,
                    )
                )
        else:
            step = _INTERVAL_STEPS.get(pattern, 2)
            pairs = build_interval_pairs_over_octaves(scale, step, spec.octave_count)
            all_pairs.extend(pairs)
            up_pairs = build_interval_pairs_over_octaves(scale, step, spec.octave_count)
            up_pitched = pairs_to_pitched_notes(
                up_pairs,
                direction="ascending",
                start_octave=start_oct,
                scale=scale,
                step=step,
                octave_count=spec.octave_count,
            )
            interval_line = _format_interval_pairs_line(build_interval_pairs(scale, step), ref)
            desc_pairs = build_interval_pairs_descending_over_octaves(scale, step, spec.octave_count)
            interval_line_desc = _format_interval_pairs_line(desc_pairs[: len(scale)], ref)
            if spec.direction == "both":
                down_pitched = pairs_to_pitched_notes(
                    desc_pairs,
                    direction="descending",
                    start_octave=start_oct,
                    scale=scale,
                    step=step,
                    octave_count=spec.octave_count,
                )
                seq = [n for n, _ in up_pitched] + [n for n, _ in down_pitched]
                exercise_names.extend(seq)
                per_system = 10 if spec.note_value in ("eighth", "sixteenth") else 12
                abc_sections.append(
                    build_abc_from_note_names(
                        [n for n, _ in up_pitched],
                        title=f"{display_label} in {pattern} (ascending)",
                        pitched=up_pitched,
                        pair_mode=True,
                        tokens_per_system=per_system,
                        tune_number=1,
                        **abc_kw,
                    )
                )
                abc_sections.append(
                    build_abc_from_note_names(
                        [n for n, _ in down_pitched],
                        title=f"{display_label} in {pattern} (descending)",
                        pitched=down_pitched,
                        pair_mode=True,
                        tokens_per_system=per_system,
                        tune_number=1,
                        **abc_kw,
                    )
                )
            else:
                pitched_pairs = pairs_to_pitched_notes(
                    pairs,
                    direction=spec.direction,
                    start_octave=start_oct,
                    scale=scale,
                    step=step,
                    octave_count=spec.octave_count,
                )
                seq = [n for n, _ in pitched_pairs]
                exercise_names.extend(seq)
                per_system = 10 if spec.note_value in ("eighth", "sixteenth") else 12
                abc_sections.append(
                    build_abc_from_note_names(
                        seq,
                        title=f"{display_label} in {pattern}",
                        pitched=pitched_pairs,
                        pair_mode=True,
                        tokens_per_system=per_system,
                        **abc_kw,
                    )
                )

    if not practice_seq and exercise_names:
        practice_seq = list(exercise_names)

    display_practice = _format_notes_display(practice_seq or exercise_names, ref)
    if straight and practice_seq:
        display_practice = _format_notes_display(practice_seq, ref)
    written = " ".join(display_practice)

    guidance = _build_practice_guidance(spec, straight=straight)
    listen = _build_listen_for(
        straight=straight,
        scale=scale,
        reference_key=ref,
        spec=spec,
        tonic=spec.tonic,
    )
    if spec.pattern_id or spec.exercise_pattern in (
        "four_note_sequence",
        "three_note_cell",
        "broken_thirds_1324",
        "perm_1342",
        "triplet_three_note",
    ):
        from music_coach_ami.exercise_patterns import enrich_exercise_coaching

        extra_g, extra_l = enrich_exercise_coaching(spec)
        guidance.extend(extra_g)
        listen.extend(extra_l)
    notation_sections = [s for s in abc_sections if s]
    abc = notation_sections[0] if notation_sections else ""

    return ScalePracticeResult(
        label=label,
        display_label=display_label,
        tonic=spec.tonic,
        scale_type=spec.scale_type,
        reference_key=ref,
        scale_degrees=list(scale),
        scale_notes=list(scale),
        practice_sequence=practice_seq or list(exercise_names),
        exercise_note_names=practice_seq or list(exercise_names),
        abc_key=key_field,
        interval_pairs=all_pairs,
        abc=abc,
        notation_sections=notation_sections,
        written_sequence=written,
        scale_reference=scale_reference,
        scale_reference_descending=scale_ref_desc,
        interval_pairs_display=interval_line,
        interval_pairs_display_descending=interval_line_desc,
        key_signature_hint=key_signature_hint,
        practice_guidance=guidance,
        what_to_listen_for=listen,
        chosen_start_octave=start_oct,
    )
