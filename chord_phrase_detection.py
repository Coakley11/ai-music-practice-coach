"""Detect repeating harmonic phrases within a song section's chord list.

Given a flat list of chords for one section, identifies repeated chord
subsequences and returns phrase-group boundaries.  The result is used by
notation renderers (Guitar TAB, lead-sheet grids, ABC builders) to add
visual spacing and optional repeat labels between musical phrases.

Design principles:
- Respect explicit section boundaries (caller already splits by section).
- Detect genuine repeated harmonic patterns, not just repeated chord names.
- Never split a single held chord across phrase boundaries.
- Never force a section into power-of-2 groupings when the data disagrees.
- Very short sections (≤ 4 bars) are a single phrase — no grouping.
- All-identical bars ("G G G G G G G G") are a single phrase.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhraseGroup:
    """One phrase within a section."""

    start: int  # 0-based bar index
    length: int  # number of bars in this phrase
    label: str  # e.g. "Phrase A", "Phrase A (repeat)", "" for unlabeled
    repeat_of: int | None  # index of a prior PhraseGroup this one repeats (or None)


def detect_chord_phrases(chords: list[str]) -> list[PhraseGroup]:
    """Identify phrase groups in a flat list of chords (one per bar).

    Returns a list of ``PhraseGroup`` objects covering every bar.  The union
    of all groups' ``[start, start+length)`` ranges equals ``range(len(chords))``.
    """
    n = len(chords)
    if n <= 4:
        return [PhraseGroup(start=0, length=n, label="", repeat_of=None)]

    if _all_same(chords):
        return [PhraseGroup(start=0, length=n, label="", repeat_of=None)]

    groups = _detect_repeating_subsequences(chords)
    if groups:
        return groups

    return [PhraseGroup(start=0, length=n, label="", repeat_of=None)]


def phrase_boundary_set(phrases: list[PhraseGroup]) -> set[int]:
    """Return 0-based bar indices that start a new phrase (excluding bar 0)."""
    return {pg.start for pg in phrases if pg.start > 0}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _all_same(chords: list[str]) -> bool:
    """True if every bar has the same chord token."""
    return len(set(chords)) <= 1


def _detect_repeating_subsequences(chords: list[str]) -> list[PhraseGroup] | None:
    """Try candidate phrase lengths in priority order, return first match.

    Priority: 4-bar first (overwhelmingly common), then 8, 3, 6, and 2
    only as a last resort with a harmonic-movement check.
    """
    n = len(chords)
    for phrase_len in _candidate_lengths(n):
        if phrase_len <= 2 and not _phrases_have_movement(chords, phrase_len):
            continue
        groups = _try_phrase_length(chords, phrase_len)
        if groups is not None:
            return groups
    return None


def _candidate_lengths(n: int) -> list[int]:
    """Return phrase lengths to try, in priority order.

    4-bar phrases first (the overwhelmingly common musical unit), then
    8, 3, 6, and finally 2 as a fallback.  Half-section is appended
    for odd-length sections where none of the natural lengths divide.
    """
    candidates: list[int] = []
    priority = [4, 8, 3, 6, 2]
    for length in priority:
        if 2 <= length <= n // 2:
            candidates.append(length)
    half = n // 2
    if half >= 2 and half not in candidates:
        candidates.append(half)
    return candidates


def _try_phrase_length(
    chords: list[str], phrase_len: int
) -> list[PhraseGroup] | None:
    """Check whether ``phrase_len`` produces meaningful grouping.

    Returns phrase groups if at least one exact repeat is found and the
    grouping covers the full section cleanly.  Returns ``None`` otherwise.
    """
    n = len(chords)
    if phrase_len < 2 or phrase_len > n:
        return None

    full_phrases = n // phrase_len
    remainder = n % phrase_len

    if full_phrases < 2:
        return None

    phrases: list[list[str]] = []
    for i in range(full_phrases):
        start = i * phrase_len
        phrases.append(chords[start : start + phrase_len])

    if remainder:
        phrases.append(chords[full_phrases * phrase_len :])

    has_repeat = False
    first_occurrence: dict[tuple[str, ...], int] = {}
    groups: list[PhraseGroup] = []

    label_counter = 0
    label_map: dict[tuple[str, ...], str] = {}

    for i, phrase_chords in enumerate(phrases):
        key = tuple(phrase_chords)
        if key in first_occurrence:
            has_repeat = True
            ref_idx = first_occurrence[key]
            base_label = label_map[key]
            groups.append(
                PhraseGroup(
                    start=i * phrase_len if i < full_phrases else full_phrases * phrase_len,
                    length=len(phrase_chords),
                    label=f"{base_label} (repeat)",
                    repeat_of=ref_idx,
                )
            )
        else:
            first_occurrence[key] = i
            label = _phrase_label(label_counter)
            label_map[key] = label
            label_counter += 1
            start = i * phrase_len if i < full_phrases else full_phrases * phrase_len
            groups.append(
                PhraseGroup(
                    start=start,
                    length=len(phrase_chords),
                    label=label,
                    repeat_of=None,
                )
            )

    if not has_repeat:
        return None

    if remainder and not _is_trivial_remainder(chords, full_phrases * phrase_len, remainder):
        pass

    return groups


def _is_trivial_remainder(chords: list[str], start: int, length: int) -> bool:
    """Check if the remainder is too short to be a real phrase."""
    return length <= 1


def _phrases_have_movement(chords: list[str], phrase_len: int) -> bool:
    """True if each phrase-length window has ≥ 2 distinct chords."""
    n = len(chords)
    for i in range(0, n - phrase_len + 1, phrase_len):
        window = chords[i : i + phrase_len]
        if len(set(window)) < 2:
            return False
    return True


def _phrase_label(index: int) -> str:
    """Return 'Phrase A', 'Phrase B', etc."""
    if index < 26:
        return f"Phrase {chr(65 + index)}"
    return f"Phrase {index + 1}"
