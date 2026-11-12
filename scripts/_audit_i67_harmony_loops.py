"""Issue 67: does the reported progression match one the song actually plays?

Catalog-wide, in several Practice Keys. The checks are the ones that would have
caught the reported defects:

  SYNTAX    a musician-facing chord label still carries chart-only syntax
  ABSENT    the reported progression is not played by a section credited with it
  NONMAIN   it is credited only to an intro / coda / tag, without saying so
  FREQORDER the summary lists chords joined by dashes that the song never plays
            in that order

Run it after a change; it prints a verdict line and exits non-zero on a failure.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from song_card_guidance import (  # noqa: E402
    _is_main_section,
    _section_progression,
    analyze_song_harmony,
    build_song_card_guidance,
    section_bars,
)
from song_catalog.catalog import curated_song_records  # noqa: E402

#: Chart-only syntax *attached to a chord symbol*. Prose has colons of its own,
#: so a bare ``[:|]`` search flagged every "come in pairs: a gentle chord" line.
CHART_SYNTAX = re.compile(r"[A-G][#b♯♭]?[^\s,;.()]*(?::[0-9.]+|\|)")
KEYS = ("C", "Eb", "A")
LEVELS = ("Beginner", "Intermediate", "Advanced")


def out(line: str) -> None:
    print(line.encode("ascii", "replace").decode("ascii"), flush=True)


def plays(bars, want) -> bool:
    """Does this section's own recurring unit contain the progression, in order?"""
    prog = _section_progression(bars)
    if not prog:
        return False
    seq, n = list(prog.chords), len(want)
    doubled = seq + seq  # a cycle may be entered anywhere
    return any(tuple(doubled[i:i + n]) == tuple(want) for i in range(len(seq)))


def check(record) -> list[str]:
    problems: list[str] = []
    title = str(record.get("title") or "")
    sections = record.get("sections") or {}
    if not sections:
        return problems
    facts = analyze_song_harmony(record)
    rows = dict(section_bars(sections))

    if facts.loop:
        credited = [n for n in facts.loop_sections if n in rows]
        if credited and not any(plays(rows[n], facts.loop) for n in credited):
            problems.append(f"ABSENT {title}: {' - '.join(facts.loop)} not played by {credited}")
        if credited and not any(_is_main_section(n) for n in credited):
            if facts.loop_from_main_section:
                problems.append(f"NONMAIN {title}: credited only to {credited}")

    for key in KEYS:
        for level in LEVELS:
            card = build_song_card_guidance(
                record, level=level, instrument="Piano", focus="Chords & Harmony",
                practice_key=key, chart_key=key,
            )
            text = str(card.get("harmony") or "")
            if CHART_SYNTAX.search(text):
                problems.append(f"SYNTAX {title} @ {key} [{level}]: {text[:110]}")
            # A dash-joined run of chords is a claim about order, so it may only
            # appear when an ordered progression was found - never out of a
            # frequency ranking.
            if not facts.has_progression and re.search(r"[A-G][^\s]* – [A-G]", text):
                problems.append(f"FREQORDER {title} @ {key} [{level}]: {text[:110]}")
    return problems


def main() -> int:
    records = list(curated_song_records())
    problems: list[str] = []
    with_prog = 0
    for record in records:
        if analyze_song_harmony(record).has_progression:
            with_prog += 1
        problems.extend(check(record))

    out(f"{len(records)} songs, {with_prog} with a recurring progression, "
        f"{len(KEYS)} keys x {len(LEVELS)} levels each")
    for line in problems[:40]:
        out("  " + line)
    out(f"VERDICT: {'CLEAN' if not problems else f'{len(problems)} PROBLEMS'}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
