"""Which note is the +11 one, and what did the ABC say about it?"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _proof_issue65_line_octave_abcjs import (  # noqa: E402
    CHORDS, _DECODE_JS, _PAGE, build_abc, engine_events,
)


def main() -> None:
    from playwright.sync_api import sync_playwright

    cases = [
        ("Saxophone", "Alto Sax (Eb)", "Intermediate", "C", "scales"),
        ("Trumpet", "Bb Trumpet", "Beginner", "Bb", "auto"),
        ("Clarinet", "Bb Clarinet", "Advanced", "Eb", "arpeggios"),
    ]
    jobs = []
    for instrument, reg, level, key, mode in cases:
        events = engine_events(instrument, reg, level, key, mode)
        jobs.append({
            "name": f"{reg or instrument} {level} {key} {mode}",
            "events": events, "key": key, "abc": build_abc(events, key),
        })

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(_PAGE)
        page.wait_for_function("typeof ABCJS !== 'undefined'", timeout=30000)
        decoded = page.evaluate(f"(a) => a.map({_DECODE_JS})", [j["abc"] for j in jobs])
        browser.close()

    for job, got in zip(jobs, decoded):
        sounding = [e for e in job["events"] if not e.is_rest and e.midi]
        print(f"\n=== {job['name']} ===")
        print("K field:", [ln for ln in job["abc"].splitlines() if ln.startswith("K:")])
        body = [ln for ln in job["abc"].splitlines()
                if ln and not ln[1:2] == ":" and not ln.startswith("%")]
        print("ABC body:", " ".join(body)[:220])
        for i, (ev, pitch) in enumerate(zip(sounding, got["pitches"])):
            delta = pitch - int(ev.midi)
            if delta != 12:
                print(f"   note {i:2d}: engine {ev.pitch}={ev.midi} -> abcjs {pitch} "
                       f"(delta {delta:+d})  <-- NOT a clean octave")
        bad = sum(1 for ev, p in zip(sounding, got["pitches"]) if p - int(ev.midi) != 12)
        print(f"   {bad} of {len(sounding)} notes are not a clean +12")


if __name__ == "__main__":
    main()
