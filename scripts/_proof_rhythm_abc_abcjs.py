"""Real-abcjs proof for rhythm-engine motifs: pitch, onset, and duration of every note.

For each Auto / Musical pattern (several meters, keys, levels) and several successive
Change Rhythm steps, the motif's ABC is decoded by abcjs 6.4.4 (the app's renderer)
and compared with the motif: sounding MIDI, note onsets, and note durations must match
the rhythm engine exactly (triplets, dotted figures, rests, 6/8 duplets included).

Usage: python scripts/_proof_rhythm_abc_abcjs.py   (needs network + Playwright Chromium)
"""

from __future__ import annotations

import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Engine imports first (before Playwright starts its event loop).
from improvisation_motif import cycle_motif_rhythm, motif_rhythm_events  # noqa: E402
from motif_engine import build_motif_abc, build_phrase_pattern  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ABCJS_URL = "https://cdn.jsdelivr.net/npm/abcjs@6.4.4/dist/abcjs-basic-min.js"
PAGE = f'<html><head><script src="{ABCJS_URL}"></script></head><body><div id="paper"></div></body></html>'
DECODE_JS = """(abcs) => abcs.map((abc) => {
  const vo = ABCJS.renderAbc("paper", abc)[0];
  const notes = [];
  for (const tr of vo.setUpAudio().tracks) for (const ev of tr)
    if (ev.cmd === "note") notes.push([ev.pitch, ev.start, ev.duration]);
  return {notes, warnings: (vo.warnings || []).length};
})"""

CONTEXTS = [("C", "G7"), ("Bm", "F#7"), ("Dm", "A7"), ("Eb", "Bb7"), ("F#", "C#7"), ("Ab", "Eb7")]
METERS = ("4/4", "3/4", "6/8")
LEVELS = ("Beginner", "Intermediate", "Advanced")


def corpus() -> list[tuple[str, dict, str]]:
    out = []
    for meter in METERS:
        for key, chord in CONTEXTS:
            for level in LEVELS:
                for seed in (1, 2):
                    p = build_phrase_pattern({"chord": chord, "notes": [], "meter": meter}, key_center=key,
                                             pattern_type="auto", level=level, pattern_seed=seed, length=4)
                    for step in range(4):
                        out.append((f"{meter} {key}/{chord} {level} s{seed} #{step} {p['pattern_family']}", p, key))
                        p = cycle_motif_rhythm(p)
    return out


def expected(p: dict) -> list[tuple[int, Fraction, Fraction]]:
    events = motif_rhythm_events(p)
    return [(p["midi"][e.note], e.onset, e.duration) for e in events if not e.rest]


def main() -> int:
    items = corpus()
    abcs = [build_motif_abc(p, key_center=key) for _l, p, key in items]
    calib = "X:1\nM:4/4\nL:1/4\nK:C\nC D2 z |"
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_content(PAGE)
        page.wait_for_function("typeof ABCJS !== 'undefined'", timeout=60000)
        cal = page.evaluate(DECODE_JS, [calib])[0]["notes"]
        results = page.evaluate(DECODE_JS, abcs)
        browser.close()
    # Calibrate abcjs time units: second note (D2) is two quarters long.
    unit = Fraction(2) / Fraction(cal[1][2]).limit_denominator(10000)
    bad = 0
    n_notes = 0
    samples = []
    stats = {"tuplet": 0, "rest": 0, "dotted": 0, "6/8": 0}
    for (label, p, _key), abc, got in zip(items, abcs, results):
        want = expected(p)
        have = [(int(pt), (Fraction(st).limit_denominator(10000) * unit), (Fraction(d).limit_denominator(10000) * unit))
                for pt, st, d in got["notes"]]
        n_notes += len(want)
        ok = got["warnings"] == 0 and len(have) == len(want) and all(
            w[0] == h[0] and w[1] == h[1] and w[2] == h[2] for w, h in zip(want, have)
        )
        ev = p["rhythm_events"]
        stats["tuplet"] += any(e["tup"] for e in ev)
        stats["rest"] += any(e["rest"] for e in ev)
        stats["dotted"] += any(Fraction(e["w"]).numerator == 3 for e in ev)
        stats["6/8"] += p["meter"] == "6/8"
        if not ok:
            bad += 1
            if len(samples) < 5:
                first = next((i for i, (w, h) in enumerate(zip(want, have)) if w != h), None)
                samples.append(f"{label}: warnings={got['warnings']} first diff at {first}: "
                               f"want {want[first] if first is not None else None} have "
                               f"{have[first] if first is not None else None}\n    {abc.splitlines()[-1][:110]}")
    print(f"abcjs rhythm decode: {len(items)} motifs, {n_notes} notes — {bad} motifs differ "
          f"(pitch/onset/duration); unit calibration: abcjs duration x {unit}")
    print(f"  coverage: {stats['tuplet']} with tuplets, {stats['dotted']} with dotted figures, "
          f"{stats['rest']} with rests, {stats['6/8']} in 6/8")
    for s in samples:
        print("  ", s)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
