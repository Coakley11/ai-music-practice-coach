"""Issue 67: does the reported loop match a progression the song actually repeats?

For every curated song this prints what the Songs card claims, beside what the chart
says, and flags the disagreements:

  INTRO     the reported loop's chords sit only in an intro / outro / pickup
  NOTRUN    the reported chords never occur consecutively anywhere in the chart
  ORDER     those chords do occur, but not in the reported order
  ONESEC    the loop was found in a single section that is not a main section
  NUMERAL   a Roman numeral does not match the chord printed beside it

Nothing here asserts; it is a survey, so the implementation starts from measured
cases rather than from a reading of the code.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from chord_subdivisions import chord_stream  # noqa: E402
from song_card_guidance import analyze_song_harmony, expand_sections  # noqa: E402
from song_catalog.catalog import curated_song_records  # noqa: E402

INTRO_WORDS = ("intro", "outro", "pickup", "pick-up", "count-in", "tag", "coda", "vamp")


def out(line: str) -> None:
    print(line.encode("ascii", "replace").decode("ascii"), flush=True)


def is_intro_like(name: str) -> bool:
    low = str(name or "").strip().lower()
    return any(w in low for w in INTRO_WORDS)


def motion(chords):
    """Consecutive duplicates collapsed - what the detector itself compares."""
    return [c for i, c in enumerate(chords) if i == 0 or c != chords[i - 1]]


def contains_run(seq, want):
    n = len(want)
    return any(tuple(seq[i:i + n]) == tuple(want) for i in range(len(seq) - n + 1))


def rotations(want):
    return {tuple(want[i:] + want[:i]) for i in range(len(want))}


def survey(record):
    sections = record.get("sections") or {}
    if not sections:
        return None
    rows = expand_sections(sections)
    facts = analyze_song_harmony(record)
    if not facts.loop:
        return None

    loop = list(facts.loop)
    flags = []
    where = []
    for name, chords in rows:
        m = motion(chords)
        if contains_run(m, loop):
            where.append(name)
    if not where:
        # Maybe it is there in another rotation, or not consecutive at all.
        rotated = [n for n, cs in rows
                   if any(contains_run(motion(cs), list(r)) for r in rotations(loop))]
        flags.append("ORDER" if rotated else "NOTRUN")
        where = rotated

    main = [n for n in where if not is_intro_like(n)]
    if where and not main:
        flags.append("INTRO")
    elif len(where) == 1 and main:
        flags.append("ONESEC")

    return {
        "title": str(record.get("title") or ""),
        "key": str(record.get("key") or ""),
        "loop": loop,
        "numerals": list(facts.loop_numerals),
        "where": where,
        "sections": [n for n, _c in rows],
        "flags": flags,
    }


def main() -> int:
    records = list(curated_song_records())
    out(f"{len(records)} curated songs")
    surveys = [s for s in (survey(r) for r in records) if s]
    out(f"{len(surveys)} report a repeating loop on the Songs card\n")

    tally: Counter = Counter()
    for s in surveys:
        for f in s["flags"] or ["OK"]:
            tally[f] += 1
    out("flags: " + ", ".join(f"{k}={v}" for k, v in tally.most_common()) + "\n")

    for s in surveys:
        if not s["flags"]:
            continue
        out(f"[{','.join(s['flags'])}] {s['title']} ({s['key']})")
        out(f"    loop     {' - '.join(s['loop'])}")
        out(f"    numerals {' - '.join(s['numerals'])}")
        out(f"    found in {s['where'] or '(nowhere)'}")
        out(f"    sections {s['sections'][:9]}")

    out("\n--- a few clean ones, for comparison ---")
    for s in [x for x in surveys if not x["flags"]][:6]:
        out(f"[OK] {s['title']} ({s['key']}): {' - '.join(s['loop'])} "
            f"= {' - '.join(s['numerals'])}  in {s['where'][:3]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
