"""Practice studio helpers: song cards, transpose tips, scales, rhythm, sessions."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import date, timedelta
from typing import Any

from music_theory import (
    COMMON_KEYS,
    NOTE_TO_MIDI,
    display_key_options,
    normalize_root,
    semitone_distance,
    split_chord,
    transpose_chord,
)

GUITAR_FRIENDLY_KEYS = ("G", "D", "A", "E", "C")
VOCAL_EASY_KEYS = ("C", "G", "D", "A", "F")
PIANO_EASY_KEYS = ("C", "F", "G", "Am center via C", "D")

STRUM_PATTERNS = {
    "Pop groove": ("D", "D", "U", "D", "U", "D", "U"),
    "Rock groove": ("D", "D", "U", "U", "D", "U"),
    "Ballad": ("D", "—", "D", "U", "—", "U"),
    "Funk groove": ("D", "U", "D", "U", "D", "U", "D", "U"),
    "Bossa nova": ("D", "—", "U", "—", "D", "—", "U", "—"),
    "Jazz swing": ("D", "—", "U", "D", "U", "—"),
}

PIANO_COMP_PATTERNS = {
    "Pop groove": "LH root on 1 & 3 · RH chords on 2 & 4 (and & of 2)",
    "Rock groove": "LH root octaves · RH stabs on 2 & 4",
    "Ballad": "LH whole-note root/5th · RH broken chord on beat 3",
    "Bossa nova": "LH bossa pattern (root-chord-chord) · RH syncopated offbeats",
    "Jazz swing": "LH walking root · RH shell voicings on 2 and 4",
    "Funk groove": "LH syncopated root · RH short staccato grips on the pocket",
}


def _accidental_count(key: str) -> int:
    return sum(1 for c in str(key) if c in "#b")


def song_card_meta(record: dict[str, Any]) -> dict[str, Any]:
    """Display metadata for a song selection card."""
    genre = record.get("genre", "Pop")
    key = record.get("key", "C")
    ext = record.get("extensions") or {}
    bpm = ext.get("default_bpm")
    versions = record.get("chart_versions") or {}
    levels = list(versions.keys()) if versions else ["Beginner", "Intermediate", "Advanced"]
    if len(levels) >= 3:
        difficulty = "All levels"
    elif "Advanced" in levels:
        difficulty = "Intermediate–Advanced"
    elif "Beginner" in levels and len(levels) == 1:
        difficulty = "Beginner-friendly"
    else:
        difficulty = " · ".join(levels[:2])

    instruments = _instruments_for_genre(genre)
    return {
        "title": record.get("title", "Song"),
        "artist": record.get("artist", ""),
        "genre": genre,
        "key": key,
        "bpm": int(bpm) if bpm else None,
        "difficulty": difficulty,
        "instruments": instruments,
        "trusted": bool(record.get("trusted_core")),
    }


def sections_for_record(record: dict[str, Any], level: str = "Intermediate") -> dict[str, list[str]]:
    versions = record.get("chart_versions") or {}
    if level in versions and versions[level]:
        return versions[level]
    return record.get("sections") or {}


def _ordered_section_labels(sections: dict[str, list[str]]) -> list[str]:
    return practice_ordered_section_names(sections)


def _default_bpm_for_record(record: dict[str, Any]) -> int:
    ext = record.get("extensions") or {}
    if ext.get("default_bpm"):
        try:
            return int(ext["default_bpm"])
        except (TypeError, ValueError):
            pass
    title = (record.get("title") or "").lower()
    if "how deep" in title:
        return 105
    if "shape of you" in title:
        return 96
    return 100


def _default_time_signature_for_record(record: dict[str, Any], sections: dict[str, list[str]]) -> str:
    title = (record.get("title") or "").lower()
    keys = " ".join(sections.keys()).lower()
    if "3/4" in keys or "piano man" in title:
        return "3/4"
    if "6/8" in keys or "perfect" in title:
        return "6/8"
    return "4/4"


def genre_visual_style(genre: str) -> dict[str, str]:
    g = (genre or "Pop").lower()
    styles = {
        "jazz": ("Jazz", "🎷", "linear-gradient(145deg, #1e3a5f 0%, #312e81 55%, #4c1d95 100%)"),
        "blues": ("Blues", "🎸", "linear-gradient(145deg, #1c1917 0%, #44403c 50%, #78350f 100%)"),
        "rock": ("Rock", "🤘", "linear-gradient(145deg, #450a0a 0%, #7f1d1d 55%, #1e293b 100%)"),
        "funk": ("Funk", "🕺", "linear-gradient(145deg, #422006 0%, #a16207 45%, #713f12 100%)"),
        "soul": ("Soul", "💜", "linear-gradient(145deg, #3b0764 0%, #6b21a8 55%, #831843 100%)"),
        "bossa": ("Bossa", "🌴", "linear-gradient(145deg, #064e3b 0%, #047857 50%, #0f766e 100%)"),
    }
    for token, payload in styles.items():
        if token in g:
            return {"label": payload[0], "emoji": payload[1], "gradient": payload[2]}
    if "pop" in g:
        return {
            "label": "Pop",
            "emoji": "🎤",
            "gradient": "linear-gradient(145deg, #1d4ed8 0%, #6366f1 50%, #ec4899 100%)",
        }
    return {
        "label": genre or "Song",
        "emoji": "🎵",
        "gradient": "linear-gradient(145deg, #0f172a 0%, #334155 55%, #475569 100%)",
    }


def chord_concepts_from_sections(sections: dict[str, list[str]], *, genre: str = "") -> list[str]:
    chords = [str(c).strip() for chs in sections.values() for c in (chs or []) if str(c).strip()]
    if not chords:
        return ["form reading", "steady pulse"]

    concepts: list[str] = []
    if any("maj7" in c or "maj9" in c for c in chords):
        concepts.append("major 7th color")
    if any("/" in c for c in chords):
        concepts.append("slash chords / bass motion")
    if any(
        re.search(r"(?<![a-z])7(?!#|b|\d)", c, re.I) and "maj7" not in c.lower() and "m7" not in c.lower()
        for c in chords
    ):
        concepts.append("dominant 7th tension")
    if any("m7b5" in c.lower() or "ø" in c for c in chords):
        concepts.append("half-diminished color")
    if any("sus" in c.lower() for c in chords):
        concepts.append("suspended voicings")

    roots: list[int] = []
    for ch in chords:
        head = ch.split("/")[0]
        root, _ = split_chord(head)
        midi = NOTE_TO_MIDI.get(normalize_root(root))
        if midi is not None:
            roots.append(midi)

    for i in range(len(roots) - 1):
        a, b = roots[i], roots[i + 1]
        if (b - a) % 12 in (1, 2, 11):
            concepts.append("chromatic passing motion")
            break

    for i in range(len(chords) - 1):
        c1, c2 = chords[i], chords[i + 1]
        if "m7" in c1.lower() and re.search(r"7(?!#|b|\d)", c2, re.I) and "maj" not in c2.lower():
            concepts.append("ii–V movement")
            break

    g = (genre or "").lower()
    if "bossa" in g:
        concepts.append("bossa rhythm")
    elif "jazz" in g:
        concepts.append("swing feel & extensions")
    elif "pop" in g or "ballad" in " ".join(sections.keys()).lower():
        concepts.append("pop ballad comping")
    elif "funk" in g or "soul" in g:
        concepts.append("pocket & syncopation")

    seen: set[str] = set()
    ordered: list[str] = []
    for item in concepts:
        low = item.lower()
        if low not in seen:
            seen.add(low)
            ordered.append(item)
    return ordered[:6]


def practice_focus_hints(record: dict[str, Any], sections: dict[str, list[str]]) -> str:
    ext = record.get("extensions") or {}
    if ext.get("arrangement_notes"):
        return str(ext["arrangement_notes"])
    genre = (record.get("genre") or "Pop").lower()
    concepts = chord_concepts_from_sections(sections, genre=record.get("genre", ""))
    bits = []
    if "maj7" in " ".join(concepts):
        bits.append("smooth voice leading")
    if "slash" in " ".join(concepts):
        bits.append("bass-line clarity")
    if "ii–V" in " ".join(concepts):
        bits.append("cadence resolution")
    if "pop" in genre:
        bits.append("pop ballad rhythm")
    if "jazz" in genre:
        bits.append("swing time & chord extensions")
    if "funk" in genre or "soul" in genre:
        bits.append("tight groove pocket")
    if not bits:
        bits = ["steady tempo", "clean chord changes", "section awareness"]
    return ", ".join(bits[:4])


def practice_goals_for_record(record: dict[str, Any], sections: dict[str, list[str]]) -> list[str]:
    title = record.get("title", "this song")
    section_names = _ordered_section_labels(sections)
    goals = [
        f"Lock the form: {' → '.join(section_names[:5])}" if section_names else "Map the full form once slowly",
        "Play each section 4× with metronome before adding backing",
    ]
    concepts = chord_concepts_from_sections(sections, genre=record.get("genre", ""))
    if concepts:
        goals.append(f"Study harmonic color: {', '.join(concepts[:3])}")
    if any("chorus" in n.lower() for n in section_names):
        goals.append("Save strongest dynamics for the chorus arrival")
    if record.get("trusted_core"):
        goals.append(f"Use verified chart moves in **{title}** for ear-training, not just muscle memory")
    return goals[:4]


def active_song_card_details(record: dict[str, Any], level: str = "Intermediate") -> dict[str, Any]:
    """Rich metadata for the highlighted Active Song card."""
    base = song_card_meta(record)
    sections = sections_for_record(record, level)
    ext = record.get("extensions") or {}
    genre = record.get("genre", "Pop")
    visual = genre_visual_style(genre)
    section_labels = _ordered_section_labels(sections)
    concepts = chord_concepts_from_sections(sections, genre=genre)
    bpm = base.get("bpm") or _default_bpm_for_record(record)
    key = base.get("key") or "C"
    style_label = genre
    g = genre.lower()
    notes = (ext.get("arrangement_notes") or "").lower()
    title_low = (record.get("title") or "").lower()
    if "pop" in g and ("ballad" in notes or "deep" in title_low):
        style_label = "Pop / Soft Rock Ballad"

    return {
        **base,
        "bpm": bpm,
        "time_signature": _default_time_signature_for_record(record, sections),
        "key_display": f"{key} major" if "m" not in str(key).lower() else f"{key} minor",
        "style_label": style_label,
        "sections": section_labels,
        "section_summary": ", ".join(_short_section_label(n) for n in section_labels[:6]),
        "practice_focus": practice_focus_hints(record, sections),
        "chord_concepts": concepts,
        "practice_goals": practice_goals_for_record(record, sections),
        "why_practice": (
            ext.get("arrangement_notes")
            or (
                f"Trusted practice chart for {base['title']} — "
                "work section-by-section with backing and coach tools."
            )
        ),
        "visual_emoji": visual["emoji"],
        "visual_gradient": visual["gradient"],
        "visual_genre": visual["label"],
    }


def _short_section_label(name: str) -> str:
    low = name.lower()
    if "pre" in low and "chorus" in low:
        return "Pre-Chorus"
    if "verse" in low:
        return "Verse"
    if "chorus" in low:
        return "Chorus"
    if "bridge" in low:
        return "Bridge"
    if "outro" in low:
        return "Outro"
    if "intro" in low:
        return "Intro"
    return name.split("/")[0].split("(")[0].strip()


def _instruments_for_genre(genre: str) -> str:
    g = (genre or "").lower()
    if g == "jazz":
        return "Piano, Guitar, Sax, Bass"
    if g == "rock":
        return "Guitar, Bass, Drums, Voice"
    if g == "funk" or g == "soul":
        return "Guitar, Bass, Keys, Drums"
    if g == "pop":
        return "Piano, Guitar, Voice, Bass"
    return "Piano, Guitar, Voice"


def beginner_transpose_suggestions(
    *,
    concert_key: str,
    instrument: str,
    level: str,
) -> list[str]:
    """Friendly key/capo hints for beginners."""
    if level != "Beginner":
        return []

    tips: list[str] = []
    concert_key = concert_key or "C"

    if instrument == "Guitar":
        best_shape, capo = _best_guitar_shape_key(concert_key)
        if capo > 0:
            tips.append(
                f"**Guitar:** Try **{best_shape} shapes with capo {capo}** — "
                f"you'll sound in **{concert_key}** with open-friendly grips."
            )
        else:
            tips.append(
                f"**Guitar:** **{best_shape} shapes** work well in this key (no capo needed)."
            )

    if instrument == "Voice":
        alt = _easier_vocal_key(concert_key)
        if alt != concert_key:
            tips.append(
                f"**Voice:** If the melody feels high or low, try practicing charts in **{alt}** "
                f"(+{semitone_distance(concert_key, alt)} semitones) and adjust by ear."
            )
        else:
            tips.append("**Voice:** Stay in the written key; focus on comfortable vowels and breath before words.")

    if instrument in ("Piano", "Keyboard"):
        alt = _piano_easy_key(concert_key)
        if alt != concert_key:
            tips.append(
                f"**Piano:** **{alt}** has fewer black-key chords for simpler shapes "
                f"(chart transpose: +{semitone_distance(concert_key, alt)} semitones)."
            )

    if not tips:
        tips.append(
            f"**Tip:** Use the sidebar **Practice / Display Key** to try a simpler center "
            f"(C, G, D, A) if chord shapes feel crowded."
        )
    return tips


def transposing_instrument_labels(instrument: str) -> list[str]:
    if instrument == "Saxophone":
        return ["Alto Sax (Eb)", "Tenor Sax (Bb)"]
    if instrument == "Trumpet":
        return ["Bb Trumpet"]
    if instrument == "Clarinet":
        return ["Bb Clarinet"]
    return []


def transpose_for_label(concert_key: str, label: str) -> str:
    steps = {"Alto Sax (Eb)": 9, "Tenor Sax (Bb)": 2, "Bb Trumpet": 2, "Bb Clarinet": 2}.get(label, 0)
    return transpose_chord(concert_key, steps)


def _best_guitar_shape_key(concert_key: str) -> tuple[str, int]:
    best = "G"
    best_capo = 99
    for shape in GUITAR_FRIENDLY_KEYS:
        capo = semitone_distance(shape, concert_key)
        if capo < best_capo:
            best_capo = capo
            best = shape
    return best, best_capo


def _easier_vocal_key(key: str) -> str:
    opts = [k for k in display_key_options(key) if _accidental_count(k) <= 1]
    if key in opts:
        return key
    return opts[0] if opts else "C"


def _piano_easy_key(key: str) -> str:
    for candidate in ("C", "G", "F", "D", "A"):
        if candidate in display_key_options(key):
            steps = abs(semitone_distance(key, candidate))
            if steps <= 3 and _accidental_count(candidate) <= 1:
                return candidate
    return key


def scale_suggestions_for_chord(chord: str, key_name: str, level: str, instrument: str) -> str:
    """Scale / arpeggio hints for a chord or short progression."""
    head = str(chord).split()[0] if " " in str(chord) and "–" in str(chord) else str(chord)
    if "–" in str(chord) or "->" in str(chord):
        return progression_coach_markdown(str(chord), key_name, level, instrument)

    root, suffix = split_chord(head)
    root = normalize_root(root)
    minor = "m" in suffix.lower() and "maj" not in suffix.lower()
    dom = "7" in suffix.lower() and "maj7" not in suffix.lower() and not minor

    if dom:
        scale = f"{root} mixolydian · {root} blues · target 3rd & b7"
        arpeggio = f"{root}7 chord tones: root, 3rd, 5th, b7"
    elif minor:
        scale = f"{root} natural minor · {root} dorian (raised 6)"
        arpeggio = f"{root}m7 arpeggio: root, b3, 5th, b7"
    else:
        scale = f"{root} major · {root} major pentatonic"
        arpeggio = f"{root} triad + 6th color"

    inst = (instrument or "").lower()
    extra = ""
    if "guitar" in inst:
        if level == "Beginner":
            extra = " · **Guitar:** one-octave box from root on strings 5–3; add b3 on beat 3 for minor."
        elif level == "Advanced":
            extra = " · **Guitar:** try 3-note-per-string run resolving to chord tone on beat 1."
        else:
            extra = " · **Guitar:** double stops on 3rd+5th or 3rd+7th through the bar."
    elif "piano" in inst:
        extra = " · **Piano:** RH scale in one hand position; LH root on 1."

    return f"**{head}** — Scales: {scale}. Arpeggio: {arpeggio}.{extra}"


def progression_coach_markdown(progression: str, key_name: str, level: str, instrument: str) -> str:
    """Explain a progression string like ii–V–I or Am7-D7-G."""
    text = progression.replace("->", "–").replace("-", "–")
    if re.search(r"ii\s*[–-]\s*V\s*[–-]\s*I", text, re.I):
        return _ii_v_i_coach(key_name, level, instrument)
    chords = [c.strip() for c in re.split(r"[–-]", text) if c.strip()]
    if len(chords) >= 2:
        return (
            f"**Progression {' – '.join(chords[:4])}** — Connect chord tones voice-leading from "
            f"**{chords[0]}** into **{chords[1]}**; land on a chord tone of the next harmony on beat 1. "
            f"In **{key_name}**, sing the root motion first, then add 3rds."
        )
    return scale_suggestions_for_chord(progression, key_name, level, instrument)


def _ii_v_i_coach(key_name: str, level: str, instrument: str) -> str:
    lines = [
        "**ii–V–I** — The bread-and-butter jazz/pop cadence.",
        "- **ii:** use the minor 7 scale (dorian) — target b3 and b7.",
        "- **V:** mixolydian or altered dominant — emphasize 3rd and b7, resolve 7→3 of I.",
        "- **I:** major / major pentatonic — rest on root or 3rd.",
    ]
    if level == "Beginner":
        lines.append("- **Beginner:** practice only the *roots* of ii → V → I on one string first.")
    if "guitar" in (instrument or "").lower():
        lines.append(
            "- **Guitar:** shell grips (root on bass string, b7 on top for V); "
            "add **double stops** 3rd+7th on the V chord."
        )
    if "piano" in (instrument or "").lower():
        lines.append("- **Piano:** LH roots on 1; RH play 3rd+7th shells, not full block jumps.")
    lines.append(f"- In key **{key_name}**, hear the V chord *pull* into I before adding fills.")
    return "\n".join(lines)


def rhythm_guide_markdown(instrument: str, groove_style: str, time_sig: str = "4/4") -> str:
    """Strumming / comping pattern hints."""
    inst = (instrument or "").lower()
    pattern = STRUM_PATTERNS.get(groove_style, STRUM_PATTERNS["Pop groove"])
    beats = " | ".join(pattern)
    count_in = "1 – 2 – 3 – 4" if time_sig.startswith("4") else "1 – 2 – 3"

    if "guitar" in inst:
        return f"""
**Rhythm guide (guitar)** — {groove_style} · {time_sig}

| Beat | {' | '.join(str(i + 1) for i in range(len(pattern)))} |
|------|{'|'.join(['---'] * len(pattern))}|
| Strum | {' | '.join(pattern)} |

- **D** = downstroke · **U** = upstroke · **—** = rest
- Count-in: *{count_in}* then start on beat 1 with the first chord change.
- Keep the wrist loose; mute between changes if the chart moves quickly.
""".strip()

    if "piano" in inst:
        comp = PIANO_COMP_PATTERNS.get(groove_style, PIANO_COMP_PATTERNS["Pop groove"])
        return f"""
**Rhythm guide (piano)** — {groove_style} · {time_sig}

- **Pattern:** {comp}
- **Count-in:** *{count_in}*
- **LH/RH:** bass defines the pulse; RH stays lighter than you think on verses.
""".strip()

    return f"**Rhythm:** lock to **{groove_style}** at {time_sig}; use metronome on 2 & 4."


def section_deep_practice_markdown(
    *,
    section_name: str,
    section_chords: list[str],
    instrument: str,
    level: str,
    focus: str,
    display_key: str,
    bpm: int,
    groove_style: str,
) -> str:
    """Detailed breakdown for one section."""
    if not section_chords:
        return "No chords in this section."

    transitions = []
    for i in range(len(section_chords) - 1):
        a, b = section_chords[i], section_chords[i + 1]
        if a != b:
            transitions.append(f"**{a} → {b}**")

    hard = transitions[:4]
    chord_summary = " · ".join(section_chords[:12])
    if len(section_chords) > 12:
        chord_summary += " …"

    exercise = _section_exercise(section_name, section_chords, instrument, level, focus)

    return f"""
### Section focus: {html.escape(section_name)}
**{len(section_chords)} bars** in **{html.escape(display_key)}** · **{bpm} BPM** · {html.escape(groove_style)}

**Chord path:** {html.escape(chord_summary)}

**Key changes:** {html.escape(', '.join(hard) if hard else 'Loop one bar until steady, then link pairs.')}

**Section exercise:** {exercise}

**Loop tip:** Use **Backing Track** with *Single section* scope, or metronome at **{bpm}** BPM for {max(4, len(section_chords))} bars only.
""".strip()


def _section_exercise(section_name: str, chords: list[str], instrument: str, level: str, focus: str) -> str:
    role = section_name.lower()
    if "chorus" in role:
        return "Play the section 4× with backing; last time add dynamics +10%."
    if "bridge" in role:
        return "Map the first chord change only; then add the full bar line."
    if focus == "Rhythm":
        return "Metronome: 2 min chord changes only, then 2 min with groove pattern."
    if level == "Beginner":
        return "3 min: one bar at a time. 3 min: two-bar links. 2 min: full section slow."
    return "Loop 6×: accuracy pass, then musical pass, then one pass with eyes on chart only."


def fretboard_ascii(chord: str, level: str) -> str:
    """Simple ASCII fretboard diagram for guitar."""
    options = _fretboard_positions(chord, level)
    if not options:
        return f"No diagram for **{chord}** — use a chord finder app for this grip."
    label, frets, strings = options[0]
    lines = [f"**{chord}** ({label})", "```", "  " + " ".join(strings)]
    for i, row in enumerate(frets):
        lines.append(f"{i}| " + " ".join(row))
    lines.append("```")
    return "\n".join(lines)


def _fretboard_positions(chord: str, level: str) -> list[tuple[str, list[list[str]], list[str]]]:
    """Return (label, fret rows, string labels) — simplified catalog."""
    catalog: dict[str, list[tuple[str, list[str]]]] = {
        "G": [("open", ["3", "2", "0", "0", "0", "3"])],
        "D": [("open", ["x", "x", "0", "2", "3", "2"])],
        "D/F#": [("slash", ["2", "x", "0", "2", "3", "2"])],
        "Em": [("open", ["0", "2", "2", "0", "0", "0"])],
        "Em7": [("open", ["0", "2", "0", "0", "0", "0"])],
        "Am": [("open", ["x", "0", "2", "2", "1", "0"])],
        "Am7b5": [("compact", ["x", "1", "2", "2", "1", "x"])],
        "C": [("open", ["x", "3", "2", "0", "1", "0"])],
        "F": [("easy", ["x", "x", "3", "2", "1", "1"])],
        "A": [("open", ["x", "0", "2", "2", "2", "0"])],
        "A7": [("open", ["x", "0", "2", "0", "2", "0"])],
        "Bm": [("barre", ["x", "2", "4", "4", "3", "2"])],
        "F#m": [("barre", ["2", "4", "4", "2", "2", "2"])],
    }
    entry = catalog.get(chord)
    if not entry and "/" in chord:
        entry = catalog.get(chord.split("/")[0])
    if not entry:
        return []
    strings = ["E", "A", "D", "G", "B", "e"]
    out = []
    for label, fret_nums in entry:
        rows = [[fret_nums[s] if fret_nums[s] != "x" else "x" for s in range(6)]]
        if level == "Advanced" and label == "open":
            label = "position (open)"
        out.append((label, rows, strings))
    return out


def build_practice_session_from_logs(
    logs: list[dict[str, Any]],
    all_records: list[dict[str, Any]],
    *,
    minutes: int = 45,
) -> dict[str, str]:
    """AI-style session plan from practice history."""
    today = date.today()
    recent = [e for e in logs if e.get("song")][-20:]

    def pick_song(prefer_easy: bool = False, avoid: set[str] | None = None):
        avoid = avoid or set()
        if recent:
            for entry in reversed(recent):
                title = entry.get("song", "")
                if title and title not in avoid:
                    for r in all_records:
                        if r.get("title") == title:
                            return f"{title} — {r.get('artist', '')}", r
                    return f"{title}", None
        pool = [r for r in all_records if r.get("chart_status") != "placeholder"]
        if prefer_easy:
            pool = [r for r in pool if r.get("trusted_core")] or pool
        for r in pool:
            key = r.get("title", "")
            if key not in avoid:
                return f"{r['title']} — {r.get('artist', '')}", r
        return "Open song catalog", None

    used: set[str] = set()
    warmup_title, _ = pick_song(prefer_easy=True, avoid=used)
    used.add(warmup_title.split("—")[0].strip())
    main_title, _ = pick_song(avoid=used)
    used.add(main_title.split("—")[0].strip())
    tech_focus = recent[-1].get("focus", "Technique") if recent else "Rhythm / changes"
    challenge_title, _ = pick_song(avoid=used)
    cooldown_title, _ = pick_song(prefer_easy=True, avoid=used)

    block = max(5, minutes // 5)
    return {
        "warmup": f"**{warmup_title}** — {block} min easy groove, one section only.",
        "technique": f"**{tech_focus}** — {block} min scales / changes from your recent logs.",
        "main": f"**{main_title}** — {block * 2} min full chart or chorus + verse.",
        "challenge": f"**{challenge_title}** — {block} min harder chart or faster tempo.",
        "cooldown": f"**{cooldown_title}** — {block} min slow tempo, dynamics down.",
        "summary": (
            f"Session (~{minutes} min) built from **{len(recent)}** recent log entries "
            f"since {recent[0].get('date', today) if recent else today}."
        ),
    }


PRACTICE_FOCUS_FULL = "Full Song"

_SECTION_SORT_HINTS = (
    "intro",
    "verse",
    "pre-chorus",
    "pre chorus",
    "chorus",
    "bridge",
    "solo",
    "outro",
    "ending",
    "tag",
    "final",
)


def practice_ordered_section_names(sections: dict[str, list[str]]) -> list[str]:
    """Section names in musician-friendly order (chart keys, not normalized labels)."""
    from songs.form import section_order

    names = [name for name, chords in section_order(sections) if chords]
    ordered: list[str] = []
    for hint in _SECTION_SORT_HINTS:
        for name in names:
            if hint in name.lower() and name not in ordered:
                ordered.append(name)
    for name in names:
        if name not in ordered:
            ordered.append(name)
    return ordered


def practice_section_options(sections: dict[str, list[str]]) -> list[str]:
    """Dropdown/radio choices: Full Song plus each chart section."""
    return [PRACTICE_FOCUS_FULL] + practice_ordered_section_names(sections)


def practice_is_full_song(focus: str | None) -> bool:
    return not focus or focus == PRACTICE_FOCUS_FULL


def practice_display_sections(
    sections: dict[str, list[str]],
    focus: str | None,
) -> dict[str, list[str]]:
    """Lead sheet / coach view: one section or the full form."""
    if practice_is_full_song(focus):
        return sections
    if focus and focus in sections and sections.get(focus):
        return {focus: sections[focus]}
    return sections


def practice_active_section_name(
    focus: str | None,
    sections: dict[str, list[str]],
) -> str | None:
    """Resolved chart section key, or None when Full Song is selected."""
    if practice_is_full_song(focus):
        return None
    if focus and focus in sections:
        return focus
    return None


def song_groove_seed(title: str, artist: str = "") -> int:
    """Stable per-song variation for backing synthesis."""
    blob = f"{title}|{artist}".encode("utf-8")
    return int(hashlib.md5(blob).hexdigest()[:8], 16)
