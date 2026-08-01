"""Piano keyboard HTML with chart-key note spelling (shared across Creative surfaces)."""

from __future__ import annotations

import html

from music_theory import NOTE_TO_MIDI, normalize_root, spell_note_in_key, split_chord


def pitch_class_label(pc: int, reference_key: str) -> str:
    """Spell a pitch class (0–11) for display on a piano diagram."""
    return spell_note_in_key(int(pc) % 12, reference_key)


def build_piano_keyboard_html(
    highlight_notes: list[str],
    chord_tones: list[str],
    *,
    reference_key: str = "C",
) -> str:
    """Two-octave keyboard; motif notes highlighted, chord tones outlined."""

    def _pc(note: str) -> int:
        root, _ = split_chord(str(note))
        return NOTE_TO_MIDI.get(normalize_root(root), 60) % 12

    ref = str(reference_key or "C").strip() or "C"
    motif_pcs = {_pc(n) for n in highlight_notes}
    chord_pcs = {_pc(n) for n in chord_tones}

    white_midi = [60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79, 81, 83]
    black_midi = [61, 63, 66, 68, 70, 73, 75, 78, 80, 82]

    def _label(midi: int) -> str:
        return pitch_class_label(midi % 12, ref)

    def _cls(midi: int) -> str:
        pc = midi % 12
        if pc in motif_pcs:
            return "pk hi"
        if pc in chord_pcs:
            return "pk chord"
        return "pk"

    whites_html = []
    for i, midi in enumerate(white_midi):
        whites_html.append(
            f'<div class="{_cls(midi)} white" style="--i:{i}">'
            f"<span>{html.escape(_label(midi))}</span></div>"
        )

    black_positions = {
        61: 0.72,
        63: 1.72,
        66: 3.72,
        68: 4.72,
        70: 5.72,
        73: 7.72,
        75: 8.72,
        78: 10.72,
        80: 11.72,
        82: 12.72,
    }
    blacks_html = []
    for midi in black_midi:
        left = black_positions.get(midi, 0)
        blacks_html.append(
            f'<div class="{_cls(midi)} black" style="left:calc({left} * var(--wk))">'
            f"<span>{html.escape(_label(midi))}</span></div>"
        )

    voicing = " · ".join(html.escape(n) for n in chord_tones[:4])
    chips = "".join(f'<span class="pk-chip">{html.escape(n)}</span>' for n in chord_tones[:4])
    return (
        f'<p class="pk-voicing-hint"><strong>Chord tones:</strong> {voicing}</p>'
        f'<p class="pk-motif-notes"><strong>Highlighted:</strong> {chips or "—"}</p>'
        '<div class="improv-piano-wrap">'
        '<div class="improv-piano-kb" style="--wk:42px">'
        + "".join(whites_html)
        + "".join(blacks_html)
        + "</div></div>"
        "<style>"
        ".improv-piano-wrap{overflow-x:auto;padding:4px 0 8px;}"
        ".improv-piano-kb{position:relative;display:flex;gap:2px;height:118px;--wk:42px;}"
        ".improv-piano-kb .pk.white{width:var(--wk);height:112px;border-radius:0 0 6px 6px;"
        "border:1px solid #cbd5e1;background:#fff;display:flex;align-items:flex-end;"
        "justify-content:center;font-size:0.68rem;font-weight:700;padding-bottom:5px;box-sizing:border-box;}"
        ".improv-piano-kb .pk.black{position:absolute;top:0;width:calc(var(--wk)*0.58);height:68px;"
        "border-radius:0 0 5px 5px;background:#1e293b;color:#f8fafc;border:1px solid #0f172a;"
        "display:flex;align-items:flex-end;justify-content:center;font-size:0.58rem;"
        "font-weight:700;padding-bottom:4px;z-index:2;box-sizing:border-box;}"
        ".improv-piano-kb .pk.hi{background:#bbf7d0;border-color:#16a34a;}"
        ".improv-piano-kb .pk.black.hi{background:#15803d;color:#fff;}"
        ".improv-piano-kb .pk.chord{box-shadow:inset 0 0 0 2px #6366f1;}"
        ".pk-chip{display:inline-block;background:#e0e7ff;border:1px solid #6366f1;"
        "border-radius:6px;padding:2px 8px;margin:2px 4px 2px 0;font-weight:700;}"
        ".pk-voicing-hint,.pk-motif-notes{margin:0 0 6px 0;font-size:0.85rem;color:#475569;}"
        "</style>"
    )
