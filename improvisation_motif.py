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
    "♩": "",
    "♪": "/2",
    "♬": "/4",
    "♩.": "3/2",
    "𝅗": "2",
    "z": "",
    "Z": "",
}

_RHYTHM_BEATS: dict[str, float] = {
    "♩": 1.0,
    "♪": 0.5,
    "♬": 0.25,
    "♩.": 1.5,
    "𝅗": 2.0,
    "z": 1.0,
    "Z": 1.0,
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


def concert_song_sections_from_session(session_state: dict) -> dict[str, list[str]] | None:
    """Transposed catalog progression in concert pitch (Song-Based practice key)."""
    try:
        from workflow_musical_authority import (
            custom_owns_active_song_material,
            resolve_custom_concert_sections_at_practice_key,
        )

        if custom_owns_active_song_material(session_state):
            custom_secs = resolve_custom_concert_sections_at_practice_key(session_state)
            if custom_secs:
                return custom_secs
    except ImportError:
        pass
    try:
        from backing_context import _song_improv_sections_dict

        resolved = _song_improv_sections_dict(session_state)
        if isinstance(resolved, dict) and resolved:
            try:
                from music_workflow_pending_song_practice_key_edit import (
                    overlay_sections_with_pending_practice_key,
                )
                from music_workflow_song_practice import resolve_song_practice_key_token

                spelled = resolve_song_practice_key_token(session_state) or str(
                    session_state.get("concert_key") or ""
                )
                return overlay_sections_with_pending_practice_key(
                    session_state,
                    resolved,
                    spelled_in_key=spelled,
                )
            except ImportError:
                return resolved
    except ImportError:
        pass
    raw = session_state.get("improv_song_concert_sections")
    if not isinstance(raw, dict) or not raw:
        return None
    out: dict[str, list[str]] = {}
    for key, val in raw.items():
        if isinstance(val, list):
            clean = [str(c).strip() for c in val if str(c).strip()]
            if clean:
                out[str(key)] = clean
    if not out:
        return None
    try:
        from music_workflow_pending_song_practice_key_edit import (
            overlay_sections_with_pending_practice_key,
        )
        from music_workflow_song_practice import resolve_song_practice_key_token

        spelled = resolve_song_practice_key_token(session_state) or str(
            session_state.get("concert_key") or ""
        )
        return overlay_sections_with_pending_practice_key(
            session_state,
            out,
            spelled_in_key=spelled,
        )
    except ImportError:
        return out


def resolve_improv_sections(
    session_state: dict,
    improv_ctx: Any,
) -> list[tuple[str, list[str]]]:
    """Section-based chord map (deduped) for Live Coach / Phrase Motif."""
    concert = concert_song_sections_from_session(session_state)
    if concert:
        order = list(getattr(improv_ctx, "section_order", None) or concert.keys())
        mapped = dedupe_sections_for_display(concert, section_names=order or None)
        if mapped:
            return mapped
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
    """Root, 3rd, 5th, and 7th when applicable — diatonic letter-aware spelling."""
    from music_theory import spell_chord_tones

    head = str(chord or "").strip()
    ref = str(reference_key or "").strip()
    if not ref:
        from music_theory import normalize_chord_for_theory, normalize_root, split_chord

        parsed = normalize_chord_for_theory(head).split("/")[0].strip() or head.split("/")[0].strip()
        root, _ = split_chord(parsed)
        ref = normalize_root(root) or "C"
    return spell_chord_tones(head, reference_key=ref)


def _midi_from_note(name: str, octave: int = 4) -> int:
    root = normalize_root(split_chord(str(name))[0])
    return NOTE_TO_MIDI.get(root, 60) + 12 * (octave - 4)


def _pc_of_note(name: str) -> int:
    return _midi_from_note(str(name), 4) % 12


def _nearest_midi_for_pc(pc: int, near: int) -> int:
    """Nearest MIDI with pitch class ``pc`` to ``near`` (smooth voice-leading)."""
    pc = int(pc) % 12
    near = int(near)
    base = (near // 12) * 12 + pc
    options = [base - 24, base - 12, base, base + 12, base + 24]
    return min(options, key=lambda m: abs(m - near))


def _compact_midis_from_notes(
    notes: list[str],
    *,
    anchor_midi: int | None = None,
) -> list[int]:
    """Assign midis with nearest-register voice-leading — no gratuitous octave jumps.

    Independent octave-4 assignment (e.g. B4 then C4) produced octave zigzags; motifs
    must occupy a compact register with small melodic intervals.

    First note prefers scientific octave 4 when it is within a minor third of
    mid-staff (~E4); later notes nearest-link so B4–A4–G4–A4 stays nearby.
    """
    if not notes:
        return []
    midis: list[int] = []
    prev = int(anchor_midi) if anchor_midi is not None else 64
    for i, n in enumerate(notes):
        pc = _pc_of_note(str(n))
        if i == 0 and anchor_midi is None:
            oct4 = _midi_from_note(str(n), 4)
            near = _nearest_midi_for_pc(pc, 64)
            # Prefer octave 4 when leaps-to-mid-staff are comparable (B4 over B3).
            mid = oct4 if abs(oct4 - 64) <= abs(near - 64) + 2 else near
        else:
            mid = _nearest_midi_for_pc(pc, prev)
        midis.append(mid)
        prev = mid
    return midis


def _max_leap(midis: list[int]) -> int:
    if len(midis) < 2:
        return 0
    return max(abs(int(midis[i]) - int(midis[i - 1])) for i in range(1, len(midis)))


# Comfortable staff-ish bounds for long patterns. Ascending may start below LO;
# descending may start above HI — never mid-pattern octave-reset.
_PATTERN_MIDI_LO = 53  # F3
_PATTERN_MIDI_HI = 88  # E6


def _plan_pattern_source_midis(
    notes: list[str],
    source_midis: list[int],
    *,
    key_center: str,
    collection_pcs: list[int],
    n_cells: int,
    step: int,
    sign: int,
) -> list[int]:
    """Choose starting register for the WHOLE pattern before generation.

    Ascending: start low enough so the final cell stays continuous upward.
    Descending: start high enough so the final cell stays continuous downward.
    Never repair individual notes mid-pattern.
    """
    compact = _compact_midis_from_notes(notes)
    if len(source_midis) >= len(notes):
        raw = [int(m) for m in source_midis[: len(notes)]]
        # Keep an already-compact contour. Only replace when the provided midis zigzag.
        if _max_leap(raw) > 7 and _max_leap(compact) <= _max_leap(raw):
            source = compact
        else:
            source = raw
    else:
        source = compact

    last_steps = int(sign) * int(max(0, n_cells - 1)) * int(step)
    _, last_midis = _shift_notes_by_collection_steps(
        notes,
        key_center=key_center,
        collection_pcs=collection_pcs,
        steps=last_steps,
        source_midis=source,
    )
    if not last_midis:
        return source
    overall_lo = min(min(source), min(last_midis))
    overall_hi = max(max(source), max(last_midis))
    # Octave-only shifts — never add a non-multiple of 12 (that changes pitch class
    # and sync_motif_midi then discards the planned register for cell 0).
    delta = 0
    if sign >= 0:
        # Climbing: pull the whole sequence down by octaves if the top exceeds HI.
        while overall_hi + delta > _PATTERN_MIDI_HI:
            delta -= 12
    else:
        # Falling: push the whole sequence up by octaves if the bottom goes below LO.
        while overall_lo + delta < _PATTERN_MIDI_LO:
            delta += 12
    if delta == 0:
        return source
    return [int(m) + int(delta) for m in source]


def _note_from_midi(midi: int, reference_key: str = "C") -> str:
    from music_theory import spell_note_in_key

    return spell_note_in_key(midi % 12, reference_key)


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


def _note_name_to_abc_pitch(note: str, *, octave: int = 4) -> str:
    """Spell a note name (with b or #) for ABC; respects flats like Bb."""
    text = str(note or "C").strip()
    if not text:
        return "C"
    head = text[0].upper()
    rest = text[1:]
    acc = ""
    if rest.startswith("b") or rest.startswith("♭"):
        acc = "_"
    elif rest.startswith("#") or rest.startswith("♯"):
        acc = "^"
    letter = head.lower() if octave <= 3 else head
    if octave < 4:
        letter = "," + letter
    elif octave >= 5:
        letter = letter + "'" * (octave - 4)
    return f"{acc}{letter}"


def motif_rhythm_symbols(motif: dict[str, Any]) -> list[str]:
    """Per-note rhythm symbols — single source aligned with motif['rhythm'] text."""
    stored = motif.get("rhythm_symbols")
    if isinstance(stored, list) and stored:
        syms = [str(s) for s in stored]
    else:
        syms = str(motif.get("rhythm") or "").split()
    notes = list(motif.get("notes") or [])
    if not syms:
        syms = ["♩"] * len(notes)
    while len(syms) < len(notes):
        syms = syms + syms
    return syms[: len(notes)]


def _abc_key_header(key_center: str) -> str:
    """ABC ``K:`` token from a practice/concert key center.

    Preserve accidentals and **mode**. Accidental minors must not emit bare
    ``K:Db`` / ``K:C#`` (those are major in ABC). Prefer explicit minor forms:

    - natural minors: ``c``, ``e``, … (legacy ABC lowercase)
    - accidental minors: ``C#m``, ``Dbm``, ``Ebm``, ``F#m``, …
    """
    raw = str(key_center or "C").strip() or "C"
    root, suffix = split_chord(raw)
    # Prefer the spelled root from the user/token (Db from Dbm) before enharmonic normalize.
    k = str(root or "").strip() or "C"
    if k not in CHROMATIC and normalize_root(k) in CHROMATIC:
        if "b" in k.lower() or "#" in k:
            pass
        else:
            k = normalize_root(k)
    minor = "m" in str(suffix).lower() and "maj" not in str(suffix).lower()
    if not minor and "minor" in raw.lower():
        minor = True
    if not minor:
        return k
    # Natural single-letter minors use lowercase ABC (Cm → c, Em → e).
    if len(k) == 1 and k.isupper():
        return k.lower()
    # Accidental minors must keep an explicit minor marker (Db → Dbm, not Db major).
    if k.lower().endswith("m") and len(k) > 1:
        return k
    return f"{k}m"


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


def _beginner_minimal_notes(chord_tones: list[str], *, idea_variant: int) -> list[str]:
    if len(chord_tones) >= 3:
        patterns = [
            chord_tones[:2],
            [chord_tones[0], chord_tones[2]],
            [chord_tones[0], chord_tones[1], chord_tones[0]],
        ]
        return list(patterns[idea_variant % len(patterns)])[:4]
    return chord_tones[:2] or ["C", "E"]


def _beginner_plus_notes(
    chord: str,
    chord_tones: list[str],
    scale_pcs: list[int],
    *,
    idea_variant: int,
) -> list[str]:
    """Beginner «harder»: a few more notes, one passing tone, still simple."""
    if len(chord_tones) < 2:
        chord_tones = chord_tone_names(chord)[:3]
    root = chord_tones[0]
    third = chord_tones[1] if len(chord_tones) > 1 else root
    fifth = chord_tones[2] if len(chord_tones) > 2 else _scale_step_note(scale_pcs, root, 2)
    passing = _scale_step_note(scale_pcs, third, -1)
    patterns = [
        [root, third, fifth, third],
        [root, passing, third, fifth],
        [root, third, passing, third, fifth],
        [third, root, passing, third],
        [root, third, fifth, third, root],
        [root, passing, third, third, fifth],
    ]
    return _dedupe_consecutive(list(patterns[idea_variant % len(patterns)]))[:8]


def _intermediate_plus_notes(
    chord: str,
    chord_tones: list[str],
    scale_pcs: list[int],
    rng: random.Random,
    idea_variant: int,
) -> list[str]:
    """Intermediate «harder»: richer than default intermediate, not full advanced lick."""
    advanced = _advanced_notes(chord, chord_tones, scale_pcs, rng, idea_variant)
    if len(advanced) > 11:
        return advanced[:11]
    extra = _intermediate_notes(chord, chord_tones, scale_pcs, rng, (idea_variant + 3) % 12)
    merged = _dedupe_consecutive(advanced + extra[2:4])
    return merged[:12]


def _rhythm_for_tier(
    level_norm: str,
    tier: str,
    rng: random.Random,
    idea_variant: int,
    override: str,
) -> str:
    if override and override in _RHYTHM_PATTERNS:
        return override
    tier = tier if tier in ("easier", "normal", "harder") else "normal"
    if level_norm == "Beginner":
        if tier == "easier":
            return "quarter-quarter-half"
        if tier == "harder":
            return "quarter-eighth-eighth" if idea_variant % 2 else "eighth-eighth-quarter"
        return _rhythm_for_level(level_norm, rng, idea_variant, "")
    if level_norm == "Intermediate":
        if tier == "easier":
            return "quarter-quarter-quarter"
        if tier == "harder":
            opts = ["eighth-quart-eighth-eighth", "eighth-eighth-quarter", "quarter-eighth-eighth"]
            return opts[idea_variant % len(opts)]
        return _rhythm_for_level(level_norm, rng, idea_variant, "")
    # Advanced
    if tier == "easier":
        opts = ["eighth-eighth-quarter", "quarter-eighth-eighth", "quarter-dotted-eighth"]
        return opts[idea_variant % len(opts)]
    if tier == "harder":
        return _rhythm_for_level(level_norm, rng, idea_variant, "")
    return _rhythm_for_level(level_norm, rng, idea_variant, "")


def _motif_notes_for_tier(
    chord: str,
    chord_tones: list[str],
    scale_pcs: list[int],
    level_norm: str,
    tier: str,
    rng: random.Random,
    idea_variant: int,
) -> list[str]:
    tier = tier if tier in ("easier", "normal", "harder") else "normal"
    tones = chord_tones
    if level_norm == "Beginner":
        if tier == "easier":
            return _beginner_minimal_notes(tones, idea_variant=idea_variant)
        if tier == "harder":
            return _beginner_plus_notes(chord, tones, scale_pcs, idea_variant=idea_variant)
        return _beginner_notes(tones, rng, idea_variant)
    if level_norm == "Intermediate":
        if tier == "easier":
            return _beginner_plus_notes(chord, tones, scale_pcs, idea_variant=idea_variant)
        if tier == "harder":
            return _intermediate_plus_notes(chord, tones, scale_pcs, rng, idea_variant)
        return _intermediate_notes(chord, tones, scale_pcs, rng, idea_variant)
    # Advanced
    if tier == "easier":
        notes = _advanced_notes(chord, tones, scale_pcs, rng, idea_variant)
        return notes[:10] if len(notes) > 10 else notes
    if tier == "harder":
        return _harder_example_notes(chord, tones, scale_pcs, rng, idea_variant)
    return _advanced_notes(chord, tones, scale_pcs, rng, idea_variant)


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


MOTIF_NEW_NONCE_KEY = "improv_motif_new_nonce"


def generate_motif_with_variant(
    chord: str,
    *,
    key_center: str = "C",
    level: str = "Intermediate",
    variant: str = "normal",
    session_state: dict | None = None,
    rhythm_key: str = "quarter-quarter-quarter",
) -> dict[str, Any]:
    """Shared entry for Phrase & Motif and Missions (easier / harder / new idea)."""
    variant = variant if variant in ("normal", "easier", "harder", "new") else "normal"
    tier = {"easier": "easier", "harder": "harder"}.get(variant, "normal")
    idea = 0
    seed = hash(f"{chord}|{key_center}|{level}|{variant}") % 100000
    rng = random.Random(seed)
    if variant == "new" and session_state is not None:
        idea = int(session_state.get(MOTIF_NEW_NONCE_KEY) or 0)
        session_state[MOTIF_NEW_NONCE_KEY] = idea + 1
        rng = random.Random(seed + idea * 997)
    elif variant == "harder":
        idea = (seed * 5 + 7) % 12
    return generate_motif_for_chord(
        chord,
        key_center=key_center,
        rhythm_key=rhythm_key,
        level=level,
        rng=rng,
        idea_variant=idea if variant == "new" else idea,
        difficulty_tier=tier,
    )


def generate_motif_for_chord(
    chord: str,
    *,
    key_center: str = "C",
    rhythm_key: str = "quarter-quarter-quarter",
    level: str = "Intermediate",
    rng: random.Random | None = None,
    idea_variant: int = 0,
    difficulty_tier: str = "normal",
    harder_example: bool = False,
) -> dict[str, Any]:
    """Build a motif; complexity scales with student level and easier/normal/harder tier."""
    rng = rng or random.Random(idea_variant)
    level_norm = _normalize_motif_level(level)
    tier = difficulty_tier if difficulty_tier in ("easier", "normal", "harder") else "normal"
    if harder_example and tier == "normal":
        tier = "harder"
    tones = chord_tone_names(chord, reference_key=key_center)
    _mode, scale_pcs = _parse_key_scale(key_center)

    notes = _motif_notes_for_tier(chord, tones, scale_pcs, level_norm, tier, rng, idea_variant)
    use_hard_rhythm = level_norm == "Advanced" and tier == "harder"
    if use_hard_rhythm:
        rhythm_key, rhythm_syms = _rhythm_for_harder(len(notes), idea_variant)
    else:
        rhythm_key = _rhythm_for_tier(level_norm, tier, rng, idea_variant, rhythm_key)
        rhythm_syms = list(_RHYTHM_PATTERNS.get(rhythm_key, _RHYTHM_PATTERNS["quarter-quarter-quarter"]))
        while len(rhythm_syms) < len(notes):
            rhythm_syms = rhythm_syms + rhythm_syms
        rhythm_syms = rhythm_syms[: len(notes)]

    rhythm = " ".join(rhythm_syms)
    tier_label = {"easier": "Easier", "harder": "Harder", "normal": level_norm}.get(tier, level_norm)
    motif: dict[str, Any] = {
        "chord": chord,
        "notes": list(notes),
        "display": " – ".join(notes),
        "rhythm": rhythm,
        "rhythm_key": rhythm_key,
        "rhythm_symbols": list(rhythm_syms),
        "midi": _compact_midis_from_notes(list(notes)),
        "variation_prompt": f"{tier_label} example on **{chord}** — practice in time with the backing.",
        "difficulty_tier": tier,
        "student_level": level_norm,
        "harder_example": use_hard_rhythm,
    }
    try:
        from harmonic_spelling import apply_motif_chord_spelling

        apply_motif_chord_spelling(motif, chord, song_display_key=key_center)
    except ImportError:
        from music_theory import respell_notes_for_key

        motif["notes"] = respell_notes_for_key(list(notes), key_center)
        motif["display"] = " – ".join(motif["notes"])
    # Spelling may change note names — re-bind compact register to final names.
    motif["midi"] = _compact_midis_from_notes(list(motif.get("notes") or []))
    motif["display"] = " – ".join(list(motif.get("notes") or []))
    return motif


PATTERN_TYPES = (
    "auto",
    "diatonic",
    "scalar",
    "thirds",
    "fourths",
    "pentatonic",
)
PATTERN_DIRECTIONS = ("ascending", "descending")
PATTERN_LENGTHS = (8, 12, 16)


def _pitch_collection_pcs(key_center: str, pattern_type: str) -> list[int]:
    """Pitch classes for motif-pattern sequencing."""
    _mode, diatonic = _parse_key_scale(key_center)
    ptype = str(pattern_type or "auto").strip().lower()
    if ptype in ("pentatonic",):
        root_pc = diatonic[0]
        if _mode == "minor":
            intervals = (0, 3, 5, 7, 10)
        else:
            intervals = (0, 2, 4, 7, 9)
        return [(root_pc + i) % 12 for i in intervals]
    return list(diatonic)


def _pattern_step_size(pattern_type: str) -> int:
    ptype = str(pattern_type or "auto").strip().lower()
    if ptype in ("thirds",):
        return 2
    if ptype in ("fourths",):
        return 3
    # auto / diatonic / scalar / pentatonic → one collection degree per cell
    return 1


def _shift_notes_by_collection_steps(
    notes: list[str],
    *,
    key_center: str,
    collection_pcs: list[int],
    steps: int,
    source_midis: list[int] | None = None,
) -> tuple[list[str], list[int]]:
    """Shift each motif note by collection degrees with continuous register.

    ``steps == 0`` returns the exact source notes/midis — never snap non-diatonic
    tones (e.g. B in Fm) to a nearest scale degree.

    For ``steps != 0``, every note walks the same number of collection steps in
    actual sounding register (no isolated octave wrap). Callers must pass a
    globally planned compact ``source_midis`` so the whole motif moves as a unit.
    """
    if not notes:
        return [], []
    if source_midis is None or len(source_midis) < len(notes):
        source_midis = _compact_midis_from_notes(notes)
    else:
        source_midis = [int(m) for m in source_midis[: len(notes)]]

    if not collection_pcs or int(steps or 0) == 0:
        return list(notes), list(source_midis)

    out: list[str] = []
    out_midi: list[int] = []
    direction = 1 if steps > 0 else -1
    for i, n in enumerate(notes):
        midi = int(source_midis[i])
        deg = _nearest_scale_degree(str(n), collection_pcs)
        idx = deg
        for _ in range(abs(int(steps))):
            next_idx = (idx + direction) % len(collection_pcs)
            next_pc = collection_pcs[next_idx]
            if direction > 0:
                candidate = (midi // 12) * 12 + next_pc
                if candidate <= midi:
                    candidate += 12
            else:
                candidate = (midi // 12) * 12 + next_pc
                if candidate >= midi:
                    candidate -= 12
            midi = candidate
            idx = next_idx
        out.append(_note_from_midi(midi, key_center))
        out_midi.append(midi)
    from music_theory import respell_notes_for_key

    return respell_notes_for_key(out, key_center), out_midi


def _format_pattern_display(cells: list[list[str]]) -> str:
    return " | ".join(" – ".join(cell) for cell in cells if cell)


def build_motif_pattern(
    motif: dict[str, Any],
    *,
    key_center: str = "C",
    pattern_type: str = "auto",
    direction: str = "ascending",
    length: int = 8,
) -> dict[str, Any]:
    """Expand the current motif into a longer practice pattern (first cell = motif).

    Register is planned globally before generation: ascending starts low enough,
    descending starts high enough, and cells climb/fall continuously with no
    mid-pattern octave reset. Cell 1 preserves exact source pitch classes.
    """
    base_notes = list(motif.get("base_motif_notes") or motif.get("notes") or [])
    if not base_notes:
        return dict(motif)
    ptype = str(pattern_type or "auto").strip().lower()
    if ptype not in PATTERN_TYPES:
        ptype = "auto"
    direction_norm = str(direction or "ascending").strip().lower()
    if direction_norm not in PATTERN_DIRECTIONS:
        direction_norm = "ascending"
    try:
        n_cells = int(length)
    except (TypeError, ValueError):
        n_cells = 8
    if n_cells not in PATTERN_LENGTHS:
        n_cells = 8 if n_cells < 10 else (12 if n_cells < 14 else 16)

    collection = _pitch_collection_pcs(key_center, ptype)
    step = _pattern_step_size(ptype)
    sign = 1 if direction_norm == "ascending" else -1
    raw_midis = list(motif.get("midi") or [])
    source_midis = _plan_pattern_source_midis(
        base_notes,
        [int(m) for m in raw_midis[: len(base_notes)]] if len(raw_midis) >= len(base_notes) else [],
        key_center=key_center,
        collection_pcs=collection,
        n_cells=n_cells,
        step=step,
        sign=sign,
    )
    cells: list[list[str]] = []
    cell_midis: list[list[int]] = []
    for i in range(n_cells):
        cell_notes, cell_ms = _shift_notes_by_collection_steps(
            base_notes,
            key_center=key_center,
            collection_pcs=collection,
            steps=sign * i * step,
            source_midis=source_midis,
        )
        cells.append(cell_notes)
        cell_midis.append(cell_ms)
    flat = [n for cell in cells for n in cell]
    flat_midi = [m for cell in cell_midis for m in cell]
    cell_len = max(1, len(base_notes))
    base_rk = str(motif.get("rhythm_key") or "quarter-quarter-quarter")
    base_syms = list(motif.get("rhythm_symbols") or _RHYTHM_PATTERNS.get(base_rk, ["♩"] * cell_len))
    while len(base_syms) < cell_len:
        base_syms = base_syms + base_syms
    base_syms = base_syms[:cell_len]
    rhythm_syms: list[str] = []
    for _ in range(n_cells):
        rhythm_syms.extend(base_syms)
    rhythm_syms = rhythm_syms[: len(flat)]

    out = dict(motif)
    out.update(
        {
            "chord": motif.get("chord", ""),
            "notes": flat,
            "cells": cells,
            "display": _format_pattern_display(cells),
            "rhythm": " ".join(rhythm_syms),
            "rhythm_key": base_rk,
            "rhythm_symbols": rhythm_syms,
            "is_pattern": True,
            "pattern_type": ptype,
            "pattern_direction": direction_norm,
            "pattern_length": n_cells,
            "base_motif_notes": list(base_notes),
            "base_motif_midi": list(source_midis),
            "midi": flat_midi,
            "variation_prompt": (
                f"Pattern ({ptype}, {direction_norm}, {n_cells} cells) on "
                f"**{motif.get('chord', '')}**"
            ),
            "last_transform": "build_pattern",
        }
    )
    return sync_motif_midi(out)


def rebuild_motif_pattern(
    motif: dict[str, Any],
    *,
    key_center: str = "C",
    pattern_type: str | None = None,
    direction: str | None = None,
    length: int | None = None,
) -> dict[str, Any]:
    """Rebuild pattern pitches from stored base motif; preserve rhythm when possible."""
    if not motif.get("is_pattern") and not motif.get("base_motif_notes"):
        return build_motif_pattern(
            motif,
            key_center=key_center,
            pattern_type=pattern_type or "auto",
            direction=direction or "ascending",
            length=length or 8,
        )
    preserved_rk = str(motif.get("rhythm_key") or "quarter-quarter-quarter")
    base_notes = list(motif.get("base_motif_notes") or motif.get("notes") or [])
    # Prefer planned first-cell midis; fall back to flat pattern head.
    flat_midi = list(motif.get("base_motif_midi") or motif.get("midi") or [])
    base_midi = (
        [int(m) for m in flat_midi[: len(base_notes)]]
        if len(flat_midi) >= len(base_notes)
        else []
    )
    seed: dict[str, Any] = {
        "chord": motif.get("chord", ""),
        "notes": list(base_notes),
        "base_motif_notes": list(base_notes),
        "rhythm_key": preserved_rk,
        "rhythm_symbols": list(motif.get("rhythm_symbols") or [])[: len(base_notes)],
    }
    if base_midi:
        seed["midi"] = base_midi
    rebuilt = build_motif_pattern(
        seed,
        key_center=key_center,
        pattern_type=pattern_type or str(motif.get("pattern_type") or "auto"),
        direction=direction or str(motif.get("pattern_direction") or "ascending"),
        length=length if length is not None else int(motif.get("pattern_length") or 8),
    )
    # Re-apply current rhythm key across full flat notes (pitches already rebuilt).
    return _apply_rhythm_key(rebuilt, preserved_rk)


def _apply_rhythm_key(motif: dict[str, Any], rhythm_key: str) -> dict[str, Any]:
    notes = list(motif.get("notes") or [])
    rk = str(rhythm_key or "quarter-quarter-quarter")
    syms = list(_RHYTHM_PATTERNS.get(rk, _RHYTHM_PATTERNS["quarter-quarter-quarter"]))
    while len(syms) < len(notes):
        syms = syms + syms
    syms = syms[: len(notes)]
    updated = dict(motif)
    updated["rhythm_key"] = rk
    updated["rhythm"] = " ".join(syms)
    updated["rhythm_symbols"] = syms
    return sync_motif_midi(updated)


def _invert_around_first_note(
    notes: list[str],
    source_midis: list[int],
    *,
    key_center: str,
) -> tuple[list[str], list[int]]:
    """Invert intervals around the first MIDI pitch (canonical motif pivot).

    ``out[i] = 2 * pivot - in[i]``. Note names are re-spelled in ``key_center``.
    """
    if not notes or not source_midis:
        return list(notes), list(source_midis)
    pivot = int(source_midis[0])
    out_midis = [2 * pivot - int(m) for m in source_midis[: len(notes)]]
    out_notes = [_note_from_midi(m, key_center) for m in out_midis]
    return out_notes, out_midis


def transform_motif(
    motif: dict[str, Any],
    operation: str,
    *,
    key_center: str = "C",
) -> dict[str, Any]:
    """Apply sequence, inversion, or rhythmic variation (whole pattern when expanded)."""
    notes = list(motif.get("notes") or [])
    if not notes:
        return motif
    _mode, scale_pcs = _parse_key_scale(key_center)
    out_notes = notes

    source_midis = list(motif.get("midi") or [])
    if len(source_midis) < len(notes):
        source_midis = [_midi_from_note(n, 4) for n in notes]
    else:
        source_midis = [int(m) for m in source_midis[: len(notes)]]
    out_midis: list[int] | None = None

    if operation == "sequence_up":
        out_notes, out_midis = _shift_notes_by_collection_steps(
            notes,
            key_center=key_center,
            collection_pcs=scale_pcs,
            steps=1,
            source_midis=source_midis,
        )
    elif operation == "sequence_down":
        out_notes, out_midis = _shift_notes_by_collection_steps(
            notes,
            key_center=key_center,
            collection_pcs=scale_pcs,
            steps=-1,
            source_midis=source_midis,
        )
    elif operation == "invert":
        # Melodic inversion around the first note (documented pivot).
        # Interval from pivot to each later pitch is negated; order, count,
        # and rhythm stay the same. This is not a retrograde (reverse).
        out_notes, out_midis = _invert_around_first_note(
            notes,
            source_midis,
            key_center=key_center,
        )
    elif operation in ("rhythmic", "change_rhythm"):
        return cycle_motif_rhythm(motif)

    op_labels = {
        "sequence_up": "Sequence up",
        "sequence_down": "Sequence down",
        "invert": "Inversion",
    }
    label = op_labels.get(operation, operation)
    from music_theory import respell_notes_for_key

    out_notes = respell_notes_for_key(out_notes, key_center)
    updated = {
        "chord": motif.get("chord", ""),
        "notes": out_notes,
        "display": " – ".join(out_notes),
        "rhythm": motif.get("rhythm", "♩ ♩ ♩"),
        "rhythm_key": motif.get("rhythm_key", "quarter-quarter-quarter"),
        "rhythm_symbols": list(motif.get("rhythm_symbols") or []),
        "variation_prompt": f"{label}: {' – '.join(out_notes)}",
        "last_transform": operation,
        "is_pattern": bool(motif.get("is_pattern")),
        "pattern_type": motif.get("pattern_type"),
        "pattern_direction": motif.get("pattern_direction"),
        "pattern_length": motif.get("pattern_length"),
        "base_motif_notes": list(motif.get("base_motif_notes") or []),
        "cells": list(motif.get("cells") or []),
    }
    if out_midis is not None:
        updated["midi"] = out_midis
    # Keep pattern cell structure aligned after whole-pattern pitch shift.
    if updated["is_pattern"] and updated["base_motif_notes"]:
        cell_len = max(1, len(updated["base_motif_notes"]))
        cells = [out_notes[i : i + cell_len] for i in range(0, len(out_notes), cell_len)]
        updated["cells"] = cells
        updated["display"] = _format_pattern_display(cells)
        # Shift stored base motif with the same operation so rebuild stays coherent.
        base = list(motif.get("base_motif_notes") or [])
        base_midis = list(motif.get("midi") or [])[: len(base)]
        if len(base_midis) < len(base):
            base_midis = [_midi_from_note(n, 4) for n in base]
        if operation == "sequence_up":
            updated["base_motif_notes"], _ = _shift_notes_by_collection_steps(
                base,
                key_center=key_center,
                collection_pcs=scale_pcs,
                steps=1,
                source_midis=base_midis,
            )
        elif operation == "sequence_down":
            updated["base_motif_notes"], _ = _shift_notes_by_collection_steps(
                base,
                key_center=key_center,
                collection_pcs=scale_pcs,
                steps=-1,
                source_midis=base_midis,
            )
        elif operation == "invert":
            updated["base_motif_notes"], _ = _invert_around_first_note(
                base,
                base_midis,
                key_center=key_center,
            )
    return sync_motif_midi(updated)


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
    while len(syms) < len(notes):
        syms = syms + syms
    syms = syms[: len(notes)]
    updated = dict(motif)
    updated["notes"] = notes
    cells = updated.get("cells")
    if updated.get("is_pattern") and isinstance(cells, list) and cells:
        updated["display"] = _format_pattern_display(cells)
    else:
        updated["display"] = " – ".join(notes)
    updated["rhythm_key"] = new_rk
    updated["rhythm"] = " ".join(syms)
    updated["rhythm_symbols"] = syms[: len(notes)]
    # Durations only — never flatten register to octave 4.
    existing = list(motif.get("midi") or [])
    if len(existing) >= len(notes):
        updated["midi"] = [int(m) for m in existing[: len(notes)]]
    updated["variation_prompt"] = (
        f"Rhythm on **{motif.get('chord', '')}**: {updated['display']} · {updated['rhythm']}"
    )
    updated["last_transform"] = "change_rhythm"
    return sync_motif_midi(updated)


def sync_motif_midi(motif: dict[str, Any]) -> dict[str, Any]:
    """Ensure midi[], display, and rhythm_symbols match notes[] after any edit.

    Prefer existing midi when pitch class matches — register-aware transforms
    (pattern ascend/descend, sequence up/down) must not be flattened to octave 4.
    """
    notes = list(motif.get("notes") or [])
    motif["notes"] = notes
    cells = motif.get("cells")
    if motif.get("is_pattern") and isinstance(cells, list) and cells:
        motif["display"] = _format_pattern_display(cells)
    else:
        motif["display"] = " – ".join(notes)
    existing = list(motif.get("midi") or [])
    midis: list[int] = []
    prev: int | None = None
    for i, n in enumerate(notes):
        target_pc = _midi_from_note(str(n), 4) % 12
        if (
            i < len(existing)
            and isinstance(existing[i], (int, float))
            and int(existing[i]) % 12 == target_pc
        ):
            mid = int(existing[i])
        elif prev is not None:
            mid = _nearest_midi_for_pc(target_pc, prev)
        else:
            mid = _nearest_midi_for_pc(target_pc, 64)
        midis.append(mid)
        prev = mid
    motif["midi"] = midis
    stored = motif.get("rhythm_symbols")
    if isinstance(stored, list) and stored and any(str(s) in ("z", "Z") for s in stored):
        motif["rhythm_symbols"] = [str(s) for s in stored]
        motif["rhythm"] = " ".join(motif["rhythm_symbols"])
        return motif
    syms = motif_rhythm_symbols(motif)
    motif["rhythm_symbols"] = syms
    motif["rhythm"] = " ".join(syms)
    return motif


def build_motif_abc(
    motif: dict[str, Any],
    *,
    key_center: str = "C",
    bpm: int = 100,
    title: str = "Motif",
) -> str:
    """ABC for the full motif — every note and rhythm symbol from the motif dict."""
    notes = list(motif.get("notes") or [])
    midis = list(motif.get("midi") or [])
    if len(midis) < len(notes):
        midis = list(sync_motif_midi(dict(motif)).get("midi") or [])
    if len(midis) < len(notes):
        midis = [_midi_from_note(n, 4) for n in notes]
    else:
        midis = [int(m) for m in midis[: len(notes)]]
    syms = motif_rhythm_symbols(motif)

    abc_tokens: list[str] = []
    beats_in_bar = 0.0
    note_idx = 0
    for sym in syms:
        length = _RHYTHM_TO_ABC_LEN.get(sym, "")
        if sym in ("z", "Z"):
            abc_tokens.append(f"z{length}")
        else:
            if note_idx >= len(notes):
                break
            # Scientific octave from MIDI so sheet music follows register-aware patterns.
            sci_oct = int(midis[note_idx]) // 12 - 1
            pitch = _note_name_to_abc_pitch(str(notes[note_idx]), octave=sci_oct)
            abc_tokens.append(f"{pitch}{length}")
            note_idx += 1
        beats_in_bar += _RHYTHM_BEATS.get(sym, 1.0)
        if beats_in_bar >= 4.0 - 1e-6:
            abc_tokens.append("|")
            beats_in_bar = 0.0

    if beats_in_bar > 0 and abc_tokens and abc_tokens[-1] != "|":
        abc_tokens.append("|")

    music = " ".join(abc_tokens)
    ref_key = str(key_center or motif.get("spelling_reference") or "C").strip() or "C"
    k = _abc_key_header(ref_key)

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
    """ASCII guitar TAB for all motif notes (same order as notation)."""
    midis = motif.get("midi") or [_midi_from_note(n, 4) for n in motif.get("notes", [])]
    placements: list[tuple[int, int]] = []
    used: set[tuple[int, int]] = set()
    for m in midis:
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
