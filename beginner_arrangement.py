"""Beginner-mode song arrangement simplification.

The catalog charts are designed for Intermediate / Advanced players and
often include several verses, bridges, solos, and extended outros. That
is too much structure for someone learning a tune from scratch.

This module produces a **derived view** of a song:

* It trims the playback ``section_order`` down to a short, beginner-
  friendly arc such as ``Intro -> Verse -> Chorus -> Verse -> Chorus
  -> Outro``.
* It produces a matching filtered ``sections`` dict so backing-track
  generation, the lead sheet, and the chord-follow highlight all
  reflect the simplified arrangement.
* It does **not** mutate the underlying catalog data. The original
  multi-verse / bridge / solo arrangement is still available for
  Intermediate and Advanced.

Heuristic (chosen to match the user spec):

* Keep at most **two** verses (the first two found in the catalog).
* Keep at most **two** choruses.
* Keep the first Intro (if any) and the first Outro (if any).
* Keep one Pre-Chorus (if the song has one), used before the first
  chorus only - kept once to keep the form short.
* Drop bridges, solos, interludes, extended outros, repeated intros,
  and instrumentals.

For songs that already only have one Verse and one Chorus this is a
no-op trim of any solos/bridges/interludes, which already feels
beginner-appropriate.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

__all__ = (
    "BEGINNER_LEVEL",
    "is_beginner_level",
    "classify_section_role",
    "select_beginner_section_names",
    "beginner_view_of_song_data",
    "beginner_view_of_sections",
    "build_beginner_display_labels",
    "beginner_display_label_for_section",
    "is_beginner_arrangement_active",
    "ROLE_INTRO",
    "ROLE_VERSE",
    "ROLE_PRECHORUS",
    "ROLE_CHORUS",
    "ROLE_BRIDGE",
    "ROLE_SOLO",
    "ROLE_INTERLUDE",
    "ROLE_OUTRO",
    "ROLE_OTHER",
)


BEGINNER_LEVEL = "Beginner"

ROLE_INTRO = "Intro"
ROLE_VERSE = "Verse"
ROLE_PRECHORUS = "Pre-Chorus"
ROLE_CHORUS = "Chorus"
ROLE_BRIDGE = "Bridge"
ROLE_SOLO = "Solo"
ROLE_INTERLUDE = "Interlude"
ROLE_OUTRO = "Outro"
ROLE_OTHER = "Other"


_ROLE_DISPLAY_LABEL = {
    ROLE_INTRO: "Intro",
    ROLE_VERSE: "Verse",
    ROLE_PRECHORUS: "Pre-Chorus",
    ROLE_CHORUS: "Chorus",
    ROLE_BRIDGE: "Bridge",
    ROLE_SOLO: "Solo",
    ROLE_INTERLUDE: "Interlude",
    ROLE_OUTRO: "Outro",
}


def is_beginner_level(level: Any) -> bool:
    """``True`` when ``level`` is the Beginner tier (case-insensitive)."""
    return str(level or "").strip().lower() == BEGINNER_LEVEL.lower()


def classify_section_role(name: str) -> str:
    """Map a raw section name (e.g. ``"Verse 2A"``) to a canonical role.

    Order matters: ``Pre-Chorus`` must be checked before ``Chorus`` so
    "Pre-Chorus 1" doesn't get classified as a chorus.
    """
    low = str(name or "").strip().lower()
    if not low:
        return ROLE_OTHER
    if "pre-chorus" in low or "prechorus" in low or "pre chorus" in low:
        return ROLE_PRECHORUS
    if "chorus" in low or "refrain" in low or "hook" in low:
        return ROLE_CHORUS
    if "intro" in low:
        return ROLE_INTRO
    if any(tok in low for tok in ("outro", "coda", "ending", "fade-out", "fadeout")):
        return ROLE_OUTRO
    if "verse" in low:
        return ROLE_VERSE
    if "bridge" in low:
        return ROLE_BRIDGE
    if any(tok in low for tok in ("solo", "instrumental")):
        return ROLE_SOLO
    if any(tok in low for tok in ("interlude", "intermezzo", "vamp", "tag", "turnaround")):
        return ROLE_INTERLUDE
    if "harmonica" in low:
        return ROLE_SOLO
    return ROLE_OTHER


def select_beginner_section_names(
    section_names: list[str] | None,
    *,
    max_verses: int = 2,
    max_choruses: int = 2,
) -> list[str]:
    """Pick a beginner-friendly subset of an existing section name order.

    Keeps:

    * the first Intro (if any)
    * the first Pre-Chorus before the first chorus (if any)
    * up to ``max_verses`` distinct Verses (default 2)
    * up to ``max_choruses`` distinct Choruses (default 2)
    * the first Outro (if any)

    Drops bridges, solos, interludes, instrumentals, and extra repeats
    of any kept role. Returns ``[]`` only if the input was empty.
    """
    if not section_names:
        return []

    by_role: dict[str, list[str]] = {}
    for name in section_names:
        role = classify_section_role(name)
        by_role.setdefault(role, []).append(name)

    intros = by_role.get(ROLE_INTRO, [])
    verses = by_role.get(ROLE_VERSE, [])
    prechor = by_role.get(ROLE_PRECHORUS, [])
    choruses = by_role.get(ROLE_CHORUS, [])
    outros = by_role.get(ROLE_OUTRO, [])

    chosen_verses = verses[: max(0, int(max_verses))]
    chosen_choruses = choruses[: max(0, int(max_choruses))]

    out: list[str] = []

    if intros:
        out.append(intros[0])

    if chosen_verses or chosen_choruses:
        # First cycle: (Verse) -> (Pre-Chorus) -> (Chorus)
        if chosen_verses:
            out.append(chosen_verses[0])
            if prechor:
                out.append(prechor[0])
        if chosen_choruses:
            out.append(chosen_choruses[0])

        # Second cycle: (Verse2) -> (Chorus2)
        if len(chosen_verses) >= 2 and (len(chosen_choruses) >= 2 or chosen_choruses):
            out.append(chosen_verses[1])
            if len(chosen_choruses) >= 2:
                out.append(chosen_choruses[1])

    if outros and (outros[0] not in out):
        out.append(outros[0])

    # Defensive: if classification ate the whole song (e.g. only "Section
    # A" / "Section B" jazz-form labels), fall back to the first 4
    # sections as-is so the user still has a workable arrangement.
    if not out:
        return list(section_names[:4])

    # Preserve uniqueness (defensive; the picks above are already unique).
    seen: set[str] = set()
    deduped: list[str] = []
    for name in out:
        if name in seen:
            continue
        seen.add(name)
        deduped.append(name)
    return deduped


def beginner_view_of_song_data(
    song_data: Mapping[str, Any] | None,
    *,
    level: Any,
) -> dict[str, Any] | None:
    """Return a shallow-copied song_data dict with a trimmed section_order.

    * When ``level`` is not Beginner: returns a plain dict copy with no
      structural changes (so callers can always use the returned value
      without worrying about which level is active).
    * When the song has no ``section_order`` (or trimming would be a
      no-op): same as above.
    * Otherwise: returns a dict copy with ``section_order`` shortened
      and an internal flag ``_beginner_arrangement_active = True`` so
      downstream code (e.g. debug pills) can detect the simplified view.

    The original catalog object is never mutated.
    """
    if song_data is None:
        return None
    base = dict(song_data) if isinstance(song_data, Mapping) else {}
    if not is_beginner_level(level):
        return base

    order = list(base.get("section_order") or [])
    if not order:
        return base
    trimmed = select_beginner_section_names(order)
    if trimmed == order:
        return base
    base["section_order"] = trimmed
    base["_beginner_arrangement_active"] = True
    base["_beginner_arrangement_original_order"] = list(order)
    # Optional convenience map consumed by the chord-chart renderer:
    # swaps "Verse 1" -> "Verse", "Chorus 2" -> "Chorus" on the chart
    # card headers without renaming the underlying dict keys.
    base["_beginner_display_labels"] = build_beginner_display_labels(trimmed)
    return base


def beginner_view_of_sections(
    sections: Mapping[str, Any] | None,
    *,
    section_order_for_level: list[str] | None,
) -> dict[str, Any]:
    """Filter a sections dict down to the kept beginner sections.

    Preserves the dict ordering to match ``section_order_for_level`` so
    iteration order is musically correct for backing-track generation
    and lead-sheet rendering. Returns a plain ``dict``.
    """
    if not sections:
        return {}
    if not section_order_for_level:
        return dict(sections)
    out: dict[str, Any] = {}
    for name in section_order_for_level:
        if name in sections:
            out[name] = sections[name]
    return out


def is_beginner_arrangement_active(song_data: Mapping[str, Any] | None) -> bool:
    """``True`` when the given song_data is a beginner-trimmed view."""
    if not song_data:
        return False
    return bool(song_data.get("_beginner_arrangement_active"))


def beginner_display_label_for_section(name: str) -> str:
    """Return the short display label ("Verse", "Chorus", ...) for a
    raw section name. Falls back to the original name when no role
    match is found."""
    role = classify_section_role(name)
    if role == ROLE_OTHER:
        return str(name or "").strip()
    return _ROLE_DISPLAY_LABEL.get(role, str(name or "").strip())


def build_beginner_display_labels(section_names: list[str] | None) -> dict[str, str]:
    """Return a ``{raw_section_name -> short_display_label}`` map.

    Used by the chord-chart renderer to swap "Verse 1" / "Verse 2" /
    "Chorus 1" / "Chorus 2" for the cleaner short labels users want
    in Beginner mode, **without** renaming any dict keys (so lyric
    cues, harmony maps, and chord-follow lookups all still work).
    """
    out: dict[str, str] = {}
    for raw in section_names or ():
        label = beginner_display_label_for_section(raw)
        if label and label != raw:
            out[raw] = label
    return out
