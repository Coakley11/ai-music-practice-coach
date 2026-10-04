"""Print original generated pattern-vocabulary examples for musical review (no UI).

Usage: python scripts/_proof_melodic_pattern_vocabulary.py [--all]

``--all`` prints one short example of every registered family in C major / G7.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from melodic_pattern_engine import (  # noqa: E402
    PATTERN_FAMILIES,
    PatternResult,
    generate_auto_pattern,
    generate_pattern,
    validate_pattern,
)

EXAMPLES: list[tuple[str, dict]] = [
    ("C major scalar", dict(family="scale_1235", key="C", direction="ascending", length=4)),
    ("C major permutation", dict(family="perm_1324", key="C", direction="descending", length=4)),
    ("B minor interval cell", dict(family="perm_1425", key="Bm", direction="ascending", length=4)),
    ("G7 chord tones + chromatic approach", dict(family="lower_approach_arpeggio", key="C", chord="G7", length=4)),
    ("G7 upper chromatic approach", dict(family="upper_approach_cell", key="C", chord="G7", direction="descending", length=4)),
    ("D minor enclosure", dict(family="enclosure_classic", key="Dm", chord="Dm7", length=4)),
    ("D minor four-note enclosure (A7)", dict(family="enclosure_four_note", key="Dm", chord="A7", length=4)),
    ("Bebop line (G7)", dict(family="bebop_scale_run", key="C", chord="G7", direction="descending", length=2)),
    ("Bebop run into enclosure (Bb7 in Eb)", dict(family="bebop_run_to_enclosure", key="Eb", chord="Bb7", direction="descending", length=2)),
    ("Bebop passing descent (G7)", dict(family="bebop_passing_descent", key="C", chord="G7", direction="descending", length=4)),
    ("Guide tones (Dm7)", dict(family="guide_tone_leap", key="C", chord="Dm7", length=4)),
    ("Chromatic real sequence", dict(family="chromatic_sequence_1235", key="C", direction="ascending", length=4)),
    ("Accidental-heavy: F# major arpeggio + 9th", dict(family="arpeggio_approach_ninth", key="F#", length=3)),
    ("Accidental-heavy: Ebm chromatic run (Bb7)", dict(family="chromatic_run_to_target", key="Ebm", chord="Bb7", length=4)),
]


def show(title: str, r: PatternResult) -> None:
    f = r.family
    ctx = r.context
    print(f"=== {title}")
    print(f"family     : {f.id} — {f.name} [{f.category}, {f.difficulty}]")
    print(f"context    : key {ctx.key} ({ctx.mode}) · chord {ctx.chord} ({ctx.quality}) · {r.direction}")
    print(f"chord-scale: {' '.join(ctx.scale_names)}")
    for ci, cell in enumerate(r.cells):
        notes = " ".join(f"{n.name:<2}" for n in cell)
        midis = " ".join(f"{n.midi:<3}" for n in cell)
        degs = " ".join(f"{n.degree:<3}" for n in cell)
        fns = " ".join(
            ("*" if n.chromatic else "") + {"chord_tone": "ct", "scale": "sc", "approach": "ap",
                                             "neighbor": "nb", "passing": "ps"}[n.function]
            + (f">{n.target}" if n.target is not None else "")
            for n in cell
        )
        print(f"  cell {ci}: {notes:<34} midi {midis:<34} deg {degs:<30} {fns}")
    tg = [f"{n.name}({n.chord_role or 'tension'})" for _ci, _ni, n in r.targets()[:4]]
    if tg:
        print(f"targets    : {', '.join(tg)}{' …' if len(r.targets()) > 4 else ''}")
    problems = validate_pattern(r)
    print(f"valid      : {'yes' if not problems else problems}")
    print()


def main() -> None:
    print("Legend: ct chord tone · sc scale · ap approach · nb diatonic neighbour · ps passing")
    print("        * = outside the chord-scale · >n = resolves to cell index n\n")
    if "--all" in sys.argv:
        for fid in PATTERN_FAMILIES:
            try:
                show(fid, generate_pattern(fid, key="C", chord="G7", length=2))
            except ValueError:
                show(fid, generate_pattern(fid, key="C", length=2))
        return
    for title, kw in EXAMPLES:
        fam = kw.pop("family")
        show(title, generate_pattern(fam, **kw))
    for seed in (1, 2, 3):
        show(
            f"Auto / Musical (Advanced, G7, seed {seed})",
            generate_auto_pattern(key="C", chord="G7", difficulty="Advanced", length=2, seed=seed),
        )


if __name__ == "__main__":
    main()
