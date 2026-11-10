"""Would passing the two flags Composition already passes fix both defects?

Measures the same corpus three ways, so the recommendation is a measurement and not a
guess:

  as shipped          octave_shift=0,  musical_spelling=False
  octave only         octave_shift=-1, musical_spelling=False
  octave + spelling   octave_shift=-1, musical_spelling=True
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _proof_issue65_line_octave_abcjs import (  # noqa: E402
    CASES, CHORDS, KEYS, LEVELS, MODES, _DECODE_JS, _PAGE, engine_events,
)

VARIANTS = {
    "as shipped": dict(octave_shift=0, musical_spelling=False),
    "octave only": dict(octave_shift=-1, musical_spelling=False),
    "octave + spelling": dict(octave_shift=-1, musical_spelling=True),
}


def build(events, key, **kw):
    from chord_navigation_notation import arpeggio_events_to_melody_dicts
    from composition_melody_notation import build_abc_from_melody_events
    from practice_notation import NOTATION_METER

    return build_abc_from_melody_events(
        arpeggio_events_to_melody_dicts(events), key=key, meter=NOTATION_METER,
        bpm=100, title="t", chords=CHORDS, clef="treble", **kw,
    )


def main() -> None:
    from playwright.sync_api import sync_playwright

    corpus = []
    for instrument, reg, label in CASES:
        for level, _d in LEVELS:
            for mode in MODES:
                for key in KEYS:
                    events = engine_events(instrument, reg, level, key, mode)
                    want = [int(e.midi) for e in events if not e.is_rest and e.midi]
                    if want:
                        corpus.append((label, key, events, want))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(_PAGE)
        page.wait_for_function("typeof ABCJS !== 'undefined'", timeout=30000)
        for name, kw in VARIANTS.items():
            abcs = [build(ev, key, **kw) for _l, key, ev, _w in corpus]
            decoded = page.evaluate(f"(a) => a.map({_DECODE_JS})", abcs)
            deltas: Counter = Counter()
            mismatched_lengths = 0
            for (_label, _key, _ev, want), got in zip(corpus, decoded):
                pitches = got["pitches"]
                if len(pitches) != len(want):
                    mismatched_lengths += 1
                    continue
                deltas.update(g - w for g, w in zip(pitches, want))
            total = sum(deltas.values())
            exact = deltas.get(0, 0)
            print(f"{name:<20} notes={total:<6} exactly right={exact:<6} "
                  f"({100.0 * exact / max(1, total):5.1f}%)  "
                  f"deltas={dict(sorted(deltas.items()))}"
                  + (f"  [{mismatched_lengths} length mismatches]"
                     if mismatched_lengths else ""))
        browser.close()


if __name__ == "__main__":
    main()
