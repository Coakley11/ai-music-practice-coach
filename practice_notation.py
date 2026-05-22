"""Short practice notation: guitar TAB (lesson-style HTML) and ABC for other instruments."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any

from music_theory import NOTE_TO_MIDI, normalize_root, split_chord, transpose_guitar_tabs

from practice_studio import (
    practice_active_section_name,
    practice_display_sections,
    practice_is_full_song,
)

_STRING_LABELS_HI_TO_LO = ("e", "B", "G", "D", "A", "E")
_BEATS = 4
_BEAT_WIDTH = 7  # chars per beat in plain-text export

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


@dataclass
class NotationResult:
    format: str
    title: str
    chord_labels: str
    rhythm_counts: str
    body: str
    html: str = ""
    abc: str = ""
    practice_cues: list[str] = field(default_factory=list)
    num_lines: int = 2
    instrument: str = ""
    section: str = ""
    focus: str = ""
    difficulty: str = ""


def _focus_kind(focus: str) -> str:
    f = (focus or "").lower()
    if any(t in f for t in ("rhythm", "strum", "comp", "groove", "pocket")):
        return "rhythm"
    if any(t in f for t in ("transition",)):
        return "transitions"
    if any(t in f for t in ("chord", "voicing", "voice", "inversion")):
        return "chords"
    if any(t in f for t in ("scale", "improv", "solo", "lick", "arpegg", "finger")):
        return "scales"
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


def _groove_pattern(groove: str, focus_kind: str) -> dict[str, Any]:
    g = (groove or "").lower()
    if "bossa" in g or "samba" in g:
        return {
            "name": "Bossa / samba",
            "counts": ["1", "&", "2", "&", "3", "&", "4", "&"],
            "strum": ["·", "↓", "·", "↑", "·", "↓", "·", "↑"],
            "pattern": "bossa",
            "finger": None,
        }
    if "funk" in g:
        return {
            "name": "Funk pocket",
            "counts": ["1", "&", "2", "&", "3", "&", "4", "&"],
            "strum": ["↓", "×", "↓", "·", "↓", "×", "↓", "·"],
            "pattern": "funk",
            "finger": None,
        }
    if "ballad" in g:
        return {
            "name": "Ballad arpeggio",
            "counts": ["1", "·", "2", "·", "3", "·", "4", "·"],
            "strum": ["p", "·", "i", "·", "m", "·", "a", "·"],
            "pattern": "fingerstyle",
            "finger": ["p", "i", "m", "a"],
        }
    if any(t in (focus_kind, "") for t in ("scales",)) or "finger" in g:
        return {
            "name": "Fingerstyle",
            "counts": ["1", "·", "2", "·", "3", "·", "4", "·"],
            "strum": ["p", "i", "m", "a", "·", "·", "·", "·"],
            "pattern": "fingerstyle",
            "finger": ["p", "i", "m", "a"],
        }
    return {
        "name": "Pop / rock strum",
        "counts": ["1", "&", "2", "&", "3", "&", "4", "&"],
        "strum": ["↓", "↑", "↓", "↑", "↓", "↑", "↓", "↑"],
        "pattern": "pop",
        "finger": None,
    }


def _plain_beat(fret: str | None) -> str:
    if not fret or fret in ("-", "x"):
        return "-" * _BEAT_WIDTH
    f = str(fret)[:2]
    mid = _BEAT_WIDTH // 2
    return ("-" * (mid - 1) + f + "-" * (_BEAT_WIDTH - mid - len(f))).ljust(_BEAT_WIDTH, "-")[:_BEAT_WIDTH]


def _plain_string_line(label: str, beats: list[str | None]) -> str:
    cells = "".join(_plain_beat(b) for b in beats)
    return f"{label}|{cells}|"


def _html_beat_cell(fret: str | None, *, highlight: bool = False, muted: bool = False) -> str:
    cls = "tab-beat"
    if highlight:
        cls += " tab-beat-hi"
    if muted:
        cls += " tab-beat-muted"
    if not fret or fret == "-":
        inner = "·"
    elif fret == "x":
        inner = "×"
    else:
        inner = html.escape(str(fret))
        cls += " tab-beat-fret"
    return f'<span class="{cls}">{inner}</span>'


def _html_row(label: str, cells: list[str], *, row_class: str = "") -> str:
    parts = "".join(cells)
    rc = f" {row_class}" if row_class else ""
    return (
        f'<div class="tab-string-line{rc}">'
        f'<span class="tab-str-label">{html.escape(label)}</span>'
        f'<span class="tab-str-track">{parts}</span></div>'
    )


def _bossa_bass_beats(shape_frets: list[str], beats: int = 8) -> tuple[list[str | None], list[str | None]]:
    bass_e = shape_frets[5] if shape_frets[5] not in ("x", "-") else "0"
    bass_a = shape_frets[4] if shape_frets[4] not in ("x", "-") else bass_e
    try:
        e2 = str(min(12, int(bass_e) + 2))
    except ValueError:
        e2 = bass_e
    e_seq: list[str | None] = [bass_e, None, e2, None, bass_e, None, e2, None][:beats]
    a_seq: list[str | None] = [None, bass_a, None, None, None, bass_a, None, None][:beats]
    return e_seq, a_seq


def _measure_beats(
    shape_frets: list[str],
    groove_info: dict[str, Any],
    focus_kind: str,
    *,
    highlight_mask: list[bool] | None = None,
) -> dict[str, list[str | None]]:
    """Per string, list of fret values per eighth-note slot (8 slots = 4 beats)."""
    n = 8
    grip = [None if f in ("x", "-") else f for f in shape_frets]
    pat = groove_info["pattern"]
    out: dict[str, list[str | None]] = {s: [None] * n for s in _STRING_LABELS_HI_TO_LO}

    if pat == "bossa" and focus_kind in ("rhythm", "general", "chords"):
        e_seq, a_seq = _bossa_bass_beats(shape_frets, n)
        out["E"] = e_seq
        out["A"] = a_seq
        for si, lbl in enumerate(_STRING_LABELS_HI_TO_LO[:4]):
            out[lbl] = [grip[si]] * n
    elif pat == "fingerstyle" or focus_kind == "scales":
        order = [0, 1, 2, 3]
        for beat_i in range(_BEATS):
            for j, si in enumerate(order):
                idx = beat_i * 2
                if idx < n and grip[si] not in (None,):
                    out[_STRING_LABELS_HI_TO_LO[si]][idx] = grip[si]
    elif focus_kind == "transitions":
        for si, lbl in enumerate(_STRING_LABELS_HI_TO_LO):
            out[lbl] = [grip[si]] * n
    else:
        for si, lbl in enumerate(_STRING_LABELS_HI_TO_LO):
            out[lbl] = [grip[si]] * n

    if highlight_mask:
        for lbl in _STRING_LABELS_HI_TO_LO:
            for i in range(n):
                if highlight_mask[min(i, len(highlight_mask) - 1)]:
                    pass  # applied in html cell renderer
    return out


def _diff_mask(a: list[str], b: list[str]) -> list[bool]:
    return [fa != fb for fa, fb in zip(a, b)]


def _render_measure_html(
    *,
    chord: str,
    shape: str,
    bar_index: int,
    groove_info: dict[str, Any],
    focus_kind: str,
    highlight_strings: set[str] | None = None,
    transition_prev_shape: str | None = None,
) -> str:
    frets = _frets_hi_to_lo(shape)
    prev_frets = _frets_hi_to_lo(transition_prev_shape) if transition_prev_shape else None
    string_beats = _measure_beats(frets, groove_info, focus_kind)
    counts = groove_info["counts"]
    strum = groove_info["strum"]

    count_cells = "".join(f'<span class="tab-count-cell">{html.escape(c)}</span>' for c in counts)
    strum_cells = "".join(
        f'<span class="tab-strum-cell{" tab-strum-accent" if s in ("↓", "D") else ""}">{html.escape(s)}</span>'
        for s in strum
    )

    lines_html = []
    for lbl in _STRING_LABELS_HI_TO_LO:
        hi_row = highlight_strings and lbl in highlight_strings
        cells = []
        beats = string_beats[lbl]
        prev_beats = None
        if prev_frets:
            prev_map = _measure_beats(_frets_hi_to_lo(transition_prev_shape), groove_info, focus_kind)
            prev_beats = prev_map.get(lbl, [])
        for i, fret in enumerate(beats):
            hi = hi_row
            if prev_beats and i < len(prev_beats) and prev_beats[i] != fret and fret not in (None,):
                hi = True
            cells.append(_html_beat_cell(fret, highlight=bool(hi), muted=fret is None))
        lines_html.append(_html_row(lbl, cells, row_class="tab-str-low" if lbl == "E" else ""))

    plain_lines = []
    for lbl in _STRING_LABELS_HI_TO_LO:
        plain_lines.append(_plain_string_line(lbl, string_beats[lbl]))

    transition_badge = ""
    if transition_prev_shape:
        transition_badge = (
            f'<span class="tab-transition-badge">change → {html.escape(chord)}</span>'
        )

    measure_cls = "tab-measure"
    if transition_prev_shape:
        measure_cls += " tab-measure-transition"

    block = f"""
<div class="{measure_cls}">
  <div class="tab-measure-head">
    <span class="tab-chord-name">{html.escape(chord)}</span>
    <span class="tab-bar-label">bar {bar_index}</span>
    {transition_badge}
  </div>
  <div class="tab-count-row">{count_cells}</div>
  <div class="tab-strum-row" title="{html.escape(groove_info['name'])}">{strum_cells}</div>
  {''.join(lines_html)}
</div>
"""
    count_plain = "   " + " ".join(f"{c:>3}" for c in counts[:8])
    strum_plain = "   " + " ".join(f"{s:>3}" for s in strum[:8])
    plain = (
        f"   {chord}\n"
        f"{count_plain}\n"
        f"{strum_plain}\n"
        + "\n".join(plain_lines)
    )
    return block, plain


def _tab_legend_html() -> str:
    return """
<div class="tab-legend">
  <span class="tab-legend-title">How to read this TAB</span>
  <ul class="tab-legend-list">
    <li><strong>Numbers</strong> = fret to press</li>
    <li><strong>Top line (e)</strong> = thin high E string</li>
    <li><strong>Bottom line (E)</strong> = thick low E string</li>
    <li><strong>Read left → right</strong> in time</li>
    <li><strong>Stacked vertically</strong> = play together</li>
    <li><span class="tab-strum-cell tab-strum-accent">↓</span> down · <span class="tab-strum-cell">↑</span> up · <span class="tab-beat-muted">×</span> mute</li>
  </ul>
</div>
"""


def _practice_cues(
    *,
    chords: list[str],
    section: str,
    focus: str,
    focus_kind: str,
    bpm: int,
    difficulty: str,
    groove_info: dict[str, Any],
) -> list[str]:
    slow = max(45, int(bpm * 0.7))
    cues = [
        f"Section: {section} only",
        f"Groove: {groove_info['name']}",
        f"Practice slowly at {slow} BPM" if difficulty != "advanced" else f"Full tempo {bpm} BPM",
        "Loop each measure 4× before speeding up",
    ]
    if len(chords) >= 2 and focus_kind == "transitions":
        cues.append(f"Focus on smooth {chords[0]} → {chords[1]} — keep one finger anchored if possible")
    elif len(chords) >= 2:
        cues.append(f"Watch the change {chords[0]} → {chords[1]}")
    if focus_kind == "rhythm":
        cues.append("Keep strumming light — let the bass notes speak in bossa patterns")
    if focus_kind == "scales":
        cues.append("Target chord tones on beat 1 — use arpeggio fingers p-i-m-a")
    return cues


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
    bpm: int,
) -> NotationResult:
    use = chords[: max(1, min(4, num_lines))]
    if not use:
        use = ["C"]
    fk = _focus_kind(focus)
    groove_info = _groove_pattern(groove, fk)
    shapes = [_resolve_shape(c, guitar_tabs) for c in use]

    section_badge = html.escape(section)
    prog = " ".join(f'<span class="tab-prog-chord">{html.escape(c)}</span>' for c in use)
    progression_html = f'<div class="tab-section-badge">[{section_badge}]</div><div class="tab-progression">{prog}</div>'

    measures_html: list[str] = []
    plain_parts: list[str] = []
    prev_shape = None
    for i, (ch, sh) in enumerate(zip(use, shapes), start=1):
        prev_sh = prev_shape if (fk == "transitions" and i > 1) else None
        if fk == "scales":
            hi_strings = {"e", "B", "G"}
        elif fk == "chords":
            hi_strings = {"e", "B"}
        else:
            hi_strings = set()
        block, plain = _render_measure_html(
            chord=ch,
            shape=sh,
            bar_index=i,
            groove_info=groove_info,
            focus_kind=fk,
            highlight_strings=hi_strings if fk == "scales" else None,
            transition_prev_shape=prev_sh,
        )
        measures_html.append(block)
        plain_parts.append(plain)
        prev_shape = sh

    cues = _practice_cues(
        chords=use,
        section=section,
        focus=focus,
        focus_kind=fk,
        bpm=bpm,
        difficulty=difficulty,
        groove_info=groove_info,
    )
    cues_html = "".join(f"<li>{html.escape(c)}</li>" for c in cues)

    doc = f"""
<div class="tab-lesson">
  {_tab_legend_html()}
  {progression_html}
  <div class="tab-cues"><strong>Practice cues</strong><ul>{cues_html}</ul></div>
  <div class="tab-scroll-wrap">
    <div class="tab-measures-row">{''.join(measures_html)}</div>
  </div>
</div>
"""

    return NotationResult(
        format="tab",
        title=f"{song_title} — {section} — Guitar TAB",
        chord_labels=" | ".join(use),
        rhythm_counts=groove_info["name"],
        body="\n\n".join(plain_parts),
        html=doc.strip(),
        practice_cues=cues,
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
        staff_lines.append(f"Bar {i + 1}  {ch}:  {'  '.join(tones)}  |  beats: 1 · 2 · 3 · 4")

    return NotationResult(
        format="abc",
        title=f"{song_title} — {section} — {instrument}",
        chord_labels=" | ".join(use[:num_lines]),
        rhythm_counts="1 + 2 + 3 + 4" if fk == "rhythm" else "chord tones on beats 1 & 3",
        body="\n".join(staff_lines),
        html="",
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
            bpm=bpm,
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
    if result.html:
        return f"""
<div class="notation-output notation-tab">
  <div class="notation-title">{html.escape(result.title)}</div>
  {result.html}
</div>
""".strip()
    body = html.escape(result.body)
    return f"""
<div class="notation-output notation-tab">
  <div class="notation-title">{html.escape(result.title)}</div>
  <pre class="notation-tab-pre">{body}</pre>
</div>
""".strip()
