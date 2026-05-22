"""Short practice notation: guitar TAB (ASCII) and ABC for other instruments."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any

from music_theory import NOTE_TO_MIDI, normalize_root, split_chord, transpose_guitar_tabs

from practice_studio import (
    practice_active_section_name,
    practice_display_sections,
    practice_is_full_song,
)

# Low E → high e (for parsing 6-char tab shapes)
_STRING_LABELS_HI_TO_LO = ("e", "B", "G", "D", "A", "E")

GUITAR_SHAPES: dict[str, str] = {
    "C": "x32010",
    "Cmaj7": "x32000",
    "D": "xx0232",
    "Dm": "xx0231",
    "Dm7": "xx0211",
    "E": "022100",
    "Em": "022000",
    "Em7": "020000",
    "F": "133211",
    "Fmaj7": "1x2210",
    "G": "320003",
    "G7": "320001",
    "Gm": "355333",
    "Gm7": "353333",
    "A": "x02220",
    "Am": "x02210",
    "Am7": "x02010",
    "A7": "x02020",
    "Bb": "x13331",
    "Bbmaj7": "x13231",
    "Bbm7": "x13121",
    "Bb7": "x13131",
    "Bm": "x24432",
    "Bm7": "x24232",
    "B7": "x21202",
    "Eb": "x65343",
    "Ebmaj7": "x6534x",
    "Ab": "466544",
    "Abmaj7": "465544",
    "Dbm": "x46654",
    "Dbm7": "x46454",
    "C7": "x32310",
    "Bdim": "x2x3x0",
}


def _focus_kind(focus: str) -> str:
    f = (focus or "").lower()
    if any(t in f for t in ("rhythm", "strum", "groove", "comp", "pocket")):
        return "rhythm"
    if any(t in f for t in ("chord", "voicing", "voice", "inversion", "transition")):
        return "chords"
    if any(t in f for t in ("scale", "improv", "solo", "lick", "arpegg")):
        return "scales"
    if any(t in f for t in ("transition",)):
        return "transitions"
    return "general"


def _resolve_shape(chord: str, guitar_tabs: dict[str, str]) -> str:
    if chord in guitar_tabs:
        return guitar_tabs[chord]
    if chord in GUITAR_SHAPES:
        return GUITAR_SHAPES[chord]
    head = chord.split("/")[0]
    if head in guitar_tabs:
        return guitar_tabs[head]
    if head in GUITAR_SHAPES:
        return GUITAR_SHAPES[head]
    return "x32010"


def _frets_hi_to_lo(tab6: str) -> list[str]:
    """Six frets high e → low E."""
    s = (tab6 + "xxxxxx")[:6]
    low = list(s)
    return [low[5], low[4], low[3], low[2], low[1], low[0]]


def _chord_tones(chord: str) -> list[str]:
    head = chord.split("/")[0]
    root, suffix = split_chord(head)
    root = normalize_root(root)
    base = NOTE_TO_MIDI.get(root, 60)
    low = suffix.lower()
    if "m7b5" in low:
        intervals = [0, 3, 6, 10]
    elif "maj7" in low:
        intervals = [0, 4, 7, 11]
    elif "m7" in low and "maj" not in low:
        intervals = [0, 3, 7, 10]
    elif re.search(r"(?<![a-z])7", low) and "maj" not in low:
        intervals = [0, 4, 7, 10]
    elif "m" in low and "maj" not in low:
        intervals = [0, 3, 7]
    else:
        intervals = [0, 4, 7]
    names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    return [names[(base + i) % 12] for i in intervals[:4]]


def _abc_pitch(midi: int) -> str:
    names = ["C", "^C", "D", "^D", "E", "F", "^F", "G", "^G", "A", "^A", "B"]
    return names[midi % 12] + ("'" if midi >= 72 else "")


def _midi_from_note(name: str, octave: int = 4) -> int:
    root = normalize_root(split_chord(name)[0])
    base = NOTE_TO_MIDI.get(root, 60)
    return base + 12 * (octave - 4)


@dataclass
class NotationResult:
    format: str  # tab | abc
    title: str
    chord_labels: str
    rhythm_counts: str
    body: str
    abc: str
    num_lines: int
    instrument: str
    section: str
    focus: str
    difficulty: str


def _tab_row(label: str, cells: list[str], width: int = 14) -> str:
    body = "".join(cells)
    pad = max(0, width - len(body))
    return f"{label}|--{body}{'-' * pad}|"


def _static_grip_tab(chord: str, shape: str) -> tuple[str, str]:
    frets = _frets_hi_to_lo(shape)
    width = 12
    lines = []
    for lbl, f in zip(_STRING_LABELS_HI_TO_LO, frets):
        fret = f if f != "x" else "x"
        cells = [fret] + ["-"] * (width - 1)
        lines.append(_tab_row(lbl, cells, width))
    rhythm = "   1   +   2   +   3   +   4"
    return "\n".join(lines), rhythm


def _bossa_tab(chord: str, shape: str, difficulty: str) -> tuple[str, str]:
    frets = _frets_hi_to_lo(shape)
    bass_e = frets[5] if frets[5] not in ("x", "-") else "0"
    bass_a = frets[4] if frets[4] not in ("x", "-") else bass_e
    try:
        e2 = str(min(12, int(bass_e) + 2))
    except ValueError:
        e2 = bass_e
    if difficulty == "easy":
        e_cells = [bass_e, "-", bass_e, "-", e2, "-", bass_e, "-"]
        a_cells = ["-", bass_a, "-", "-", "-", bass_a, "-", "-"]
    else:
        e_cells = [bass_e, "-", e2, "-", bass_e, "-", e2, "-"]
        a_cells = ["-", bass_a, "-", "-", "-", bass_a, "-", "-"]
    treble = [f if f != "x" else "0" for f in frets[:4]]
    lines = [
        _tab_row("e", treble[:4] + treble[4:8] if len(treble) >= 4 else treble * 2),
        _tab_row("B", ["-"] * 8),
        _tab_row("G", ["-"] * 8),
        _tab_row("D", ["-"] * 8),
        _tab_row("A", a_cells),
        _tab_row("E", e_cells),
    ]
    rhythm = "   1   +   2   +   3   +   4   (bossa bass)"
    return "\n".join(lines), rhythm


def _arpeggio_tab(chord: str, shape: str, difficulty: str) -> tuple[str, str]:
    frets = _frets_hi_to_lo(shape)
    active = [f if f not in ("x", "-") else "0" for f in frets]
    seq = active * 2 if difficulty != "advanced" else active + active[::-1]
    width = min(16, max(8, len(seq)))
    lines = [_tab_row(lbl, (seq + ["-"] * width)[:width], width) for lbl, f in zip(_STRING_LABELS_HI_TO_LO, frets)]
    rhythm = "   p  i  m  a  (arpeggio)"
    return "\n".join(lines), rhythm


def _transition_tab(chords: list[str], shapes: list[str]) -> tuple[str, str]:
    parts = []
    rhythms = []
    for ch, sh in zip(chords[:2], shapes[:2]):
        block, rh = _static_grip_tab(ch, sh)
        parts.append(f"  [{ch}]")
        parts.append(block)
        rhythms.append(rh)
    return "\n\n".join(parts), " | ".join(rhythms)


def _guitar_line(chord: str, shape: str, focus: str, groove: str, difficulty: str, line_idx: int) -> tuple[str, str]:
    fk = _focus_kind(focus)
    if line_idx == 0 or fk == "chords":
        return _static_grip_tab(chord, shape)
    if fk == "rhythm" or "bossa" in groove.lower() or "samba" in groove.lower():
        return _bossa_tab(chord, shape, difficulty)
    if fk == "scales":
        return _arpeggio_tab(chord, shape, difficulty)
    if fk == "transitions":
        return _arpeggio_tab(chord, shape, difficulty)
    return _bossa_tab(chord, shape, difficulty) if "bossa" in groove.lower() else _static_grip_tab(chord, shape)


def _build_guitar_tab(
    *,
    chords: list[str],
    guitar_tabs: dict[str, str],
    focus: str,
    groove: str,
    difficulty: str,
    num_lines: int,
    section: str,
    song_title: str,
) -> NotationResult:
    use = chords[: max(1, min(4, num_lines))]
    if not use:
        use = ["C"]
    fk = _focus_kind(focus)
    blocks: list[str] = []
    rhythms: list[str] = []
    shapes = [_resolve_shape(c, guitar_tabs) for c in use]

    if fk == "transitions" and len(use) >= 2:
        body, rhythm = _transition_tab(use[:2], shapes[:2])
        blocks.append(body)
    else:
        for i in range(min(num_lines, len(use))):
            ch = use[i]
            sh = shapes[i]
            if i == 0:
                tab, rh = _guitar_line(ch, sh, focus, groove, difficulty, 0)
            elif fk == "rhythm":
                tab, rh = _bossa_tab(ch, sh, difficulty)
            elif fk == "scales":
                tab, rh = _arpeggio_tab(ch, sh, difficulty)
            else:
                tab, rh = _static_grip_tab(ch, sh)
            blocks.append(f"{ch}\n{tab}")
            rhythms.append(rh)

    chord_row = "  ".join(use)
    title = f"{song_title} — {section} — Guitar TAB"
    body = "\n\n".join(blocks[:num_lines])
    return NotationResult(
        format="tab",
        title=title,
        chord_labels=chord_row,
        rhythm_counts=" · ".join(rhythms[:num_lines]),
        body=body,
        abc="",
        num_lines=num_lines,
        instrument="Guitar",
        section=section,
        focus=focus,
        difficulty=difficulty,
    )


def _build_abc(
    *,
    chords: list[str],
    display_key: str,
    focus: str,
    difficulty: str,
    num_lines: int,
    section: str,
    song_title: str,
    instrument: str,
    bpm: int,
) -> NotationResult:
    use = chords[: max(2, min(8, num_lines * 2))]
    if not use:
        use = ["C"]
    fk = _focus_kind(focus)
    notes: list[str] = []
    for ch in use:
        tones = _chord_tones(ch)
        if fk == "scales":
            for t in tones:
                notes.extend([_abc_pitch(_midi_from_note(t, 4)), "2"])
        elif fk == "rhythm":
            notes.extend([_abc_pitch(_midi_from_note(tones[0], 3)), "4", "z", "4"])
            notes.extend([_abc_pitch(_midi_from_note(tones[1] if len(tones) > 1 else tones[0], 3)), "4"])
        else:
            for t in tones[:3]:
                notes.extend([_abc_pitch(_midi_from_note(t, 4)), "2"])
            notes.append("z2")

    bars_needed = num_lines
    notes_per_bar = max(4, len(notes) // bars_needed)
    bars: list[str] = []
    for i in range(0, min(len(notes), notes_per_bar * bars_needed), notes_per_bar):
        bars.append(" ".join(notes[i : i + notes_per_bar]))
    while len(bars) < bars_needed:
        bars.append("z4 z4 z4 z4")
    music = " | ".join(bars[:bars_needed]) + " |"

    key_root = normalize_root(split_chord(display_key)[0])
    k = key_root if key_root in "ABCDEFG" else "C"
    if "m" in display_key.lower() and "maj" not in display_key.lower():
        k = k.lower()

    abc = f"""X:1
T:{song_title} ({section})
M:4/4
L:1/4
Q:1/4={bpm}
K:{k}
{music}"""

    staff_lines = []
    for i, ch in enumerate(use[:num_lines]):
        tones = _chord_tones(ch)
        staff_lines.append(
            f"Bar {i + 1}  {ch}:  {'  '.join(tones)}  |  beats: 1 · 2 · 3 · 4"
        )

    return NotationResult(
        format="abc",
        title=f"{song_title} — {section} — {instrument}",
        chord_labels=" | ".join(use[:num_lines]),
        rhythm_counts="1 + 2 + 3 + 4" if fk == "rhythm" else "chord tones on beats 1 & 3",
        body="\n".join(staff_lines),
        abc=abc.strip(),
        num_lines=num_lines,
        instrument=instrument,
        section=section,
        focus=focus,
        difficulty=difficulty,
    )


def generate_practice_notation(
    *,
    song_title: str,
    artist: str,
    display_key: str,
    original_key: str,
    bpm: int,
    groove_style: str,
    instrument: str,
    focus: str,
    section_focus: str | None,
    sections: dict[str, list[str]],
    guitar_tabs: dict[str, str] | None = None,
    num_lines: int = 2,
    difficulty: str = "medium",
) -> NotationResult:
    """Up to 4 lines of TAB or ABC for the current practice setup."""
    num_lines = max(1, min(4, int(num_lines)))
    diff = (difficulty or "medium").lower()
    if diff not in ("easy", "medium", "advanced"):
        diff = "medium"

    view = practice_display_sections(sections, section_focus)
    active = practice_active_section_name(section_focus, sections)
    is_full = practice_is_full_song(section_focus)
    section_label = "Full Song" if is_full else (active or "Section")
    chords = (
        [c for chs in view.values() for c in (chs or [])]
        if is_full
        else list(view.get(active or "", []) or [])
    )
    if not chords:
        chords = ["C"]

    tabs = transpose_guitar_tabs(guitar_tabs or {}, original_key, display_key)
    inst = (instrument or "").lower()

    if "guitar" in inst:
        return _build_guitar_tab(
            chords=chords,
            guitar_tabs=tabs,
            focus=focus,
            groove=groove_style,
            difficulty=diff,
            num_lines=num_lines,
            section=section_label,
            song_title=song_title,
        )
    return _build_abc(
        chords=chords,
        display_key=display_key,
        focus=focus,
        difficulty=diff,
        num_lines=num_lines,
        section=section_label,
        song_title=song_title,
        instrument=instrument,
        bpm=bpm,
    )


def notation_tab_html(result: NotationResult) -> str:
    """Monospace TAB block for unsafe_allow_html."""
    body = html.escape(result.body)
    chords = html.escape(result.chord_labels)
    rhythm = html.escape(result.rhythm_counts)
    return f"""
<div class="notation-output notation-tab">
  <div class="notation-title">{html.escape(result.title)}</div>
  <div class="notation-chords"><strong>Chords:</strong> {chords}</div>
  <pre class="notation-tab-pre">{body}</pre>
  <div class="notation-rhythm"><strong>Counts:</strong> {rhythm}</div>
</div>
""".strip()
