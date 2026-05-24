"""Improvisation Intelligence — coaching engine (harmony, motifs, missions, style jams)."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any

from music_theory import CHROMATIC, normalize_root, split_chord, transpose_chord

STYLE_JAM_STYLES: tuple[str, ...] = (
    "Bossa Nova",
    "Jazz Swing",
    "Blues",
    "Funk",
    "Pop",
    "Rock",
    "Neo Soul",
    "Fusion",
    "Modal Vamp",
    "Lo-fi",
    "Latin",
)

MOOD_OPTIONS: tuple[str, ...] = ("Bright", "Mellow", "Dark", "Energetic", "Dreamy", "Gritty")
DIFFICULTY_LEVELS: tuple[str, ...] = ("Beginner", "Intermediate", "Advanced")
GROOVE_INTENSITY: tuple[str, ...] = ("Light", "Medium", "Heavy")

# Progression templates: list of (section_label, chords)
STYLE_PROGRESSIONS: dict[str, list[tuple[str, list[str]]]] = {
    "Bossa Nova": [
        ("A", ["Dm7", "G7", "Cmaj7", "Cmaj7"]),
        ("B", ["Dm7", "G7", "Em7", "A7"]),
        ("A'", ["Dm7", "G7", "Cmaj7", "Cmaj7"]),
    ],
    "Jazz Swing": [
        ("Head", ["Dm7", "G7", "Cmaj7", "A7"]),
        ("Bridge", ["Dm7", "G7", "Em7", "A7", "Dm7", "G7", "Cmaj7", "Cmaj7"]),
    ],
    "Blues": [
        ("12-bar", ["C7", "C7", "C7", "C7", "F7", "F7", "C7", "C7", "G7", "F7", "C7", "G7"]),
    ],
    "Funk": [
        ("Groove", ["Em7", "Em7", "Am7", "Am7", "D7", "D7", "G7", "G7"]),
    ],
    "Pop": [
        ("Verse", ["C", "G", "Am", "F"]),
        ("Chorus", ["F", "G", "C", "C"]),
    ],
    "Rock": [
        ("Riff", ["E", "E", "D", "A"]),
        ("Chorus", ["C", "D", "E", "E"]),
    ],
    "Neo Soul": [
        ("Vamp", ["Dm9", "G13", "Cmaj9", "Fmaj7"]),
    ],
    "Fusion": [
        ("A", ["Dm7", "G7alt", "Cmaj7", "F#m7b5"]),
        ("B", ["B7", "E7", "Amaj7", "Amaj7"]),
    ],
    "Modal Vamp": [
        ("Vamp", ["Dm7", "Dm7", "Dm7", "Dm7"]),
    ],
    "Lo-fi": [
        ("Loop", ["Am7", "D7", "Gmaj7", "Cmaj7"]),
    ],
    "Latin": [
        ("A", ["Am", "Dm", "G7", "C"]),
        ("B", ["F", "Fm", "C", "G"]),
    ],
}

PRACTICE_MISSIONS: tuple[str, ...] = (
    "Improvise using only chord tones",
    "Use only 5 notes in one register",
    "Focus on rhythm over note choice",
    "Create tension on dominant chords",
    "Develop one motif for the entire solo",
    "Use silence intentionally (rest every 2 bars)",
    "Resolve every phrase on beat 1",
    "No repeated rhythmic pattern twice in a row",
    "Target only guide tones (3rds & 7ths)",
    "Play one chorus without scalar runs",
)


@dataclass
class ScaleSuggestion:
    label: str
    notes: list[str]


@dataclass
class ChordCoachInsight:
    chord: str
    scales: list[str]
    scale_suggestions: list[ScaleSuggestion]
    chord_tones: list[str]
    tensions: list[str]
    avoid_notes: list[str]
    target_notes: list[str]
    motif_idea: str
    resolve_hint: str
    instrument_tips: list[str] = field(default_factory=list)


_SCALE_INTERVALS: dict[str, tuple[int, ...]] = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "major scale": (0, 2, 4, 5, 7, 9, 11),
    "major pentatonic": (0, 2, 4, 7, 9),
    "minor pentatonic": (0, 3, 5, 7, 10),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "locrian": (0, 1, 3, 5, 6, 8, 10),
    "blues": (0, 3, 5, 6, 7, 10),
    "melodic minor": (0, 2, 3, 5, 7, 9, 11),
    "melodic minor (jazz)": (0, 2, 3, 5, 7, 9, 11),
    "altered": (0, 1, 3, 4, 6, 8, 10),
    "altered (advanced)": (0, 1, 3, 4, 6, 8, 10),
    "half-diminished": (0, 1, 3, 5, 6, 8, 10),
    "half-diminished scale": (0, 1, 3, 5, 6, 8, 10),
    "locrian #2": (0, 2, 3, 5, 6, 8, 10),
}


def _note_name_at_semitone(root: str, semitone: int) -> str:
    r = normalize_root(split_chord(str(root))[0])
    if r not in CHROMATIC:
        return str(root)
    return CHROMATIC[(CHROMATIC.index(r) + semitone) % 12]


def spell_scale_notes(root: str, kind: str) -> list[str]:
    """Spell scale degrees from a root and mode name (matches chart/display key)."""
    low = str(kind or "major").lower().strip()
    intervals = _SCALE_INTERVALS.get(low)
    if intervals is None:
        for key, ivals in _SCALE_INTERVALS.items():
            if key in low or low in key:
                intervals = ivals
                break
    if intervals is None:
        intervals = _SCALE_INTERVALS["major"]
    return [_note_name_at_semitone(root, i) for i in intervals]


def _pretty_scale_label(root: str, kind: str) -> str:
    k = str(kind or "major").lower().strip()
    if "pentatonic" in k:
        return f"{root} Minor Pentatonic" if "minor" in k else f"{root} Major Pentatonic"
    if "mixolydian" in k:
        return f"{root} Mixolydian"
    if "dorian" in k:
        return f"{root} Dorian"
    if "lydian" in k:
        return f"{root} Lydian"
    if "locrian" in k:
        return f"{root} Locrian" + (" #2" if "#2" in k else "")
    if "blues" in k:
        return f"{root} Blues"
    if "altered" in k:
        return f"{root} Altered"
    if "melodic minor" in k:
        return f"{root} Melodic Minor"
    if "half-diminished" in k or "diminished" in k:
        return f"{root} Half-Diminished" if "half" in k else f"{root} Diminished"
    if k in ("major", ""):
        return f"{root} Major Scale"
    return f"{root} {kind.title()} Scale"


def build_scale_suggestion(label: str) -> ScaleSuggestion:
    """Parse 'G mixolydian' / 'C major pentatonic' into labeled note spellings."""
    text = str(label or "").strip()
    parts = text.split(None, 1)
    root = parts[0] if parts else "C"
    kind = parts[1] if len(parts) > 1 else "major"
    return ScaleSuggestion(
        label=_pretty_scale_label(root, kind),
        notes=spell_scale_notes(root, kind),
    )


def format_scale_line(suggestion: ScaleSuggestion, chord_tones: list[str] | None = None) -> str:
    """Markdown bullet: scale name → notes (chord tones bold)."""
    tone_set = {normalize_root(split_chord(t)[0]) for t in (chord_tones or [])}
    parts: list[str] = []
    for note in suggestion.notes:
        n = normalize_root(split_chord(note)[0])
        if n in tone_set:
            parts.append(f"**{note}**")
        else:
            parts.append(note)
    return f"• {suggestion.label} → {' '.join(parts)}"


@dataclass
class ImprovSessionContext:
    song_title: str
    artist: str
    key_center: str
    display_key: str
    instrument: str
    level: str
    focus: str
    sections: dict[str, list[str]]
    bpm: int = 100
    style_label: str = ""
    progression_flat: list[str] = field(default_factory=list)


def _chord_quality(ch: str) -> str:
    c = str(ch).lower()
    if "m7b5" in c or "ø" in c:
        return "half-dim"
    if "dim" in c:
        return "dim"
    if "maj7" in c or "maj9" in c or "maj" in c:
        return "maj7"
    if "m7" in c or "m9" in c:
        return "m7"
    if c.endswith("m") and "maj" not in c:
        return "minor"
    if "7" in c or "13" in c or "9" in c or "11" in c:
        return "dom"
    return "major"


def _chord_root(ch: str) -> str:
    text = str(ch).split("/", 1)[0].strip()
    if text.lower() == "dorian":
        return "D"
    root, _ = split_chord(text)
    return normalize_root(root)


def flatten_sections(sections: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    for _name, chords in (sections or {}).items():
        for ch in chords or []:
            if ch and str(ch).strip():
                out.append(str(ch).strip())
    return out


def generate_style_progression(
    *,
    style: str,
    key_center: str = "C",
    difficulty: str = "Intermediate",
    mood: str = "Mellow",
    seed: int | None = None,
) -> dict[str, list[str]]:
    """Build section dict for a style jam in the requested key."""
    rng = random.Random(seed)
    template = STYLE_PROGRESSIONS.get(style, STYLE_PROGRESSIONS["Pop"])
    steps = _key_steps_to_center(key_center)
    sections: dict[str, list[str]] = {}
    for label, chords in template:
        transposed = [transpose_chord(c, steps) for c in chords]
        if difficulty == "Beginner" and style == "Modal Vamp":
            root = _chord_root(transposed[0])
            transposed = [f"{root}m7"] * len(transposed)
        if mood == "Dark" and _chord_quality(transposed[0]) == "major":
            transposed[0] = transpose_chord(transposed[0], -3)
        sections[f"{label} ({style})"] = transposed
    if rng.random() < 0.3 and len(sections) >= 1:
        first_key = next(iter(sections))
        sections[first_key] = sections[first_key] + sections[first_key][-2:]
    return sections


def _key_steps_to_center(key_center: str) -> int:
    from music_theory import semitone_distance

    root, suffix = split_chord(str(key_center or "C"))
    target = normalize_root(root)
    if "m" in suffix.lower() and "maj" not in suffix.lower():
        pass
    return semitone_distance("C", target)


def chord_coach_insight(
    chord: str,
    *,
    key_center: str,
    next_chord: str = "",
    instrument: str = "Guitar",
    level: str = "Intermediate",
) -> ChordCoachInsight:
    """Real-time improvisation suggestions for one harmony."""
    root = _chord_root(chord)
    qual = _chord_quality(chord)
    third = transpose_chord(root, 4 if qual in ("major", "maj7", "dom") else 3)
    if qual in ("minor", "m7", "half-dim"):
        third = transpose_chord(root, 3)
    fifth = transpose_chord(root, 7)
    seventh = ""
    scales: list[str] = []
    tensions: list[str] = []
    avoid: list[str] = []
    targets: list[str] = []

    if qual == "dom":
        scales = [f"{root} mixolydian", f"{root} blues", f"{root} altered (advanced)"]
        seventh = transpose_chord(root, 10)
        tensions = [f"9 on {root}", f"13 color", f"b9 / #9 (tension)"]
        avoid = [f"Avoid lingering on {transpose_chord(root, 11)} without resolving"]
        targets = [third, seventh]
    elif qual in ("m7", "minor"):
        scales = [f"{root} dorian", f"{root} minor pentatonic", f"{root} melodic minor (jazz)"]
        seventh = transpose_chord(root, 10)
        tensions = [f"11 on {root}", "passing 9th"]
        avoid = [f"Major 3rd against {chord} (unless blues inflection)"]
        targets = [root, third, seventh or fifth]
    elif qual == "maj7":
        scales = [f"{root} major", f"{root} lydian", f"{root} major pentatonic"]
        seventh = transpose_chord(root, 11)
        tensions = [f"maj7", f"9", f"#11 (lydian)"]
        avoid = [f"b3 on {root} major sonority"]
        targets = [third, seventh or root]
    elif qual == "half-dim":
        scales = [f"{root} locrian", f"{root} locrian #2", "half-diminished scale"]
        tensions = ["b5 as color", "approach from below"]
        avoid = ["Natural major 3rd"]
        targets = [root, transpose_chord(root, 3)]
    else:
        scales = [f"{root} major", f"{root} major pentatonic"]
        targets = [root, third, fifth]

    motif = f"3-note motif: {root} – {third} – {fifth}; repeat rhythmically, then invert interval direction."
    resolve = ""
    if next_chord:
        nr = _chord_root(next_chord)
        resolve = f"Resolve voice-leading into **{next_chord}** — land on a chord tone of {nr} on beat 1."

    inst_tips = instrument_coaching_lines(instrument, chord, level, qual, root)

    scale_labels = scales[:4]
    scale_suggestions = [build_scale_suggestion(label) for label in scale_labels]

    return ChordCoachInsight(
        chord=chord,
        scales=scale_labels,
        scale_suggestions=scale_suggestions,
        chord_tones=[root, third, fifth] + ([seventh] if seventh else []),
        tensions=tensions[:3],
        avoid_notes=avoid[:2],
        target_notes=targets[:4],
        motif_idea=motif,
        resolve_hint=resolve,
        instrument_tips=inst_tips,
    )


def instrument_coaching_lines(
    instrument: str,
    chord: str,
    level: str,
    quality: str,
    root: str,
) -> list[str]:
    inst = (instrument or "").strip()
    lines: list[str] = []
    if inst == "Guitar":
        lines.append(f"Pentatonic box from **{root}** — connect chord-shape grips for {chord}.")
        if level != "Beginner":
            lines.append("Guide tones: 3rd & 7th on adjacent strings; target-note exercise into next change.")
        if level == "Advanced":
            lines.append("Try enclosure around 3rd, or superimpose a triad a tone above the root.")
    elif inst == "Piano":
        lines.append(f"LH shell: root + 7th of {chord}; RH chord tones or mode in one position.")
        if level != "Beginner":
            lines.append("Voice-lead 3rd→3rd and 7th→3rd into the next harmony.")
        if level == "Advanced":
            lines.append("Comp sparse hits on 2 & 4; melodic phrase in opposite register from LH.")
    elif inst in ("Saxophone", "Trumpet", "Clarinet", "Flute"):
        lines.append("Phrase in 2-bar units; leave space — breath before the downbeat of bar 3.")
        if quality == "dom":
            lines.append("Articulation: accent arrival tones; use softer tonguing on approach notes.")
        if level == "Advanced":
            lines.append("Motif: repeat a 3-note shape, then rhythmic displacement by an eighth note.")
    else:
        lines.append(f"Sing the chord tones of {chord}, then improvise a short motif from the suggested scale.")
    return lines[:4]


def level_coaching_summary(level: str) -> dict[str, str]:
    if level == "Beginner":
        return {
            "focus": "One scale · root targeting · simple rhythm",
            "scale": "Use one pentatonic or major/minor scale for the whole section.",
            "rhythm": "Quarter notes and half notes only — leave rests.",
            "harmony": "Start every phrase on the root or 5th of the current chord.",
        }
    if level == "Advanced":
        return {
            "focus": "Substitutions · altered colors · rhythmic displacement",
            "scale": "Superimpose alternate scales; outside → inside resolutions.",
            "rhythm": "Displace motifs by 8th/16th; use metric modulation across 2-bar cells.",
            "harmony": "Play altered dominants, tritone subs, and upper-structure triads.",
        }
    return {
        "focus": "Chord tones · guide tones · modal color · phrase development",
        "scale": "Primary mode per chord; connect chord tones across changes.",
        "rhythm": "Vary phrase length: 1-bar, 2-bar, and 3-bar ideas.",
        "harmony": "Target 3rds and 7ths on strong beats; use approach tones.",
    }


def generate_motif(seed: int | None = None) -> dict[str, Any]:
    rng = random.Random(seed)
    pcs = ["C", "D", "E", "G", "A", "B"]
    notes = rng.sample(pcs, 3)
    rhythms = ["♩ ♩ ♩", "♪ ♪ ♩", "♩ ♪ ♪", "♩. ♪"]
    return {
        "notes": notes,
        "display": " – ".join(notes),
        "rhythm": rng.choice(rhythms),
        "variation_prompt": (
            f"Take **{' – '.join(notes)}** and vary rhythmically for 8 bars "
            f"(try {rng.choice(rhythms)} feel). Then invert the interval direction on repetition 3."
        ),
    }


def generate_jam_session(
    *,
    ensemble: str = "Jazz trio",
    style: str = "Jazz Swing",
    key_center: str = "Eb",
    tempo: int = 120,
    mood: str = "Dark",
    seed: int | None = None,
) -> dict[str, Any]:
    rng = random.Random(seed)
    sections = generate_style_progression(
        style=style,
        key_center=key_center,
        difficulty="Intermediate",
        mood=mood,
        seed=seed,
    )
    atmosphere = {
        "Bright": "daylight clarity, forward motion",
        "Mellow": "warm room, brushed feel",
        "Dark": "late-night, minor leaning",
        "Energetic": "uptempo drive, tight hits",
        "Dreamy": "reverb wash, floating time",
        "Gritty": "edge and backbeat",
    }.get(mood, "focused groove")
    return {
        "title": f"{mood} {style} — {ensemble}",
        "ensemble": ensemble,
        "style": style,
        "key": key_center,
        "bpm": tempo + rng.randint(-8, 8),
        "atmosphere": atmosphere,
        "sections": sections,
        "prompt": (
            f"**{ensemble}** in **{key_center}** · {style} · ~{tempo} BPM · {atmosphere}."
        ),
    }


def harmony_flow_map(sections: dict[str, list[str]], key_center: str) -> list[dict[str, str]]:
    """Color-coded progression flow for visualization."""
    rows: list[dict[str, str]] = []
    flat = flatten_sections(sections)
    for i, ch in enumerate(flat[:24]):
        qual = _chord_quality(ch)
        if qual == "dom":
            role, color = "Dominant / tension", "#f59e0b"
        elif qual in ("m7", "minor"):
            role, color = "Minor / color", "#6366f1"
        elif qual == "maj7":
            role, color = "Tonic / release", "#22c55e"
        else:
            role, color = "Stable / color", "#94a3b8"
        next_ch = flat[i + 1] if i + 1 < len(flat) else ""
        rows.append({
            "index": str(i + 1),
            "chord": ch,
            "role": role,
            "color": color,
            "arrow": f"→ {next_ch}" if next_ch else "",
        })
    return rows


def creativity_metrics_placeholder() -> dict[str, float]:
    """Non-judgmental diversity indices (demo / future audio analysis)."""
    return {
        "melodic_diversity": 0.72,
        "rhythmic_diversity": 0.65,
        "motif_development": 0.58,
        "tension_release_balance": 0.61,
        "repetition_index": 0.42,
        "phrase_spacing": 0.70,
    }


def ai_feedback_preview_lines() -> list[str]:
    return [
        "Each selected metric gets a % score, what went well, and what to improve.",
        "Overall Improvisation Score averages your selected criteria for this take.",
        "Scoring uses your active song, chords, instrument, level, focus, and the recording.",
        "Progress history tracks metrics across uploads (e.g. Motif development 52% → 76%).",
    ]
