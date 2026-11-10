"""Decode piano grand-staff ABC with real abcjs 6.4.4 and check it against the source MIDI.

Three invariants, each the answer to a question unit tests could not answer, because a unit
test reads the token this app wrote and abcjs reads the token the ABC standard defines:

1. **Octaves.** Every pitch abcjs sounds equals the MIDI the hand split chose - absolute
   pitch, not pitch class. This is what caught the octave being written one too high: the
   speller writes MIDI 60 as ``c`` and abcjs decodes ``c`` as 72.
2. **Key signatures.** Decoding happens under the tune's own ``K:`` field, so a note whose
   accidental disagrees with the key signature comes back as the wrong MIDI number. Run
   over sharp keys, flat keys and minors.
3. **Scale membership.** Over a single chord, every pitch class in either hand belongs to
   that chord's scale - the check that contrary motion is walking the scale rather than
   mirroring it in semitones.

Usage: python scripts/_proof_piano_grand_staff_abcjs.py [--shots OUT_DIR]

Needs network (jsDelivr) and Playwright Chromium, like the motif and rhythm proofs
beside it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ABCJS_URL = "https://cdn.jsdelivr.net/npm/abcjs@6.4.4/dist/abcjs-basic-min.js"  # same as the app

_PAGE = f"""<html><head><script src="{ABCJS_URL}"></script>
<style>body{{background:#fff;margin:0;padding:8px;font-family:sans-serif}}</style>
</head><body><div id="paper"></div></body></html>"""

# Sorted, because a grand staff's two voices arrive as two tracks and what is being proved
# is which pitches sound, not which order abcjs happens to list them in.
#
# ``chordsOff`` matters: left on, abcjs realises the chord symbols as its own accompaniment
# track - a bass note and a voicing it invented - and those are not notes this app wrote.
# Measured without it, every tune "failed" by exactly a G1/C2 plus a C E G B stack.
_DECODE_JS = """(abc) => {
  const vo = ABCJS.renderAbc("paper", abc)[0];
  const audio = vo.setUpAudio({chordsOff: true});
  const out = [];
  for (const tr of audio.tracks) for (const ev of tr) if (ev.cmd === "note") out.push(ev.pitch);
  out.sort((a, b) => a - b);
  return {pitches: out, warnings: vo.warnings || []};
}"""

KEYS = ["C", "G", "Bb", "Am", "F#", "Eb", "D", "F", "Dm", "Ab"]
LEVELS = ["Beginner", "Intermediate", "Advanced"]
MODES = ["scales", "arpeggios", "auto"]
# One focus per left-hand role plus two that name none, so every role is rendered.
FOCI = ["Improvisation", "Guide Tones", "Voice Leading", "Left-Hand Independence",
        "Inversions", "Comping", "Technique", "Tone"]

PROGRESSION = ["Am7", "D7", "Gmaj7", "Cmaj7"]


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


def adapter_cases() -> list[tuple[str, list[int], str]]:
    """``(label, midis, abc)`` straight through the adapter, with the MIDI known exactly."""
    from piano_grand_staff import grand_staff_abc, hands_for_scale, hands_for_voicing

    out: list[tuple[str, list[int], str]] = []
    for key in KEYS:
        for motion in ("parallel", "contrary", "separate"):
            line = [60, 62, 64, 65, 67, 69, 71, 72]
            pcs = [0, 2, 4, 5, 7, 9, 11]
            bars = [hands_for_scale(line, motion=motion, scale_pcs=pcs)]
            midis = sorted(m for voicing in bars[0] for m in voicing)
            out.append((
                f"adapter scale {key}/{motion}",
                midis,
                grand_staff_abc(bars, key=key, meter="4/4", bpm=100, title="t", chords=["C"]),
            ))
        for level in LEVELS:
            hands = hands_for_voicing([48, 55, 64, 67, 71], "Cmaj7", level=level)
            bars = [[hands]]
            midis = sorted(list(hands[0]) + list(hands[1]))
            out.append((
                f"adapter voicing {key}/{level}",
                midis,
                grand_staff_abc(bars, key=key, meter="4/4", bpm=100, title="t", chords=["Cmaj7"]),
            ))
    return out


def end_to_end_cases() -> list[tuple[str, str, str, str, str]]:
    """``(label, key, chord, abc, mode)`` for one chord at a time, so the scale is unambiguous."""
    from practice_notation import generate_practice_notation

    out = []
    for key, chord in (("Am", "Am6"), ("G", "Gmaj7"), ("Bb", "Bb7"), ("C", "C7b9"),
                       ("Eb", "Ebm7"), ("F#", "F#m7b5"), ("D", "D7"), ("F", "Fmaj7")):
        for level in LEVELS:
            for mode in MODES:
                for focus in FOCI:
                    res = generate_practice_notation(
                        song_title="P", artist="", display_key=key, original_key=key,
                        bpm=100, groove_style="Jazz swing", instrument="Piano",
                        focus=focus, section_focus=None, sections={"A": [chord]},
                        difficulty={"Beginner": "easy", "Intermediate": "medium",
                                    "Advanced": "advanced"}[level],
                        exercise_mode=mode,
                    )
                    out.append((f"{key}/{chord}/{level}/{mode}/{focus}", key, chord,
                                res.abc or "", mode))
    return out


def prove_octaves() -> int:
    cases = adapter_cases()
    decoded = decode_all([abc for _l, _m, abc in cases])
    bad = []
    for (label, want, _abc), got in zip(cases, decoded):
        if got["pitches"] != want or got["warnings"]:
            bad.append(f"{label}: want {want} got {got['pitches']} warn {got['warnings']}")
    print(f"1. octaves + key signatures: {len(cases)} tunes, {len(bad)} differ from source MIDI")
    for b in bad[:6]:
        print("   ", b)
    return len(bad)


def prove_scales_and_register() -> int:
    from notation_exercise_patterns import scale_pcs
    from piano_grand_staff import LEFT_HAND_CEILING, LEFT_HAND_FLOOR, PIANO_EXERCISE_REGISTERS

    cases = end_to_end_cases()
    decoded = decode_all([abc for _l, _k, _c, abc, _m in cases])
    off_scale, out_of_window = [], []
    hi = max(h for _l, h in PIANO_EXERCISE_REGISTERS.values())
    for (label, key, chord, _abc, mode), got in zip(cases, decoded):
        pitches = got["pitches"]
        if not pitches:
            off_scale.append(f"{label}: no notes decoded")
            continue
        if mode in ("scales", "arpeggios"):
            allowed = {p % 12 for p in scale_pcs(chord, key)}
            strays = sorted({p % 12 for p in pitches} - allowed)
            if strays:
                off_scale.append(f"{label}: pitch classes {strays} not in scale {sorted(allowed)}")
        if min(pitches) < LEFT_HAND_FLOOR - 12 or max(pitches) > hi:
            out_of_window.append(f"{label}: range {min(pitches)}-{max(pitches)}")
    print(f"2. scale membership: {len(cases)} tunes, {len(off_scale)} contain a note "
          f"outside the chord's scale")
    for b in off_scale[:6]:
        print("   ", b)
    print(f"3. readable register: {len(out_of_window)} tunes fall outside "
          f"{LEFT_HAND_FLOOR - 12}-{hi} (bass-staff floor to right-hand ceiling); "
          f"left hand ceiling {LEFT_HAND_CEILING}")
    for b in out_of_window[:6]:
        print("   ", b)
    return len(off_scale) + len(out_of_window)


def screenshots(out_dir: Path) -> None:
    from playwright.sync_api import sync_playwright

    from practice_notation import generate_practice_notation

    items = []
    for level, diff in (("Beginner", "easy"), ("Intermediate", "medium"), ("Advanced", "advanced")):
        for mode in MODES:
            for key in ("G", "Bb", "Am"):
                res = generate_practice_notation(
                    song_title="P", artist="", display_key=key, original_key=key, bpm=100,
                    groove_style="Jazz swing", instrument="Piano", focus="Improvisation",
                    section_focus=None, sections={"A": PROGRESSION}, difficulty=diff,
                    exercise_mode=mode,
                )
                items.append((f"{level}_{mode}_{key}", res.abc or ""))
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1000, "height": 420})
        page.set_content(_PAGE)
        page.wait_for_function("typeof ABCJS !== 'undefined'", timeout=30000)
        for name, abc in items:
            got = page.evaluate(_DECODE_JS, abc)
            page.evaluate("(abc) => ABCJS.renderAbc('paper', abc, {staffwidth: 940, scale: 1.2})", abc)
            page.locator("#paper").screenshot(path=str(out_dir / f"piano_{name}.png"))
            ps = got["pitches"]
            print(f"   shot {name}: {len(ps)} notes, range {min(ps)}-{max(ps)}")
        browser.close()


def main() -> None:
    failures = prove_octaves() + prove_scales_and_register()
    if "--shots" in sys.argv:
        screenshots(Path(sys.argv[sys.argv.index("--shots") + 1]))
    print("RESULT:", "PASS" if not failures else f"FAIL ({failures})")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
