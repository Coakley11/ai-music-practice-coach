"""Custom practice worksheet generator — song, section, instrument, and focus aware."""

from __future__ import annotations

import html
import re
from typing import Any

from music_theory import (
    NOTE_TO_MIDI,
    normalize_root,
    semitone_distance,
    split_chord,
    transpose_chord,
)

from practice_studio import (
    PIANO_COMP_PATTERNS,
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

# Song-specific coaching blurbs (title, artist) -> notes by context
_SONG_COACHING: dict[tuple[str, str], dict[str, str]] = {
    ("how deep is your love", "bee gees"): {
        "style": "Pop / soft rock ballad — warm maj7 color, gentle lift into the chorus.",
        "verse": "Verse sits on **Ebmaj7 → Gm7 → Fm7 → Bb7** — keep the bass line smooth; let maj7ths ring.",
        "chorus": "Chorus opens wider on **Abmaj7**; save 10% more tone when the hook lands.",
        "piano": "Ballad comp: LH whole-note root/5th, RH offbeat shells. Voice-lead 3rd→7th between maj7 chords.",
        "guitar": "Light arpeggio or half-notes; avoid heavy strums. Watch **Fm7 → Bb7** with a common-tone finger.",
        "sax": "Concert **Eb**; sing through the line on verse — target 3rd on maj7, b7 on Bb7.",
        "voice": "Soft falsetto setup in verse; breathe before the question-hook in chorus. Vowels narrow on ascent.",
    },
    ("so nice (summer samba)", "marcos valle"): {
        "style": "Bossa / samba — light swing, nylon or piano bossa pattern, never rush beat 2.",
        "verse": "Verse cycles **Fmaj7 → G7 → Gm7 → C7** — bossa bass anticipates beat 3.",
        "chorus": "Chorus brightens on **Fmaj7 → Dm7 → Gm7 → C7**; keep the samba bounce.",
        "guitar": "Bossa pattern: bass on 1 and anticipatory 8th before 3; fingers brush up on 2 & 4.",
        "piano": "LH bossa: root – chord – chord; RH syncopated offbeats. Stay lighter than you think.",
        "sax": "Concert **F**; use mixolydian on G7, dorian on Gm7. Phrase behind the beat.",
        "voice": "Portuguese/English lyric sits behind the groove; short breaths every 2 bars.",
    },
}


def normalize_practice_focus(focus: str) -> str:
    """Map UI focus dropdown to worksheet category."""
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


def _song_lookup(title: str, artist: str) -> dict[str, str]:
    return _SONG_COACHING.get(
        (title.strip().lower(), (artist or "").strip().lower()),
        {},
    )


def _section_transitions(chords: list[str], limit: int = 4) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for i in range(len(chords) - 1):
        a, b = chords[i], chords[i + 1]
        if a != b:
            out.append((a, b))
    return out[:limit]


def _chord_color_note(chord: str) -> str:
    c = chord.lower()
    if "maj7" in c or "maj9" in c:
        return "major 7th color"
    if "m7b5" in c or "ø" in c:
        return "half-diminished"
    if "m7" in c and "maj" not in c:
        return "minor 7th"
    if "/" in chord:
        return "slash bass motion"
    if re.search(r"(?<![a-z])7", c) and "maj" not in c:
        return "dominant tension"
    if "dim" in c:
        return "diminished pull"
    return "tonal center"


def _simple_roman_line(chords: list[str], key: str) -> str:
    if not chords or not key:
        return ""
    key_root = normalize_root(split_chord(key)[0])
    key_midi = NOTE_TO_MIDI.get(key_root)
    if key_midi is None:
        return ""
    uniq: list[str] = []
    for ch in chords[:8]:
        if ch not in uniq:
            uniq.append(ch)
    numerals: list[str] = []
    for ch in uniq:
        root, suf = split_chord(ch.split("/")[0])
        rm = NOTE_TO_MIDI.get(normalize_root(root))
        if rm is None:
            continue
        deg = (rm - key_midi) % 12
        map_deg = {
            0: "I",
            2: "ii",
            4: "iii",
            5: "IV",
            7: "V",
            9: "vi",
            11: "vii°",
        }
        n = map_deg.get(deg, f"?({root})")
        if "m" in suf.lower() and "maj" not in suf.lower() and not n.startswith("vii"):
            n = n.lower() if len(n) == 1 else "ii" if deg == 2 else "vi" if deg == 9 else n + "m"
        if "7" in suf and "maj" not in suf.lower():
            n = n + "7" if "7" not in n else n
        if "maj7" in suf.lower():
            n = n.replace("7", "") + "maj7" if n in ("I", "IV") else n
        numerals.append(f"**{ch}** ≈ {n}")
    return " · ".join(numerals[:6])


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
        for line in text.splitlines()[:6]:
            line = line.strip()
            if line:
                items.append(f"<li>{html.escape(line)}</li>")
    for cue in cues[:4]:
        items.append(f"<li><em>{html.escape(str(cue))}</em></li>")
    if not items:
        return "<p><em>Add lyric cues in the sidebar to personalize phrasing notes.</em></p>"
    return "<ul class='pw-list'>" + "".join(items) + "</ul>"


def _instrument_block(
    *,
    instrument: str,
    level: str,
    display_key: str,
    section_chords: list[str],
    groove_style: str,
    time_sig: str,
    song_notes: dict[str, str],
    section_name: str,
) -> str:
    inst = (instrument or "").lower()
    hard = _section_transitions(section_chords)
    hard_txt = ", ".join(f"{html.escape(a)}→{html.escape(b)}" for a, b in hard[:3]) or "steady bar-by-bar"

    if "guitar" in inst:
        shape, capo = _best_guitar_shape_key(display_key)
        capo_line = (
            f"<li><strong>Capo:</strong> {capo} fret — play <strong>{shape}</strong> shapes, sounds in <strong>{display_key}</strong>.</li>"
            if capo
            else f"<li><strong>Shapes:</strong> open <strong>{shape}</strong> grips work in this key.</li>"
        )
        fb = ""
        if section_chords:
            fb = f"<div class='pw-sub'>{fretboard_ascii(section_chords[0], level)}</div>"
        sn = song_notes.get("guitar") or song_notes.get("verse", "")
        return f"""
<ul class="pw-list">
  {capo_line}
  <li><strong>Strum / feel:</strong> {html.escape(groove_style)} — see rhythm grid below.</li>
  <li><strong>Hard changes:</strong> {hard_txt}</li>
  <li><strong>Color:</strong> {_chord_color_note(section_chords[0]) if section_chords else '—'} on first harmony.</li>
  {f'<li><strong>Song tip:</strong> {html.escape(sn)}</li>' if sn else ''}
</ul>
{fb}
""".strip()

    if "piano" in inst or "keyboard" in inst:
        comp = PIANO_COMP_PATTERNS.get(groove_style, PIANO_COMP_PATTERNS["Pop groove"])
        sn = song_notes.get("piano") or song_notes.get("verse", "")
        return f"""
<ul class="pw-list">
  <li><strong>LH pattern:</strong> roots on 1; add 5th or chord tone on 3 in ballads.</li>
  <li><strong>RH voicings:</strong> 3rd+7th shells; avoid jumping both hands on every change.</li>
  <li><strong>Comping:</strong> {html.escape(comp)}</li>
  <li><strong>Bass movement:</strong> connect roots by step where possible ({hard_txt}).</li>
  {f'<li><strong>Song tip:</strong> {html.escape(sn)}</li>' if sn else ''}
</ul>
""".strip()

    if "sax" in inst or "trumpet" in inst or "clarinet" in inst:
        labels = transposing_instrument_labels(instrument)
        written = [transpose_for_label(display_key, lb) for lb in labels[:1]] or [display_key]
        sn = song_notes.get("sax") or song_notes.get("verse", "")
        scale_lines = ""
        if section_chords:
            scale_lines = f"<li>{scale_suggestions_for_chord(section_chords[0], display_key, level, instrument)}</li>"
        return f"""
<ul class="pw-list">
  <li><strong>Concert key:</strong> {html.escape(display_key)} · <strong>Written:</strong> {html.escape(written[0])}</li>
  <li><strong>Target tones:</strong> land 3rd/7th of each chord on beat 1; use guide tones between changes.</li>
  {scale_lines}
  <li><strong>Breath / phrasing:</strong> 2-bar phrases; breathe before {html.escape(section_name)} peaks.</li>
  {f'<li><strong>Song tip:</strong> {html.escape(sn)}</li>' if sn else ''}
</ul>
""".strip()

    if "voice" in inst or "vocal" in inst:
        sn = song_notes.get("voice") or song_notes.get("verse", "")
        return f"""
<ul class="pw-list">
  <li><strong>Range:</strong> practice in <strong>{html.escape(display_key)}</strong>; transpose sidebar if tight.</li>
  <li><strong>Pitch targets:</strong> root of each chord on downbeats; hum 3rd before words.</li>
  <li><strong>Breathing:</strong> mark one breath every 2 bars; inhale on rest before chorus if present.</li>
  <li><strong>Delivery:</strong> verse = intimate; chorus = fuller tone without pushing.</li>
  {f'<li><strong>Song tip:</strong> {html.escape(sn)}</li>' if sn else ''}
</ul>
""".strip()

    if "bass" in inst:
        return f"""
<ul class="pw-list">
  <li><strong>Root on 1</strong> · fifth or octave on 3 where the groove allows.</li>
  <li><strong>Approach:</strong> chromatic walk into the next root ({hard_txt}).</li>
  <li><strong>Pocket:</strong> lock to kick; {html.escape(groove_style)} at {html.escape(time_sig)}.</li>
</ul>
""".strip()

    return f"<p>Lock to the chord chart in <strong>{html.escape(display_key)}</strong>; emphasize clean changes ({hard_txt}).</p>"


def _focus_block(
    *,
    category: str,
    instrument: str,
    level: str,
    section_chords: list[str],
    display_key: str,
    bpm: int,
    groove_style: str,
    time_sig: str,
    section_name: str,
    section_bar_count: int,
) -> str:
    hard = _section_transitions(section_chords, 3)
    loop_bars = max(4, min(section_bar_count, 8)) if section_bar_count else 4
    inst = (instrument or "").lower()

    if category == "Rhythm":
        rhythm_md = rhythm_guide_markdown(instrument, groove_style, time_sig)
        return f"""
<p><strong>Count-in:</strong> 1 – 2 – 3 – 4 · start on beat 1 at <strong>{bpm} BPM</strong>.</p>
<div class="pw-rhythm-md">{_md_to_html_block(rhythm_md)}</div>
<p><strong>Where chords change:</strong> every bar — {' · '.join(html.escape(c) for c in section_chords[:6])}{'…' if len(section_chords) > 6 else ''}</p>
<p><strong>Loop:</strong> metronome or backing — <strong>{loop_bars} bars</strong> of <strong>{html.escape(section_name)}</strong> × 5.</p>
""".strip()

    if category == "Chords":
        roman = _simple_roman_line(section_chords, display_key)
        colors = ", ".join(_chord_color_note(c) for c in section_chords[:4])
        trans = "<br/>".join(
            f"• <strong>{html.escape(a)} → {html.escape(b)}</strong> — common tone or nearest inversion"
            for a, b in hard
        ) or "• Loop single bars until each change is clean."
        return f"""
<p><strong>Progression:</strong> {' · '.join(html.escape(c) for c in section_chords[:12])}</p>
{f'<p><strong>Roman numerals (approx.):</strong> {roman}</p>' if roman else ''}
<p><strong>Chord color:</strong> {html.escape(colors)}</p>
<div class="pw-sub"><strong>Hardest transitions</strong><br/>{trans}</div>
""".strip()

    if category == "Scales & Improvisation":
        licks = []
        for ch in section_chords[:4]:
            licks.append(f"<li>{scale_suggestions_for_chord(ch, display_key, level, instrument)}</li>")
        return f"<ul class='pw-list'>{''.join(licks)}</ul>" if licks else "<p>Use chord tones on beats 1 and 3.</p>"

    if category == "Transitions":
        items = "".join(
            f"<li>Loop <strong>{html.escape(a)} → {html.escape(b)}</strong> 8× at 60% tempo, then 4× at full tempo.</li>"
            for a, b in hard[:4]
        )
        return f"<ul class='pw-list'>{items or '<li>Link pairs of bars slowly.</li>'}</ul>"

    if category == "Timing":
        slow = max(40, int(bpm * 0.65))
        med = max(50, int(bpm * 0.82))
        return f"""
<ul class="pw-list">
  <li><strong>Slow ({slow} BPM):</strong> quarter-note pulse — 2 min</li>
  <li><strong>Medium ({med} BPM):</strong> eighth subdivisions — 2 min</li>
  <li><strong>Full ({bpm} BPM):</strong> full section — 3 min</li>
  <li><strong>Subdivision:</strong> {'8ths' if time_sig.startswith('4') else 'triplets'} on the hi-hat / inner pulse</li>
</ul>
""".strip()

    return f"<p>Apply your <strong>{html.escape(category)}</strong> focus across the chord path in <strong>{html.escape(section_name)}</strong>.</p>"


def _ten_minute_plan(level: str, category: str, bpm: int, loop_bars: int) -> str:
    if level == "Beginner":
        return f"""
<ol class="pw-checklist">
  <li>2 min — count 1-2-3-4 at <strong>{bpm} BPM</strong> (no instrument)</li>
  <li>3 min — one bar at a time through the loop</li>
  <li>3 min — two-bar links</li>
  <li>2 min — full <strong>{loop_bars}-bar</strong> loop × 2</li>
</ol>
<p class="pw-goal"><strong>Goal before moving on:</strong> one clean loop with no stopped beats.</p>
""".strip()
    if level == "Advanced":
        return f"""
<ol class="pw-checklist">
  <li>2 min — guide-tone line through the section</li>
  <li>3 min — full tempo with one rhythmic variation</li>
  <li>3 min — backing track / Send to Backing Track loop</li>
  <li>2 min — one musical risk (fill, reharm, or dynamic arc)</li>
</ol>
<p class="pw-goal"><strong>Goal before moving on:</strong> one performance-ready pass with intentional dynamics.</p>
""".strip()
    return f"""
<ol class="pw-checklist">
  <li>2 min — chord-tone warm-up on the first change</li>
  <li>4 min — <strong>{loop_bars}-bar</strong> loop × 5 at <strong>{bpm} BPM</strong></li>
  <li>2 min — hardest transition only</li>
  <li>2 min — full section with {category.lower()} focus</li>
</ol>
<p class="pw-goal"><strong>Goal before moving on:</strong> confident time + clean chord change at full tempo.</p>
""".strip()


def _md_to_html_block(md: str) -> str:
    """Minimal markdown table/lines to HTML for rhythm block."""
    out: list[str] = []
    for line in md.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("|"):
            out.append(f"<p class='pw-mono'>{html.escape(line)}</p>")
        elif line.startswith("**"):
            out.append(f"<p>{line.replace('**', '<strong>', 1).replace('**', '</strong>', 1)}</p>")
        else:
            out.append(f"<p>{html.escape(line)}</p>")
    return "\n".join(out)


def _practice_goal_sentence(
    *,
    title: str,
    section_label: str,
    instrument: str,
    focus: str,
    category: str,
    song_notes: dict[str, str],
) -> str:
    sec_key = section_label.lower()
    if "verse" in sec_key and song_notes.get("verse"):
        return song_notes["verse"]
    if "chorus" in sec_key and song_notes.get("chorus"):
        return song_notes["chorus"]
    if song_notes.get("style"):
        return f"{song_notes['style']} — {category} work on {section_label} for {instrument}."
    return f"Master <strong>{section_label}</strong> of <strong>{title}</strong> with {category} focus ({focus})."


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
) -> dict[str, Any]:
    """Build HTML worksheet + plain markdown export."""
    section_lyrics = section_lyrics or {}
    lyric_cues = lyric_cues or {}
    view_sections = practice_display_sections(sections, section_focus)
    active = practice_active_section_name(section_focus, sections)
    is_full = practice_is_full_song(section_focus)
    section_label = "Full Song" if is_full else (active or "Section")
    section_chords = (
        [c for chs in view_sections.values() for c in (chs or [])]
        if is_full
        else list(view_sections.get(active or "", []) or [])
    )
    bar_count = len(section_chords) if not is_full else sum(len(v) for v in view_sections.values())

    category = normalize_practice_focus(focus)
    song_notes = _song_lookup(song_title, artist)
    concepts = chord_concepts_from_sections(
        {k: v for k, v in view_sections.items() if v},
        genre=genre,
    )
    goal = _practice_goal_sentence(
        title=song_title,
        section_label=section_label,
        instrument=instrument,
        focus=focus,
        category=category,
        song_notes=song_notes,
    )
    loop_bars = max(4, bar_count) if bar_count else 8

    deep = ""
    if active and section_chords:
        deep = section_deep_practice_markdown(
            section_name=active,
            section_chords=section_chords,
            instrument=instrument,
            level=level,
            focus=focus,
            display_key=display_key,
            bpm=bpm,
            groove_style=groove_style,
        )

    inst_html = _instrument_block(
        instrument=instrument,
        level=level,
        display_key=display_key,
        section_chords=section_chords,
        groove_style=groove_style,
        time_sig=time_signature,
        song_notes=song_notes,
        section_name=section_label,
    )
    focus_html = _focus_block(
        category=category,
        instrument=instrument,
        level=level,
        section_chords=section_chords,
        display_key=display_key,
        bpm=bpm,
        groove_style=groove_style,
        time_sig=time_signature,
        section_name=section_label,
        section_bar_count=bar_count,
    )
    plan_html = _ten_minute_plan(level, category, bpm, loop_bars)

    lyric_html = ""
    if is_full:
        parts = []
        for name in view_sections:
            block = _lyrics_block(name, section_lyrics, lyric_cues)
            if "Add lyric" not in block:
                parts.append(f"<p><strong>{html.escape(name)}</strong></p>{block}")
        lyric_html = "".join(parts) if parts else _lyrics_block("", section_lyrics, lyric_cues)
    elif active:
        lyric_html = _lyrics_block(active, section_lyrics, lyric_cues)

    chord_sections_html = ""
    if is_full:
        for name, chs in view_sections.items():
            if chs:
                chord_sections_html += (
                    f'<div class="pw-section-block"><h4>{html.escape(name)}</h4>'
                    f"{_chord_bar_grid(chs)}</div>"
                )
    else:
        chord_sections_html = _chord_bar_grid(section_chords)

    backing_tip = (
        f"Use <strong>Send to Backing Track</strong> — loops <strong>{html.escape(section_label)}</strong> "
        f"at <strong>{bpm} BPM</strong>."
        if not is_full
        else "Use <strong>Send to Backing Track</strong> for full song or pick a section on Practice first."
    )

    html_doc = f"""
<div class="practice-worksheet">
  <div class="pw-header">
    <p class="pw-kicker">Custom Practice Sheet</p>
    <h2 class="pw-title">{html.escape(song_title)}</h2>
    <p class="pw-artist">{html.escape(artist)}</p>
    <div class="pw-meta-grid">
      <span><b>Key</b> {html.escape(display_key)}</span>
      <span><b>BPM</b> {bpm}</span>
      <span><b>Time</b> {html.escape(time_signature)}</span>
      <span><b>Style</b> {html.escape(genre)}</span>
      <span><b>Section</b> {html.escape(section_label)}</span>
      <span><b>Instrument</b> {html.escape(instrument)}</span>
      <span><b>Level</b> {html.escape(level)}</span>
      <span><b>Focus</b> {html.escape(focus)}</span>
    </div>
    <p class="pw-goal-line"><strong>Today&apos;s goal:</strong> {goal}</p>
    {f'<p class="pw-concepts"><strong>Harmony in this chart:</strong> {html.escape(", ".join(concepts[:5]))}</p>' if concepts else ''}
  </div>

  <div class="pw-panel">
    <h3>Chord chart — {html.escape(section_label)}</h3>
    {chord_sections_html}
  </div>

  <div class="pw-panel">
    <h3>Lyrics &amp; cues</h3>
    {lyric_html}
  </div>

  <div class="pw-panel pw-split">
    <div><h3>Instrument guide — {html.escape(instrument)}</h3>{inst_html}</div>
    <div><h3>Focus — {html.escape(category)}</h3>{focus_html}</div>
  </div>

  {f'<div class="pw-panel"><h3>Section coach</h3><div class="pw-md">{_md_to_html_block(deep)}</div></div>' if deep else ''}

  <div class="pw-panel pw-tools">
    <h3>Connect to your tools</h3>
    <ul class="pw-checklist-tools">
      <li>Metronome — loop <strong>{loop_bars} bars</strong> · {bpm} BPM · {html.escape(time_signature)}</li>
      <li>Section Deep Focus — same section as this sheet</li>
      <li>Chord coach &amp; scale suggestions — chords from this sheet</li>
      <li>{backing_tip}</li>
    </ul>
  </div>

  <div class="pw-panel pw-plan">
    <h3>Today&apos;s 10-minute plan</h3>
    {plan_html}
    <p class="pw-repeat"><strong>Repeat this loop 5 times</strong> before raising tempo or changing section.</p>
  </div>
</div>
""".strip()

    plain = _plain_export(
        song_title=song_title,
        artist=artist,
        genre=genre,
        display_key=display_key,
        bpm=bpm,
        time_signature=time_signature,
        groove_style=groove_style,
        level=level,
        instrument=instrument,
        focus=focus,
        section_label=section_label,
        section_chords=section_chords,
        view_sections=view_sections,
        goal=goal,
        category=category,
        inst_html=inst_html,
        focus_html=focus_html,
        plan_html=plan_html,
        deep=deep,
        backing_tip=backing_tip,
    )

    return {
        "html": html_doc,
        "plain": plain,
        "section_label": section_label,
        "category": category,
    }


def _plain_export(**kwargs: Any) -> str:
    """Strip HTML for download."""
    title = kwargs["song_title"]
    lines = [
        f"# Custom Practice Sheet — {title}",
        f"Artist: {kwargs['artist']}",
        f"Key: {kwargs['display_key']} | BPM: {kwargs['bpm']} | Time: {kwargs['time_signature']}",
        f"Style: {kwargs['genre']} | Groove: {kwargs['groove_style']}",
        f"Section: {kwargs['section_label']} | Instrument: {kwargs['instrument']} | Level: {kwargs['level']}",
        f"Focus: {kwargs['focus']} ({kwargs['category']})",
        "",
        f"Today's goal: {re.sub('<[^>]+>', '', kwargs['goal'])}",
        "",
        "## Chords",
    ]
    for name, chs in kwargs["view_sections"].items():
        if chs:
            lines.append(f"### {name}")
            lines.append(" | ".join(chs))
    lines.extend(["", "## 10-minute plan", re.sub("<[^>]+>", "", kwargs["plan_html"])])
    lines.extend(["", "## Tools", kwargs["backing_tip"]])
    return "\n".join(lines)
