"""Motif generation, transformations, ABC notation, and guitar TAB for Improvisation Intelligence."""

from __future__ import annotations

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
    "eighth-eighth-quarter": ["♪", "♪", "♩"],
    "quarter-eighth-eighth": ["♩", "♪", "♪"],
    "quarter-dotted-eighth": ["♩", "♩.", "♪"],
}

_RHYTHM_TO_ABC_LEN: dict[str, str] = {
    "♩": "2",
    "♪": "/2",
    "♩.": "3",
}


def _section_base_key(name: str) -> str:
    """Normalize section labels for deduplication (Verse 2 → verse, etc.)."""
    n = str(name or "").strip()
    n = re.sub(r"\s*\(repeat\)\s*$", "", n, flags=re.I)
    n = re.sub(r"\s*\(alternate\)\s*$", "", n, flags=re.I)
    n = re.sub(r"\s*\(\d+\)\s*$", "", n)
    n = re.sub(r"\s+\d+$", "", n)
    return n.lower()


def _display_section_label(name: str) -> str:
    """Short, readable section heading for the chord map."""
    n = str(name or "").strip()
    aliases = {
        "a section": "A",
        "b section": "B",
        "final a / outro": "Outro",
        "final a / tag": "Outro",
        "coda": "Outro",
    }
    return aliases.get(n.lower(), n)


def dedupe_sections_for_display(
    sections: dict[str, list[str]],
) -> list[tuple[str, list[str]]]:
    """
    One row per unique section identity — skip repeated Verse/Chorus blocks
  with identical chords; keep alternates when harmony differs.
    """
    seen: dict[str, tuple[str, ...]] = {}
    out: list[tuple[str, list[str]]] = []
    for name, chords in section_order(sections):
        clean = [str(c).strip() for c in (chords or []) if c and str(c).strip()]
        if not clean:
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
        mapped = dedupe_sections_for_display(improv_ctx.sections)
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


def resolve_improv_chords(session_state: dict, improv_ctx: Any) -> list[str]:
    """Flat chord list (deduped sections) for next-chord / legacy helpers."""
    return flatten_section_map(resolve_improv_sections(session_state, improv_ctx))


def chord_tone_names(chord: str) -> list[str]:
    """Root, 3rd, 5th, and 7th when applicable."""
    head = str(chord).split("/")[0].strip()
    root, suffix = split_chord(head)
    root = normalize_root(root)
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
    names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    return [names[(base + i) % 12] for i in intervals[:4]]


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


def generate_motif_for_chord(
    chord: str,
    *,
    key_center: str = "C",
    rhythm_key: str = "quarter-quarter-quarter",
) -> dict[str, Any]:
    """Build a 3-note motif from chord tones."""
    tones = chord_tone_names(chord)
    notes = tones[:3] if len(tones) >= 3 else (tones + ["C", "E", "G"])[:3]
    rhythm_syms = _RHYTHM_PATTERNS.get(rhythm_key, _RHYTHM_PATTERNS["quarter-quarter-quarter"])
    rhythm = " ".join(rhythm_syms)
    return {
        "chord": chord,
        "notes": notes,
        "display": " – ".join(notes),
        "rhythm": rhythm,
        "rhythm_key": rhythm_key,
        "midi": [_midi_from_note(n, 4) for n in notes],
        "variation_prompt": f"Motif on **{chord}**: {' – '.join(notes)}",
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
    elif operation == "rhythmic":
        rk = motif.get("rhythm_key", "quarter-quarter-quarter")
        order = list(_RHYTHM_PATTERNS.keys())
        try:
            idx = order.index(rk)
        except ValueError:
            idx = 0
        new_rk = order[(idx + 1) % len(order)]
        updated = dict(motif)
        updated["rhythm_key"] = new_rk
        updated["rhythm"] = " ".join(_RHYTHM_PATTERNS[new_rk])
        updated["variation_prompt"] = (
            f"Rhythmic variation on **{motif.get('chord', '')}**: "
            f"{' – '.join(notes)} · {updated['rhythm']}"
        )
        return updated

    op_labels = {
        "sequence_up": "Sequence up",
        "sequence_down": "Sequence down",
        "invert": "Inversion",
    }
    label = op_labels.get(operation, operation)
    return {
        "chord": motif.get("chord", ""),
        "notes": out_notes,
        "display": " – ".join(out_notes),
        "rhythm": motif.get("rhythm", "♩ ♩ ♩"),
        "rhythm_key": motif.get("rhythm_key", "quarter-quarter-quarter"),
        "midi": [_midi_from_note(n, 4) for n in out_notes],
        "variation_prompt": f"{label}: {' – '.join(out_notes)}",
        "last_transform": operation,
    }


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
