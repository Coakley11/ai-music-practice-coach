"""Data-driven custom practice worksheet — branches on song, section, instrument, focus, BPM, backing."""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field
from typing import Any

from music_theory import NOTE_TO_MIDI, normalize_root, semitone_distance, split_chord

from practice_studio import (
    PIANO_COMP_PATTERNS,
    STRUM_PATTERNS,
    _best_guitar_shape_key,
    chord_concepts_from_sections,
    fretboard_ascii,
    practice_active_section_name,
    practice_display_sections,
    practice_is_full_song,
    rhythm_guide_markdown,
    scale_suggestions_for_chord,
    section_deep_practice_markdown,
    transposing_instrument_labels,
    transpose_for_label,
)


@dataclass
class SheetInputs:
    """Snapshot of user choices the generator must honor."""

    song_title: str
    artist: str
    genre: str
    display_key: str
    original_key: str
    bpm: int
    time_signature: str
    groove_style: str
    level: str
    instrument: str
    focus: str
    section_focus: str | None
    sections: dict[str, list[str]]
    section_lyrics: dict[str, str] = field(default_factory=dict)
    lyric_cues: dict[str, list[str]] = field(default_factory=dict)
    backing_scope: str = ""
    backing_section: str = ""
    backing_loops: int = 0
    metronome_loop_bars: int = 0

    def instrument_kind(self) -> str:
        inst = (self.instrument or "").lower()
        if "guitar" in inst:
            return "guitar"
        if "piano" in inst or "keyboard" in inst:
            return "piano"
        if "sax" in inst:
            return "sax"
        if "trumpet" in inst or "clarinet" in inst:
            return "horn"
        if "voice" in inst or "vocal" in inst:
            return "voice"
        if "bass" in inst:
            return "bass"
        return "other"

    def focus_category(self) -> str:
        return normalize_practice_focus(self.focus)


def normalize_practice_focus(focus: str) -> str:
    f = (focus or "").lower()
    if any(t in f for t in ("rhythm", "strum", "comp", "groove", "pocket", "syncop", "left-hand", "left hand")):
        return "Rhythm"
    if any(t in f for t in ("chord", "voicing", "voice leading", "inversion", "barre", "transition", "triad", "harmony")):
        return "Chords"
    if any(t in f for t in ("scale", "improv", "solo", "lead", "bebop", "lick", "walking")):
        return "Scales & Improvisation"
    if any(t in f for t in ("timing", "metronome", "tempo", "subdivision")):
        return "Timing"
    if any(t in f for t in ("dynamic", "touch", "crescendo")):
        return "Dynamics"
    if any(t in f for t in ("ear", "pitch")):
        return "Ear Training"
    if any(t in f for t in ("melody", "phrasing", "breath", "tone", "articulation", "range")):
        return "Melody & Phrasing"
    return "Technique"


# Per-song profiles: section drills + instrument/focus combo blurbs
_SONG_PROFILES: dict[tuple[str, str], dict[str, Any]] = {
    ("how deep is your love", "bee gees"): {
        "style": "Pop / soft rock ballad — warm maj7 color, gentle lift into the chorus.",
        "default_groove": "Ballad",
        "sections": {
            "verse": {
                "drill": "Verse: **Ebmaj7 → Gm7 → Fm7 → Bb7** — one bar each; keep LH steady, RH shells on 2 & 4.",
                "piano_chords": "Voice-lead 3rd→7th between maj7 chords; keep Ebmaj7–Gm7–Fm7–Bb7 in close position.",
                "guitar_rhythm": "Light arpeggio or half-notes — no heavy downstrokes in the verse.",
            },
            "chorus": {
                "drill": "Chorus: widen on **Abmaj7**; add 10% tone when the hook lands on Bb7.",
                "piano_chords": "Open RH on Abmaj7; prepare Bb7 with b7 in the bass if using slash grips.",
            },
        },
        "combos": {
            ("piano", "chords", "verse"): (
                "Ballad verse in Eb: LH whole-note root/5th, RH **3rd+7th shells**. "
                "Smooth **Fm7 → Bb7** by holding common tone (Eb) in RH while moving bass Bb→Bb."
            ),
            ("guitar", "chords", "verse"): (
                "Use maj7 grips; arpeggiate **Ebmaj7–Gm7–Fm7–Bb7**. "
                "Anchor finger on Eb when sliding Fm7→Bb7."
            ),
        },
        "instruments": {
            "piano": "Ballad comp: LH root on 1, RH offbeat shells; never jump both hands on every bar.",
            "guitar": "Fingerstyle or light strum; capo-friendly G shapes if transposed.",
            "sax": "Concert Eb — sing through verse; maj7 = 3rd color, Bb7 = b7 resolution.",
            "voice": "Soft falsetto in verse; narrow vowels on ascent into chorus.",
        },
    },
    ("so nice (summer samba)", "marcos valle"): {
        "style": "Bossa / samba — anticipate beat 3, never rush beat 2.",
        "default_groove": "Bossa nova",
        "sections": {
            "verse": {
                "drill": "Verse: **Fmaj7 → G7 → Gm7 → C7** — bossa bass anticipates beat 3 each bar.",
                "guitar_rhythm": "Bossa: bass on 1 + anticipatory 8th before 3; brush up on 2 & 4.",
                "piano_rhythm": "LH root–chord–chord; RH syncopated offbeats — stay lighter than you think.",
            },
            "chorus": {
                "drill": "Chorus: **Fmaj7 → Dm7 → Gm7 → C7** — brighter top note, same pocket.",
            },
        },
        "combos": {
            ("guitar", "rhythm", "verse"): (
                "Bossa **verse** at ~135 BPM: pattern **D — U — D — — D — — U —** on nylon. "
                "Bass notes: F root → G → G → C approaching each change."
            ),
            ("piano", "rhythm", "verse"): (
                "Bossa LH: root on 1, chord on & of 2 and on 3; RH fills only on & of 4 in verse."
            ),
        },
        "instruments": {
            "guitar": "Nylon strings; thumb bass separate from finger brush.",
            "piano": "Bossa clave in LH; RH never doubles the bass rhythm.",
            "sax": "Concert F — mixolydian on G7, dorian on Gm7; phrase behind the beat.",
        },
    },
    ("one note samba", "antonio carlos jobim"): {
        "style": "Jobim bossa — verse in Db minor area, chorus resolves to C major.",
        "default_groove": "Bossa nova",
        "sections": {
            "verse": {
                "drill": "Verse: shifting dominants **Dbm7 → C7 → B7 → Bb7** — melody is one-note; harmony moves.",
                "sax_scales": "Target 3rd of each dominant; use altered scale on A7#5 bar.",
            },
            "chorus": {
                "drill": "Chorus: **Dm7 → G7 → Cmaj7** then **Cm7 → F7 → Bbmaj7** — classic ii–V–I in C.",
                "sax_scales": "Dm7 dorian → G7 mixolydian → Cmaj7 major; land 3rd on beat 1 of Cmaj7.",
            },
        },
        "combos": {
            ("saxophone", "scales & improvisation", "chorus"): (
                "Chorus in concert **C**: written for alto in **A**. "
                "Arpeggiate **Dm7–G7–Cmaj7** (1-3-5-7 each bar), then **Cm7–F7–Bbmaj7**. "
                "Improv targets: 3rd of G7 → 3rd of Cmaj7; b7 of F7 → 3rd of Bbmaj7."
            ),
            ("sax", "scales & improvisation", "chorus"): (
                "Same as saxophone combo — chorus ii–V–I cells in C major."
            ),
        },
        "instruments": {
            "sax": "Verse = dominant chain in Db; chorus = C major — transpose reads accordingly.",
            "piano": "Keep LH bossa; RH highlight guide tones through Dbm7–C7–B7–Bb7.",
            "guitar": "Sparse comp; let the single-note melody breathe.",
        },
    },
}


def _song_key(title: str, artist: str) -> tuple[str, str]:
    return (title.strip().lower(), (artist or "").strip().lower())


def _song_profile(title: str, artist: str) -> dict[str, Any]:
    return _SONG_PROFILES.get(_song_key(title, artist), {})


def _section_key(name: str) -> str:
    return (name or "").lower().split("/")[0].strip()


def _combo_note(ctx: SheetContext) -> str:
    profile = ctx.profile
    combos = profile.get("combos") or {}
    inst = ctx.inputs.instrument
    cat = ctx.category.lower()
    sec = _section_key(ctx.active or ctx.section_label)
    for key, text in combos.items():
        k_inst, k_cat, k_sec = key
        if k_inst.lower() in inst.lower() or inst.lower() in k_inst.lower():
            if k_cat.lower() in cat or cat in k_cat.lower():
                if k_sec == sec or (k_sec == "verse" and "verse" in sec):
                    return text
    sec_notes = (profile.get("sections") or {}).get(sec) or {}
    if ctx.inputs.instrument_kind() == "piano" and ctx.category == "Chords":
        return sec_notes.get("piano_chords") or sec_notes.get("drill") or ""
    if ctx.inputs.instrument_kind() == "guitar" and ctx.category == "Rhythm":
        return sec_notes.get("guitar_rhythm") or sec_notes.get("drill") or ""
    if ctx.inputs.instrument_kind() == "sax" and ctx.category == "Scales & Improvisation":
        return sec_notes.get("sax_scales") or sec_notes.get("drill") or ""
    return sec_notes.get("drill") or ""


@dataclass
class SheetContext:
    inputs: SheetInputs
    view_sections: dict[str, list[str]]
    active: str | None
    is_full: bool
    section_label: str
    section_chords: list[str]
    bar_count: int
    category: str
    profile: dict[str, Any]
    concepts: list[str]
    loop_bars: int
    variant_id: str
    combo_note: str = ""


def _variant_id(inputs: SheetInputs, section_label: str, category: str) -> str:
    raw = "|".join(
        [
            inputs.song_title,
            inputs.artist,
            section_label,
            inputs.instrument,
            inputs.level,
            inputs.focus,
            str(inputs.bpm),
            inputs.groove_style,
            inputs.backing_scope,
            inputs.backing_section,
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _resolve_context(inputs: SheetInputs) -> SheetContext:
    view = practice_display_sections(inputs.sections, inputs.section_focus)
    active = practice_active_section_name(inputs.section_focus, inputs.sections)
    is_full = practice_is_full_song(inputs.section_focus)
    section_label = "Full Song" if is_full else (active or "Section")
    if is_full:
        section_chords = [c for chs in view.values() for c in (chs or [])]
        bar_count = sum(len(v) for v in view.values())
    else:
        section_chords = list(view.get(active or "", []) or [])
        bar_count = len(section_chords)
    category = inputs.focus_category()
    profile = _song_profile(inputs.song_title, inputs.artist)
    concepts = chord_concepts_from_sections(
        {k: v for k, v in view.items() if v},
        genre=inputs.genre,
    )
    loop_bars = inputs.metronome_loop_bars or max(4, bar_count) if bar_count else 8
    ctx = SheetContext(
        inputs=inputs,
        view_sections=view,
        active=active,
        is_full=is_full,
        section_label=section_label,
        section_chords=section_chords,
        bar_count=bar_count,
        category=category,
        profile=profile,
        concepts=concepts,
        loop_bars=loop_bars,
        variant_id="",
        combo_note="",
    )
    ctx.variant_id = _variant_id(inputs, section_label, category)
    ctx.combo_note = _combo_note(ctx)
    return ctx


def _transition_score(a: str, b: str) -> int:
    ra, _ = split_chord(a.split("/")[0])
    rb, _ = split_chord(b.split("/")[0])
    ma = NOTE_TO_MIDI.get(normalize_root(ra))
    mb = NOTE_TO_MIDI.get(normalize_root(rb))
    if ma is None or mb is None:
        return 1
    return abs((mb - ma) % 12 - 6) + (3 if a != b else 0)


def _hardest_transitions(chords: list[str], limit: int = 4) -> list[tuple[str, str]]:
    pairs: list[tuple[int, str, str]] = []
    for i in range(len(chords) - 1):
        a, b = chords[i], chords[i + 1]
        if a != b:
            pairs.append((_transition_score(a, b), a, b))
    pairs.sort(reverse=True)
    return [(a, b) for _, a, b in pairs[:limit]]


def _chord_color_note(chord: str) -> str:
    c = chord.lower()
    if "maj7" in c or "maj9" in c:
        return "major 7th"
    if "m7b5" in c or "ø" in c or "dim" in c:
        return "half-dim / dim"
    if "m7" in c and "maj" not in c:
        return "minor 7th"
    if re.search(r"(?<![a-z])7", c) and "maj" not in c:
        return "dominant 7th"
    if "/" in chord:
        return "slash bass"
    return "tonal center"


def _simple_roman_line(chords: list[str], key: str) -> str:
    if not chords or not key:
        return ""
    key_root = normalize_root(split_chord(key)[0])
    key_midi = NOTE_TO_MIDI.get(key_root)
    if key_midi is None:
        return ""
    uniq: list[str] = []
    for ch in chords[:10]:
        if ch not in uniq:
            uniq.append(ch)
    numerals: list[str] = []
    for ch in uniq:
        root, suf = split_chord(ch.split("/")[0])
        rm = NOTE_TO_MIDI.get(normalize_root(root))
        if rm is None:
            continue
        deg = (rm - key_midi) % 12
        map_deg = {0: "I", 2: "ii", 4: "iii", 5: "IV", 7: "V", 9: "vi", 11: "vii°"}
        n = map_deg.get(deg, f"?({root})")
        if "m" in suf.lower() and "maj" not in suf.lower() and n in ("I", "IV"):
            n = "vi" if deg == 9 else "ii" if deg == 2 else n + "m"
        if "7" in suf and "maj" not in suf.lower():
            n = (n + "7") if "7" not in n else n
        numerals.append(f"<strong>{html.escape(ch)}</strong> ≈ {n}")
    return " · ".join(numerals[:8])


def _chord_bar_grid(chords: list[str], bars_per_row: int = 4) -> str:
    if not chords:
        return "<p><em>No chords in this section.</em></p>"
    cells = []
    for i, ch in enumerate(chords, start=1):
        cells.append(
            f'<div class="pw-chord-cell"><span class="pw-bar">Bar {i}</span>'
            f'<span class="pw-chord">{html.escape(ch)}</span></div>'
        )
    rows = []
    for start in range(0, len(cells), bars_per_row):
        rows.append('<div class="pw-chord-row">' + "".join(cells[start : start + bars_per_row]) + "</div>")
    return "".join(rows)


def _lyrics_block(section_name: str, section_lyrics: dict[str, str], lyric_cues: dict[str, list[str]]) -> str:
    items: list[str] = []
    text = (section_lyrics or {}).get(section_name, "").strip()
    cues = (lyric_cues or {}).get(section_name) or []
    if text:
        for line in text.splitlines()[:8]:
            line = line.strip()
            if line:
                items.append(f"<li>{html.escape(line)}</li>")
    for cue in cues[:6]:
        items.append(f"<li><em>{html.escape(str(cue))}</em></li>")
    if not items:
        return "<p><em>No lyrics/cues for this section — add them on Practice.</em></p>"
    return "<ul class='pw-list'>" + "".join(items) + "</ul>"


def _beat_grid_html(groove_style: str) -> str:
    pattern = STRUM_PATTERNS.get(groove_style, STRUM_PATTERNS["Pop groove"])
    headers = "".join(f"<th>{i + 1}</th>" for i in range(len(pattern)))
    cells = "".join(f"<td>{html.escape(p)}</td>" for p in pattern)
    return (
        f"<table class='pw-beat-grid'><tr>{headers}</tr><tr>{cells}</tr></table>"
        f"<p class='pw-grid-legend'><strong>D</strong> down · <strong>U</strong> up · <strong>—</strong> rest</p>"
    )


def _piano_voicing_line(chord: str) -> str:
    c = chord.lower()
    if "maj7" in c:
        return f"<li><strong>{html.escape(chord)}</strong> — RH: 3rd+7th shell · LH: root+5th</li>"
    if "m7" in c and "maj" not in c:
        return f"<li><strong>{html.escape(chord)}</strong> — RH: b3+7th · LH: root</li>"
    if re.search(r"(?<![a-z])7", c) and "maj" not in c:
        return f"<li><strong>{html.escape(chord)}</strong> — RH: 3rd+b7 · LH: root or tritone sub bass</li>"
    if "dim" in c:
        return f"<li><strong>{html.escape(chord)}</strong> — RH: b3+b5 · LH: root</li>"
    return f"<li><strong>{html.escape(chord)}</strong> — RH: root+3rd+5th block (beginner) or 3rd+5th</li>"


def _voice_leading_tips(transitions: list[tuple[str, str]]) -> str:
    if not transitions:
        return "<p>Loop one bar until steady, then link pairs.</p>"
    items = []
    for a, b in transitions[:4]:
        items.append(
            f"<li><strong>{html.escape(a)} → {html.escape(b)}</strong> — "
            f"keep a common tone in RH (3rd or 7th); move LH root only on beat 1.</li>"
        )
    return "<ul class='pw-list'>" + "".join(items) + "</ul>"


def _build_guitar_panel(ctx: SheetContext) -> tuple[str, str]:
    inp = ctx.inputs
    chords = ctx.section_chords
    hard = _hardest_transitions(chords)
    hard_txt = ", ".join(f"{html.escape(a)}→{html.escape(b)}" for a, b in hard[:3]) or "steady bars"
    shape, capo = _best_guitar_shape_key(inp.display_key)
    pattern = STRUM_PATTERNS.get(inp.groove_style, STRUM_PATTERNS["Pop groove"])
    strum = " ".join(pattern)
    inst_note = (ctx.profile.get("instruments") or {}).get("guitar", "")
    capo_html = (
        f"<li><strong>Capo {capo}</strong> — play <strong>{shape}</strong> shapes → sounds <strong>{html.escape(inp.display_key)}</strong></li>"
        if capo
        else f"<li><strong>Open shapes</strong> in <strong>{shape}</strong> for {html.escape(inp.display_key)}</li>"
    )
    shapes_html = ""
    if chords:
        shapes_html = "<p><strong>Chord shapes (first changes):</strong></p>" + "".join(
            f"<div class='pw-sub'>{fretboard_ascii(ch, inp.level)}</div>" for ch in chords[:3]
        )
    title = f"Guitar — {inp.groove_style}"
    body = f"""
<ul class="pw-list">
  {capo_html}
  <li><strong>Strum pattern:</strong> <code>{html.escape(strum)}</code> ({html.escape(inp.groove_style)})</li>
  <li><strong>Comping:</strong> match {html.escape(inp.time_signature)} at <strong>{inp.bpm} BPM</strong></li>
  <li><strong>Hardest changes:</strong> {hard_txt}</li>
  {f'<li><strong>Song:</strong> {html.escape(inst_note)}</li>' if inst_note else ''}
</ul>
{shapes_html}
""".strip()
    return title, body


def _build_piano_panel(ctx: SheetContext) -> tuple[str, str]:
    inp = ctx.inputs
    chords = ctx.section_chords
    hard = _hardest_transitions(chords)
    comp = PIANO_COMP_PATTERNS.get(inp.groove_style, PIANO_COMP_PATTERNS["Pop groove"])
    inst_note = (ctx.profile.get("instruments") or {}).get("piano", "")
    voicings = "".join(_piano_voicing_line(ch) for ch in chords[:6])
    title = f"Piano — {ctx.category if ctx.category == 'Chords' else inp.groove_style}"
    body = f"""
<ul class="pw-list">
  <li><strong>LH pattern:</strong> root on 1; add 5th or chord tone on 3 in ballads</li>
  <li><strong>RH voicings:</strong> shells & inversions — see bar-by-bar below</li>
  <li><strong>Comping:</strong> {html.escape(comp)}</li>
  <li><strong>Bass movement:</strong> stepwise roots where possible ({', '.join(f'{html.escape(a)}→{html.escape(b)}' for a,b in hard[:2])})</li>
  {f'<li><strong>Song:</strong> {html.escape(inst_note)}</li>' if inst_note else ''}
</ul>
<p><strong>Voicings for this section:</strong></p>
<ul class="pw-list">{voicings}</ul>
""".strip()
    return title, body


def _build_sax_panel(ctx: SheetContext) -> tuple[str, str]:
    inp = ctx.inputs
    labels = transposing_instrument_labels(inp.instrument) or ["Concert pitch"]
    written = transpose_for_label(inp.display_key, labels[0])
    inst_note = (ctx.profile.get("instruments") or {}).get("sax", "")
    tone_lines = ""
    for ch in ctx.section_chords[:6]:
        tone_lines += f"<li><strong>{html.escape(ch)}</strong> — target 3rd & 7th on beat 1; {scale_suggestions_for_chord(ch, inp.display_key, inp.level, inp.instrument)}</li>"
    title = f"Saxophone — concert {inp.display_key} / written {written}"
    body = f"""
<ul class="pw-list">
  <li><strong>Concert key:</strong> {html.escape(inp.display_key)} · <strong>Written:</strong> {html.escape(written)} ({html.escape(labels[0])})</li>
  <li><strong>Chord tones:</strong> land guide tones through {html.escape(ctx.section_label)}</li>
  <li><strong>Breath:</strong> 2-bar phrases; inhale before {html.escape(ctx.active or 'peak')} harmony</li>
  {f'<li><strong>Song:</strong> {html.escape(inst_note)}</li>' if inst_note else ''}
</ul>
<p><strong>Arpeggios & targets per bar:</strong></p>
<ul class="pw-list">{tone_lines}</ul>
""".strip()
    return title, body


def _build_voice_panel(ctx: SheetContext) -> tuple[str, str]:
    inp = ctx.inputs
    inst_note = (ctx.profile.get("instruments") or {}).get("voice", "")
    title = f"Voice — {inp.display_key}"
    body = f"""
<ul class="pw-list">
  <li><strong>Range:</strong> chart in {html.escape(inp.display_key)}; transpose sidebar if tight</li>
  <li><strong>Pitch targets:</strong> chord root on downbeats; hum 3rd before lyrics</li>
  <li><strong>Breathing:</strong> one breath every 2 bars in {html.escape(ctx.section_label)}</li>
  <li><strong>Delivery:</strong> verse = intimate · chorus = fuller, not louder</li>
  {f'<li><strong>Song:</strong> {html.escape(inst_note)}</li>' if inst_note else ''}
</ul>
""".strip()
    return title, body


def _build_focus_primary(ctx: SheetContext) -> tuple[str, str]:
    """Dominant panel — content changes completely by focus category."""
    inp = ctx.inputs
    cat = ctx.category
    chords = ctx.section_chords
    hard = _hardest_transitions(chords)
    loop = ctx.loop_bars
    sec = html.escape(ctx.section_label)

    if cat == "Rhythm":
        rhythm_md = rhythm_guide_markdown(inp.instrument, inp.groove_style, inp.time_signature)
        changes = " · ".join(
            f"bar {i + 1}: {html.escape(c)}" for i, c in enumerate(chords[:8])
        )
        title = f"Rhythm — {inp.groove_style} @ {inp.bpm} BPM"
        body = f"""
<p><strong>Count-in:</strong> 1 – 2 – 3 – 4 → enter on beat 1</p>
<p><strong>Beat grid ({inp.groove_style}):</strong></p>
{_beat_grid_html(inp.groove_style)}
<div class="pw-rhythm-md">{_md_to_html_block(rhythm_md)}</div>
<p><strong>Chord changes in {sec}:</strong> {changes or 'one chord per bar'}</p>
<p><strong>Loop drill:</strong> {loop} bars × 5 at <strong>{inp.bpm} BPM</strong></p>
""".strip()
        return title, body

    if cat == "Chords":
        roman = _simple_roman_line(chords, inp.display_key)
        title = f"Chords — {sec} analysis"
        vl = _voice_leading_tips(hard) if inp.instrument_kind() == "piano" else ""
        trans = "<ul class='pw-list'>" + "".join(
            f"<li>Drill <strong>{html.escape(a)} → {html.escape(b)}</strong> 8× slow, 4× tempo</li>"
            for a, b in hard[:4]
        ) + "</ul>"
        body = f"""
<p><strong>Progression ({len(chords)} bars):</strong> {' · '.join(html.escape(c) for c in chords[:16])}</p>
{f'<p><strong>Roman numerals:</strong> {roman}</p>' if roman else ''}
<p><strong>Color:</strong> {', '.join(_chord_color_note(c) for c in chords[:5])}</p>
<p><strong>Hardest 2–4 changes:</strong></p>
{trans}
{f'<p><strong>Voice leading ({inp.instrument}):</strong></p>{vl}' if vl else ''}
""".strip()
        return title, body

    if cat == "Scales & Improvisation":
        title = f"Scales & improv — {sec}"
        licks = []
        for i, ch in enumerate(chords[:8]):
            licks.append(
                f"<li><strong>Bar {i + 1} {html.escape(ch)}:</strong> "
                f"{scale_suggestions_for_chord(ch, inp.display_key, inp.level, inp.instrument)}</li>"
            )
        short_lick = ""
        if len(chords) >= 2:
            short_lick = (
                f"<p><strong>2-bar lick idea:</strong> chord tones of <strong>{html.escape(chords[0])}</strong> "
                f"→ resolve to 3rd of <strong>{html.escape(chords[1])}</strong> on beat 1.</p>"
            )
        body = f"<ul class='pw-list'>{''.join(licks)}</ul>{short_lick}"
        return title, body

    if cat == "Transitions":
        title = f"Transitions — hardest changes in {sec}"
        items = "".join(
            f"<li><strong>{html.escape(a)} → {html.escape(b)}</strong> — loop 8× @ {max(40, int(inp.bpm * 0.6))} BPM, then 4× @ {inp.bpm} BPM</li>"
            for a, b in hard[:4]
        )
        body = f"<ul class='pw-list'>{items or '<li>Link pairs of bars slowly.</li>'}</ul>"
        body += f"<p class='pw-repeat'><strong>Repeat this loop 5 times</strong> before adding the next change.</p>"
        return title, body

    if cat == "Timing":
        slow = max(40, int(inp.bpm * 0.65))
        med = max(50, int(inp.bpm * 0.82))
        title = f"Timing — {inp.bpm} BPM plan"
        body = f"""
<ul class="pw-list">
  <li><strong>Slow ({slow} BPM):</strong> quarters — 2 min, {sec} only</li>
  <li><strong>Medium ({med} BPM):</strong> 8th subdivisions — 2 min</li>
  <li><strong>Full ({inp.bpm} BPM):</strong> full section — 3 min</li>
  <li><strong>Subdivision:</strong> {'8ths on 2 & 4' if inp.time_signature.startswith('4') else 'triplet pulse'}</li>
</ul>
""".strip()
        return title, body

    return (
        f"{cat} — {sec}",
        f"<p>Apply <strong>{html.escape(cat)}</strong> across {len(chords)} bars in <strong>{sec}</strong>.</p>",
    )


def _build_instrument_secondary(ctx: SheetContext) -> tuple[str, str]:
    kind = ctx.inputs.instrument_kind()
    if kind == "guitar":
        return _build_guitar_panel(ctx)
    if kind == "piano":
        return _build_piano_panel(ctx)
    if kind == "sax" or kind == "horn":
        return _build_sax_panel(ctx)
    if kind == "voice":
        return _build_voice_panel(ctx)
    if kind == "bass":
        hard = _hardest_transitions(ctx.section_chords)
        ht = ", ".join(f"{a}→{b}" for a, b in hard[:3])
        return (
            "Bass",
            f"<ul class='pw-list'><li>Root on 1 · fifth on 3</li><li>Approach: {html.escape(ht)}</li>"
            f"<li>Pocket: {html.escape(ctx.inputs.groove_style)} @ {ctx.inputs.bpm} BPM</li></ul>",
        )
    return ("Instrument", f"<p>Practice in <strong>{html.escape(ctx.inputs.display_key)}</strong>.</p>")


def _practice_goal(ctx: SheetContext) -> str:
    if ctx.combo_note:
        return ctx.combo_note
    profile = ctx.profile
    sec = _section_key(ctx.active or "")
    sec_data = (profile.get("sections") or {}).get(sec) or {}
    if sec_data.get("drill"):
        return sec_data["drill"]
    if profile.get("style"):
        return (
            f"{profile['style']} — <strong>{ctx.category}</strong> on "
            f"<strong>{html.escape(ctx.section_label)}</strong> ({html.escape(ctx.inputs.instrument)})."
        )
    return (
        f"<strong>{html.escape(ctx.section_label)}</strong> of "
        f"<strong>{html.escape(ctx.inputs.song_title)}</strong> — "
        f"{html.escape(ctx.category)} focus for {html.escape(ctx.inputs.instrument)}."
    )


def _ten_minute_plan(ctx: SheetContext) -> str:
    inp = ctx.inputs
    loop = ctx.loop_bars
    cat = ctx.category
    kind = inp.instrument_kind()
    if inp.level == "Beginner":
        steps = [
            f"2 min — count-in at <strong>{inp.bpm} BPM</strong> (no instrument)",
            f"3 min — one bar at a time ({html.escape(ctx.section_label)})",
            f"3 min — hardest change only",
            f"2 min — {loop}-bar loop × 2",
        ]
        goal = "One clean loop with steady pulse."
    elif inp.level == "Advanced":
        if cat == "Scales & Improvisation":
            steps = [
                "2 min — chord-tone arpeggios through section",
                f"3 min — improv with one rhythmic motif @ {inp.bpm} BPM",
                "3 min — backing track loop with ears-first",
                "2 min — one risk (outside note → chord tone)",
            ]
            goal = "One chorus/section pass that sounds intentional, not mechanical."
        else:
            steps = [
                "2 min — guide-tone line",
                f"3 min — full tempo {cat.lower()} focus",
                "3 min — backing / metronome loop",
                "2 min — dynamics arc",
            ]
            goal = "Performance-ready pass with dynamics."
    else:
        if kind == "guitar" and cat == "Rhythm":
            steps = [
                f"2 min — strum pattern only @ {max(40, int(inp.bpm * 0.7))} BPM",
                f"4 min — {loop}-bar loop with chord changes @ {inp.bpm} BPM",
                "2 min — hardest transition",
                "2 min — full verse/section with groove",
            ]
            goal = "Bossa/pop pocket feels automatic at tempo."
        elif kind == "piano" and cat == "Chords":
            steps = [
                "2 min — RH shells on first 4 bars",
                f"4 min — voice-lead full {html.escape(ctx.section_label)}",
                "2 min — hardest inversion change",
                f"2 min — comping with LH pattern @ {inp.bpm} BPM",
            ]
            goal = "Smooth voice-leading through the section."
        else:
            steps = [
                f"2 min — warm-up first chord change",
                f"4 min — {loop}-bar loop × 5 @ {inp.bpm} BPM",
                f"2 min — {cat} isolation",
                f"2 min — full section musical pass",
            ]
            goal = "Confident time + clean changes at full tempo."
    items = "".join(f"<li>{s}</li>" for s in steps)
    return f"""
<ol class="pw-checklist">{items}</ol>
<p class="pw-goal"><strong>Goal before moving on:</strong> {goal}</p>
""".strip()


def _backing_line(ctx: SheetContext) -> str:
    inp = ctx.inputs
    scope = (inp.backing_scope or "").strip()
    sec = inp.backing_section or ctx.active or ctx.section_label
    loops = inp.backing_loops or 4
    if scope == "Single section" and sec:
        return (
            f"Backing track: loop <strong>{html.escape(sec)}</strong> "
            f"({loops}×) @ <strong>{inp.bpm} BPM</strong> — use <strong>Send to Backing Track</strong>."
        )
    if scope == "Full song":
        return f"Backing track: <strong>full song</strong> @ <strong>{inp.bpm} BPM</strong>."
    if scope == "Multiple selected sections":
        return f"Backing track: <strong>multiple sections</strong> @ <strong>{inp.bpm} BPM</strong>."
    if ctx.is_full:
        return "Pick a section (Verse/Chorus) then Send to Backing Track for a tight loop."
    return (
        f"Send to Backing Track — loop <strong>{html.escape(ctx.section_label)}</strong> "
        f"@ <strong>{inp.bpm} BPM</strong> ({loops}× suggested)."
    )


def _md_to_html_block(md: str) -> str:
    out: list[str] = []
    for line in md.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("|"):
            out.append(f"<p class='pw-mono'>{html.escape(line)}</p>")
        elif "**" in line:
            safe = html.escape(line).replace("**", "<strong>", 1).replace("**", "</strong>", 1)
            out.append(f"<p>{safe}</p>")
        else:
            out.append(f"<p>{html.escape(line)}</p>")
    return "\n".join(out)


def build_custom_practice_sheet(
    *,
    song_title: str,
    artist: str,
    genre: str,
    display_key: str,
    original_key: str,
    bpm: int,
    time_signature: str,
    groove_style: str,
    level: str,
    instrument: str,
    focus: str,
    section_focus: str | None,
    sections: dict[str, list[str]],
    section_lyrics: dict[str, str] | None = None,
    lyric_cues: dict[str, list[str]] | None = None,
    backing_scope: str = "",
    backing_section: str = "",
    backing_loops: int = 0,
    metronome_loop_bars: int = 0,
) -> dict[str, Any]:
    """Build HTML worksheet + plain export from live user inputs."""
    inputs = SheetInputs(
        song_title=song_title,
        artist=artist,
        genre=genre,
        display_key=display_key,
        original_key=original_key,
        bpm=bpm,
        time_signature=time_signature,
        groove_style=groove_style,
        level=level,
        instrument=instrument,
        focus=focus,
        section_focus=section_focus,
        sections=sections,
        section_lyrics=section_lyrics or {},
        lyric_cues=lyric_cues or {},
        backing_scope=backing_scope,
        backing_section=backing_section,
        backing_loops=backing_loops,
        metronome_loop_bars=metronome_loop_bars,
    )
    ctx = _resolve_context(inputs)

    focus_title, focus_html = _build_focus_primary(ctx)
    inst_title, inst_html = _build_instrument_secondary(ctx)
    goal = _practice_goal(ctx)
    plan_html = _ten_minute_plan(ctx)
    backing_tip = _backing_line(ctx)

    deep = ""
    if ctx.active and ctx.section_chords:
        deep = section_deep_practice_markdown(
            section_name=ctx.active,
            section_chords=ctx.section_chords,
            instrument=instrument,
            level=level,
            focus=focus,
            display_key=display_key,
            bpm=bpm,
            groove_style=groove_style,
        )

    if ctx.is_full:
        lyric_parts = []
        for name in ctx.view_sections:
            block = _lyrics_block(name, inputs.section_lyrics, inputs.lyric_cues)
            if "No lyrics" not in block:
                lyric_parts.append(f"<h4>{html.escape(name)}</h4>{block}")
        lyric_html = "".join(lyric_parts) if lyric_parts else _lyrics_block("", inputs.section_lyrics, inputs.lyric_cues)
        chord_html = "".join(
            f'<div class="pw-section-block"><h4>{html.escape(name)}</h4>{_chord_bar_grid(chs)}</div>'
            for name, chs in ctx.view_sections.items()
            if chs
        )
        section_drill = "<p>Full song overview — drill one section at a time from the chart below.</p>"
    else:
        lyric_html = _lyrics_block(ctx.active or "", inputs.section_lyrics, inputs.lyric_cues)
        chord_html = _chord_bar_grid(ctx.section_chords)
        section_drill = ctx.combo_note or (ctx.profile.get("sections") or {}).get(
            _section_key(ctx.active or ""), {}
        ).get("drill", f"Isolate <strong>{html.escape(ctx.section_label)}</strong> only — {ctx.bar_count} bars.")

    variant_label = f"{instrument} · {ctx.category} · {ctx.section_label}"
    style = ctx.profile.get("style") or genre

    html_doc = f"""
<div class="practice-worksheet" data-variant="{html.escape(ctx.variant_id)}">
  <div class="pw-header">
    <p class="pw-kicker">Custom Practice Sheet · <code>{html.escape(ctx.variant_id)}</code></p>
    <h2 class="pw-title">{html.escape(song_title)}</h2>
    <p class="pw-artist">{html.escape(artist)}</p>
    <p class="pw-variant-badge">{html.escape(variant_label)} @ <strong>{bpm} BPM</strong></p>
    <div class="pw-meta-grid">
      <span><b>Key</b> {html.escape(display_key)}</span>
      <span><b>BPM</b> {bpm}</span>
      <span><b>Time</b> {html.escape(time_signature)}</span>
      <span><b>Style</b> {html.escape(style)}</span>
      <span><b>Section</b> {html.escape(ctx.section_label)}</span>
      <span><b>Instrument</b> {html.escape(instrument)}</span>
      <span><b>Level</b> {html.escape(level)}</span>
      <span><b>Focus</b> {html.escape(focus)}</span>
    </div>
    <p class="pw-goal-line"><strong>Today&apos;s goal:</strong> {goal}</p>
    {f'<p class="pw-concepts"><strong>Harmony:</strong> {html.escape(", ".join(ctx.concepts[:5]))}</p>' if ctx.concepts else ''}
  </div>

  <div class="pw-panel pw-primary">
    <h3>{html.escape(focus_title)}</h3>
    {focus_html}
  </div>

  <div class="pw-panel">
    <h3>{html.escape(inst_title)}</h3>
    {inst_html}
  </div>

  <div class="pw-panel">
    <h3>Section drill — {html.escape(ctx.section_label)}</h3>
    <p>{section_drill}</p>
  </div>

  <div class="pw-panel">
    <h3>Chord chart — {html.escape(ctx.section_label)} only</h3>
    {chord_html}
  </div>

  <div class="pw-panel">
    <h3>Lyrics &amp; cues — {html.escape(ctx.section_label)}</h3>
    {lyric_html}
  </div>

  {f'<div class="pw-panel"><h3>Section coach</h3><div class="pw-md">{_md_to_html_block(deep)}</div></div>' if deep and not ctx.is_full else ''}

  <div class="pw-panel pw-tools">
    <h3>Studio tools (matched to your settings)</h3>
    <ul class="pw-checklist-tools">
      <li>Metronome — <strong>{ctx.loop_bars} bars</strong> · <strong>{bpm} BPM</strong> · {html.escape(time_signature)}</li>
      <li>Section Deep Focus — <strong>{html.escape(ctx.section_label)}</strong></li>
      <li>Chord coach — chords from this sheet only</li>
      <li>{backing_tip}</li>
    </ul>
  </div>

  <div class="pw-panel pw-plan">
    <h3>Today&apos;s 10-minute plan ({html.escape(level)})</h3>
    {plan_html}
    <p class="pw-repeat"><strong>Repeat this loop 5 times</strong> before raising tempo or changing section.</p>
  </div>
</div>
""".strip()

    inputs_echo = {
        "song": song_title,
        "artist": artist,
        "section": ctx.section_label,
        "section_focus_raw": section_focus,
        "instrument": instrument,
        "instrument_kind": inputs.instrument_kind(),
        "level": level,
        "focus": focus,
        "focus_category": ctx.category,
        "bpm": bpm,
        "groove_style": groove_style,
        "display_key": display_key,
        "backing_scope": backing_scope or "(not set on Backing page yet)",
        "backing_section": backing_section,
        "backing_loops": backing_loops,
        "metronome_loop_bars": ctx.loop_bars,
        "variant_id": ctx.variant_id,
        "variant_label": variant_label,
        "bar_count": ctx.bar_count,
        "chords_preview": ctx.section_chords[:8],
    }

    plain = _plain_export(ctx=ctx, goal=goal, focus_title=focus_title, inst_title=inst_title, backing_tip=backing_tip, plan_html=plan_html, inputs_echo=inputs_echo)

    return {
        "html": html_doc,
        "plain": plain,
        "section_label": ctx.section_label,
        "category": ctx.category,
        "variant_id": ctx.variant_id,
        "variant_label": variant_label,
        "inputs_echo": inputs_echo,
    }


def _plain_export(
    *,
    ctx: SheetContext,
    goal: str,
    focus_title: str,
    inst_title: str,
    backing_tip: str,
    plan_html: str,
    inputs_echo: dict[str, Any],
) -> str:
    inp = ctx.inputs
    lines = [
        f"# {inp.song_title} — {inputs_echo['variant_label']}",
        f"Variant: {ctx.variant_id}",
        "",
        "## Generator inputs",
        f"- Song: {inp.song_title} ({inp.artist})",
        f"- Section: {ctx.section_label}",
        f"- Instrument: {inp.instrument} ({inputs_echo['instrument_kind']})",
        f"- Level: {inp.level}",
        f"- Focus: {inp.focus} → {ctx.category}",
        f"- BPM: {inp.bpm} | Groove: {inp.groove_style}",
        f"- Backing: {inputs_echo['backing_scope']} / {inputs_echo['backing_section']}",
        "",
        f"## Goal",
        re.sub(r"<[^>]+>", "", goal),
        "",
        f"## {focus_title}",
        f"## {inst_title}",
        "",
        "## Chords",
    ]
    for name, chs in ctx.view_sections.items():
        if chs:
            lines.append(f"### {name}")
            lines.append(" | ".join(chs))
    lines.extend(["", "## 10-minute plan", re.sub(r"<[^>]+>", "", plan_html), "", "## Tools", re.sub(r"<[^>]+>", "", backing_tip)])
    return "\n".join(lines)
