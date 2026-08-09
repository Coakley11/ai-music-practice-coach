"""Deterministic scale-pattern exercises — register-safe cells and profile selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from music_coach_ami.scale_engine import (
    ScalePracticeSpec,
    _default_start_octave,
    _midi_for_spelled,
    _octave_for_diatonic_spellings,
)


@dataclass(frozen=True)
class PracticePattern:
    pattern_id: str
    display_name: str
    degree_offsets: tuple[int, ...]
    rhythmic_grouping: str = "4"
    difficulty: str = "intermediate"
    pedagogical_goal: str = "even finger coordination"
    instrument_suitability: tuple[str, ...] = ("all",)


@dataclass
class ExerciseProfile:
    instrument: str = ""
    level: str = ""
    practice_focus: str = ""
    scale_or_mode: str = ""
    requested_pattern: str = ""
    requested_difficulty: bool = False
    resolved_difficulty: str = "intermediate"
    octave_count: int = 2
    rhythm: str = "quarter"
    articulation: str = ""
    range_start_octave: int = 4
    pedagogical_goal: str = ""
    selected: PracticePattern | None = None


PATTERN_LIBRARY: dict[str, PracticePattern] = {
    "straight_scale": PracticePattern(
        pattern_id="straight_scale",
        display_name="Straight scale",
        degree_offsets=(0, 1, 2, 3, 4, 5, 6),
        difficulty="beginner",
        pedagogical_goal="even tone and time",
    ),
    "three_note_cell": PracticePattern(
        pattern_id="three_note_cell",
        display_name="Three-note sequence",
        degree_offsets=(0, 1, 2),
        rhythmic_grouping="3",
        difficulty="beginner",
        pedagogical_goal="compact fingering groups",
    ),
    "four_note_sequence": PracticePattern(
        pattern_id="four_note_sequence",
        display_name="Four-note ascending sequence",
        degree_offsets=(0, 1, 2, 3),
        difficulty="intermediate",
        pedagogical_goal="overlapping scale cells",
    ),
    "broken_thirds_1324": PracticePattern(
        pattern_id="broken_thirds_1324",
        display_name="Broken-third cells (1-3-2-4)",
        degree_offsets=(0, 2, 1, 3),
        difficulty="intermediate",
        pedagogical_goal="thirds with scalar recovery",
    ),
    "perm_1342": PracticePattern(
        pattern_id="perm_1342",
        display_name="Four-note permutation (1-3-4-2)",
        degree_offsets=(0, 2, 3, 1),
        difficulty="advanced",
        pedagogical_goal="finger independence within the mode",
    ),
    "triplet_three_note": PracticePattern(
        pattern_id="triplet_three_note",
        display_name="Triplet three-note cells",
        degree_offsets=(0, 1, 2),
        rhythmic_grouping="3",
        difficulty="advanced",
        pedagogical_goal="even triplet subdivision",
    ),
}


def _normalize_level(level: str) -> str:
    low = str(level or "").strip().lower()
    if not low:
        return ""
    if "begin" in low:
        return "beginner"
    if "adv" in low or "pro" in low:
        return "advanced"
    if "inter" in low:
        return "intermediate"
    return ""


def _instrument_family(instrument: str) -> str:
    low = str(instrument or "").lower()
    if any(x in low for x in ("flute", "piccolo", "clarinet", "sax", "trumpet", "horn", "oboe", "bassoon")):
        return "wind"
    if "piano" in low or "keyboard" in low:
        return "keyboard"
    if "guitar" in low or "bass" in low and "double" not in low:
        return "guitar"
    return "generic"


def _focus_bucket(focus: str) -> str:
    low = str(focus or "").lower()
    if "tone" in low or "sound" in low or "breath" in low:
        return "tone"
    if "artic" in low or "tongue" in low:
        return "articulation"
    if "harmony" in low or "chord" in low or "voic" in low:
        return "harmony"
    if "rhythm" in low or "timing" in low or "groove" in low:
        return "rhythm"
    if "technique" in low or "speed" in low or "finger" in low:
        return "technique"
    if "improv" in low or "solo" in low:
        return "improvisation"
    return ""


def resolve_difficulty(level: str, *, requested: bool) -> str:
    norm = _normalize_level(level)
    if not norm:
        norm = "intermediate"
    if not requested:
        return norm
    if norm == "beginner":
        return "beginner"
    if norm == "advanced":
        return "advanced"
    if norm == "intermediate":
        return "intermediate_plus"
    return norm


def select_pattern_for_profile(profile: ExerciseProfile) -> PracticePattern:
    resolved = profile.resolved_difficulty
    fam = _instrument_family(profile.instrument)
    focus = _focus_bucket(profile.practice_focus)

    if profile.rhythm == "triplet" or profile.rhythm.endswith("triplet"):
        return PATTERN_LIBRARY["triplet_three_note"]

    if focus == "tone" and fam == "wind":
        return PATTERN_LIBRARY["three_note_cell"]
    if focus == "articulation" and fam == "wind":
        return PATTERN_LIBRARY["four_note_sequence"]
    if focus == "harmony" and fam == "keyboard":
        return PATTERN_LIBRARY["broken_thirds_1324"]
    if focus == "rhythm" and fam == "guitar":
        return PATTERN_LIBRARY["three_note_cell"]

    if resolved in ("beginner", "beginner_plus"):
        if resolved == "beginner_plus":
            return PATTERN_LIBRARY["four_note_sequence"]
        return PATTERN_LIBRARY["three_note_cell"]
    if resolved == "advanced":
        if profile.articulation or profile.rhythm == "eighth":
            return PATTERN_LIBRARY["perm_1342"]
        return PATTERN_LIBRARY["broken_thirds_1324"]
    if resolved == "intermediate_plus":
        return PATTERN_LIBRARY["four_note_sequence"]
    return PATTERN_LIBRARY["four_note_sequence"]


def _midi_walk_scale(scale: list[str], start_idx: int, steps: int, start_octave: int) -> int:
    """MIDI after ``steps`` diatonic steps up from scale[start_idx] at start_octave."""
    n = len(scale)
    if n == 0:
        return _midi_for_spelled("C", start_octave)
    idx = start_idx % n
    octave = start_octave
    midi = _midi_for_spelled(scale[idx], octave)
    for _ in range(steps):
        idx = (idx + 1) % n
        if idx == 0:
            octave += 1
        midi = _midi_for_spelled(scale[idx], octave)
    return midi


def _pitch_note_near_target(note: str, target_midi: int, anchor_oct: int) -> tuple[str, int]:
    best_oct = anchor_oct
    best_dist = abs(_midi_for_spelled(note, best_oct) - target_midi)
    for o in range(anchor_oct - 1, anchor_oct + 3):
        dist = abs(_midi_for_spelled(note, o) - target_midi)
        if dist < best_dist:
            best_dist = dist
            best_oct = o
    return note, best_oct


def build_degree_pattern_pitched(
    scale: list[str],
    degree_offsets: tuple[int, ...],
    *,
    octave_count: int,
    start_octave: int = 4,
) -> list[tuple[str, int]]:
    """Cell-based register: each cell starts on the next scale degree of the spine."""
    n = len(scale)
    if n < 2 or not degree_offsets:
        return []

    out: list[tuple[str, int]] = []
    source_names: list[str] = []
    for rep in range(max(1, octave_count)):
        for i in range(n):
            source_names.append(scale[i])
    source_pitched = _octave_for_diatonic_spellings(source_names, start_octave)

    cell_index = 0
    for _rep in range(max(1, octave_count)):
        for start_i in range(n):
            src_name, src_oct = source_pitched[cell_index]
            cell_index += 1
            for off in degree_offsets:
                deg_idx = (start_i + off) % n
                note = scale[deg_idx]
                if off == 0:
                    out.append((src_name, src_oct))
                    continue
                target_midi = _midi_walk_scale(scale, start_i, off, src_oct)
                out.append(_pitch_note_near_target(note, target_midi, src_oct))
    return out


def build_degree_pattern_sequence(
    scale: list[str],
    degree_offsets: tuple[int, ...],
    *,
    octave_count: int,
    start_octave: int = 4,
) -> list[str]:
    return [n for n, _ in build_degree_pattern_pitched(
        scale, degree_offsets, octave_count=octave_count, start_octave=start_octave
    )]


def apply_exercise_profile(
    spec: ScalePracticeSpec,
    *,
    level: str = "",
    practice_focus: str = "",
    instrument: str = "",
) -> ExerciseProfile:
    """Mutates ``spec`` pattern fields from coach context (read-only inputs)."""
    inst = str(instrument or spec.instrument or "").strip()
    if inst and not spec.instrument:
        spec.instrument = inst

    requested = bool(getattr(spec, "requested_difficulty", False))
    resolved = resolve_difficulty(level, requested=requested)
    profile = ExerciseProfile(
        instrument=inst,
        level=level,
        practice_focus=practice_focus,
        scale_or_mode=spec.scale_type,
        requested_pattern=spec.exercise_pattern,
        requested_difficulty=requested,
        resolved_difficulty=resolved,
        octave_count=spec.octave_count,
        rhythm=spec.note_value if spec.rhythm_triplet else spec.note_value,
        articulation=spec.articulation,
        range_start_octave=spec.start_octave or _default_start_octave(inst),
    )
    if spec.rhythm_triplet:
        profile.rhythm = "triplet"

    if spec.exercise_pattern == "four_note_sequence" or spec.requested_difficulty:
        pattern = select_pattern_for_profile(profile)
        if resolved == "beginner":
            pattern = PATTERN_LIBRARY["three_note_cell"]
        profile.selected = pattern
        profile.pedagogical_goal = pattern.pedagogical_goal
        spec.exercise_pattern = pattern.pattern_id
        spec.pattern_id = pattern.pattern_id
        spec.pattern_degree_formula = "-".join(str(o + 1) for o in pattern.degree_offsets)
        spec.resolved_difficulty = resolved
        spec.player_level = level
        spec.practice_focus = practice_focus
        spec.pedagogical_goal = pattern.pedagogical_goal
        if resolved in ("beginner", "beginner_plus") and not spec.octave_count_explicit:
            spec.octave_count = 1
        if resolved == "advanced" and not spec.octave_count_explicit:
            spec.octave_count = max(spec.octave_count, 2)
        if profile.rhythm == "triplet" and not spec.note_value_explicit:
            spec.note_value = "eighth"
            spec.rhythm_triplet = True
    return profile


def exercise_profile_to_dev_dict(profile: ExerciseProfile) -> dict[str, Any]:
    pat = profile.selected
    return {
        "instrument_used": profile.instrument,
        "level_used": profile.level,
        "practice_focus_used": profile.practice_focus,
        "requested_difficulty": profile.requested_difficulty,
        "resolved_difficulty": profile.resolved_difficulty,
        "selected_pattern_id": pat.pattern_id if pat else "",
        "pattern_degree_formula": "-".join(str(o + 1) for o in pat.degree_offsets) if pat else "",
        "rhythm": profile.rhythm,
        "articulation": profile.articulation,
        "octave_count": profile.octave_count,
        "starting_register": profile.range_start_octave,
        "pedagogical_goal": profile.pedagogical_goal,
    }


def enrich_exercise_coaching(spec: ScalePracticeSpec) -> tuple[list[str], list[str]]:
    """Extra focus/instrument lines for pattern exercises."""
    if not getattr(spec, "pattern_id", ""):
        return [], []
    fam = _instrument_family(spec.instrument)
    focus = _focus_bucket(spec.practice_focus or getattr(spec, "practice_focus", ""))
    guidance: list[str] = []
    listen: list[str] = []
    if fam == "wind" and focus == "tone":
        guidance.append("**Focus:** Tone through the pattern — prefer smooth slurs and steady air.")
        listen.append("Keep the sound centered as the line moves register.")
    elif fam == "wind" and focus == "articulation":
        guidance.append("**Focus:** Clean tongue coordination on each cell.")
        listen.append("Each attack speaks clearly without breaking the airstream.")
    elif fam == "keyboard" and focus == "harmony":
        guidance.append("**Focus:** Hear the modal color while you move through the cells.")
        if "dorian" in spec.scale_type:
            listen.append("Notice how the natural 6 distinguishes Dorian from natural minor.")
    elif fam == "guitar" and focus == "rhythm":
        guidance.append("**Focus:** Keep the rhythmic grouping even across string changes.")
        listen.append("Time stays steady even when the contour shifts inside each cell.")
    elif spec.pedagogical_goal:
        guidance.append(f"**Focus:** {spec.pedagogical_goal.capitalize()}.")
    return guidance, listen
