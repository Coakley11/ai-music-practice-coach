"""Level-aware guitar chord voicing generator (C1a).

Produces real, playable fretboard voicings per difficulty level:

- Beginner: open/cowboy chords from ``GUITAR_SHAPES``/song ``guitar_tabs``
  where available; compact shapes with root bass in low position for
  chords without a stored shape; simplified but preserving chord identity.
- Intermediate: fuller 4-5-6 string voicings with root or correct slash
  bass, allowing barre chords and manageable stretches; important chord
  tones and extensions preserved.
- Advanced: harmonically rich voicings preserving chord-defining extensions
  (9ths, 11ths, 13ths), correct slash-bass notes, drop-2 and shell
  voicings where appropriate, with voice leading across chord changes.

All voicings are 6-character fret strings (low E .. high e; ``x`` = muted,
digit 0-9 = fret) compatible with ``practice_notation.py``'s TAB renderer.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass

from music_theory import (
    classify_chord_quality,
    normalize_chord_for_theory,
    pitch_class_from_spelled_note,
    semitone_distance,
    spell_chord_tones,
)

# Standard tuning: pitch class of each open string, low E to high e.
_OPEN_PC = [4, 9, 2, 7, 11, 4]  # E A D G B e
_NUM_STRINGS = 6
_MAX_FRET = 9  # single-character fret slot in the shape format

_MAX_SPAN = {"Beginner": 3, "Intermediate": 4, "Advanced": 5}
_PREFERRED_STRINGS = {"Beginner": (4, 5), "Intermediate": (4, 6), "Advanced": (4, 6)}


@dataclass
class GuitarVoicingEvent:
    measure: int
    chord: str
    shape: str  # 6-char low-to-high fret string, e.g. "x32010"
    label: str  # "open", "barre", "drop-2", etc.
    position: int  # lowest fretted fret used (0 = open position)
    tones: list[str]  # chord tones actually voiced, spelled


def song_guitar_tabs_for_key(
    guitar_tabs: dict[str, str] | None,
    original_key: str,
    chart_key: str,
) -> dict[str, str]:
    """Song-supplied grips, but only when the chart is in the key they were written for."""
    if not guitar_tabs:
        return {}
    if semitone_distance(original_key, chart_key) != 0:
        return {}
    return dict(guitar_tabs)


# ---------------------------------------------------------------------------
# Pitch-class helpers
# ---------------------------------------------------------------------------

def _chord_tone_pcs(chord: str) -> list[int]:
    head = chord.split("/")[0]
    tones = spell_chord_tones(head)
    return [pitch_class_from_spelled_note(t) for t in tones if t]


def _parse_slash_bass(chord: str) -> int | None:
    """Return the pitch class of an explicit slash-bass note, or None."""
    if "/" not in chord:
        return None
    parts = chord.split("/", 1)
    bass_str = parts[1].strip()
    if not bass_str or not bass_str[0].isalpha():
        return None
    return pitch_class_from_spelled_note(bass_str)


def _root_pc(chord: str) -> int:
    head = chord.split("/")[0]
    tones = spell_chord_tones(head)
    if tones:
        return pitch_class_from_spelled_note(tones[0])
    return 0


def _fret_for_pc_on_string(string_idx: int, target_pc: int, *, min_fret: int = 0) -> int | None:
    open_pc = _OPEN_PC[string_idx]
    for fret in range(min_fret, _MAX_FRET + 1):
        if (open_pc + fret) % 12 == target_pc:
            return fret
    return None


def _all_frets_for_pc_on_string(
    string_idx: int, target_pc: int, min_fret: int = 0, max_fret: int = _MAX_FRET,
) -> list[int]:
    """All frets on *string_idx* that sound *target_pc* within [min_fret, max_fret]."""
    result = []
    open_pc = _OPEN_PC[string_idx]
    for fret in range(min_fret, max_fret + 1):
        if (open_pc + fret) % 12 == target_pc:
            result.append(fret)
    return result


def _pc_at(string_idx: int, fret: int) -> int:
    return (_OPEN_PC[string_idx] + fret) % 12


# ---------------------------------------------------------------------------
# Voicing candidate generation
# ---------------------------------------------------------------------------

@dataclass
class _VoicingCandidate:
    frets: dict[int, int]  # string_idx -> fret
    bass_pc: int
    sounding_pcs: set[int]
    n_strings: int
    min_fret: int
    max_fret: int
    span: int
    has_open: bool
    has_barre: bool


def _classify_barre(frets: dict[int, int]) -> bool:
    """True if the voicing likely requires a barre (same fret across 2+ adjacent strings)."""
    vals = sorted(frets.items())
    fretted = [(s, f) for s, f in vals if f > 0]
    if len(fretted) < 2:
        return False
    min_f = min(f for _, f in fretted)
    count_at_min = sum(1 for _, f in fretted if f == min_f)
    return count_at_min >= 2


def _generate_candidates(
    chord_pcs: list[int],
    *,
    root_pc: int,
    slash_bass_pc: int | None,
    quality: str,
    max_span: int,
    center_fret: int,
    min_strings: int = 3,
    max_strings: int = 6,
    prefer_open: bool = False,
    allow_muted_inner: bool = False,
) -> list[_VoicingCandidate]:
    """Generate playable voicing candidates for the given chord.

    Builds voicings bottom-up (low E to high e), allowing doubling of
    chord tones.  The bass string is constrained to the desired bass note
    (slash bass or root).
    """
    if not chord_pcs:
        return []

    desired_bass = slash_bass_pc if slash_bass_pc is not None else root_pc
    pcs_set = set(chord_pcs)

    # Determine the fret search window.
    if prefer_open:
        fret_lo, fret_hi = 0, min(max_span + 2, _MAX_FRET)
    else:
        fret_lo = max(0, center_fret - max_span)
        fret_hi = min(_MAX_FRET, center_fret + max_span)

    # For each string, find all chord-tone frets within the window.
    # Also include the desired bass note options on the lowest strings.
    string_options: list[list[tuple[int, int]]] = []  # [(fret, pc), ...] per string
    for s in range(_NUM_STRINGS):
        opts: list[tuple[int, int]] = []
        for pc in pcs_set | {desired_bass}:
            for fret in _all_frets_for_pc_on_string(s, pc, fret_lo, fret_hi):
                opts.append((fret, pc))
        # Also allow muting (represented by not including the string).
        string_options.append(opts)

    candidates: list[_VoicingCandidate] = []
    _MAX_CANDIDATES = 600

    # Build voicings by choosing fret or mute for each string, bottom-up.
    # To keep combinatorics manageable, use a bounded search:
    # 1. Fix the bass string first (must be desired_bass or muted).
    # 2. Fill remaining strings with chord tones or mute.
    # 3. Prune by span, string count, and contiguity.

    # Find which strings can carry the desired bass note.
    bass_placements: list[tuple[int, int]] = []  # (string_idx, fret)
    for s in range(3):  # only strings 0-2 (E, A, D) for bass
        for fret in _all_frets_for_pc_on_string(s, desired_bass, fret_lo, fret_hi):
            bass_placements.append((s, fret))

    if not bass_placements:
        # Fallback: try root as bass if slash bass not found
        if slash_bass_pc is not None:
            for s in range(3):
                for fret in _all_frets_for_pc_on_string(s, root_pc, fret_lo, fret_hi):
                    bass_placements.append((s, fret))
        if not bass_placements:
            # Last resort: any chord tone as bass
            for s in range(3):
                for fret, pc in string_options[s]:
                    if pc in pcs_set:
                        bass_placements.append((s, fret))
                        break

    if not bass_placements:
        return []

    for bass_s, bass_fret in bass_placements:
        if len(candidates) >= _MAX_CANDIDATES:
            break

        # Strings below the bass string are muted.
        # Strings from bass_s upward need to be filled.
        active_strings = list(range(bass_s, _NUM_STRINGS))

        # For each string above bass, gather feasible frets within span of bass_fret.
        per_string_choices: list[list[int | None]] = []
        for s in active_strings:
            if s == bass_s:
                per_string_choices.append([bass_fret])
                continue
            choices: list[int | None] = [None]  # None = muted
            for fret, pc in string_options[s]:
                if pc not in pcs_set and pc != desired_bass:
                    continue
                choices.append(fret)
            per_string_choices.append(choices)

        # Limit combinatorics: keep at most 3 fret options per upper string.
        for i in range(len(per_string_choices)):
            if len(per_string_choices[i]) > 4:
                non_none = [f for f in per_string_choices[i] if f is not None]
                non_none.sort(key=lambda f: abs(f - center_fret))
                per_string_choices[i] = [None] + non_none[:3]

        for combo in itertools.product(*per_string_choices):
            if len(candidates) >= _MAX_CANDIDATES:
                break

            frets_map: dict[int, int] = {}
            for idx, fret_val in enumerate(combo):
                if fret_val is not None:
                    frets_map[active_strings[idx]] = fret_val

            n_sounding = len(frets_map)
            if n_sounding < min_strings or n_sounding > max_strings:
                continue

            fret_vals = list(frets_map.values())
            fretted = [f for f in fret_vals if f > 0]
            if fretted:
                span = max(fretted) - min(fretted)
                if span > max_span:
                    continue
            else:
                span = 0

            # Check for muted inner strings (a muted string between two sounding ones).
            sounding_indices = sorted(frets_map.keys())
            if not allow_muted_inner and len(sounding_indices) >= 2:
                full_range = set(range(sounding_indices[0], sounding_indices[-1] + 1))
                if full_range - set(sounding_indices):
                    continue

            # Finger count check: distinct non-zero frets (barre = 1 finger).
            distinct_frets = set(fretted)
            min_fretted = min(fretted) if fretted else 0
            # A barre at the lowest fret uses 1 finger for all strings at that fret.
            finger_count = len(distinct_frets)
            if finger_count > 4:
                continue

            sounding_pcs = {_pc_at(s, f) for s, f in frets_map.items()}
            bass_pc_actual = _pc_at(sounding_indices[0], frets_map[sounding_indices[0]])

            candidates.append(_VoicingCandidate(
                frets=frets_map,
                bass_pc=bass_pc_actual,
                sounding_pcs=sounding_pcs,
                n_strings=n_sounding,
                min_fret=min(fret_vals) if fret_vals else 0,
                max_fret=max(fret_vals) if fret_vals else 0,
                span=span,
                has_open=0 in fret_vals,
                has_barre=_classify_barre(frets_map),
            ))

    return candidates


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _essential_pcs(pcs: list[int], quality: str) -> set[int]:
    """Pitch classes that define the chord's harmonic identity."""
    if len(pcs) <= 3:
        return set(pcs)
    root, third = pcs[0], pcs[1]
    fifth = pcs[2] if len(pcs) > 2 else None
    seventh = pcs[3] if len(pcs) > 3 else None
    extensions = pcs[4:]
    essential = {root, third}
    if seventh is not None:
        essential.add(seventh)
    for e in extensions:
        essential.add(e)
    if fifth is not None and quality in ("aug", "dim", "half-dim"):
        essential.add(fifth)
    return essential


def _score_candidate(
    c: _VoicingCandidate,
    *,
    chord_pcs: list[int],
    root_pc: int,
    slash_bass_pc: int | None,
    quality: str,
    level: str,
    center_fret: int,
) -> float:
    """Score a voicing candidate. Higher is better."""
    score = 0.0

    desired_bass = slash_bass_pc if slash_bass_pc is not None else root_pc

    # --- Bass correctness (most important) ---
    if c.bass_pc == desired_bass:
        score += 30.0
    elif c.bass_pc == root_pc:
        score += 15.0  # root bass is decent even when slash was requested

    # --- Harmonic completeness ---
    essential = _essential_pcs(chord_pcs, quality)
    covered = c.sounding_pcs & essential
    coverage_ratio = len(covered) / max(len(essential), 1)
    score += coverage_ratio * 20.0

    # Bonus for having the third (defines major/minor quality).
    if len(chord_pcs) >= 2 and chord_pcs[1] in c.sounding_pcs:
        score += 5.0
    # Bonus for having the seventh (defines chord type).
    if len(chord_pcs) >= 4 and chord_pcs[3] in c.sounding_pcs:
        score += 3.0
    # Bonus for extensions present.
    for ext_pc in chord_pcs[4:]:
        if ext_pc in c.sounding_pcs:
            score += 2.0

    # --- String count ---
    min_s, max_s = _PREFERRED_STRINGS.get(level, (4, 6))
    if min_s <= c.n_strings <= max_s:
        score += 8.0
    elif c.n_strings == 3:
        score -= 5.0 if level != "Advanced" else 0.0

    # --- Playability ---
    # Prefer smaller spans.
    score -= c.span * 2.0

    # Penalize open strings mixed with high frets (physically awkward).
    fret_vals = list(c.frets.values())
    has_open_str = any(f == 0 for f in fret_vals)
    max_fretted = max((f for f in fret_vals if f > 0), default=0)
    if has_open_str and max_fretted > 4:
        score -= (max_fretted - 4) * 3.0

    # Penalize split barre: a string at the barre fret that has no
    # adjacent neighbor at the same fret AND sits next to an open string.
    # A straight barre from the nearest partner would fret the open
    # string, so the player needs an extra finger at the same fret on a
    # distant string — impractical at Beginner/Intermediate.
    if c.has_barre:
        fretted_pairs = [(s, f) for s, f in c.frets.items() if f > 0]
        min_f = min(f for _, f in fretted_pairs)
        barre_strings = sorted(s for s, f in fretted_pairs if f == min_f)
        if len(barre_strings) >= 2:
            for bs in barre_strings:
                has_barre_neighbor = any(
                    abs(bs - o) == 1 for o in barre_strings if o != bs
                )
                if has_barre_neighbor:
                    continue
                for adj in (bs - 1, bs + 1):
                    if (0 <= adj < _NUM_STRINGS
                            and adj in c.frets and c.frets[adj] == 0):
                        score -= 5.0
                        break

    # Proximity to center (voice-leading continuity).
    if c.min_fret > 0:
        score -= abs(c.min_fret - center_fret) * 0.5
    elif center_fret <= 2:
        score += 2.0  # open position when we're already there

    # --- Level-specific preferences ---
    if level == "Beginner":
        if c.has_open:
            score += 6.0
        if c.has_barre:
            score -= 8.0
        if c.max_fret > 4:
            score -= 4.0
        if c.n_strings >= 4:
            score += 3.0
    elif level == "Intermediate":
        if c.n_strings >= 5:
            score += 3.0
        if c.has_barre and c.span <= 3:
            score += 1.0  # barres are OK at intermediate
    else:  # Advanced
        # Prefer rich voicings.
        if c.n_strings >= 5:
            score += 4.0
        elif c.n_strings >= 4:
            score += 2.0

    # --- Penalize non-chord tones ---
    non_chord = c.sounding_pcs - set(chord_pcs)
    if slash_bass_pc is not None:
        non_chord -= {slash_bass_pc}
    score -= len(non_chord) * 10.0

    return score


# ---------------------------------------------------------------------------
# Voicing construction helpers
# ---------------------------------------------------------------------------

def _frets_to_shape(frets_by_string: dict[int, int]) -> str:
    out = ["x"] * _NUM_STRINGS
    for s, f in frets_by_string.items():
        out[s] = str(min(9, max(0, f)))
    return "".join(out)


def _position_of(frets_by_string: dict[int, int]) -> int:
    fretted = [f for f in frets_by_string.values() if f > 0]
    return min(fretted) if fretted else 0


def validate_voicing(frets_by_string: dict[int, int], *, max_span: int = 4) -> tuple[bool, str]:
    """Playability check: fret span, string count, finger count."""
    if not frets_by_string:
        return False, "no sounding strings"
    frets = list(frets_by_string.values())
    fretted = [f for f in frets if f > 0]
    if fretted:
        span = max(fretted) - min(fretted)
        if span > max_span:
            return False, f"fret span {span} exceeds {max_span}"
    distinct_frets = len(set(fretted))
    if distinct_frets > 4:
        return False, f"{distinct_frets} distinct frets needs more than 4 fingers"
    if len(frets_by_string) < 3:
        return False, "fewer than 3 sounding strings"
    return True, "ok"


def _alteration_hint(chord: str) -> int | None:
    head = normalize_chord_for_theory(chord)
    low = head.lower()
    if "b9" in low:
        return 1
    if "#9" in low or "#9" in head:
        return 3
    if "#5" in low or "b13" in low:
        return 8
    if "alt" in low:
        return 1
    return None


# ---------------------------------------------------------------------------
# Legacy search (kept as last-resort fallback for Advanced shells)
# ---------------------------------------------------------------------------

def _search_voicing(
    target_pcs: list[int],
    string_order: list[int],
    *,
    center_fret: int | None,
    max_span: int,
) -> dict[int, int] | None:
    """Assign each pitch class in *target_pcs* to a distinct string."""
    if not target_pcs or not string_order:
        return None
    anchor = center_fret if center_fret is not None else 2
    best: dict[int, int] | None = None
    best_cost = None

    def backtrack(i: int, used_strings: list[int], chosen: dict[int, int]) -> None:
        nonlocal best, best_cost
        if i == len(target_pcs):
            frets = list(chosen.values())
            span = max(frets) - min(frets) if frets else 0
            if span > max_span:
                return
            cost = span + sum(abs(f - anchor) for f in frets) * 0.1
            if best_cost is None or cost < best_cost:
                best_cost = cost
                best = dict(chosen)
            return
        pc = target_pcs[i]
        candidates: list[tuple[int, int]] = []
        for s in string_order:
            if s in used_strings:
                continue
            lo = max(0, anchor - max_span)
            fret = _fret_for_pc_on_string(s, pc, min_fret=lo)
            while fret is not None and fret <= anchor + max_span:
                candidates.append((s, fret))
                fret = _fret_for_pc_on_string(s, pc, min_fret=fret + 1)
        candidates.sort(key=lambda sf: abs(sf[1] - anchor))
        for s, fret in candidates[:4]:
            chosen[s] = fret
            backtrack(i + 1, used_strings + [s], chosen)
            del chosen[s]

    backtrack(0, [], {})
    return best


# ---------------------------------------------------------------------------
# Level-specific voicing builders
# ---------------------------------------------------------------------------

def _best_candidate(
    chord: str,
    level: str,
    center_fret: int,
    *,
    prefer_open: bool = False,
    min_strings: int = 3,
) -> _VoicingCandidate | None:
    """Generate and score candidates, return the best one."""
    pcs = _chord_tone_pcs(chord)
    if not pcs:
        return None
    rpc = _root_pc(chord)
    slash = _parse_slash_bass(chord)
    quality = classify_chord_quality(chord)
    max_span = _MAX_SPAN.get(level, 4)

    candidates = _generate_candidates(
        pcs,
        root_pc=rpc,
        slash_bass_pc=slash,
        quality=quality,
        max_span=max_span,
        center_fret=center_fret,
        min_strings=min_strings,
        prefer_open=prefer_open,
    )
    if not candidates:
        return None

    scored = [(
        _score_candidate(
            c,
            chord_pcs=pcs,
            root_pc=rpc,
            slash_bass_pc=slash,
            quality=quality,
            level=level,
            center_fret=center_fret,
        ),
        c,
    ) for c in candidates]
    scored.sort(key=lambda x: -x[0])
    return scored[0][1]


def _voicing_label(c: _VoicingCandidate, chord: str, level: str) -> str:
    """Human-readable label for the voicing style."""
    if c.has_open and c.max_fret <= 3:
        return "open"
    if c.n_strings <= 3:
        return "shell"
    if level == "Beginner" and c.span <= 3 and not c.has_barre:
        return "compact"
    if c.has_barre:
        return "barre"
    if c.span <= 2 and c.n_strings >= 4:
        return "compact"
    return "movable"


def _beginner_voicing(chord: str, guitar_tabs: dict[str, str]) -> GuitarVoicingEvent:
    from practice_notation import GUITAR_SHAPES

    # For explicit slash chords, try to generate a voicing with correct bass
    # before falling back to stored shapes (which don't honor the bass note).
    slash = _parse_slash_bass(chord)
    if slash is not None:
        c = _best_candidate(chord, "Beginner", center_fret=1, prefer_open=True, min_strings=3)
        if c is not None and c.bass_pc == slash:
            shape = _frets_to_shape(c.frets)
            return GuitarVoicingEvent(0, chord, shape, _voicing_label(c, chord, "Beginner"), _position_of(c.frets), spell_chord_tones(chord))

    # Prefer stored shapes (song tabs or built-in dictionary).
    for source in (guitar_tabs, GUITAR_SHAPES):
        if chord in source:
            return GuitarVoicingEvent(0, chord, source[chord], "open", 0, spell_chord_tones(chord))
    head = chord.split("/")[0]
    for source in (guitar_tabs, GUITAR_SHAPES):
        if head in source:
            return GuitarVoicingEvent(0, chord, source[head], "open", 0, spell_chord_tones(chord))

    # Generate a candidate voicing.
    c = _best_candidate(chord, "Beginner", center_fret=1, prefer_open=True, min_strings=3)
    if c is not None:
        shape = _frets_to_shape(c.frets)
        label = _voicing_label(c, chord, "Beginner")
        return GuitarVoicingEvent(0, chord, shape, label, _position_of(c.frets), spell_chord_tones(chord))

    # Last fallback: use legacy search for a minimal shell.
    pcs = _chord_tone_pcs(chord)
    if len(pcs) >= 3:
        result = _search_voicing(pcs[:3], [1, 2, 3, 4], center_fret=2, max_span=3)
        if result is not None:
            return GuitarVoicingEvent(0, chord, _frets_to_shape(result), "compact shell", _position_of(result), spell_chord_tones(chord))

    return GuitarVoicingEvent(0, chord, "x32010", "open (fallback)", 0, spell_chord_tones(chord))


def _intermediate_voicing(chord: str, prev_position: int | None) -> GuitarVoicingEvent:
    center = prev_position if prev_position is not None else 2
    c = _best_candidate(chord, "Intermediate", center_fret=center, min_strings=4)
    if c is not None:
        shape = _frets_to_shape(c.frets)
        label = _voicing_label(c, chord, "Intermediate")
        return GuitarVoicingEvent(0, chord, shape, label, _position_of(c.frets), spell_chord_tones(chord))

    # Fallback: try with 3-string minimum.
    c = _best_candidate(chord, "Intermediate", center_fret=center, min_strings=3)
    if c is not None:
        shape = _frets_to_shape(c.frets)
        return GuitarVoicingEvent(0, chord, shape, _voicing_label(c, chord, "Intermediate"), _position_of(c.frets), spell_chord_tones(chord))

    return GuitarVoicingEvent(0, chord, "x32010", "barre (fallback)", 0, spell_chord_tones(chord))


def _advanced_voicing(chord: str, prev_position: int | None) -> GuitarVoicingEvent:
    center = prev_position if prev_position is not None else 3
    quality = classify_chord_quality(chord)
    pcs = _chord_tone_pcs(chord)
    rpc = _root_pc(chord)
    seventh_pc = pcs[3] if len(pcs) >= 4 else None

    # Try full candidate search first.
    c = _best_candidate(chord, "Advanced", center_fret=center, min_strings=3)
    if c is not None:
        shape = _frets_to_shape(c.frets)
        label = _voicing_label(c, chord, "Advanced")
        # More descriptive labels for Advanced.
        if c.n_strings <= 3 and seventh_pc is not None:
            label = "shell"
        elif c.n_strings >= 5 and len(pcs) >= 5:
            label = "extended voicing"
        elif c.n_strings >= 4 and c.has_barre:
            label = "drop-2" if c.span >= 2 else "barre"
        return GuitarVoicingEvent(0, chord, shape, label, _position_of(c.frets), spell_chord_tones(chord))

    # Legacy fallback for difficult chords.
    alt = _alteration_hint(chord)
    if seventh_pc is not None:
        third_pc = pcs[1] if len(pcs) > 1 else rpc
        shell = [third_pc, seventh_pc, rpc]
        label = "shell (3-7-R)"
        if quality == "dom" and alt is not None:
            shell = shell[:2] + [(rpc + alt) % 12]
            label = "shell + altered color"
        result = _search_voicing(shell, [1, 2, 3, 4], center_fret=center, max_span=5)
        if result is not None:
            return GuitarVoicingEvent(0, chord, _frets_to_shape(result), label, _position_of(result), spell_chord_tones(chord))

    return GuitarVoicingEvent(0, chord, "x32010", "shell (fallback)", 0, spell_chord_tones(chord))


def build_level_guitar_voicings(
    chords: list[str],
    *,
    level: str,
    guitar_tabs: dict[str, str] | None = None,
) -> list[GuitarVoicingEvent]:
    """One voicing per chord, level-appropriate and position-connected."""
    tabs = guitar_tabs or {}
    out: list[GuitarVoicingEvent] = []
    prev_position: int | None = None
    for m_idx, chord in enumerate(chords):
        if level == "Beginner":
            ev = _beginner_voicing(chord, tabs)
        elif level == "Advanced":
            ev = _advanced_voicing(chord, prev_position)
        else:
            ev = _intermediate_voicing(chord, prev_position)
        ev.measure = m_idx
        out.append(ev)
        prev_position = ev.position
    return out


__all__ = [
    "GuitarVoicingEvent",
    "build_level_guitar_voicings",
    "song_guitar_tabs_for_key",
    "validate_voicing",
]
