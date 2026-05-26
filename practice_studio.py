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
from groove_feel import (
    GROOVE_PROFILE,
    get_profile as groove_get_profile,
    instrument_phrasing_hint as groove_instrument_hint,
    resolve_groove_style as groove_resolve,
    short_feel_tag as groove_feel_tag,
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


_STANDARD_LEVELS: tuple[str, ...] = ("Beginner", "Intermediate", "Advanced")


def _normalize_levels_list(record: dict[str, Any]) -> list[str]:
    """Return the levels supported by this record, preserving Beginner ->
    Intermediate -> Advanced order. Falls back to the full set so the
    active-song card never has a blank "Levels" line."""
    versions = record.get("chart_versions") or {}
    if versions:
        ordered: list[str] = []
        for canonical in _STANDARD_LEVELS:
            if canonical in versions:
                ordered.append(canonical)
        # Catch any non-standard tier names the chart provider added.
        for tier in versions:
            if tier not in ordered:
                ordered.append(str(tier))
        if ordered:
            return ordered
    return list(_STANDARD_LEVELS)


def song_card_meta(record: dict[str, Any]) -> dict[str, Any]:
    """Display metadata for a song selection card.

    Always returns non-empty values for ``levels``, ``difficulty``,
    ``instruments``, and ``genre`` so the active-song card on Song
    Selection never renders blank fields.
    """
    genre = record.get("genre") or "Pop"
    key = record.get("key") or "C"
    ext = record.get("extensions") or {}
    bpm = ext.get("default_bpm")
    levels = _normalize_levels_list(record)
    if len(levels) >= 3 and all(lvl in levels for lvl in _STANDARD_LEVELS):
        difficulty = "All levels"
    elif "Advanced" in levels:
        difficulty = "Intermediate–Advanced"
    elif "Beginner" in levels and len(levels) == 1:
        difficulty = "Beginner-friendly"
    else:
        difficulty = " · ".join(levels[:2])

    # Prefer an explicit catalog/instrument list if the record provides
    # one; otherwise fall back to a genre-based default so the card
    # never shows a blank "Instruments" row.
    instruments_value = (
        ext.get("instruments")
        or record.get("instruments")
        or _instruments_for_genre(genre)
    )
    if isinstance(instruments_value, (list, tuple)):
        instruments = ", ".join(str(i) for i in instruments_value if str(i).strip())
    else:
        instruments = str(instruments_value or "")
    if not instruments.strip():
        instruments = _instruments_for_genre(genre)
    return {
        "title": record.get("title") or "Song",
        "artist": record.get("artist") or "",
        "genre": genre,
        "key": key,
        "bpm": int(bpm) if bpm else None,
        "difficulty": difficulty,
        "levels": levels,
        "levels_display": " / ".join(levels) if levels else "Beginner / Intermediate / Advanced",
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
    from songs.meter import default_time_signature_for_record

    return default_time_signature_for_record(record, sections)


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


_DOM7_RE = re.compile(r"(?<![A-Za-z])7(?!#|b|\d|sus)")
_ALT_TOKENS = ("b9", "#9", "#11", "b13", "alt")
_NINE_RE = re.compile(r"(?<!1)(?<!2)9")
_THIRTEEN_RE = re.compile(r"13")


def _has_pattern(chords: list[str], pat: "re.Pattern[str]") -> bool:
    return any(pat.search(c) for c in chords)


def _has_token(chords: list[str], token: str) -> bool:
    return any(token in c.lower() for c in chords)


def practice_focus_hints(
    record: dict[str, Any],
    sections: dict[str, list[str]],
    *,
    level: str = "Intermediate",
    instrument: str = "",
) -> str:
    """Concise, level- and instrument-aware practice focus.

    Returns a short ``"phrase A \u00b7 phrase B \u00b7 ..."`` string with
    at most ~5 musical ideas - intelligent and easy to scan. The
    arrangement_notes paragraph from the catalog is intentionally **not**
    used here (it lives on the lead sheet); this string is the
    quick-glance practice intent.
    """

    chords_flat = [str(c).strip() for chs in sections.values() for c in (chs or []) if str(c).strip()]
    chords_lower = [c.lower() for c in chords_flat]
    genre = (record.get("genre") or "").lower()
    ext = record.get("extensions") or {}
    groove = str(ext.get("default_groove") or "").lower()
    level_norm = (level or "").strip().lower()
    instr_norm = (instrument or "").strip().lower()

    # ---- Level-driven musical focus (max 3 bits) -------------------------
    level_bits: list[str] = []
    if level_norm.startswith("beg"):
        level_bits.append("core chord changes")
        level_bits.append("rhythm feel & timing")
        level_bits.append("clean transitions")
    elif level_norm.startswith("adv"):
        if _has_token(chords_lower, "maj7") or _has_token(chords_lower, "maj9"):
            level_bits.append("maj7 / maj9 colors")
        if any(tok in c for c in chords_lower for tok in _ALT_TOKENS):
            level_bits.append("altered tensions")
        if _has_pattern(chords_flat, _THIRTEEN_RE) or _has_pattern(chords_flat, _NINE_RE):
            level_bits.append("9th / 13th extensions")
        if not level_bits:
            level_bits.append("rich harmonic color")
        level_bits.append("reharm ideas")
        level_bits.append("expressive dynamics & phrasing")
    else:  # Intermediate (default)
        if any("/" in c for c in chords_flat):
            level_bits.append("slash-chord voice leading")
        if _has_token(chords_lower, "maj7"):
            level_bits.append("maj7 colors")
        if _has_pattern(chords_flat, _DOM7_RE):
            level_bits.append("dominant 7th resolution")
        if any(re.search(r"(?<![A-Za-z])6(?!\d|sus)", c) for c in chords_flat):
            level_bits.append("6th-chord color")
        if _has_pattern(chords_flat, _NINE_RE) and not any(b in level_bits for b in ("maj7 colors",)):
            level_bits.append("9th-chord color")
        if not level_bits:
            level_bits.extend(("steady form", "section transitions"))

    # ---- Instrument-aware focus (max 2 bits) -----------------------------
    instrument_bits: list[str] = []
    has_slash = any("/" in c for c in chords_flat)
    if "piano" in instr_norm:
        instrument_bits.append("rolling LH arpeggios")
        instrument_bits.append("sustained slash voicings" if has_slash else "sustained voicings")
    elif "guitar" in instr_norm:
        if "ballad" in groove or "ballad" in genre:
            instrument_bits.append("fingerpicking + open strings")
        else:
            instrument_bits.append("strumming feel & picking patterns")
        instrument_bits.append("fretboard movement")
    elif "bass" in instr_norm:
        instrument_bits.append("root motion & groove lock")
        if has_slash:
            instrument_bits.append("slash-chord bass motion")
        else:
            instrument_bits.append("walking movement")
    elif "voice" in instr_norm or "vocal" in instr_norm or "singer" in instr_norm:
        instrument_bits.append("lyrical phrasing & breath pacing")
        instrument_bits.append("dynamic contour & vowel sustain")
    elif any(t in instr_norm for t in ("saxophone", "sax", "trumpet", "flute", "clarinet", "winds")):
        instrument_bits.append("breath control & long-tone phrasing")
        instrument_bits.append("target-note melodic contour")

    # ---- Genre/feel (max 1 bit) ------------------------------------------
    feel_bit = ""
    if "bossa" in genre:
        feel_bit = "bossa pulse"
    elif "jazz" in genre:
        feel_bit = "swing time"
    elif "funk" in genre or "soul" in genre:
        feel_bit = "pocket groove"
    elif "rock" in genre:
        feel_bit = "rock pulse"
    elif "ballad" in groove:
        feel_bit = "ballad pacing"

    # ---- Compose (dedupe + cap at 5) -------------------------------------
    out: list[str] = []
    for bit in level_bits[:3] + instrument_bits[:2] + ([feel_bit] if feel_bit else []):
        if bit and bit not in out:
            out.append(bit)
        if len(out) >= 5:
            break

    if not out:
        out = ["steady form", "clean chord changes"]
    return " \u00b7 ".join(out)


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


def active_song_card_details(
    record: dict[str, Any],
    level: str = "Intermediate",
    *,
    instrument: str = "",
) -> dict[str, Any]:
    """Rich metadata for the highlighted Active Song card.

    ``instrument`` (e.g. ``"Piano"``, ``"Voice"``) tunes the
    Practice Focus text. ``level`` (``"Beginner"`` /
    ``"Intermediate"`` / ``"Advanced"``) tunes both the focus text,
    which chart tier the section list comes from, and (for Beginner)
    whether the section flow is trimmed to a short Intro / Verse /
    Chorus / Outro arrangement.
    """
    base = song_card_meta(record)
    sections = sections_for_record(record, level)
    ext = record.get("extensions") or {}
    genre = record.get("genre", "Pop")
    visual = genre_visual_style(genre)
    section_labels = practice_ordered_section_names(
        sections,
        section_names=record.get("section_order"),
    )
    # Beginner-mode arrangement simplification: trim the section list
    # to the same short arc the Backing Track page uses (Intro -> Verse
    # -> Chorus -> Verse -> Chorus -> Outro) so the song card matches
    # what the singer / player will actually hear.
    try:
        from beginner_arrangement import (
            is_beginner_level as _is_beginner_lvl,
            select_beginner_section_names as _trim_for_beginner,
        )

        if _is_beginner_lvl(level):
            trimmed = _trim_for_beginner(section_labels)
            if trimmed:
                section_labels = trimmed
    except Exception:
        # Defensive: never break the song card if the helper module is
        # unavailable - fall back to the full section list.
        pass
    concepts = chord_concepts_from_sections(sections, genre=genre)
    bpm = base.get("bpm") or _default_bpm_for_record(record)
    key = base.get("key") or "C"
    style_label = genre
    g = genre.lower()
    notes = (ext.get("arrangement_notes") or "").lower()
    title_low = (record.get("title") or "").lower()
    if "pop" in g and ("ballad" in notes or "deep" in title_low):
        style_label = "Pop / Soft Rock Ballad"

    # The section flow ("Intro -> Verse -> Chorus -> ...") is the
    # primary way the song card communicates structure. If for any
    # reason the simplified flow comes back empty, fall back to a
    # readable join of the raw section labels so the card never
    # renders an empty "Sections" row.
    section_summary = _build_section_flow(section_labels)
    if not section_summary.strip() and section_labels:
        section_summary = " -> ".join(section_labels[:8])
    if not section_summary.strip():
        section_summary = "Intro -> Verse -> Chorus -> Outro"

    practice_focus_text = practice_focus_hints(
        record,
        sections,
        level=level,
        instrument=instrument,
    )
    if not str(practice_focus_text or "").strip():
        practice_focus_text = (
            "core chord changes · rhythm feel · clean transitions"
        )

    return {
        **base,
        "bpm": bpm,
        "time_signature": _default_time_signature_for_record(record, sections),
        "key_display": f"{key} major" if "m" not in str(key).lower() else f"{key} minor",
        "style_label": style_label,
        "sections": section_labels,
        # Visual section flow: arrow-separated, numbers stripped, adjacent
        # sub-parts (Verse 3A | Verse 3B) collapsed - while non-adjacent
        # repetition (Verse ... Chorus ... Verse) is preserved.
        "section_summary": section_summary,
        "practice_focus": practice_focus_text,
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
    """Strip numbering and reduce a section name to one of the canonical
    short labels used on the active-song card.

    Rules (checked in priority order):

    * "Pre-Chorus", "Pre Chorus" -> ``Pre-Chorus``
    * any "...Chorus..." (including "Final Chorus") -> ``Chorus``
    * any "...Verse..." -> ``Verse``
    * "Bridge" -> ``Bridge``
    * "Refrain" -> ``Refrain``
    * "Outro", "Ending", "Coda", "Final ..." (non-chorus) -> ``Outro``
    * "Intro" -> ``Intro``
    * "Interlude", "Tag", "Turnaround" -> ``Interlude``
    * "Solo", "Harmonica", "Instrumental", "Guitar Solo" -> ``Solo``

    Falls back to the first segment of the raw name (everything before
    "/" or "(") so unusual section names still display cleanly.
    """
    low = (name or "").lower()
    if "pre" in low and "chorus" in low:
        return "Pre-Chorus"
    if "chorus" in low:
        return "Chorus"
    if "verse" in low:
        return "Verse"
    if "bridge" in low:
        return "Bridge"
    if "refrain" in low:
        return "Refrain"
    if any(tok in low for tok in ("outro", "ending", "coda")):
        return "Outro"
    if "final" in low:
        return "Outro"
    if "intro" in low:
        return "Intro"
    if any(tok in low for tok in ("interlude", "tag", "turnaround")):
        return "Interlude"
    if any(tok in low for tok in ("solo", "harmonica", "instrumental")):
        return "Solo"
    # AABA / form-letter sections (jazz standards): "A1", "A2", "B3", "C2B"
    # -> reduce to the form letter ("A", "B", "C").
    m = re.match(r"^([A-Z])\d+[A-Za-z]?$", (name or "").strip())
    if m:
        return m.group(1)
    # Generic fallback: strip a trailing " 1", " 2A", etc. so any odd
    # section name still reads cleanly on the card. ``\s+`` (one or more
    # whitespace required) preserves meaningful range expressions like
    # "Bars 1-4" or "Section A-B" intact.
    fallback = (name or "").split("/")[0].split("(")[0].strip()
    fallback = re.sub(r"\s+\d+[A-Za-z]?$", "", fallback).strip()
    return fallback or (name or "").strip()


def _build_section_flow(section_labels: list[str]) -> str:
    """Compose the visual section flow shown on the active song card.

    Strips numbering suffixes (`Verse 1`, `Chorus 2`, ...) via
    :func:`_short_section_label` and collapses **adjacent** duplicates
    (e.g. consecutive sub-parts like `Verse 3A | Verse 3B` become a
    single `Verse`) while preserving the actual order and any
    non-adjacent repetition. The returned string uses ``" \u2192 "`` as
    the separator so the form reads as a flow rather than a list.

    Examples:

        ["Intro", "Verse 1", "Verse 2", "Chorus 1", "Verse 3A", "Verse 3B",
         "Chorus 2", "Bridge", "Chorus 3", "Outro"]
        -> "Intro \u2192 Verse \u2192 Chorus \u2192 Verse \u2192 Chorus \u2192 Bridge \u2192 Chorus \u2192 Outro"
    """
    shorts: list[str] = []
    for raw in section_labels:
        s = _short_section_label(raw)
        if not s:
            continue
        if shorts and shorts[-1] == s:
            continue
        shorts.append(s)
    return " \u2192 ".join(shorts) if shorts else ""


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


def rhythm_guide_markdown(
    instrument: str,
    groove_style: str,
    time_sig: str = "4/4",
    *,
    song_data: dict | None = None,
) -> str:
    """Strumming / comping / phrasing hints driven by ``groove_feel.GROOVE_PROFILE``.

    *groove_style* may be ``"Auto"`` (or empty) -- it will be resolved against
    *song_data* so the Practice page Rhythm Guide actually changes when the
    user picks "Auto" on a Jazz / Bossa / Funk song.
    """
    resolved = groove_resolve(groove_style, song_data)
    profile = groove_get_profile(resolved)
    inst = (instrument or "").lower()
    count_in = profile["count_in"] if time_sig.startswith("4") else "1 - 2 - 3"
    feel_line = (
        f"**Feel:** {profile['feel']} -- accent {profile['accent']}; "
        f"{profile['time_feel']}."
    )
    dynamics_line = f"**Dynamics & articulation:** {profile['dynamics']}; {profile['articulation']}."

    if "guitar" in inst:
        pattern = list(profile["strum"])
        bar_label = "Beat" if time_sig.startswith("4") else "Pulse"
        return f"""
**Rhythm guide (guitar)** -- {resolved} ({profile['feel']}) - {time_sig}

| {bar_label} | {' | '.join(str(i + 1) for i in range(len(pattern)))} |
|------|{'|'.join(['---'] * len(pattern))}|
| Strum | {' | '.join(pattern)} |

- **D** = downstroke - **U** = upstroke - **u** = light upstroke - **x** = muted - **-** = rest
- **Count-in:** *{count_in}*
- {feel_line}
- {dynamics_line}
- Tempo zone: *{profile['tempo_hint']}*.
""".strip()

    if "piano" in inst or "key" in inst:
        return f"""
**Rhythm guide (piano)** -- {resolved} ({profile['feel']}) - {time_sig}

- **Pattern:** {profile['piano_comp']}
- **Count-in:** *{count_in}*
- {feel_line}
- {dynamics_line}
- Tempo zone: *{profile['tempo_hint']}*.
""".strip()

    if "bass" in inst:
        return f"""
**Rhythm guide (bass)** -- {resolved} ({profile['feel']}) - {time_sig}

- **Bass line shape:** {profile['bass']}
- **Count-in:** *{count_in}*
- {feel_line}
- {dynamics_line}
- Tempo zone: *{profile['tempo_hint']}*.
""".strip()

    if "voice" in inst or "vocal" in inst or "sing" in inst:
        return f"""
**Vocal phrasing guide** -- {resolved} ({profile['feel']}) - {time_sig}

- **Phrasing:** {profile['voice']}
- **Count-in:** *{count_in}*
- {feel_line}
- {dynamics_line}
- Tempo zone: *{profile['tempo_hint']}*.
""".strip()

    if any(token in inst for token in ("sax", "horn", "trumpet", "flute", "clarinet", "wind")):
        return f"""
**Rhythm guide (winds)** -- {resolved} ({profile['feel']}) - {time_sig}

- **Phrasing:** {profile['winds']}
- **Count-in:** *{count_in}*
- {feel_line}
- {dynamics_line}
- Tempo zone: *{profile['tempo_hint']}*.
""".strip()

    return f"""
**Rhythm guide** -- {resolved} ({profile['feel']}) - {time_sig}

- {feel_line}
- {dynamics_line}
- **Count-in:** *{count_in}*
- Tempo zone: *{profile['tempo_hint']}*.
""".strip()


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
    song_data: dict | None = None,
) -> str:
    """Detailed breakdown for one section.

    The body now includes a **Groove feel** block that materially changes when
    the user picks a different Rhythm / Groove Feel - per-groove count, accent,
    dynamics, articulation, and an instrument-specific phrasing tip pulled from
    ``groove_feel.GROOVE_PROFILE``.
    """
    if not section_chords:
        return "No chords in this section."

    transitions = []
    for i in range(len(section_chords) - 1):
        a, b = section_chords[i], section_chords[i + 1]
        if a != b:
            transitions.append(f"**{a} -> {b}**")

    hard = transitions[:4]
    chord_summary = " - ".join(section_chords[:12])
    if len(section_chords) > 12:
        chord_summary += " ..."

    resolved_groove = groove_resolve(groove_style, song_data)
    profile = groove_get_profile(resolved_groove)
    instrument_tip = groove_instrument_hint(instrument, resolved_groove)
    exercise = _section_exercise(
        section_name, section_chords, instrument, level, focus, resolved_groove
    )

    groove_block = (
        f"**Groove feel ({html.escape(resolved_groove)}):** "
        f"{html.escape(profile['feel'])}. "
        f"Accent {html.escape(profile['accent'])}; "
        f"{html.escape(profile['time_feel'])}. "
        f"Count it: *{html.escape(profile['count_in'])}*.\n\n"
        f"**Dynamics & articulation:** {html.escape(profile['dynamics'])}; "
        f"{html.escape(profile['articulation'])}.\n\n"
        f"**For {html.escape((instrument or 'your instrument').strip())}:** "
        f"{html.escape(instrument_tip)}"
    )

    return f"""
### Section focus: {html.escape(section_name)}
**{len(section_chords)} bars** in **{html.escape(display_key)}** - **{bpm} BPM** - {html.escape(resolved_groove)} ({html.escape(profile['feel'])})

**Chord path:** {html.escape(chord_summary)}

**Key changes:** {html.escape(', '.join(hard) if hard else 'Loop one bar until steady, then link pairs.')}

{groove_block}

**Section exercise:** {exercise}

**Loop tip:** Use **Backing Track** with *Single section* scope, or metronome at **{bpm}** BPM for {max(4, len(section_chords))} bars only. Target tempo zone: *{html.escape(profile['tempo_hint'])}*.
""".strip()


def _section_exercise(
    section_name: str,
    chords: list[str],
    instrument: str,
    level: str,
    focus: str,
    groove_style: str = "",
) -> str:
    """Section exercise prompt - now flavoured by the resolved groove feel.

    The base prompt picks up section-role / focus / level (existing behaviour)
    and we *append* a one-line groove-specific drill so the exercise text
    visibly changes when the user moves the Rhythm / Groove Feel dropdown.
    """
    role = section_name.lower()
    if "chorus" in role:
        base = "Play the section 4x with backing; last time add dynamics +10%."
    elif "bridge" in role:
        base = "Map the first chord change only; then add the full bar line."
    elif focus == "Rhythm":
        base = "Metronome: 2 min chord changes only, then 2 min with groove pattern."
    elif level == "Beginner":
        base = "3 min: one bar at a time. 3 min: two-bar links. 2 min: full section slow."
    else:
        base = "Loop 6x: accuracy pass, then musical pass, then one pass with eyes on chart only."

    if not groove_style:
        return base

    groove_drill = _groove_drill_tagline(groove_style, instrument, focus)
    return f"{base} **Groove drill:** {groove_drill}"


def _groove_drill_tagline(groove_style: str, instrument: str, focus: str) -> str:
    """One-sentence "what to focus on" drill for the resolved groove."""
    profile = groove_get_profile(groove_style)
    inst = (instrument or "").lower()
    label = profile.get("label", groove_style)
    if focus == "Rhythm":
        return (
            f"loop a 2-bar cell at half tempo, locking the {profile['time_feel']} "
            f"with the metronome ticking {profile['accent']}, then speed up 8 BPM at a time."
        )
    if focus == "Melody":
        if label.startswith("Jazz"):
            return "phrase melodies in swung 8ths; land long notes on chord tones (3rds & 7ths)."
        if label.startswith("Bossa"):
            return "phrase melodies a hair behind the beat; target the AND of 2 / AND of 4 for syncopated stabs."
        if label.startswith("Funk"):
            return "phrase in short 16th-note cells; rest as much as you play."
        if label.startswith("Rock"):
            return "lean melodies into the backbeat (beats 2 & 4); stab consonants if singing."
        if label.startswith("Ballad"):
            return "phrase across the bar line; long sustained notes with breath swells."
        return "phrase in 4-bar arcs over the straight-8th pulse; land the hook on beat 1."
    if "guitar" in inst:
        return f"strum pattern {'  '.join(profile['strum'])}; {profile['articulation']}."
    if "piano" in inst or "key" in inst:
        return profile["piano_comp"]
    if "bass" in inst:
        return profile["bass"]
    if "voice" in inst or "vocal" in inst or "sing" in inst:
        return profile["voice"]
    return f"lock to the {profile['feel']}; accent {profile['accent']}."


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


def practice_ordered_section_names(
    sections: dict[str, list[str]],
    *,
    section_names: list[str] | None = None,
) -> list[str]:
    """Section names in musician-friendly order (chart keys, not normalized labels)."""
    from songs.form import section_order

    names = [
        name
        for name, chords in section_order(sections, section_names=section_names)
        if chords
    ]
    _numbered = re.compile(
        r"^(verse|chorus|bridge|intro|outro|pre-chorus|pre chorus)\s+\d+$",
        re.I,
    )
    if any(_numbered.match(str(n or "").strip()) for n in names):
        return names
    ordered: list[str] = []
    for hint in _SECTION_SORT_HINTS:
        for name in names:
            if hint in name.lower() and name not in ordered:
                ordered.append(name)
    for name in names:
        if name not in ordered:
            ordered.append(name)
    return ordered


_SECTION_TYPE_TRAILING_NUM = re.compile(r"\s+\d+[A-Za-z]?\s*$")
_SECTION_TYPE_REPEAT_COUNT = re.compile(r"\s*[xX]\s*\d+\s*$")
_SECTION_TYPE_PAREN_TAIL = re.compile(r"\s*\([^)]*\)\s*$")


def practice_section_type(section_name: str | None) -> str:
    """Collapse a chart section name to its **type label**.

    Examples:

    * ``"Verse 1"`` -> ``"Verse"``
    * ``"Chorus 2A"`` -> ``"Chorus"``
    * ``"Bridge 3"`` -> ``"Bridge"``
    * ``"Outro x5"`` -> ``"Outro"``
    * ``"Pre-Chorus 1"`` -> ``"Pre-Chorus"``
    * ``"Harmonica Solo"`` -> ``"Harmonica Solo"`` (no trailing index, kept as-is)
    * ``"Intro"`` -> ``"Intro"``

    The section *type* is what we expose in the Section Focus selector so
    the user sees one entry per kind ("Verse", "Chorus", "Bridge", ...)
    instead of one per numbered occurrence.
    """
    if not section_name:
        return ""
    s = str(section_name).strip()
    if not s:
        return ""
    # "Outro x5" -> strip the repeat marker.
    s = _SECTION_TYPE_REPEAT_COUNT.sub("", s).strip()
    # "Verse (repeat)" -> strip the trailing parenthetical hint.
    s = _SECTION_TYPE_PAREN_TAIL.sub("", s).strip()
    # "Verse 1" / "Verse 1A" -> strip trailing index.
    s = _SECTION_TYPE_TRAILING_NUM.sub("", s).strip()
    return s or str(section_name).strip()


def practice_section_options(sections: dict[str, list[str]]) -> list[str]:
    """Section Focus selector choices.

    Returns ``["Full Song", "<Type 1>", "<Type 2>", ...]`` where each
    type appears at most once and the order matches the first
    appearance of that type in the chart (so "Intro" comes before
    "Verse" before "Chorus" before "Bridge" before "Outro" for a
    typical pop arrangement).
    """
    ordered_names = practice_ordered_section_names(sections)
    seen: set[str] = set()
    types: list[str] = []
    for name in ordered_names:
        t = practice_section_type(name)
        if not t:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        types.append(t)
    return [PRACTICE_FOCUS_FULL] + types


def practice_is_full_song(focus: str | None) -> bool:
    """``True`` when *focus* selects the entire song.

    Tolerant of legacy / case-variant values such as ``"Full song"``
    (lowercase 's') that may still live in older session state.
    """
    if not focus:
        return True
    return str(focus).strip().lower() == PRACTICE_FOCUS_FULL.lower()


def practice_first_section_for_type(
    sections: dict[str, list[str]],
    type_label: str | None,
) -> str | None:
    """Return the first real section name whose *type* matches ``type_label``.

    ``"Verse"`` matches ``"Verse 1"`` (then ``"Verse 2"`` etc., but the
    *first* one wins). Lookup is case-insensitive. Returns ``None`` when
    nothing matches.
    """
    if not type_label:
        return None
    target = practice_section_type(type_label).lower()
    if not target:
        return None
    for name in practice_ordered_section_names(sections):
        if practice_section_type(name).lower() == target and sections.get(name):
            return name
    return None


def practice_sections_for_type(
    sections: dict[str, list[str]],
    type_label: str | None,
) -> list[str]:
    """All real section names whose type matches ``type_label`` (in order)."""
    if not type_label:
        return []
    target = practice_section_type(type_label).lower()
    if not target:
        return []
    return [
        name
        for name in practice_ordered_section_names(sections)
        if practice_section_type(name).lower() == target
        and sections.get(name)
    ]


def practice_resolve_focus_section(
    focus: str | None,
    sections: dict[str, list[str]],
) -> str | None:
    """Resolve a Section Focus pick (type label *or* legacy real name) to a
    concrete section in ``sections``.

    The current Section Focus selector exposes *type labels* such as
    ``"Verse"`` / ``"Chorus"`` / ``"Bridge"``, while the chart's real
    section keys are usually numbered (``"Verse 1"`` / ``"Verse 2"``
    / ...). Downstream panels - Full Chord Chart, Section Deep Focus,
    Rhythm Guide, Metronome loop, Send to Backing Track, notation
    generation - **must** receive a real chart key, otherwise they
    silently fall back to empty content.

    Resolution order (intentionally type-first so the selector and the
    rendered panels always agree):

    1. **Type match** - first chart section whose type collapses to
       ``focus``. Handles ``"Verse"`` -> ``"Verse 1"``.
       Also handles ``focus="Verse 1"`` legacy callers correctly,
       because ``"Verse 1"``'s type is ``"Verse"`` and the first
       matching section in the chart is still ``"Verse 1"``.
    2. **Exact match** - falls through for unusual section names that
       don't have a clean type collapse (e.g. ``"Harmonica Solo"``).
    3. ``None`` - caller falls back to Full Song behaviour and the
       Practice page renders a Developer Mode warning so the issue is
       not silent.
    """
    if practice_is_full_song(focus):
        return None
    if not sections:
        return None
    type_match = practice_first_section_for_type(sections, focus)
    if type_match:
        return type_match
    if focus and focus in sections and sections.get(focus):
        return focus
    return None


def practice_display_sections(
    sections: dict[str, list[str]],
    focus: str | None,
) -> dict[str, list[str]]:
    """Lead sheet / coach view: one section or the full form.

    Type-aware: ``focus="Verse"`` resolves to ``{"Verse 1": [...]}`` so
    the chord chart shows the first matching section's progression and
    repeated verses don't clutter the focused view.
    """
    if practice_is_full_song(focus):
        return sections
    resolved = practice_resolve_focus_section(focus, sections)
    if resolved:
        return {resolved: sections[resolved]}
    return sections


def practice_active_section_name(
    focus: str | None,
    sections: dict[str, list[str]],
) -> str | None:
    """Resolved chart section key, or ``None`` when Full Song is selected.

    Returns the **first** concrete section matching a type label - so
    ``"Verse"`` resolves to ``"Verse 1"`` for the active song.
    """
    if practice_is_full_song(focus):
        return None
    return practice_resolve_focus_section(focus, sections)


def song_groove_seed(title: str, artist: str = "") -> int:
    """Stable per-song variation for backing synthesis."""
    blob = f"{title}|{artist}".encode("utf-8")
    return int(hashlib.md5(blob).hexdigest()[:8], 16)
