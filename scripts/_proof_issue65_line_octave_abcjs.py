"""Issue 65: do the single-line wind and bass staves show the pitch the engine chose?

The comparison, per instrument, level and mode:

    exercise event MIDI  ->  emitted ABC  ->  abcjs-decoded MIDI

The first is what the exercise engine decided (written pitch, already transposed for the
instrument upstream). The last is what abcjs - the library that draws the staff - reads
those tokens as. If the two differ by a constant, the staff is drawn in the wrong octave.

The written range is then checked against a published *written* range per instrument, so
the question "is the printed exercise playable" is answered separately from "is it the
pitch the engine meant". Transposing instruments are reported in both written and
concert pitch rather than being lumped together.

Usage: python scripts/_proof_issue65_line_octave_abcjs.py

Needs network (jsDelivr) and Playwright Chromium, like the other _proof_*_abcjs scripts.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ABCJS_URL = "https://cdn.jsdelivr.net/npm/abcjs@6.4.4/dist/abcjs-basic-min.js"

_PAGE = f'<html><head><script src="{ABCJS_URL}"></script></head>' \
        '<body><div id="paper"></div></body></html>'

# chordsOff, or abcjs realises the chord symbols as its own accompaniment and those
# invented notes get counted as the app's.
_DECODE_JS = """(abc) => {
  const vo = ABCJS.renderAbc("paper", abc)[0];
  const audio = vo.setUpAudio({chordsOff: true});
  const out = [];
  for (const tr of audio.tracks) for (const ev of tr) if (ev.cmd === "note") out.push(ev.pitch);
  return {pitches: out, warnings: vo.warnings || []};
}"""

# Published *written* ranges - what the player reads, not what sounds. Conservative
# professional ranges; the point is to catch an octave error, not to adjudicate altissimo.
WRITTEN_RANGE = {
    "Flute": (60, 96),              # C4-C7, concert (non-transposing)
    "Alto Sax (Eb)": (58, 89),      # written Bb3-F6
    "Tenor Sax (Bb)": (58, 89),
    "Soprano Sax (Bb)": (58, 89),
    "Bari Sax (Eb)": (58, 89),
    "Bb Clarinet": (50, 91),        # written E3-G6
    "Bb Trumpet": (54, 89),         # written F#3-F6
    "Bass": (28, 67),               # E1-G4, sounds as written on bass clef (8vb convention aside)
    "Voice": (36, 84),
}

# (instrument passed to the Practice page, register_instrument for the specific horn)
CASES = [
    ("Flute", "", "Flute"),
    ("Saxophone", "Alto Sax (Eb)", "Alto Sax (Eb)"),
    ("Saxophone", "Tenor Sax (Bb)", "Tenor Sax (Bb)"),
    ("Saxophone", "Soprano Sax (Bb)", "Soprano Sax (Bb)"),
    ("Saxophone", "Bari Sax (Eb)", "Bari Sax (Eb)"),
    ("Clarinet", "Bb Clarinet", "Bb Clarinet"),
    ("Trumpet", "Bb Trumpet", "Bb Trumpet"),
    ("Bass", "", "Bass"),
    ("Voice", "", "Voice"),
]
LEVELS = [("Beginner", "easy"), ("Intermediate", "medium"), ("Advanced", "advanced")]
MODES = ["auto", "scales", "arpeggios"]
KEYS = ["C", "G", "Bb", "Am", "Eb"]
CHORDS = ["Am7", "D7", "Gmaj7", "Cmaj7"]


def semitone_step(name: str) -> int:
    try:
        from instrument_transposition import TRANSPOSING_SEMITONE_STEPS

        return int(TRANSPOSING_SEMITONE_STEPS.get(name, 0))
    except Exception:
        return 0


def engine_events(instrument, register_instrument, level, key, mode):
    """Exactly the events practice_notation._build_line_notation would render."""
    from chord_navigation_notation import build_connected_arpeggio_line

    try:
        from notation_exercise_patterns import build_exercise_events

        events, _plan = build_exercise_events(
            CHORDS, level=level, instrument=instrument, key_center=key,
            focus="Improvisation", mode=mode, register_instrument=register_instrument,
        )
    except Exception:
        events = []
    if not events:
        events = build_connected_arpeggio_line(
            CHORDS, level=level, instrument=register_instrument or instrument,
            focus="Improvisation", groove_style="Jazz swing",
        )
    return events


def build_abc(events, key):
    from chord_navigation_notation import arpeggio_events_to_melody_dicts
    from composition_melody_notation import build_abc_from_melody_events
    from practice_notation import NOTATION_METER

    return build_abc_from_melody_events(
        arpeggio_events_to_melody_dicts(events), key=key, meter=NOTATION_METER,
        bpm=100, title="t", chords=CHORDS, clef="treble",
    )


def main() -> None:
    from playwright.sync_api import sync_playwright

    jobs = []
    for instrument, reg, label in CASES:
        for level, _diff in LEVELS:
            for mode in MODES:
                for key in KEYS:
                    events = engine_events(instrument, reg, level, key, mode)
                    want = [int(e.midi) for e in events if not e.is_rest and e.midi]
                    if not want:
                        continue
                    jobs.append({
                        "label": label, "instrument": instrument, "level": level,
                        "mode": mode, "key": key, "want": want,
                        "abc": build_abc(events, key),
                    })

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(_PAGE)
        page.wait_for_function("typeof ABCJS !== 'undefined'", timeout=30000)
        decoded = page.evaluate(
            f"(abcs) => abcs.map({_DECODE_JS})", [j["abc"] for j in jobs])
        browser.close()

    per_instrument: dict[str, Counter] = {}
    length_mismatch = 0
    rows = []
    for job, got in zip(jobs, decoded):
        pitches = got["pitches"]
        want = job["want"]
        if len(pitches) != len(want):
            length_mismatch += 1
            continue
        deltas = Counter(g - w for g, w in zip(pitches, want))
        per_instrument.setdefault(job["label"], Counter()).update(deltas)
        rows.append({**{k: job[k] for k in ("label", "level", "mode", "key")},
                     "deltas": dict(deltas),
                     "want_range": [min(want), max(want)],
                     "drawn_range": [min(pitches), max(pitches)]})

    print(f"{len(jobs)} exercises decoded "
          f"({length_mismatch} skipped for a note-count mismatch)\n")
    print(f"{'instrument':<18}{'step':>5}  {'delta (semitones) -> count':<34}"
          f"{'written range drawn':<22}{'in written range?'}")
    for label, counts in per_instrument.items():
        drawn = [r for r in rows if r["label"] == label]
        lo = min(r["drawn_range"][0] for r in drawn)
        hi = max(r["drawn_range"][1] for r in drawn)
        wlo = min(r["want_range"][0] for r in drawn)
        whi = max(r["want_range"][1] for r in drawn)
        rlo, rhi = WRITTEN_RANGE.get(label, (0, 127))
        engine_ok = rlo <= wlo and whi <= rhi
        drawn_ok = rlo <= lo and hi <= rhi
        step = semitone_step(label)
        summary = ", ".join(f"{d:+d}->{n}" for d, n in sorted(counts.items()))
        print(f"{label:<18}{step:>+5}  {summary:<34}"
              f"{f'{lo}-{hi} (engine {wlo}-{whi})':<22}"
              f"drawn={'OK' if drawn_ok else 'OUT'} engine={'OK' if engine_ok else 'OUT'}")

    allc: Counter = Counter()
    for c in per_instrument.values():
        allc.update(c)
    print("\noverall delta histogram:", dict(sorted(allc.items())))
    out = Path(__file__).resolve().parent / "_issue65_octave_rows.json"
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print("per-case detail:", out)


if __name__ == "__main__":
    main()
