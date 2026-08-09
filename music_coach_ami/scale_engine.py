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
    octave_count: int = 1
    direction: str = "ascending"  # ascending | descending | both
    instrument: str = ""
    tempo_bpm: int | None = None


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
    octaves = 2 if re.search(r"\btwo\s+octaves?\b", low) else 1
    if re.search(r"\bthree\s+octaves?\b", low):
        octaves = 3
    direction = "both" if "ascending and descending" in low or "ascending & descending" in low else "ascending"
    if "descending" in low and "ascending" not in low:
        direction = "descending"
    tempo = None
    tm = re.search(r"\b(\d{2,3})\s*bpm\b", low)
    if tm:
        tempo = int(tm.group(1))
    return ScalePracticeSpec(
        tonic=tonic,
        preferred_spelling=preferred,
        scale_type=scale_type,
        interval_patterns=patterns,
        octave_count=max(1, min(3, octaves)),
        direction=direction,
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


def build_straight_sequence(scale: list[str], *, direction: str, octave_count: int) -> list[str]:
    if not scale:
        return []
    if octave_count <= 1:
        seq = list(scale) + [scale[0]]
    else:
        seq = extend_scale_octaves(scale, octave_count)
        if seq and seq[-1] != scale[0]:
            seq = seq + [scale[0]]
    pitched = _octave_for_sequence(seq)
    names = [n for n, _ in pitched]
    if direction == "descending":
        names = list(reversed(names))
    elif direction == "both":
        names = names + list(reversed(names))[1:]
    return names


def build_interval_pairs(scale: list[str], step: int) -> list[tuple[str, str]]:
    """Diatonic interval pairs (step = scale-degree skip, 2 = thirds)."""
    if step <= 0 or len(scale) < 2:
        return []
    n = len(scale)
    pairs: list[tuple[str, str]] = []
    for i in range(n):
        a = scale[i % n]
        b = scale[(i + step) % n]
        pairs.append((a, b))
    return pairs


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
    """Assign octaves per pair — target stays in-register until the interval crosses an octave."""
    if not pairs:
        return []
    out: list[tuple[str, int]] = []
    last_midi: int | None = None
    cursor_oct = start_octave
    for a, b in pairs:
        if ascending:
            a_oct = cursor_oct
            a_midi = _midi_for_spelled(a, a_oct)
            if last_midi is not None:
                while a_midi <= last_midi:
                    a_oct += 1
                    a_midi = _midi_for_spelled(a, a_oct)
            b_oct = a_oct
            b_midi = _midi_for_spelled(b, b_oct)
            while b_midi <= a_midi:
                b_oct += 1
                b_midi = _midi_for_spelled(b, b_oct)
            out.append((a, a_oct))
            out.append((b, b_oct))
            last_midi = b_midi
            cursor_oct = b_oct
        else:
            a_oct = cursor_oct
            a_midi = _midi_for_spelled(a, a_oct)
            if last_midi is not None:
                while a_midi >= last_midi:
                    a_oct -= 1
                    a_midi = _midi_for_spelled(a, a_oct)
            b_oct = a_oct
            b_midi = _midi_for_spelled(b, b_oct)
            while b_midi >= a_midi:
                b_oct -= 1
                b_midi = _midi_for_spelled(b, b_oct)
            out.append((a, a_oct))
            out.append((b, b_oct))
            last_midi = b_midi
            cursor_oct = b_oct
    return out


def pairs_to_playable_notes(
    pairs: list[tuple[str, str]],
    *,
    direction: str,
    start_octave: int = 4,
) -> list[str]:
    if not pairs:
        return []
    asc = direction != "descending"
    pitched = _assign_interval_pair_octaves(pairs, start_octave=start_octave, ascending=asc)
    names = [n for n, _ in pitched]
    if direction == "both":
        down = _assign_interval_pair_octaves(
            list(reversed(pairs)),
            start_octave=start_octave,
            ascending=False,
        )
        down_names = [n for n, _ in down]
        names = names + down_names[1:]
    return names


def pairs_to_pitched_notes(
    pairs: list[tuple[str, str]],
    *,
    direction: str,
    start_octave: int = 4,
) -> list[tuple[str, int]]:
    if not pairs:
        return []
    asc = direction != "descending"
    pitched = _assign_interval_pair_octaves(pairs, start_octave=start_octave, ascending=asc)
    if direction == "both":
        down = _assign_interval_pair_octaves(
            list(reversed(pairs)),
            start_octave=start_octave,
            ascending=False,
        )
        pitched = pitched + down[1:]
    return pitched


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
    if straight:
        guidance.extend(
            [
                "Start around **60–72 BPM**.",
                "Keep every note even in tone and time.",
                "Connect each scale degree smoothly.",
                "Increase tempo after **three accurate repetitions**.",
            ]
        )
    else:
        guidance.extend(
            [
                "Start slowly with a metronome.",
                "Keep each pair rhythmically even.",
                "Match tone between the two notes of each interval.",
                "Increase tempo after **three accurate repetitions**.",
            ]
        )
    return guidance


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


def build_abc_from_note_names(
    note_names: list[str],
    *,
    title: str,
    key_field: str,
    bpm: int = 72,
    pitched: list[tuple[str, int]] | None = None,
) -> str:
    if not note_names and not pitched:
        return ""
    if pitched is None:
        pitched = _octave_for_sequence(note_names)
    tokens: list[str] = []
    for name, octv in pitched:
        tokens.append(_note_to_abc(name, octv, key_field=key_field))
        tokens.append("2")
    bar_size = 8
    bars: list[str] = []
    for i in range(0, len(tokens), bar_size):
        bars.append(" ".join(tokens[i : i + bar_size]))
    music = " |\n".join(bars) + " |"
    return f"""X:1
T:{title}
M:4/4
L:1/4
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
    start_oct = _default_start_octave(spec.instrument)

    all_pairs: list[tuple[str, str]] = []
    exercise_names: list[str] = []
    abc_sections: list[str] = []
    practice_seq: list[str] = []
    interval_line = ""

    for pattern in spec.interval_patterns:
        if pattern in ("straight", "unison", "scale"):
            seq = build_straight_sequence(scale, direction=spec.direction, octave_count=spec.octave_count)
            practice_seq = list(seq)
            exercise_names.extend(seq)
            abc_sections.append(
                build_abc_from_note_names(
                    seq,
                    title=f"{display_label} scale",
                    key_field=key_field,
                    bpm=spec.tempo_bpm or 72,
                )
            )
        else:
            step = _INTERVAL_STEPS.get(pattern, 2)
            pairs = build_interval_pairs(scale, step)
            all_pairs.extend(pairs)
            pitched_pairs = pairs_to_pitched_notes(
                pairs,
                direction=spec.direction,
                start_octave=start_oct,
            )
            seq = [n for n, _ in pitched_pairs]
            exercise_names.extend(seq)
            interval_line = _format_interval_pairs_line(pairs, ref)
            abc_sections.append(
                build_abc_from_note_names(
                    seq,
                    title=f"{display_label} in {pattern}",
                    key_field=key_field,
                    bpm=spec.tempo_bpm or 60,
                    pitched=pitched_pairs,
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
    )
