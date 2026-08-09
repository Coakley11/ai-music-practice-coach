"""Deterministic scale spelling, interval exercises, and ABC notation for AMI coach."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Tonic patterns — longer spellings first
_TONIC_RE = re.compile(
    r"\b(Eb|Ab|Bb|Db|Gb|F#|C#|G#|D#|A#|[A-Ga-g])(?![A-Za-z#])"
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
    rhythm_triplet: bool = False
    meter: str = "4/4"
    articulation: str = ""
    instrument: str = ""
    tempo_bpm: int | None = None
    start_octave: int | None = None


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
    written_sequence: str = ""
    scale_reference: str = ""
    interval_pairs_display: str = ""
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
    if re.search(rf"{letter}\s*♭", raw_s, re.I):
        return f"{letter}♭"
    if re.search(rf"{letter}\s*♯", raw_s, re.I):
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
    if "natural minor" in low or re.search(r"\bminor\b", low) and "harmonic" not in low and "melodic" not in low:
        if "pentatonic" in low:
            return "minor pentatonic"
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
        return "locrian"  # fallback until phrygian added
    if "locrian" in low:
        return "locrian"
    return "major"


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


def _parse_note_value(text: str) -> tuple[str, bool]:
    low = text.lower()
    triplet = any(p in low for p in ("triplet", "triplets", "triplet eighth", "eighth-note triplet"))
    if any(p in low for p in ("sixteenth", "16th", "1/16")):
        return "sixteenth", triplet
    if any(p in low for p in ("eighth", "8th", "1/8")) or "two notes per beat" in low:
        return "eighth", triplet
    if any(p in low for p in ("half note", "half notes", "1/2")) or "one note per beat" in low and "two" not in low:
        return "half", triplet
    if "four notes per beat" in low:
        return "sixteenth", triplet
    if "quarter" in low or "1/4" in low:
        return "quarter", triplet
    return "quarter", False


def _parse_meter(text: str) -> str:
    low = text.lower()
    m = re.search(r"\bin\s+(4/4|3/4|6/8|2/4|5/4)\b", low)
    if m:
        return m.group(1)
    if "in 3/4" in low:
        return "3/4"
    if "in 6/8" in low:
        return "6/8"
    return "4/4"


def _parse_articulation(text: str) -> str:
    low = text.lower()
    if "staccato" in low:
        return "staccato"
    if "two slurred two tongued" in low or "slur two" in low or "tongue two" in low:
        return "alternate_slur_tongue"
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
    tonic = "C"
    m = _TONIC_RE.search(cleaned or text or "")
    if m:
        tonic = _normalize_tonic(m.group(1))
    preferred = _preferred_tonic_spelling(raw_text, tonic)
    scale_type = _parse_scale_type(text)
    patterns = _parse_interval_patterns(text)
    octaves, oct_explicit = _parse_octave_count(text)
    direction = _parse_direction(text)
    note_value, triplet = _parse_note_value(text)
    meter = _parse_meter(text)
    articulation = _parse_articulation(text)
    tempo = _parse_tempo_bpm(text)
    return ScalePracticeSpec(
        tonic=tonic,
        preferred_spelling=preferred,
        scale_type=scale_type,
        interval_patterns=patterns,
        octave_count=max(1, min(3, octaves)),
        octave_count_explicit=oct_explicit,
        direction=direction,
        note_value=note_value,
        rhythm_triplet=triplet,
        meter=meter,
        articulation=articulation,
        instrument=str(instrument or "").strip(),
        tempo_bpm=tempo,
    )


def spell_scale(tonic: str, scale_type: str) -> tuple[list[str], str, str]:
    """Return scale degrees, human label, reference key for spelling."""
    from improvisation_intelligence import spell_scale_notes

    ref = tonic
    if scale_type in ("natural minor", "harmonic minor", "melodic minor") and not str(tonic).endswith("m"):
        ref = f"{tonic}m"
    notes = spell_scale_notes(tonic, scale_type, ref)
    label = f"{tonic} {_scale_type_label(scale_type)}"
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
    if octave_count <= 1 or not scale:
        return list(scale)
    out = list(scale)
    for _ in range(octave_count - 1):
        out.extend(scale[1:])
    return out


def build_straight_sequence(
    scale: list[str],
    *,
    direction: str,
    octave_count: int,
    start_octave: int = 4,
) -> list[str]:
    if not scale:
        return []
    if octave_count <= 1:
        seq = list(scale) + [scale[0]]
    else:
        seq = extend_scale_octaves(scale, octave_count)
        if seq and seq[-1] != scale[0]:
            seq = seq + [scale[0]]
    pitched = _octave_for_sequence(seq, start_octave)
    names = [n for n, _ in pitched]
    if direction == "descending":
        names = list(reversed(names))
    elif direction == "both":
        names = names + list(reversed(names))[1:]
    return names


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
    from music_theory import abc_key_signature_for_reference

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


def _format_notes_display(notes: list[str], reference_key: str) -> list[str]:
    from music_theory import format_musician_note_name

    return [format_musician_note_name(n, reference_key) for n in notes]


def _straight_scale_only(patterns: tuple[str, ...]) -> bool:
    return bool(patterns) and all(p in ("straight", "unison", "scale") for p in patterns)


def _build_practice_guidance(spec: ScalePracticeSpec, *, straight: bool) -> list[str]:
    inst = str(spec.instrument or "").strip()
    guidance: list[str] = []
    if inst:
        guidance.append(f"Use a comfortable register on **{inst}**.")
    else:
        guidance.append("Use a comfortable register on **your instrument**.")

    tempo_line = (
        f"Practice at **{spec.tempo_bpm} BPM**."
        if spec.tempo_bpm
        else "Start around **60–72 BPM** with a metronome."
    )
    rhythm_hint = ""
    if spec.note_value == "eighth":
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
        guidance.append("Keep **slurred** pairs connected; do not retongue between slurred notes.")
    elif spec.articulation == "staccato":
        guidance.append("Keep **staccato** attacks light and rhythm steady.")
    elif spec.articulation == "tongued":
        guidance.append("Use a clear, consistent **articulation** on each note.")
    return [g for g in guidance if g]


def _build_listen_for(*, straight: bool, display_tonic: str, scale_type: str) -> list[str]:
    if straight:
        low = scale_type.lower()
        if "major" in low and "minor" not in low:
            if "b" in display_tonic or "♭" in display_tonic:
                return [
                    "Steady tone across the scale",
                    "Smooth transitions between degrees",
                    "Secure intonation on E♭, A♭, and B♭",
                ]
        return [
            "Steady tone across the scale",
            "Smooth transitions between degrees",
            "Secure intonation on every degree",
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
    from music_theory import format_musician_note_name

    degrees = _format_notes_display(scale, reference_key)
    upper = format_musician_note_name(scale[0], reference_key) if scale else ""
    if upper and (not degrees or degrees[-1] != upper):
        degrees = degrees + [upper]
    return " ".join(degrees)


def _format_interval_pairs_line(pairs: list[tuple[str, str]], reference_key: str) -> str:
    from music_theory import format_musician_note_name

    chunks: list[str] = []
    for a, b in pairs:
        chunks.append(
            f"{format_musician_note_name(a, reference_key)}–{format_musician_note_name(b, reference_key)}"
        )
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
    if spec.note_value != "quarter":
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
        lines.append(f"**Articulation:** {spec.articulation.replace('_', ' ').title()}")
    if spec.meter and spec.meter != "4/4":
        lines.append(f"**Meter:** {spec.meter}")
    return lines


def _abc_default_length(note_value: str) -> str:
    return {
        "quarter": "1/4",
        "eighth": "1/8",
        "half": "1/2",
        "sixteenth": "1/16",
    }.get(note_value, "1/4")


def _abc_duration_suffix(note_value: str, *, triplet: bool) -> str:
    if triplet and note_value == "eighth":
        return "3"
    if note_value == "half":
        return "2"
    return ""


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


def _abc_slur_tokens(tokens: list[str], articulation: str, *, pair_mode: bool) -> str:
    if articulation != "slurred" or not tokens:
        return " ".join(tokens)
    if pair_mode:
        chunks: list[str] = []
        i = 0
        while i < len(tokens):
            if i + 1 < len(tokens):
                chunks.append(f"({tokens[i]} {tokens[i + 1]})")
                i += 2
            else:
                chunks.append(tokens[i])
                i += 1
        return " ".join(chunks)
    phrase = 4
    chunks = []
    for i in range(0, len(tokens), phrase):
        group = tokens[i : i + phrase]
        if len(group) > 1:
            chunks.append(f"({' '.join(group)})")
        else:
            chunks.append(group[0])
    return " ".join(chunks)


def _abc_layout_systems(
    body: str,
    *,
    tokens_per_system: int = 12,
    phase_break_token_index: int | None = None,
    pair_mode: bool = False,
) -> str:
    """Wrap ABC music onto multiple systems; optional break between ascending/descending phases."""
    parts = body.split()
    if not parts:
        return " |"
    stride = 2 if pair_mode else 1
    safe_per_system = tokens_per_system if not pair_mode else max(2, tokens_per_system - (tokens_per_system % 2))
    lines: list[str] = []
    buf: list[str] = []
    token_i = 0
    for part in parts:
        buf.append(part)
        token_i += 1
        at_phase_break = phase_break_token_index is not None and token_i == phase_break_token_index
        if at_phase_break and buf:
            lines.append(" ".join(buf) + " |")
            buf = []
            continue
        if len(buf) >= safe_per_system:
            lines.append(" ".join(buf) + " |")
            buf = []
    if buf:
        lines.append(" ".join(buf) + " |")
    return "\n".join(lines)


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
    phase_break_after_token: int | None = None,
    tokens_per_system: int = 12,
) -> str:
    if not note_names and not pitched:
        return ""
    if pitched is None:
        pitched = _octave_for_sequence(note_names)
    dur = _abc_duration_suffix(note_value, triplet=rhythm_triplet)
    staccato = articulation == "staccato"
    pitch_tokens: list[str] = []
    for name, octv in pitched:
        tok = _note_to_abc(name, octv, key_field=key_field)
        if staccato:
            tok = tok + "."
        if dur:
            tok = tok + dur
        pitch_tokens.append(tok)
    pair_slur = pair_mode or articulation == "slurred"
    if phase_break_after_token is not None and 0 < phase_break_after_token < len(pitch_tokens):
        up_t = pitch_tokens[:phase_break_after_token]
        down_t = pitch_tokens[phase_break_after_token:]
        up_body = _abc_slur_tokens(up_t, articulation, pair_mode=pair_mode)
        down_body = _abc_slur_tokens(down_t, articulation, pair_mode=pair_mode)
        music = (
            _abc_layout_systems(
                up_body,
                tokens_per_system=tokens_per_system,
                pair_mode=pair_slur,
            )
            + "\n"
            + _abc_layout_systems(
                down_body,
                tokens_per_system=tokens_per_system,
                pair_mode=pair_slur,
            )
        )
    else:
        slurred = _abc_slur_tokens(pitch_tokens, articulation, pair_mode=pair_mode)
        per_sys = tokens_per_system
        if len(pitch_tokens) > 14:
            per_sys = min(per_sys, 10)
        music = _abc_layout_systems(
            slurred,
            tokens_per_system=per_sys,
            pair_mode=pair_slur,
        )
    default_len = _abc_default_length(note_value)
    return f"""X:1
T:{title}
M:{meter}
L:{default_len}
Q:1/4={bpm}
K:{key_field}
{music}"""


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
    abc_kw = dict(
        key_field=key_field,
        bpm=bpm,
        note_value=spec.note_value,
        rhythm_triplet=spec.rhythm_triplet,
        meter=spec.meter,
        articulation=spec.articulation,
    )

    all_pairs: list[tuple[str, str]] = []
    exercise_names: list[str] = []
    abc_sections: list[str] = []
    practice_seq: list[str] = []
    interval_line = ""

    for pattern in spec.interval_patterns:
        if pattern in ("straight", "unison", "scale"):
            seq = build_straight_sequence(
                scale,
                direction=spec.direction,
                octave_count=spec.octave_count,
                start_octave=start_oct,
            )
            practice_seq = list(seq)
            exercise_names.extend(seq)
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
            interval_line = _format_interval_pairs_line(build_interval_pairs(scale, step), ref)
            phase_break = None
            if spec.direction == "both":
                up_only = pairs_to_pitched_notes(
                    pairs,
                    direction="ascending",
                    start_octave=start_oct,
                    scale=scale,
                    step=step,
                    octave_count=spec.octave_count,
                )
                phase_break = len(up_only)
            per_system = 10 if spec.note_value in ("eighth", "sixteenth") else 12
            abc_sections.append(
                build_abc_from_note_names(
                    seq,
                    title=f"{display_label} in {pattern}",
                    pitched=pitched_pairs,
                    pair_mode=True,
                    phase_break_after_token=phase_break,
                    tokens_per_system=per_system,
                    **abc_kw,
                )
            )

    if not practice_seq and exercise_names:
        practice_seq = list(exercise_names)

    scale_reference = _format_scale_reference(scale, ref)
    display_practice = _format_notes_display(practice_seq or exercise_names, ref)
    if straight and practice_seq:
        display_practice = _format_notes_display(practice_seq, ref)
    written = " ".join(display_practice)

    guidance = _build_practice_guidance(spec, straight=straight)
    listen = _build_listen_for(straight=straight, display_tonic=display_tonic, scale_type=spec.scale_type)
    abc = "\n\n".join(s for s in abc_sections if s)

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
        written_sequence=written,
        scale_reference=scale_reference,
        interval_pairs_display=interval_line,
        key_signature_hint=key_signature_hint,
        practice_guidance=guidance,
        what_to_listen_for=listen,
        chosen_start_octave=start_oct,
    )
