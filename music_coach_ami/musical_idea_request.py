"""Shared musical-idea request profile for AMI generators (bass line, licks, patterns)."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True)
class MusicalIdeaRequest:
    """Normalized generation intent — explicit wording beats saved context.

    ``object_type`` is the musical *role* (bass_line, lick, …), not the instrument.
    Instrument / level / focus are resolved realization constraints.
    """

    object_type: str  # bass_line | lick | riff | phrase | pattern | sequence | improvisation | melody | accompaniment | …
    style: str
    difficulty: str  # beginner | intermediate | advanced | ""
    register: str  # low | mid | high | ""
    rhythmic_character: str
    explicit_key: str = ""  # tonic / key center named in the question
    tonality: str = ""  # harmonic minor | dorian | blues | …
    bars: int | None = None
    beats: int | None = None
    direction: str = ""  # ascending | descending | both | arch | ""
    rhythm: str = ""  # quarter | eighth | sixteenth | triplet | mixed | …
    interval_pattern: str = ""  # thirds | 1-3-2-4 | broken_thirds | …
    instrument: str = ""
    level: str = ""
    practice_focus: str = ""
    meter: str = ""
    tempo_bpm: int | None = None
    section: str = ""
    duration_minutes: int | None = None
    articulation: str = ""
    harmony_source: str = ""  # explicit | song | section | ""
    song_relative: bool = False
    piano_role: str = ""  # right_hand | left_hand | both_hands | ""


def _clean(text: object) -> str:
    return str(text or "").strip()


_BAR_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "eight": 8,
    "twelve": 12,
    "sixteen": 16,
}


def _parse_bars(low: str) -> int | None:
    m = re.search(
        r"\b(\d{1,2}|one|two|three|four|five|six|eight|twelve|sixteen)\s*[- ]?\s*(?:bar|measure)s?\b",
        low,
    )
    if not m:
        return None
    token = m.group(1).lower()
    try:
        n = _BAR_WORDS[token] if token in _BAR_WORDS else int(token)
        return max(1, min(32, n))
    except ValueError:
        return None


def _parse_tempo(low: str) -> int | None:
    m = re.search(r"\b(?:at\s+)?(\d{2,3})\s*(?:bpm|BPM)\b", low)
    if not m:
        return None
    try:
        return max(40, min(240, int(m.group(1))))
    except ValueError:
        return None


def _parse_meter(low: str) -> str:
    m = re.search(r"\b([23456])/([248])\b", low)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    if "6/8" in low:
        return "6/8"
    if "3/4" in low:
        return "3/4"
    if "4/4" in low:
        return "4/4"
    return ""


def _parse_direction(low: str) -> str:
    if re.search(r"\bascend(?:ing)?\s+and\s+descend(?:ing)?\b", low) or "both directions" in low:
        return "both"
    if re.search(r"\barch\b|\brise[- ]?fall\b|\brise and fall\b", low):
        return "arch"
    if re.search(r"\bdescend(?:ing)?\b", low):
        return "descending"
    if re.search(r"\bascend(?:ing)?\b|\bclimb(?:s|ing)?\b|\bstarts low and climbs\b", low):
        return "ascending"
    return ""


def _parse_tonality_and_key(low: str) -> tuple[str, str]:
    """Return (tonic_token, scale/tonality label). Prefer explicit scale words."""
    # Order matters: longer / more specific first.
    scale_patterns: tuple[tuple[str, str], ...] = (
        (r"harmonic\s+minor", "harmonic minor"),
        (r"melodic\s+minor", "melodic minor"),
        (r"natural\s+minor", "natural minor"),
        (r"minor\s+pentatonic", "minor pentatonic"),
        (r"major\s+pentatonic", "major pentatonic"),
        (r"\bblues\b", "blues"),
        (r"\bdorian\b", "dorian"),
        (r"\bmixolydian\b", "mixolydian"),
        (r"\blydian\b", "lydian"),
        (r"\bphrygian\b", "phrygian"),
        (r"\blocrian\b", "locrian"),
        (r"\bmajor\b", "major"),
        (r"\bminor\b", "natural minor"),
    )
    tonality = ""
    for pat, label in scale_patterns:
        if re.search(pat, low):
            tonality = label
            break

    tonic = ""
    # "in Bb harmonic minor" / "in the key of F#" / "Bb minor"
    m = re.search(
        r"\bin\s+(?:concert\s+)?(?:the\s+key\s+of\s+)?([A-Ga-g](?:#|b)?)\s*"
        r"(?:harmonic\s+minor|melodic\s+minor|natural\s+minor|minor\s+pentatonic|"
        r"major\s+pentatonic|dorian|mixolydian|lydian|phrygian|locrian|blues|major|minor)?",
        low,
    )
    if m:
        tonic = m.group(1)[0].upper() + m.group(1)[1:]
    if not tonic:
        m2 = re.search(r"\b([A-Ga-g](?:#|b)?)\s+(?:harmonic|melodic|natural)?\s*minor\b", low)
        if m2:
            tonic = m2.group(1)[0].upper() + m2.group(1)[1:]
            if not tonality:
                if "harmonic" in low:
                    tonality = "harmonic minor"
                elif "melodic" in low:
                    tonality = "melodic minor"
                else:
                    tonality = "natural minor"
    if not tonic:
        m3 = re.search(r"\b([A-Ga-g](?:#|b)?)\s+major\b", low)
        if m3:
            tonic = m3.group(1)[0].upper() + m3.group(1)[1:]
            if not tonality:
                tonality = "major"
    return tonic, tonality


def _parse_interval_pattern(low: str) -> str:
    if re.search(r"\b1\s*[-–]\s*3\s*[-–]\s*2\s*[-–]\s*4\b", low) or "1-3-2-4" in low:
        return "1-3-2-4"
    if re.search(r"\b1\s*[-–]\s*3\s*[-–]\s*4\s*[-–]\s*2\b", low) or "1-3-4-2" in low:
        return "1-3-4-2"
    if re.search(r"\b1\s*[-–]\s*2\s*[-–]\s*3\s*[-–]\s*4\b", low) or "1-2-3-4" in low:
        return "1-2-3-4"
    if re.search(r"\b1\s*[-–]\s*2\s*[-–]\s*3\b", low) or "three-note" in low or "3-note" in low:
        return "1-2-3"
    if "broken third" in low or "broken-thirds" in low:
        return "broken_thirds"
    if re.search(r"\bin thirds\b|\bthirds\b", low):
        return "thirds"
    if re.search(r"\bin fourths\b|\bfourths\b", low):
        return "fourths"
    if re.search(r"\bin fifths\b|\bfifths\b", low):
        return "fifths"
    if "four-note" in low or "4-note" in low:
        return "1-2-3-4"
    return ""


def _parse_rhythm(low: str) -> str:
    if "triplet" in low:
        return "triplet"
    if "sixteenth" in low:
        return "sixteenth"
    if "eighth" in low:
        return "eighth"
    if "quarter" in low:
        return "quarter"
    if "half note" in low or "half-note" in low:
        return "half"
    if "whole note" in low:
        return "whole"
    if "sparse" in low:
        return "sparse"
    if "busy" in low or "dense" in low:
        return "busy"
    if "swing" in low:
        return "swing"
    if "syncop" in low:
        return "syncopated"
    return ""


def parse_musical_idea_request(
    question: str,
    *,
    default_object: str = "bass_line",
    practice_focus: str = "",
    level: str = "",
) -> MusicalIdeaRequest:
    low = _clean(question).lower()
    focus = _clean(practice_focus).lower()

    object_type = default_object
    if re.search(r"\bbass[- ]?line\b|\bwalking bass\b|\bbassline\b", low):
        object_type = "bass_line"
    elif re.search(r"\baccompan(?:iment|y)\b|\bvoicings?\b", low):
        object_type = "accompaniment"
    elif re.search(r"\b(improvisation|improv)\b|\b(jazz )?solo\b", low):
        object_type = "improvisation"
    elif re.search(r"\bmelody\b|\bmelodic line\b", low):
        object_type = "melody"
    elif "sequence" in low:
        object_type = "sequence"
    elif re.search(r"\b(lick|riff|phrase|pattern)\b", low):
        if "riff" in low:
            object_type = "riff"
        elif "lick" in low:
            object_type = "lick"
        elif "pattern" in low:
            object_type = "pattern"
        elif "phrase" in low:
            object_type = "phrase"

    piano_role = ""
    has_lh = bool(re.search(r"\b(left[- ]?hand|\blh\b)\b", low))
    has_rh = bool(re.search(r"\b(right[- ]?hand|\brh\b)\b", low))
    if (
        re.search(r"\b(two[- ]?hands?|both hands|grand staff)\b", low)
        or (has_lh and has_rh)
    ):
        piano_role = "both_hands"
    elif has_lh:
        piano_role = "left_hand"
    elif has_rh:
        piano_role = "right_hand"

    style = ""
    if "walking" in low or "walking" in focus or "walk bass" in focus:
        style = "walking_bass"
    elif "bebop" in low:
        style = "bebop"
    elif "jazz" in low:
        style = "jazz"
    elif "blues" in low:
        style = "blues"
    elif "phras" in low or "phras" in focus:
        style = "phrasing"
    elif "rhythm" in low or "rhythm" in focus:
        style = "rhythm"
    elif "articul" in low or "articul" in focus:
        style = "articulation"
    elif "harmon" in low or "harmon" in focus:
        style = "harmony"
    elif focus:
        style = focus.replace(" ", "_")

    difficulty = ""
    if re.search(r"\b(very easy|super easy|easy|simple|beginner)\b", low):
        difficulty = "beginner"
    elif re.search(r"\b(difficult|hard|advanced|challenging)\b", low):
        difficulty = "advanced"
    elif re.search(r"\bintermediate\b", low):
        difficulty = "intermediate"

    register = ""
    if re.search(r"\b(high|upper[- ]?register|very high)\b", low):
        register = "high"
    elif re.search(r"\b(low|lower[- ]?register|low-register)\b", low):
        register = "low"
    elif re.search(r"\bmid(?:dle)?[- ]?register\b", low):
        register = "mid"

    rhythmic = ""
    if "walking" in style or "quarter" in low:
        rhythmic = "quarter_walk"
    elif "half note" in low:
        rhythmic = "half_notes"
    elif "syncop" in low or style == "rhythm":
        rhythmic = "syncopated"
    elif style == "phrasing":
        rhythmic = "phrased"

    articulation = ""
    if "staccato" in low:
        articulation = "staccato"
    elif "legato" in low or "slur" in low:
        articulation = "legato"
    elif style == "articulation":
        articulation = "articulated"

    explicit_key, tonality = _parse_tonality_and_key(low)
    # Legacy key-only matcher fallback
    if not explicit_key:
        key_match = re.search(
            r"\bin\s+(?:the\s+key\s+of\s+)?([A-Ga-g](?:#|b)?m?)\b(?:\s+(?:major|minor))?",
            low,
        )
        if key_match:
            token = key_match.group(1)
            explicit_key = token[0].upper() + token[1:]

    song_relative = bool(
        re.search(
            r"\b(over this song|for this song|over the (?:current )?section|"
            r"over the bridge|using (?:these|the) chord|over these chords|"
            r"current section|this section|"
            r"over (?:the )?(?:chorus|verse|intro|outro|pre[- ]?chorus|solo|groove)|"
            r"over (?:the )?(?:part|section) [abc]|"
            r"for (?:the )?(?:chorus|verse|bridge|part [abc]|section [abc]))\b",
            low,
        )
    )
    harmony_source = "song" if song_relative and not explicit_key else ("explicit" if explicit_key else "")

    return MusicalIdeaRequest(
        object_type=object_type,
        style=style,
        difficulty=difficulty,
        register=register,
        rhythmic_character=rhythmic,
        explicit_key=explicit_key,
        tonality=tonality,
        bars=_parse_bars(low),
        direction=_parse_direction(low),
        rhythm=_parse_rhythm(low),
        interval_pattern=_parse_interval_pattern(low),
        practice_focus=_clean(practice_focus),
        level=_clean(level),
        articulation=articulation,
        meter=_parse_meter(low),
        tempo_bpm=_parse_tempo(low),
        harmony_source=harmony_source,
        song_relative=song_relative,
        piano_role=piano_role,
    )


def resolve_generation_level(idea: MusicalIdeaRequest, context_level: str) -> str:
    """Explicit request difficulty overrides saved context level."""
    if idea.difficulty:
        return idea.difficulty
    return _clean(context_level) or "Intermediate"


def resolve_musical_idea_request(
    question: str,
    *,
    default_object: str = "bass_line",
    instrument: str = "",
    level: str = "",
    practice_focus: str = "",
    meter: str = "",
    tempo_bpm: int | None = None,
    section: str = "",
    duration_minutes: int | None = None,
) -> MusicalIdeaRequest:
    """Parse question then attach realization context (instrument ≠ musical object)."""
    parsed = parse_musical_idea_request(
        question,
        default_object=default_object,
        practice_focus=practice_focus,
        level=level,
    )
    focus = _clean(parsed.practice_focus) or _clean(practice_focus)
    style = parsed.style or focus.replace(" ", "_").lower()
    return replace(
        parsed,
        instrument=_clean(instrument),
        level=resolve_generation_level(parsed, level),
        practice_focus=focus,
        style=style,
        meter=_clean(parsed.meter) or _clean(meter) or "4/4",
        tempo_bpm=parsed.tempo_bpm if parsed.tempo_bpm is not None else tempo_bpm,
        section=_clean(section) or parsed.section,
        duration_minutes=duration_minutes if duration_minutes is not None else parsed.duration_minutes,
    )


def musical_idea_to_diagnostics(idea: MusicalIdeaRequest) -> dict[str, Any]:
    return {
        "musical_object": idea.object_type,
        "idea_style": idea.style,
        "explicit_difficulty": idea.difficulty or None,
        "explicit_register": idea.register or None,
        "explicit_key": idea.explicit_key or None,
        "tonality": idea.tonality or None,
        "bars": idea.bars,
        "direction": idea.direction or None,
        "rhythm": idea.rhythm or None,
        "interval_pattern": idea.interval_pattern or None,
        "rhythmic_character": idea.rhythmic_character or None,
        "articulation": idea.articulation or None,
        "resolved_instrument": idea.instrument or None,
        "resolved_level": idea.level or None,
        "practice_focus": idea.practice_focus or None,
        "meter": idea.meter or None,
        "tempo_bpm": idea.tempo_bpm,
        "section": idea.section or None,
        "duration_minutes": idea.duration_minutes,
        "harmony_source": idea.harmony_source or None,
        "song_relative": idea.song_relative,
        "piano_role": idea.piano_role or None,
        "requested_object": idea.object_type,
    }
