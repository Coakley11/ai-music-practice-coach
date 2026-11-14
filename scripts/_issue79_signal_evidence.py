"""Issue 79 evidence: the corrected analysis against synthesized signals with known properties.

Every row is a signal whose pitch and loudness behaviour is known exactly, so the measurement can
be checked against the truth rather than against itself. The same signals drive
``tests/test_issue79_tone_sustain.py``; this script prints them as a table for the report, and with
``--legacy`` prints what the pre-Issue-79 analysis said about the same audio.

Usage:  python scripts/_issue79_signal_evidence.py [--legacy]
"""

from __future__ import annotations

import io
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.tone_test_signals import signal_catalog  # noqa: E402

# The signals themselves live with the tests (tests/tone_test_signals.py), so the table printed
# here and the assertions in tests/test_issue79_tone_sustain.py describe the same audio. A report
# whose evidence came from a second, slightly different set of signals would prove nothing.


def main() -> int:
    use_legacy = "--legacy" in sys.argv
    from tuner_tone import analyze_tone_practice

    if use_legacy:
        from tuner_tone import _legacy_analyze_tone_practice as analyze
        print("== PRE-ISSUE-79 ANALYSIS (for the before column) ==")
    else:
        analyze = analyze_tone_practice
        print("== CORRECTED ANALYSIS ==")

    print(
        f"{'signal':<32}{'what it is':<44}{'pitch':>7}{'vol':>7}{'sust':>7}"
        f"{'detect':>8}{'tune':>9}{'oct':>5}  notes"
    )
    for name, (audio, target, what) in signal_catalog().items():
        r = analyze(audio, target_note=target)
        if r is None:
            print(f"{name:<32}{what:<44}{'-':>7}{'-':>7}{'-':>7}{'-':>8}{'-':>9}{'-':>5}  no result")
            continue
        status = getattr(r, "status", "measured")
        pitch = "n/a" if r.pitch_stability_score is None else f"{r.pitch_stability_score:.1f}"
        vol = "n/a" if r.volume_stability_score is None else f"{r.volume_stability_score:.1f}"
        # The legacy analysis had no separate tuning number: its mean_cents WAS the raw offset
        # from the target, octave included, which is the whole of defect 3. Show that, so the
        # before column says +1200c where the after column says -30c and "1 octave".
        offset = getattr(r, "tuning_offset_cents", None)
        if offset is None and status == "measured":
            # The legacy analysis had no separate tuning number: its mean_cents WAS the raw offset
            # from the target, octave included, which is the whole of defect 3.
            offset = getattr(r, "mean_cents", None)
        # An unmeasurable take has no tuning either: "+0c" would read as a measurement.
        tune = "n/a" if (offset is None or status != "measured") else f"{offset:+.0f}c"
        oct_off = getattr(r, "octave_offset_semitones", 0) // 12
        extra = []
        if status != "measured":
            extra.append(getattr(r, "reason", "") or "insufficient")
        else:
            extra.append(f"spread {getattr(r, 'pitch_spread_cents', 0):.1f}c")
            extra.append(f"fluct {getattr(r, 'volume_fluctuation_db', 0):.1f}dB")
            if getattr(r, "volume_trend_db", 0):
                extra.append(f"trend {r.volume_trend_db:+.1f}dB")
            if getattr(r, "vibrato_rate_hz", 0):
                extra.append(f"vibrato {r.vibrato_rate_hz:.1f}Hz/{r.vibrato_depth_cents:.0f}c")
            if getattr(r, "note_change_detected", False):
                extra.append(f"step {r.largest_step_cents:.0f}c")
        print(
            f"{name:<32}{what:<44}{pitch:>7}{vol:>7}{r.sustain_seconds:>6.1f}s"
            f"{(getattr(r, 'detected_note', '') or r.median_note):>8}{tune:>9}{oct_off:>5}  "
            + "; ".join(extra)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
