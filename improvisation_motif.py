"""Motif generation, transformations, ABC notation, and guitar TAB for Improvisation Intelligence."""

from __future__ import annotations

import random
import re
from typing import Any

from music_theory import CHROMATIC, NOTE_TO_MIDI, normalize_root, split_chord

from improvisation_intelligence import flatten_sections
from songs.form import section_order

# Open-string MIDI (high e → low E)
_GUITAR_OPEN = (64, 59, 55, 50, 45, 40)
_STRING_LABELS = ("e", "B", "G", "D", "A", "E")

_RHYTHM_PATTERNS: dict[str, list[str]] = {
    "quarter-quarter-quarter": ["♩", "♩", "♩"],
    "quarter-quarter-half": ["♩", "♩", "𝅗"],
    "eighth-eighth-quarter": ["♪", "♪", "♩"],
    "quarter-eighth-eighth": ["♩", "♪", "♪"],
    "quarter-dotted-eighth": ["♩", "♩.", "♪"],
    "eighth-eighth-half": ["♪", "♪", "𝅗"],
    "eighth-quart-eighth-eighth": ["♪", "♩", "♪", "♪"],
    "syncopated-four": ["♪", "♩", "♪", "♪"],
    "sixteenth-run-four": ["♬", "♬", "♬", "♬"],
    "harder-mixed-a": ["♬", "♬", "♪", "♪", "♩", "♪", "♬", "♬", "♪", "♩", "♪", "♪", "♬", "♬", "♪", "♩"],
    "harder-mixed-b": ["♪", "♬", "♬", "♪", "♩", "♪", "♪", "♬", "♬", "♬", "♪", "♩", "♪", "♪", "♬", "♬", "♪", "♩"],
    "harder-triplet-feel": ["♪", "♪", "♪", "♩", "♬", "♬", "♪", "♪", "♩", "♪", "♬", "♬", "♪", "♪", "♩", "♪"],
}

_RHYTHM_TO_ABC_LEN: dict[str, str] = {
    "♩": "2",
    "♪": "/2",
    "♬": "/4",
    "♩.": "3",
    "𝅗": "4",
}

RHYTHM_PATTERN_KEYS: tuple[str, ...] = tuple(_RHYTHM_PATTERNS.keys())


_NUMBERED_SECTION_RE = re.compile(
    r"^(verse|chorus|bridge|intro|outro|pre-chorus|pre chorus)\s+(\d+)$",
    re.I,
)


def _is_numbered_section_instance(name: str) -> bool:
    """True for labels like Verse 1 / Chorus 2 — keep each pass in the map."""
    return bool(_NUMBERED_SECTION_RE.match(str(name or "").strip()))


def _section_base_key(name: str) -> str:
    """Normalize section labels for deduplication (Verse 2 → verse, etc.)."""
    n = str(name or "").strip()
    n = re.sub(r"\s*\(repeat\)\s*$", "", n, flags=re.I)
    n = re.sub(r"\s*\(alternate\)\s*$", "", n, flags=re.I)
    n = re.sub(r"\s*\(\d+\)\s*$", "", n)
    if _is_numbered_section_instance(n):
        return n.lower()
    n = re.sub(r"\s+\d+$", "", n)
    return n.lower()


_CANONICAL_SECTION_LABELS: dict[str, str] = {
    "verse": "Verse",
    "chorus": "Chorus",
    "bridge": "Bridge",
    "intro": "Intro",
    "outro": "Outro",
    "pre-chorus": "Pre-Chorus",
    "pre chorus": "Pre-Chorus",
    "solo": "Solo",
    "interlude": "Interlude",
}


def _display_section_label(name: str) -> str:
    """Short, readable section heading for the chord map."""
    n = str(name or "").strip()
    if _is_numbered_section_instance(n):
        return n
    aliases = {
        "a section": "A",
        "b section": "B",
        "final a / outro": "Outro",
        "final a / tag": "Outro",
        "coda": "Outro",
    }
    if n.lower() in aliases:
        return aliases[n.lower()]
    base = _section_base_key(name)
    if base in _CANONICAL_SECTION_LABELS:
        return _CANONICAL_SECTION_LABELS[base]
    return n


def collapse_consecutive_chords(chords: list[str]) -> list[str]:
    """Merge adjacent duplicate chords (2-bar holds become one cell)."""
    out: list[str] = []
    for ch in chords:
        token = str(ch).strip()
        if not token:
            continue
        if not out or out[-1] != token:
            out.append(token)
    return out


def single_progression_cycle(chords: list[str]) -> list[str]:
    """
    One harmonic pass per section — collapse repeats and repeated cycles
    (e.g. Verse with 4× the same 4-chord loop → 4 chords shown once).
    """
    clean = collapse_consecutive_chords(chords)
    if len(clean) < 2:
        return clean
    n = len(clean)
    for cycle_len in range(1, n // 2 + 1):
        if n % cycle_len != 0:
            continue
        pattern = clean[:cycle_len]
        if all(clean[i] == pattern[i % cycle_len] for i in range(n)):
            return list(pattern)
    return clean


def dedupe_sections_for_display(
    sections: dict[str, list[str]],
    *,
    section_names: list[str] | None = None,
) -> list[tuple[str, list[str]]]:
    """
    One row per unique section identity — skip repeated Verse/Chorus blocks
    with identical chords; keep alternates when harmony differs.
    Numbered sections (Verse 1, Chorus 2, …) are always listed separately.
    """
    seen: dict[str, tuple[str, ...]] = {}
    out: list[tuple[str, list[str]]] = []
    for name, chords in section_order(sections, section_names=section_names):
        raw = [str(c).strip() for c in (chords or []) if c and str(c).strip()]
        if not raw:
            continue
        clean = single_progression_cycle(raw)
        if not clean:
            continue
        if _is_numbered_section_instance(name):
            out.append((name, clean))
            continue
        base = _section_base_key(name)
        sig = tuple(clean)
        if base in seen:
            if seen[base] == sig:
                continue
            label = name
        else:
            seen[base] = sig
            label = _display_section_label(name)
        out.append((label, clean))
    return out


def resolve_improv_sections(
    session_state: dict,
    improv_ctx: Any,
) -> list[tuple[str, list[str]]]:
    """Section-based chord map (deduped) for Live Coach / Phrase Motif."""
    gen = session_state.get("improv_generated_sections")
    if gen:
        mapped = dedupe_sections_for_display(gen)
        if mapped:
            return mapped
    if improv_ctx.sections:
        order = getattr(improv_ctx, "section_order", None) or []
        mapped = dedupe_sections_for_display(
            improv_ctx.sections,
            section_names=list(order) if order else None,
        )
        if mapped:
            return mapped
    flat = list(improv_ctx.progression_flat or [])
    if flat:
        return [("Progression", flat)]
    return []


def flatten_section_map(section_map: list[tuple[str, list[str]]]) -> list[str]:
    return [ch for _label, chords in section_map for ch in chords]


def global_chord_index(
    section_map: list[tuple[str, list[str]]],
    section_idx: int,
    chord_idx: int,
) -> int:
    idx = 0
    for si, (_label, chords) in enumerate(section_map):
        if si < section_idx:
            idx += len(chords)
        elif si == section_idx:
            return idx + chord_idx
    return 0


def section_and_chord_at_global_index(
    section_map: list[tuple[str, list[str]]],
    global_idx: int,
) -> tuple[str, str]:
    """Map flattened chord index back to (section label, chord symbol)."""
    if global_idx < 0:
        global_idx = 0
    offset = 0
    for label, chords in section_map:
        if not chords:
            continue
        if global_idx < offset + len(chords):
            return label, chords[global_idx - offset]
        offset += len(chords)
    if section_map:
        label, chords = section_map[-1]
        if chords:
            return label, chords[-1]
    return "", ""


def resolve_improv_chords(session_state: dict, improv_ctx: Any) -> list[str]:
    """Flat chord list (deduped sections) for next-chord / legacy helpers."""
    return flatten_section_map(resolve_improv_sections(session_state, improv_ctx))


def chord_tone_names(chord: str, *, reference_key: str = "") -> list[str]:
    """Root, 3rd, 5th, and 7th when applicable — spelled for the selected key."""
    from music_theory import reference_spelling_mode, spell_pitch_class, split_chord, normalize_root

    head = str(chord).split("/")[0].strip()
    root, suffix = split_chord(head)
    root = normalize_root(root)
    ref = str(reference_key or root or "C")
    mode = reference_spelling_mode(ref)
    base = NOTE_TO_MIDI.get(root, 60)
    low = suffix.lower()
    if "m7b5" in low:
        intervals = (0, 3, 6, 10)
    elif "maj7" in low:
        intervals = (0, 4, 7, 11)
    elif "m7" in low and "maj" not in low:
        intervals = (0, 3, 7, 10)
    elif re.search(r"(?<![a-z])7", low) and "maj" not in low:
        intervals = (0, 4, 7, 10)
    elif "m" in low and "maj" not in low:
        intervals = (0, 3, 7)
    else:
        intervals = (0, 4, 7)
    return [spell_pitch_class((base + i) % 12, mode=mode) for i in intervals[:4]]


def _midi_from_note(name: str, octave: int = 4) -> int:
    root = normalize_root(split_chord(str(name))[0])
    return NOTE_TO_MIDI.get(root, 60) + 12 * (octave - 4)


def _note_from_midi(midi: int) -> str:
    names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    return names[midi % 12]


def _abc_pitch(midi: int) -> str:
    names = ["C", "^C", "D", "^D", "E", "F", "^F", "G", "^G", "A", "^A", "B"]
    octave = midi // 12
    pitch = names[midi % 12]
    if octave >= 5:
        pitch += "'" * (octave - 4)
    elif octave <= 3:
        pitch = pitch.lower() if pitch.isupper() else pitch
        if octave < 4:
            pitch = "," + pitch
    return pitch


def _parse_key_scale(key_center: str) -> tuple[str, list[int]]:
    """Return (mode, pitch classes) for major or natural minor."""
    text = str(key_center or "C").strip()
    root, suffix = split_chord(text)
    root = normalize_root(root)
    if root not in CHROMATIC:
        root = "C"
    ri = CHROMATIC.index(root)
    minor = "m" in suffix.lower() and "maj" not in suffix.lower()
    if minor:
        intervals = (0, 2, 3, 5, 7, 8, 10)
    else:
        intervals = (0, 2, 4, 5, 7, 9, 11)
    pcs = [(ri + i) % 12 for i in intervals]
    return ("minor" if minor else "major", pcs)


def _nearest_scale_degree(note: str, scale_pcs: list[int]) -> int:
    pc = NOTE_TO_MIDI.get(normalize_root(split_chord(note)[0]), 60) % 12
    if pc in scale_pcs:
        return scale_pcs.index(pc)
    dists = [(min((pc - s) % 12, (s - pc) % 12), i) for i, s in enumerate(scale_pcs)]
    return min(dists)[1]


def _normalize_motif_level(level: str) -> str:
    low = str(level or "").lower()
    if "begin" in low:
        return "Beginner"
    if "adv" in low:
        return "Advanced"
    return "Intermediate"


def _scale_step_note(scale_pcs: list[int], from_note: str, steps: int) -> str:
    pc = NOTE_TO_MIDI.get(normalize_root(split_chord(from_note)[0]), 60) % 12
    if pc not in scale_pcs:
        pc = scale_pcs[0]
    idx = scale_pcs.index(pc)
    target = scale_pcs[(idx + steps) % len(scale_pcs)]
    return _note_from_midi(target + 60)


def _chromatic_below(note: str) -> str:
    return _note_from_midi(_midi_from_note(note) - 1)


def _guide_tone_pair(chord_tones: list[str]) -> list[str]:
    if len(chord_tones) >= 4:
        return [chord_tones[0], chord_tones[1], chord_tones[3]]
    if len(chord_tones) >= 2:
        return chord_tones[:2]
    return chord_tones


def _color_extension_tones(
    chord_tones: list[str],
    scale_pcs: list[int],
) -> tuple[str, str, str]:
    root = chord_tones[0]
    ninth = _scale_step_note(scale_pcs, root, 2)
    eleventh = _scale_step_note(scale_pcs, root, 4)
    thirteenth = _scale_step_note(scale_pcs, root, 6)
    return ninth, eleventh, thirteenth


def _dedupe_consecutive(notes: list[str]) -> list[str]:
    out: list[str] = []
    for n in notes:
        if not out or out[-1] != n:
            out.append(n)
    return out


def _harder_example_notes(
    chord: str,
    chord_tones: list[str],
    scale_pcs: list[int],
    rng: random.Random,
    idea_variant: int,
) -> list[str]:
    """Long, vocabulary-rich lines for the Harder Example mission button (12–18 notes)."""
    if len(chord_tones) < 2:
        chord_tones = chord_tone_names(chord)[:4]
    guides = _guide_tone_pair(chord_tones)
    root = guides[0]
    third = guides[1] if len(guides) > 1 else chord_tones[0]
    seventh = guides[2] if len(guides) > 2 else _scale_step_note(scale_pcs, third, 2)
    fifth = chord_tones[2] if len(chord_tones) > 2 else _scale_step_note(scale_pcs, root, 2)
    ninth, eleventh, thirteenth = _color_extension_tones(chord_tones, scale_pcs)

    approach3 = _chromatic_below(third)
    approach7 = _chromatic_below(seventh)
    enc_lo = _scale_step_note(scale_pcs, third, -1)
    enc_hi = _scale_step_note(scale_pcs, third, 1)
    pass7 = _scale_step_note(scale_pcs, seventh, -1)
    pass5 = _scale_step_note(scale_pcs, fifth, -1)
    upper7 = _scale_step_note(scale_pcs, seventh, 1)
    arp = list(chord_tones[:4]) if len(chord_tones) >= 4 else [root, third, fifth, seventh]

    # Motif A → variation A' → cadence (developed line, not scalar wash)
    templates: list[list[str]] = [
        [approach3, third, enc_lo, enc_hi, third, seventh, pass7, fifth, third, approach3, third, ninth, seventh, third],
        [root, fifth, third, approach7, seventh, upper7, seventh, pass7, fifth, third, enc_lo, enc_hi, third, root, third],
        [enc_lo, enc_hi, third, fifth, seventh, thirteenth, eleventh, ninth, seventh, pass7, fifth, third, approach3, third],
        [root, third, fifth, seventh, upper7, eleventh, ninth, seventh, pass7, fifth, pass5, third, enc_lo, third, seventh, third],
        [approach3, third, fifth, ninth, eleventh, ninth, seventh, pass7, fifth, third, approach3, third, seventh, root, third],
        [root, approach3, third, seventh, third, fifth, seventh, upper7, seventh, pass7, fifth, enc_lo, enc_hi, third, ninth, third],
        [third, seventh, pass7, fifth, third, root, fifth, third, approach7, seventh, upper7, ninth, seventh, third, root],
        [arp[0], arp[1], arp[2], arp[3], upper7, eleventh, ninth, seventh, pass7, fifth, third, enc_lo, enc_hi, third, seventh, third],
        [root, fifth, third, enc_lo, enc_hi, third, fifth, seventh, thirteenth, eleventh, ninth, seventh, pass7, fifth, third, root],
        [approach7, seventh, third, fifth, ninth, seventh, pass7, fifth, third, approach3, third, seventh, upper7, seventh, third, root, third],
        [root, third, fifth, seventh, pass7, fifth, third, enc_lo, enc_hi, third, ninth, eleventh, ninth, seventh, third, approach3, third],
        [enc_lo, enc_hi, third, fifth, third, seventh, upper7, seventh, pass7, fifth, root, fifth, third, approach7, seventh, third, root],
    ]
    notes = list(templates[idea_variant % len(templates)])
    notes = _dedupe_consecutive(notes)
    target_len = 14 + (idea_variant % 5)  # 14–18
    if len(notes) < target_len:
        tail = [seventh, pass7, fifth, third, approach3, third, ninth, seventh, third]
        notes = _dedupe_consecutive(notes + tail)
    return notes[: min(20, max(12, len(notes)))]


def _beginner_notes(chord_tones: list[str], rng: random.Random, idea_variant: int) -> list[str]:
    if len(chord_tones) >= 3:
        patterns = [
            chord_tones[:2],
            [chord_tones[0], chord_tones[2]],
            [chord_tones[0], chord_tones[1], chord_tones[0]],
        ]
        return list(patterns[idea_variant % len(patterns)])
    return chord_tones[:2] or ["C", "E"]


def _intermediate_notes(
    chord: str,
    chord_tones: list[str],
    scale_pcs: list[int],
    rng: random.Random,
    idea_variant: int,
) -> list[str]:
    if len(chord_tones) < 2:
        chord_tones = chord_tone_names(chord)[:3]
    root, third = chord_tones[0], chord_tones[1] if len(chord_tones) > 1 else chord_tones[0]
    fifth = chord_tones[2] if len(chord_tones) > 2 else _scale_step_note(scale_pcs, root, 2)
    neighbor = _scale_step_note(scale_pcs, third, 1)
    passing = _scale_step_note(scale_pcs, third, -1)
    templates = [
        [root, passing, third, fifth],
        [third, neighbor, third, fifth, root],
        [root, third, _scale_step_note(scale_pcs, fifth, 1), fifth],
        [fifth, third, root, passing, third],
        [root, third, fifth, neighbor, third],
        [root, passing, third, passing, fifth, third],
        [third, fifth, _scale_step_note(scale_pcs, fifth, 1), fifth, root],
        [root, neighbor, root, third, fifth],
        [fifth, root, third, neighbor, third],
        [root, third, fifth, third, root, fifth],
        [third, root, passing, third, fifth, root],
        [root, _scale_step_note(scale_pcs, root, 1), third, fifth, third],
    ]
    return list(templates[idea_variant % len(templates)])


def _advanced_notes(
    chord: str,
    chord_tones: list[str],
    scale_pcs: list[int],
    rng: random.Random,
    idea_variant: int,
) -> list[str]:
    if len(chord_tones) < 2:
        chord_tones = chord_tone_names(chord)[:4]
    guides = _guide_tone_pair(chord_tones)
    third = guides[1] if len(guides) > 1 else chord_tones[0]
    seventh = guides[2] if len(guides) > 2 else _scale_step_note(scale_pcs, third, 2)
    root = guides[0]
    fifth = chord_tones[2] if len(chord_tones) > 2 else _scale_step_note(scale_pcs, root, 2)
    approach = _chromatic_below(third)
    upper = _scale_step_note(scale_pcs, seventh, 1)
    lower = _scale_step_note(scale_pcs, root, -1)
    arpeggio = chord_tones[:4] if len(chord_tones) >= 4 else guides
    scale_down = [
        arpeggio[-1],
        _scale_step_note(scale_pcs, arpeggio[-1], -1),
        _scale_step_note(scale_pcs, arpeggio[-1], -2),
        third,
    ]
    pass_from_seventh = _scale_step_note(scale_pcs, seventh, -1)
    enc_above = _scale_step_note(scale_pcs, third, 1)
    enc_below = _scale_step_note(scale_pcs, third, -1)
    templates = [
        [approach, third, seventh, pass_from_seventh, seventh],
        (arpeggio + [_scale_step_note(scale_pcs, arpeggio[-1], 1)])[:6],
        [lower, root, approach, third, seventh, upper],
        [root, third, _chromatic_below(fifth), fifth, seventh],
        scale_down + [root],
        [third, upper, seventh, pass_from_seventh, root, third],
        [enc_below, enc_above, third, seventh, third],
        [root, fifth, third, approach, third, seventh, root],
        [seventh, pass_from_seventh, fifth, third, _chromatic_below(third), third],
        [root, third, fifth, upper, seventh, pass_from_seventh, fifth],
        [approach, third, fifth, seventh, upper, seventh, third],
        [third, seventh, third, root, fifth, _scale_step_note(scale_pcs, fifth, 1), fifth],
    ]
    notes = list(templates[idea_variant % len(templates)])
    return _dedupe_consecutive(notes)[:14]


def _rhythm_for_harder(note_count: int, idea_variant: int) -> tuple[str, list[str]]:
    keys = ["harder-mixed-a", "harder-mixed-b", "harder-triplet-feel"]
    key = keys[idea_variant % len(keys)]
    syms = list(_RHYTHM_PATTERNS[key])
    while len(syms) < note_count:
        syms.extend(_RHYTHM_PATTERNS[key])
    return key, syms[:note_count]


def _rhythm_for_level(level_norm: str, rng: random.Random, idea_variant: int, override: str) -> str:
    if override and override in _RHYTHM_PATTERNS:
        return override
    if level_norm == "Beginner":
        opts = ["quarter-quarter-half", "quarter-quarter-quarter"]
        return opts[idea_variant % len(opts)]
    if level_norm == "Advanced":
        opts = [
            "syncopated-four",
            "eighth-quart-eighth-eighth",
            "quarter-dotted-eighth",
            "sixteenth-run-four",
            "eighth-eighth-quarter",
        ]
        return opts[idea_variant % len(opts)]
    opts = [
        "eighth-eighth-quarter",
        "quarter-eighth-eighth",
        "eighth-quart-eighth-eighth",
        "eighth-eighth-half",
    ]
    return opts[idea_variant % len(opts)]


def generate_motif_for_chord(
    chord: str,
    *,
    key_center: str = "C",
    rhythm_key: str = "quarter-quarter-quarter",
    level: str = "Intermediate",
    rng: random.Random | None = None,
    idea_variant: int = 0,
    harder_example: bool = False,
) -> dict[str, Any]:
    """Build a motif; melodic and rhythmic complexity scale strongly with level."""
    rng = rng or random.Random(idea_variant)
    level_norm = _normalize_motif_level(level)
    tones = chord_tone_names(chord, reference_key=key_center)
    _mode, scale_pcs = _parse_key_scale(key_center)

    if harder_example:
        notes = _harder_example_notes(chord, tones, scale_pcs, rng, idea_variant)
        rhythm_key, rhythm_syms = _rhythm_for_harder(len(notes), idea_variant)
    elif level_norm == "Beginner":
        notes = _beginner_notes(tones, rng, idea_variant)
        rhythm_key = _rhythm_for_level(level_norm, rng, idea_variant, rhythm_key)
        rhythm_syms = _RHYTHM_PATTERNS.get(rhythm_key, _RHYTHM_PATTERNS["quarter-quarter-quarter"])
    elif level_norm == "Advanced":
        notes = _advanced_notes(chord, tones, scale_pcs, rng, idea_variant)
        rhythm_key = _rhythm_for_level(level_norm, rng, idea_variant, rhythm_key)
        rhythm_syms = _RHYTHM_PATTERNS.get(rhythm_key, _RHYTHM_PATTERNS["quarter-quarter-quarter"])
    else:
        notes = _intermediate_notes(chord, tones, scale_pcs, rng, idea_variant)
        rhythm_key = _rhythm_for_level(level_norm, rng, idea_variant, rhythm_key)
        rhythm_syms = _RHYTHM_PATTERNS.get(rhythm_key, _RHYTHM_PATTERNS["quarter-quarter-quarter"])

    if not harder_example:
        while len(rhythm_syms) < len(notes):
            rhythm_syms = rhythm_syms + rhythm_syms
        rhythm_syms = rhythm_syms[: len(notes)]
    rhythm = " ".join(rhythm_syms)
    tier = "Harder example" if harder_example else level_norm
    return {
        "chord": chord,
        "notes": notes,
        "display": " – ".join(notes),
        "rhythm": rhythm,
        "rhythm_key": rhythm_key,
        "midi": [_midi_from_note(n, 4) for n in notes],
        "variation_prompt": f"{tier} line on **{chord}** — vocabulary lick to internalize.",
        "harder_example": harder_example,
    }


def transform_motif(
    motif: dict[str, Any],
    operation: str,
    *,
    key_center: str = "C",
) -> dict[str, Any]:
    """Apply sequence, inversion, or rhythmic variation."""
    notes = list(motif.get("notes") or [])
    if not notes:
        return motif
    _mode, scale_pcs = _parse_key_scale(key_center)
    out_notes = notes

    if operation == "sequence_up":
        out_notes = []
        for n in notes:
            deg = _nearest_scale_degree(n, scale_pcs)
            new_pc = scale_pcs[(deg + 1) % len(scale_pcs)]
            out_notes.append(_note_from_midi(new_pc + 60))
    elif operation == "sequence_down":
        out_notes = []
        for n in notes:
            deg = _nearest_scale_degree(n, scale_pcs)
            new_pc = scale_pcs[(deg - 1) % len(scale_pcs)]
            out_notes.append(_note_from_midi(new_pc + 60))
    elif operation == "invert":
        out_notes = list(reversed(notes))
    elif operation in ("rhythmic", "change_rhythm"):
        return cycle_motif_rhythm(motif)

    op_labels = {
        "sequence_up": "Sequence up",
        "sequence_down": "Sequence down",
        "invert": "Inversion",
    }
    label = op_labels.get(operation, operation)
    return sync_motif_midi({
        "chord": motif.get("chord", ""),
        "notes": out_notes,
        "display": " – ".join(out_notes),
        "rhythm": motif.get("rhythm", "♩ ♩ ♩"),
        "rhythm_key": motif.get("rhythm_key", "quarter-quarter-quarter"),
        "variation_prompt": f"{label}: {' – '.join(out_notes)}",
        "last_transform": operation,
    })


def cycle_motif_rhythm(motif: dict[str, Any]) -> dict[str, Any]:
    """Keep the same pitches; change only rhythm (sheet music / display update)."""
    notes = list(motif.get("notes") or [])
    rk = str(motif.get("rhythm_key") or "quarter-quarter-quarter")
    order = list(RHYTHM_PATTERN_KEYS)
    try:
        idx = order.index(rk)
    except ValueError:
        idx = 0
    new_rk = order[(idx + 1) % len(order)]
    syms = _RHYTHM_PATTERNS[new_rk]
    updated = dict(motif)
    updated["notes"] = notes
    updated["display"] = " – ".join(notes)
    updated["rhythm_key"] = new_rk
    updated["rhythm"] = " ".join(syms)
    updated["midi"] = [_midi_from_note(n, 4) for n in notes]
    updated["variation_prompt"] = (
        f"Rhythm on **{motif.get('chord', '')}**: {' – '.join(notes)} · {updated['rhythm']}"
    )
    updated["last_transform"] = "change_rhythm"
    return updated


def sync_motif_midi(motif: dict[str, Any]) -> dict[str, Any]:
    """Ensure midi[] matches notes[] after any edit."""
    notes = list(motif.get("notes") or [])
    motif["notes"] = notes
    motif["display"] = " – ".join(notes)
    motif["midi"] = [_midi_from_note(n, 4) for n in notes]
    return motif


def build_motif_abc(
    motif: dict[str, Any],
    *,
    key_center: str = "C",
    bpm: int = 100,
    title: str = "Motif",
) -> str:
    """1–2 measure ABC for motif notes."""
    midis = motif.get("midi") or [_midi_from_note(n, 4) for n in motif.get("notes", [])]
    rhythm_key = motif.get("rhythm_key", "quarter-quarter-quarter")
    syms = _RHYTHM_PATTERNS.get(rhythm_key, ["♩", "♩", "♩"])
    abc_notes: list[str] = []
    for i, midi in enumerate(midis[:3]):
        sym = syms[i] if i < len(syms) else "♩"
        length = _RHYTHM_TO_ABC_LEN.get(sym, "2")
        pitch = _abc_pitch(int(midi))
        abc_notes.append(f"{pitch}{length}")
    if len(abc_notes) < 4:
        abc_notes.append("z2")
    music = " ".join(abc_notes) + " | z4 z4 |"

    key_root = normalize_root(split_chord(key_center)[0])
    k = key_root if len(key_root) == 1 or key_root in ("Ab", "Bb", "Eb", "Gb") else key_root[:1]
    if "m" in str(key_center).lower() and "maj" not in str(key_center).lower():
        k = k.lower() if k.isupper() else k

    return f"""X:1
T:{title}
M:4/4
L:1/4
Q:1/4={bpm}
K:{k}
{music}"""


def _fret_for_note(midi: int, used: set[tuple[int, int]]) -> tuple[int, int]:
    """Lowest comfortable (string_idx, fret)."""
    best: tuple[float, int, int] | None = None
    for si, open_m in enumerate(_GUITAR_OPEN):
        fret = midi - open_m
        if 0 <= fret <= 14 and (si, fret) not in used:
            score = fret + si * 1.5
            if best is None or score < best[0]:
                best = (score, si, fret)
    if best:
        return best[1], best[2]
    return 0, min(12, max(0, midi - _GUITAR_OPEN[0]))


def build_motif_guitar_tab(motif: dict[str, Any]) -> str:
    """ASCII guitar TAB for up to 3 motif notes."""
    midis = motif.get("midi") or [_midi_from_note(n, 4) for n in motif.get("notes", [])]
    placements: list[tuple[int, int]] = []
    used: set[tuple[int, int]] = set()
    for m in midis[:3]:
        si, fr = _fret_for_note(int(m), used)
        used.add((si, fr))
        placements.append((si, fr))

    width = max(12, 4 + len(placements) * 5)
    grid: list[list[str]] = [["-" for _ in range(width)] for _ in range(6)]
    for step, (si, fr) in enumerate(placements):
        col = 2 + step * 4
        if col < width:
            grid[si][col] = str(fr)
    lines = []
    for si, label in enumerate(_STRING_LABELS):
        lines.append(f"{label}|{''.join(grid[si])}|")
    return "\n".join(lines)


def build_motif_notation_abc(
    motif: dict[str, Any],
    *,
    key_center: str = "C",
    bpm: int = 100,
) -> str:
    title = f"Motif — {motif.get('chord', '')}"
    return build_motif_abc(motif, key_center=key_center, bpm=bpm, title=title)
