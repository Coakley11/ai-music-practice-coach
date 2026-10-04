"""Print rhythm-engine examples for musical review (Slice C3, no UI).

Usage: python scripts/_proof_melodic_rhythm_engine.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from improvisation_motif import _pattern_note_roles, cycle_motif_rhythm  # noqa: E402
from melodic_pattern_engine import generate_pattern  # noqa: E402
from melodic_rhythm_engine import display_rhythm, parse_meter, rhythm_candidates  # noqa: E402
from motif_engine import build_motif_abc, build_phrase_pattern  # noqa: E402


def show(title: str, notes: list[str], roles: list[str] | None, r, meter: str, level: str) -> None:
    m = parse_meter(meter)
    print(f"=== {title}")
    print(f"meter {meter} · level {level} · rhythm level {r.level} · families {', '.join(r.families)}")
    print(f"candidate  {r.id}   (bars {r.bars}, unit {r.unit_bars} bar(s), total {r.total} quarters)")
    print(f"rhythm     {display_rhythm(r.events, meter)}")
    bar = -1
    for e in r.events:
        b = int(e.onset // m.bar)
        if b != bar:
            print(f"  bar {b + 1}:")
            bar = b
        if e.rest:
            print(f"    rest            onset {str(e.onset):>6}  dur {str(e.duration):>5}")
            continue
        role = roles[e.note] if roles else "-"
        tup = f" tuplet {e.tuplet[0]}:{e.tuplet[1]}" if e.tuplet else ""
        beat = "  <- strong" if m.strength(e.onset % m.bar) >= 0.8 else ""
        print(f"    {notes[e.note]:<3} {role:<11} onset {str(e.onset):>6}  dur {str(e.duration):>5}{tup}{beat}")
    print()


def main() -> None:
    # 1 — 4-note Beginner phrase in 4/4
    notes = ["C", "D", "E", "G"]
    roles = ["chord_tone", "scale", "chord_tone", "target"]
    show("1  4-note Beginner phrase, 4/4", notes, roles,
         rhythm_candidates(4, meter="4/4", level="Beginner", roles=roles)[0], "4/4", "Beginner")

    # 2 — 5-note Intermediate cell in 4/4 (formerly excluded one-bar size)
    res = generate_pattern("scale_12345", key="C", length=1)
    roles = _pattern_note_roles(res)
    show("2  5-note Intermediate cell (scale_12345), 4/4", res.notes, roles,
         rhythm_candidates(5, meter="4/4", level="Intermediate", roles=roles)[0], "4/4", "Intermediate")

    # 3 — 6-note cell in 6/8 (native compound grouping)
    res = generate_pattern("arpeggio_approach_ninth", key="C", length=1)
    roles = _pattern_note_roles(res)
    show("3  6-note cell (arpeggio_approach_ninth), 6/8", res.notes, roles,
         rhythm_candidates(6, meter="6/8", level="Intermediate", roles=roles)[0], "6/8", "Intermediate")

    # 4 — 8-note Advanced bebop phrase with structure identified
    res = next(
        r for r in (generate_pattern("bebop_scale_run", key="C", chord="G7", direction="descending", length=1, seed=s)
                    for s in range(8))
        if "passing" in _pattern_note_roles(r)
    )
    roles = _pattern_note_roles(res)
    show("4  8-note Advanced bebop line over G7, 4/4", res.notes, roles,
         rhythm_candidates(8, meter="4/4", level="Advanced", roles=roles)[0], "4/4", "Advanced")

    # 5 — enclosure with target placement
    res = generate_pattern("enclosure_classic", key="Dm", chord="Dm7", length=1)
    roles = _pattern_note_roles(res)
    show("5  Enclosure (enclosure_classic) over Dm7, 4/4", res.notes, roles,
         rhythm_candidates(4, meter="4/4", level="Intermediate", roles=roles)[0], "4/4", "Intermediate")

    # 6 / 7 — 12- and 16-note multi-bar phrases
    for n, level in ((12, "Intermediate"), (16, "Advanced")):
        res = generate_pattern("scale_1234", key="G", length=n // 4)
        roles = _pattern_note_roles(res)
        show(f"{6 if n == 12 else 7}  {n}-note free phrase, 4/4", res.notes, roles,
             rhythm_candidates(n, meter="4/4", level=level, roles=roles)[0], "4/4", level)

    # Change Rhythm: one unchanged pitch sequence, successive candidates
    p = build_phrase_pattern({"chord": "G7", "notes": [], "meter": "4/4"}, key_center="C", pattern_type="auto",
                             level="Advanced", pattern_seed=4, length=2)
    print(f"=== Change Rhythm on {p['pattern_family_name']} ({p['pattern_difficulty']}) — pitches never change")
    print(f"notes {' '.join(p['notes'])}")
    print(f"midi  {p['midi']}")
    for step in range(6):
        abc_body = build_motif_abc(p, key_center="C").splitlines()[-1]
        meta = p["rhythm_meta"]
        print(f"  #{meta['index']:>2}/{meta['count']}  {p['rhythm']:<28} {meta['id']}")
        print(f"        ABC {abc_body[:96]}")
        nxt = cycle_motif_rhythm(p)
        assert nxt["notes"] == p["notes"] and nxt["midi"] == p["midi"]
        assert nxt["pattern_family"] == p["pattern_family"]
        p = nxt


if __name__ == "__main__":
    main()
