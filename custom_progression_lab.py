"""Custom Progression Lab — builder, harmonic analysis, and practice exercises."""

from __future__ import annotations

from music_theory import semitone_distance, transpose_chord

from creative_lab_text import (
    chord_quality,
    chord_root,
    first_matching_pattern,
    root_pc,
    roman_path,
    section_analysis_lines,
    NOTE_TO_PC,
)

CPL_SAVED_KEY = "cpl_saved_progressions"
CPL_ACTIVE_KEY = "cpl_active_progression"
CPL_LAST_DISPLAY_KEY = "cpl_last_display_key"

DEFAULT_SECTIONS = {
    "Verse": [
        {"chord": "Am", "bars": 1},
        {"chord": "Dm", "bars": 1},
        {"chord": "G7", "bars": 1},
        {"chord": "Cmaj7", "bars": 1},
    ],
    "Chorus": [
        {"chord": "Fmaj7", "bars": 1},
        {"chord": "Bm7b5", "bars": 1},
        {"chord": "E7", "bars": 1},
        {"chord": "Am", "bars": 1},
    ],
}


def default_active_progression():
    home_key = "C"
    original = {k: [dict(x) for x in v] for k, v in DEFAULT_SECTIONS.items()}
    return {
        "name": "Untitled progression",
        "original_key_center": home_key,
        "original_sections": original,
        "time_signature": "4/4",
        "bpm": 100,
        "groove_style": "Auto",
        "loops": 2,
    }


def deep_copy_sections(sections):
    return {
        name: [dict(entry) for entry in entries]
        for name, entries in (sections or {}).items()
    }


def ensure_original_structure(active):
    """Migrate legacy active dicts to original_sections + original_key_center."""
    if not active:
        return default_active_progression()
    if not active.get("original_sections"):
        legacy = active.get("sections") or DEFAULT_SECTIONS
        active["original_sections"] = deep_copy_sections(legacy)
    if not active.get("original_key_center"):
        active["original_key_center"] = active.get("key_center", "C")
    active.pop("sections", None)
    active.pop("key_center", None)
    return active


def transpose_section_entries(entries, from_key, to_key):
    steps = semitone_distance(from_key, to_key)
    if steps == 0:
        return [dict(entry) for entry in entries or []]
    out = []
    for entry in entries or []:
        chord = normalize_chord_symbol(entry.get("chord", ""))
        if not chord:
            continue
        out.append(
            {
                "chord": transpose_chord(chord, steps),
                "bars": max(1, int(entry.get("bars", 1) or 1)),
            }
        )
    return out


def transpose_lab_sections(sections, from_key, to_key):
    return {
        name: transpose_section_entries(entries, from_key, to_key)
        for name, entries in (sections or {}).items()
    }


def display_sections_for_key(active, display_key):
    active = ensure_original_structure(active)
    home = active.get("original_key_center", "C")
    original = active.get("original_sections") or {}
    return transpose_lab_sections(original, home, display_key)


def commit_display_sections_to_original(active, display_sections, display_key):
    active = ensure_original_structure(active)
    home = active.get("original_key_center", "C")
    active["original_sections"] = transpose_lab_sections(
        display_sections,
        display_key,
        home,
    )
    return active


def anchor_home_key_to_display(active, display_key):
    """Re-home the progression in the current sidebar display key."""
    active = ensure_original_structure(active)
    active["original_sections"] = display_sections_for_key(active, display_key)
    active["original_key_center"] = display_key
    return active


def invalidate_cpl_derived_outputs(session_state):
    session_state.pop("cpl_backing_wav", None)
    session_state.pop("cpl_backing_signature", None)
    session_state.pop("cpl_analysis_md", None)
    session_state.pop("cpl_exercises_md", None)


def on_cpl_anchor_home_key() -> None:
    """Button callback: store transposed chart as the new written/home key."""
    import streamlit as st

    active = ensure_original_structure(st.session_state.get(CPL_ACTIVE_KEY) or {})
    practice_key = st.session_state.get("display_key", active.get("original_key_center", "C"))
    anchor_home_key_to_display(active, practice_key)
    st.session_state[CPL_ACTIVE_KEY] = active
    invalidate_cpl_derived_outputs(st.session_state)


def on_global_display_key_change(session_state, display_key):
    last = session_state.get(CPL_LAST_DISPLAY_KEY)
    if last is None:
        session_state[CPL_LAST_DISPLAY_KEY] = display_key
        return False
    if last != display_key:
        session_state[CPL_LAST_DISPLAY_KEY] = display_key
        invalidate_cpl_derived_outputs(session_state)
        return True
    return False


def backing_signature(display_key, sections, bpm, loops, groove_style):
    flat = all_chords_from_lab_sections(sections)
    return (display_key, tuple(flat), int(bpm), int(loops), str(groove_style))


def format_chord_bar_line(sections, max_chords: int = 12) -> str:
    """Single-line bar chart preview, e.g. | G | Em | C | D |."""
    chords = all_chords_from_lab_sections(sections)[:max_chords]
    if not chords:
        return "| *(add chords below)* |"
    return "| " + " | ".join(chords) + " |"


def cpl_transpose_explanation_markdown(
    home_key: str,
    practice_key: str,
    original_sections,
    display_sections,
) -> str:
    """Beginner-friendly explanation of written vs practice key for the CPL page."""
    home_key = str(home_key or "C")
    practice_key = str(practice_key or home_key)
    steps = semitone_distance(home_key, practice_key)
    orig_line = format_chord_bar_line(original_sections)
    trans_line = format_chord_bar_line(display_sections)

    if steps == 0:
        shift_note = (
            f"Right now both keys are **{home_key}**, so the chords you see are exactly "
            "what you typed in the written key."
        )
    else:
        shift_note = (
            f"The app moved every chord **{'+' if steps else ''}{steps} semitone(s)** "
            f"from **{home_key}** to **{practice_key}** for display, backing track, and exercises."
        )

    example_written = format_chord_bar_line(
        {
            "Example": [
                {"chord": "G", "bars": 1},
                {"chord": "Em", "bars": 1},
                {"chord": "C", "bars": 1},
                {"chord": "D", "bars": 1},
            ]
        }
    )
    example_transposed = format_chord_bar_line(
        {
            "Example": [
                {"chord": "A", "bars": 1},
                {"chord": "F#m", "bars": 1},
                {"chord": "D", "bars": 1},
                {"chord": "E", "bars": 1},
            ]
        }
    )

    return f"""### How keys work in Custom Progression Lab

**Written / Home Key — {home_key}**  
The key your progression was *written in*. These chords are stored as your original chart.

**Practice / Display Key — {practice_key}**  
The key you want to *see, hear, and practice in* right now. Change this in the **sidebar** under **Practice / display key** (it applies to the whole app).

#### What happens when you change the sidebar key?
The app keeps your **written** chords safe, then **transposes** them to the practice key for this page, backing tracks, and exercises.

**Example (not your song — just to show the idea):**

| | |
|---|---|
| Written / Home Key **G** | {example_written} |
| Practice / Display Key **A** | {example_transposed} |

#### Your progression right now
{shift_note}

**Original (written in {home_key}):**  
`{orig_line}`

**Transposed (what you see/hear in {practice_key}):**  
`{trans_line}`

*Tip: Chord boxes below show **practice** chords (what you hear). Change the sidebar **Practice / display key** to move the whole progression up or down. Use **Reset to original key** to match your written chart again.*
"""


def transpose_debug_lines(active, display_key):
    """Human-readable transpose state for UI debugging."""
    active = ensure_original_structure(active)
    home = active.get("original_key_center", "C")
    steps = semitone_distance(home, display_key)
    original_flat = all_chords_from_lab_sections(active.get("original_sections") or {})
    display_flat = all_chords_from_lab_sections(display_sections_for_key(active, display_key))
    first_orig = original_flat[0] if original_flat else "(none)"
    first_disp = display_flat[0] if display_flat else "(none)"
    lines = [
        f"**Written / Home key:** {home}",
        f"**Practice / Display key:** {display_key}",
        f"**Transpose:** {'+' if steps else ''}{steps} semitone(s)",
        f"**First chord (written):** {first_orig}",
        f"**First chord (practice):** {first_disp}",
    ]
    if len(original_flat) >= 4:
        sample_orig = " | ".join(original_flat[:4])
        sample_disp = " | ".join(display_flat[:4])
        lines.append(f"**First four (written):** {sample_orig}")
        lines.append(f"**First four (practice):** {sample_disp}")
    return lines


def normalize_chord_symbol(text):
    raw = str(text or "").strip()
    if not raw:
        return ""
    head = raw.split("/", 1)[0].strip()
    if len(head) < 1:
        return ""
    return raw


def parse_chord_line(line):
    if not line:
        return []
    parts = [p.strip() for p in line.replace("|", ",").split(",")]
    out = []
    for part in parts:
        ch = normalize_chord_symbol(part)
        if ch:
            out.append({"chord": ch, "bars": 1})
    return out


def flatten_sections_to_events(sections):
    events = []
    for section_name, entries in (sections or {}).items():
        if not entries:
            continue
        section_bars = 0
        expanded = []
        for entry in entries:
            chord = normalize_chord_symbol(entry.get("chord", ""))
            if not chord:
                continue
            bars = max(1, int(entry.get("bars", 1) or 1))
            for _ in range(bars):
                expanded.append(chord)
        section_bars = len(expanded)
        for idx, chord in enumerate(expanded):
            events.append(
                {
                    "chord": chord,
                    "section": section_name,
                    "bar_in_section": idx,
                    "section_bars": max(1, section_bars),
                }
            )
    return events


def sections_to_chord_lists(sections):
    out = {}
    for name, entries in (sections or {}).items():
        chords = []
        for entry in entries or []:
            ch = normalize_chord_symbol(entry.get("chord", ""))
            if not ch:
                continue
            bars = max(1, int(entry.get("bars", 1) or 1))
            chords.extend([ch] * bars)
        if chords:
            out[name] = chords
    return out


def all_chords_from_lab_sections(sections):
    chords = []
    for _name, chs in sections_to_chord_lists(sections).items():
        chords.extend(chs)
    return chords


def estimate_key_center(sections, fallback="C"):
    chords = all_chords_from_lab_sections(sections)
    if not chords:
        return fallback
    pcs = [root_pc(ch) for ch in chords if root_pc(ch) is not None]
    if not pcs:
        return fallback
    counts = {}
    for pc in pcs:
        counts[pc] = counts.get(pc, 0) + 1
    tonic_pc = max(counts, key=counts.get)
    for name, pc in NOTE_TO_PC.items():
        if pc == tonic_pc and "#" not in name and len(name) == 1:
            return name
        if pc == tonic_pc and name in ("C", "D", "E", "F", "G", "A", "B"):
            return name
    inv = {v: k for k, v in NOTE_TO_PC.items() if "#" not in k and len(k) == 1}
    return inv.get(tonic_pc, fallback)


def detect_progression_patterns(chords, key_center):
    findings = []
    if not chords:
        return findings
    pattern = first_matching_pattern(chords, key_center)
    if pattern:
        findings.append(pattern)

    key_pc = NOTE_TO_PC.get(chord_root(key_center))
    if key_pc is None:
        return findings

    roots = [root_pc(ch) for ch in chords]
    rel = [None if pc is None else (pc - key_pc) % 12 for pc in roots]

    # ii-V-I (any start)
    for i in range(len(rel) - 2):
        if rel[i : i + 3] == [2, 7, 0]:
            findings.append("ii-V-I resolution (local)")
            break

    # circle of fifths descent
    if len(rel) >= 3:
        fifths = 0
        for i in range(len(rel) - 1):
            if rel[i] is not None and rel[i + 1] is not None and (rel[i] - rel[i + 1]) % 12 == 7:
                fifths += 1
        if fifths >= 2:
            findings.append("circle-of-fifths root motion")

    # blues fragment (I, IV, I, V or similar)
    if len(rel) >= 4 and rel[0] == 0 and 5 in rel[:4] and 7 in rel[:4]:
        findings.append("blues / dominant-cycle movement")

    # minor-key: i -> iv -> V
    if len(rel) >= 3 and rel[0] == 9 and rel[1] == 5 and rel[2] == 7:
        findings.append("minor-key motion (i-iv-V)")

    qualities = [chord_quality(ch) for ch in chords]
    if any("half-diminished" in q for q in qualities) and any("dominant" in q for q in qualities):
        if "minor ii-V tension" not in findings:
            findings.append("minor ii-V language")

    # modal mixture hint: bVI or bVII in major
    if key_pc is not None and any(r in (8, 10) for r in rel if r is not None):
        if 0 in rel or 9 in rel:
            findings.append("possible modal mixture (borrowed color)")

    # dominant resolution moments
    for i, ch in enumerate(chords):
        if "7" in str(ch).lower() and i + 1 < len(chords):
            nxt = chords[i + 1]
            if chord_quality(nxt) in ("major", "major seventh", "minor"):
                findings.append(f"dominant resolution: {ch} -> {nxt}")
                break

    return list(dict.fromkeys(findings))


def tension_resolution_notes(chords, key_center):
    if len(chords) < 2:
        return ["Single-chord or static harmony — focus on groove and melodic rhythm."]
    lines = []
    for i, ch in enumerate(chords):
        q = chord_quality(ch)
        if "dominant" in q or "diminished" in q or "half-diminished" in q:
            target = chords[i + 1] if i + 1 < len(chords) else chords[0]
            lines.append(f"Tension at **{ch}** — aim for resolution into **{target}**.")
    if not lines:
        lines.append("Harmony is mostly stable — create interest with rhythm, register, and phrasing.")
    return lines[:4]


def suggested_scales_for_chord(ch, key_center):
    q = chord_quality(ch)
    root = chord_root(ch)
    if "dominant" in q:
        return [f"{root} mixolydian", f"{root} diminished whole-half (passing)", "altered dominant (advanced)"]
    if "minor seventh" in q or q == "minor":
        return [f"{root} dorian", f"{root} minor pentatonic", f"{root} melodic minor (jazz)"]
    if "major seventh" in q:
        return [f"{root} major scale", f"{root} lydian (for #11 color)"]
    if "half-diminished" in q:
        return [f"{root} locrian", f"{root} locrian #2", "super Locrian / altered (over V)"]
    return [f"{root} major scale", f"{root} major pentatonic"]


def harmonic_analysis_markdown(sections, key_center, time_signature="4/4"):
    chord_lists = sections_to_chord_lists(sections)
    all_chords = all_chords_from_lab_sections(sections)
    est_key = estimate_key_center(sections, key_center)
    lines = [
        "# Harmonic Analysis",
        f"**Your key center:** {key_center} | **Estimated from chords:** {est_key}",
        f"**Time signature:** {time_signature}",
        "",
        "## Progression patterns",
    ]
    patterns = detect_progression_patterns(all_chords, key_center)
    if patterns:
        lines.extend(f"- {p}" for p in patterns)
    else:
        lines.append("- No standard pop/jazz cell detected yet — listen for bass direction and dominant arrivals.")

    lines.append("\n## Roman numeral sketch")
    roman = roman_path(all_chords, key_center, limit=12)
    lines.append(f"- {roman or 'Add more chords to see a Roman numeral path.'}")

    lines.append("\n## Tension and resolution")
    lines.extend(f"- {n}" for n in tension_resolution_notes(all_chords, key_center))

    lines.append("\n## Section breakdown")
    for sec, chords in chord_lists.items():
        lines.extend(section_analysis_lines(sec, chords, key_center))

    lines.append("\n## Scales / modes (by chord)")
    seen = set()
    for ch in all_chords[:8]:
        if ch in seen:
            continue
        seen.add(ch)
        scales = suggested_scales_for_chord(ch, key_center)
        lines.append(f"- **{ch}:** {', '.join(scales[:2])}")

    return "\n".join(lines)


def _instrument_exercise_block(instrument, level, focus, chords, key_center, groove_style, patterns):
    blocks = []
    inst = instrument or "General"
    pat_text = ", ".join(patterns[:3]) if patterns else "your progression"

    if inst in ["Saxophone", "Flute", "Trumpet", "Clarinet"]:
        blocks.append("### Horn / wind practice")
        blocks.append("- Play chord tones through each change: root, 3rd, 5th, 7th (where present).")
        blocks.append("- Target **3rds and 7ths** on strong beats; use lighter articulation on stable chords.")
        blocks.append("- Write a **guide-tone line** (3rd to 3rd, 7th to 3rd) through two passes.")
        blocks.append("- Add **approach notes** (half-step above/below) into target tones on beats 1 and 3.")
        if "ii-V-I" in pat_text:
            blocks.append("- On ii-V-I: use dorian on ii, mixolydian/altered on V, resolve to chord tones on I.")
        if level == "Advanced":
            blocks.append("- Practice rhythmic displacement: start phrases on the & of 2 or beat 4.")

    elif inst == "Guitar":
        blocks.append("### Guitar practice")
        blocks.append("- **Comping:** practice Freddie Green-style quarter-note pulses, then add skips on the &s.")
        blocks.append("- Map **triad shapes** on the top three strings for each chord; move the nearest shape.")
        blocks.append("- **Voice-leading grips:** connect 3rds/7ths on the middle strings without jumping.")
        blocks.append("- Arpeggiate each chord: root–3rd–5th–7th, then 3rd–5th–7th–9th where available.")
        if focus == "Rhythm":
            blocks.append(f"- Match the **{groove_style}** feel before adding fills.")

    elif inst == "Piano":
        blocks.append("### Piano practice")
        blocks.append("- **Shell voicings:** root or 5th in left hand; 3rd and 7th in right hand.")
        blocks.append("- **Left-hand roots** on beat 1; add fifth or octave on beat 3.")
        blocks.append("- **Comping rhythm:** Charleston or off-beat hits depending on groove.")
        blocks.append("- Connect 3rds/7ths by half-step motion between chords.")

    elif inst == "Bass":
        blocks.append("### Bass practice")
        blocks.append("- Lock **root / fifth / octave** pattern per chord first.")
        blocks.append("- Write a **two-bar walking line** using chord tones and chromatic approaches.")
        blocks.append("- Approach the next root from above or below by half-step on beat 4.")
        if "blues" in pat_text.lower():
            blocks.append("- Blues: emphasize b7 on dominant chords; use shuffle feel.")

    elif inst == "Voice":
        blocks.append("### Voice practice")
        blocks.append("- **Sing roots** of each chord on beat 1 to internalize the form.")
        blocks.append("- **Sing 3rds** to hear major vs minor color changes.")
        blocks.append("- Improvise **short melodic phrases** (2 bars) that land on a chord tone.")
        blocks.append("- Mark breaths before long phrases; save strongest dynamic for dominant arrivals.")

    else:
        blocks.append("### General practice")
        blocks.append("- Play chord roots, then add 3rds and 5ths through the form.")
        blocks.append("- Use 2-bar phrases that land on a chord tone on beat 1.")

    return blocks


def generate_exercises_markdown(
    *,
    sections,
    instrument,
    level,
    focus,
    key_center,
    groove_style,
    time_signature,
    bpm,
):
    chord_lists = sections_to_chord_lists(sections)
    all_chords = all_chords_from_lab_sections(sections)
    patterns = detect_progression_patterns(all_chords, key_center)

    lines = [
        "# Practice & Improvisation Exercises",
        f"**Instrument:** {instrument} | **Level:** {level} | **Focus:** {focus}",
        f"**Key:** {key_center} | **Feel:** {groove_style} | **{time_signature} @ {bpm} BPM**",
        "",
        "## Detected harmonic ideas",
    ]
    if patterns:
        for p in patterns:
            lines.append(f"- {p}")
            if "ii-V-I" in p:
                lines.append("  - Identify the ii, V, and I chords in your chart.")
                lines.append("  - Practice scales: dorian (ii), mixolydian/altered (V), major (I).")
                lines.append("  - Target notes: 3rd of ii, 7th of V, 3rd/7th of I.")
    else:
        lines.append("- Work chord-by-chord: root, 3rd, 5th, 7th on each change.")

    lines.append("\n## Instrument drills")
    lines.extend(_instrument_exercise_block(instrument, level, focus, all_chords, key_center, groove_style, patterns))

    lines.append("\n## Section loops")
    for sec, chords in chord_lists.items():
        path = " | ".join(chords[:8])
        if len(chords) > 8:
            path += " | ..."
        lines.append(f"- **{sec}:** loop slowly — {path}")

    lines.append("\n## Level guidance")
    if level == "Beginner":
        lines.append("- One chord per bar; roots only, then roots + 3rds.")
        lines.append("- Record yourself and check that changes land on beat 1.")
    elif level == "Intermediate":
        lines.append("- Add guide-tone targeting and one repeating 2-bar motif.")
        lines.append("- Practice with the backing at 70–80% tempo first.")
    else:
        lines.append("- Use chromatic approaches, delayed resolutions, and motivic development.")
        lines.append("- Try playing only on offbeats for one chorus.")

    return "\n".join(lines)


def lab_context_for_coaching(sections, key_center, instrument, level, focus):
    chord_lists = sections_to_chord_lists(sections)
    flat = all_chords_from_lab_sections(sections)
    first_sec = next(iter(chord_lists), "Custom")
    first_chords = chord_lists.get(first_sec, flat[:4])
    return {
        "sections": chord_lists,
        "flat_chords": flat,
        "first_section": first_sec,
        "first_chords": first_chords,
        "key_center": key_center,
        "instrument": instrument,
        "level": level,
        "focus": focus,
    }


def save_progression(store, name, data):
    data = ensure_original_structure(dict(data))
    store[name] = {
        "name": name,
        "original_key_center": data.get("original_key_center", "C"),
        "original_sections": deep_copy_sections(data.get("original_sections")),
        "time_signature": data.get("time_signature", "4/4"),
        "bpm": data.get("bpm", 100),
        "groove_style": data.get("groove_style", "Auto"),
        "loops": data.get("loops", 2),
    }
    return store


def delete_progression(store, name):
    store.pop(name, None)
    return store
