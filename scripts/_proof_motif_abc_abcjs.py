"""Decode motif ABC with real abcjs 6.4.4 and compare every sounding pitch to motif MIDI.

Invariant proved: ``source motif MIDI == ABC-rendered pitch MIDI`` for every note.

Usage: python scripts/_proof_motif_abc_abcjs.py [--shots OUT_DIR]

Needs network (jsDelivr) and Playwright Chromium. ``--shots`` also saves PNG
renders of a few representative motifs for visual review.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ABCJS_URL = "https://cdn.jsdelivr.net/npm/abcjs@6.4.4/dist/abcjs-basic-min.js"  # same as the app

_PAGE = f"""<html><head><script src="{ABCJS_URL}"></script>
<style>body{{background:#fff;margin:0;padding:8px;font-family:sans-serif}} h3{{margin:10px 0 0 0;font-size:14px}}</style>
</head><body><div id="paper"></div><div id="shots"></div></body></html>"""

_DECODE_JS = """(abc) => {
  const vo = ABCJS.renderAbc("paper", abc)[0];
  const audio = vo.setUpAudio();
  const out = [];
  for (const tr of audio.tracks) for (const ev of tr) if (ev.cmd === "note") out.push(ev.pitch);
  return {pitches: out, warnings: vo.warnings || []};
}"""


def corpus() -> list[tuple[str, dict[str, Any], str]]:
    """(label, motif, key_center) across the existing generator and the C1 vocabulary."""
    import random

    from improvisation_motif import build_motif_pattern, cycle_motif_rhythm, generate_motif_for_chord
    from melodic_pattern_engine import PATTERN_FAMILIES, build_context, family_supports, generate_pattern

    out: list[tuple[str, dict[str, Any], str]] = []
    keys = [
        ("C", ["C", "G7", "Dm7"]), ("F", ["F", "C7", "Gm7"]), ("G", ["G", "D7", "Am7"]),
        ("D", ["D", "A7", "Em7"]), ("Bb", ["Bb", "F7", "Cm7"]), ("Eb", ["Eb", "Bb7", "Fm7"]),
        ("Ab", ["Ab", "Eb7"]), ("Db", ["Db", "Ab7"]), ("E", ["E", "B7"]), ("F#", ["F#", "C#7"]),
        ("Am", ["Am7", "E7"]), ("Dm", ["Dm7", "A7"]), ("Bm", ["Bm7", "F#7"]), ("Fm", ["Fm7", "C7"]),
        ("Cm", ["Cm7", "G7"]), ("F#m", ["F#m7", "C#7"]), ("Ebm", ["Ebm7", "Bb7"]), ("C#m", ["C#m7", "G#7"]),
        ("Dbm", ["Dbm7"]), ("Abm", ["Abm7", "Eb7"]),
    ]
    for key, chords in keys:
        for chord in chords:
            for level in ("Beginner", "Intermediate", "Advanced"):
                for tier in ("easier", "normal", "harder"):
                    m = generate_motif_for_chord(
                        chord, key_center=key, level=level, rng=random.Random(7),
                        idea_variant=3, difficulty_tier=tier,
                    )
                    out.append((f"motif {key}/{chord}/{level}/{tier}", m, key))
            base = generate_motif_for_chord(chord, key_center=key, level="Intermediate", rng=random.Random(1))
            for ptype in ("auto", "scalar", "thirds", "fourths", "pentatonic"):
                for direction in ("ascending", "descending"):
                    pat = build_motif_pattern(base, key_center=key, pattern_type=ptype, direction=direction, length=8)
                    out.append((f"pattern {key}/{chord}/{ptype}/{direction}", pat, key))
                    out.append((f"pattern+rhythm {key}/{chord}/{ptype}/{direction}", cycle_motif_rhythm(pat), key))
    for fam in PATTERN_FAMILIES.values():
        for key, chords in keys:
            for chord in chords[:2]:
                ctx = build_context(key, chord)
                for direction in ("ascending", "descending"):
                    if not family_supports(fam, ctx, direction):
                        continue
                    try:
                        r = generate_pattern(fam, key=key, chord=chord, direction=direction, length=4)
                    except ValueError:
                        continue
                    m = r.to_motif_fields()
                    m["rhythm_symbols"] = ["♪"] * len(m["notes"])  # 8 per bar: stresses in-bar accidentals
                    m["meter"] = "4/4"
                    out.append((f"C1 {fam.id} {key}/{chord}/{direction}", m, key))
    return out


def decode_all(abcs: list[str]) -> list[dict[str, Any]]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(_PAGE)
        page.wait_for_function("typeof ABCJS !== 'undefined'", timeout=30000)
        res = page.evaluate(f"(abcs) => abcs.map({_DECODE_JS})", abcs)
        browser.close()
    return res


def check(build: Callable[..., str], items: list[tuple[str, dict[str, Any], str]]) -> tuple[int, int, list[str]]:
    from improvisation_motif import sync_motif_midi

    abcs, expected = [], []
    for _label, motif, key in items:
        synced = sync_motif_midi(dict(motif))
        abcs.append(build(synced, key_center=key))
        expected.append([int(m) for m in synced["midi"]])
    decoded = decode_all(abcs)
    bad_motifs, bad_notes, samples = 0, 0, []
    for (label, _m, key), abc, want, got in zip(items, abcs, expected, decoded):
        pitches = got["pitches"]
        wrong = sum(1 for a, b in zip(want, pitches) if a != b) + abs(len(want) - len(pitches))
        if wrong or got["warnings"]:
            bad_motifs += 1
            bad_notes += wrong
            if len(samples) < 6:
                body = abc.split("\n", 6)[-1]
                samples.append(f"{label}: want {want[:10]} got {pitches[:10]}\n      K:{key} {body[:90]}")
    return bad_motifs, bad_notes, samples


def screenshots(out_dir: Path) -> None:
    from playwright.sync_api import sync_playwright

    from improvisation_motif import build_motif_abc
    from melodic_pattern_engine import generate_pattern

    def pat(fid: str, **kw: Any) -> dict[str, Any]:
        m = generate_pattern(fid, **kw).to_motif_fields()
        m["rhythm_symbols"] = ["♪"] * len(m["notes"])
        m["meter"] = "4/4"
        return m

    low = {"notes": ["F", "G", "A", "B", "C", "D", "B", "C"], "midi": [53, 55, 57, 59, 60, 62, 59, 60],
           "rhythm_symbols": ["♪"] * 8, "meter": "4/4"}
    fmaj = {"notes": ["A", "Bb", "B", "C", "F", "E", "Bb", "A"], "midi": [69, 70, 71, 72, 77, 76, 70, 69],
            "rhythm_symbols": ["♪"] * 8, "meter": "4/4"}
    dmaj = {"notes": ["D", "C#", "C", "B", "F#", "F", "E", "D"], "midi": [74, 73, 72, 71, 66, 65, 64, 62],
            "rhythm_symbols": ["♪"] * 8, "meter": "4/4"}
    items = [
        ("1 Low register crossing B3/C4 (C major): F3 G3 A3 B3 C4 D4 B3 C4", low, "C"),
        ("2 F major with B natural: A Bb B(nat) C | F E Bb A", fmaj, "F"),
        ("3 D major with C natural and F natural: D C# C(nat) B F# F(nat) E D", dmaj, "D"),
        ("4 C1 enclosure (D minor, Dm7)", pat("enclosure_classic", key="Dm", chord="Dm7", length=2), "Dm"),
        ("5 C1 bebop run into enclosure (Eb, Bb7)",
         pat("bebop_run_to_enclosure", key="Eb", chord="Bb7", direction="descending", length=2), "Eb"),
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 900, "height": 300})
        page.set_content(_PAGE)
        page.wait_for_function("typeof ABCJS !== 'undefined'", timeout=30000)
        for i, (title, motif, key) in enumerate(items, 1):
            abc = build_motif_abc(motif, key_center=key, title=title)
            got = page.evaluate(_DECODE_JS, abc)
            ok = got["pitches"] == [int(m) for m in motif["midi"]]
            print(f"shot {i}: {'OK ' if ok else 'BAD'} midi {motif['midi']} -> abcjs {got['pitches']}")
            print(f"        {abc.splitlines()[-2]}  {abc.splitlines()[-1]}")
            page.evaluate(
                "(abc) => ABCJS.renderAbc('paper', abc, {staffwidth: 860, scale: 1.25})", abc
            )
            page.locator("#paper").screenshot(path=str(out_dir / f"motif_abc_{i}.png"))
        browser.close()


def main() -> None:
    from improvisation_motif import build_motif_abc

    items = corpus()
    bad_motifs, bad_notes, samples = check(build_motif_abc, items)
    total_notes = sum(len(m.get("notes") or []) for _l, m, _k in items)
    print(f"abcjs decode: {len(items)} motifs, {total_notes} notes — "
          f"{bad_motifs} motifs / {bad_notes} notes differ from motif MIDI")
    for s in samples:
        print("  ", s)
    if "--shots" in sys.argv:
        screenshots(Path(sys.argv[sys.argv.index("--shots") + 1]))
    sys.exit(1 if bad_motifs else 0)


if __name__ == "__main__":
    main()
