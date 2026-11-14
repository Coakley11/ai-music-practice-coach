"""Issue 79: a Tone History saved by the old scoring must survive this change untouched.

The scoring definitions changed, so three things have to be true of rows that were already there:

* nothing is rewritten - every stored field comes back byte-identical;
* nothing is recalculated - the old numbers are what the musician saw, and reinterpreting them
  under a new formula would change their practice history without telling them;
* they are LABELLED, so an old 62% is not silently compared with a new 62%.

This builds a catalog in the pre-Issue-79 shape, runs it through the code paths that read it, and
prints what changed. Run from the Issue 79 worktree:

    python scripts/_issue79_tone_history_preservation.py
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from media_state import compact_tone_take_for_ami  # noqa: E402
from media_tone_catalog import (  # noqa: E402
    migrate_tone_take,
    normalize_tone_takes,
    tone_take_quality,
    tone_take_row_summary,
    tone_take_scoring_is_legacy,
)

#: Rows exactly as the previous build wrote them: no scoring_version, no analysis_status, no
#: separated tuning or octave fields, and a tone_consistency_score averaged from the two scores.
LEGACY_ROWS = [
    {
        "tone_take_id": "legacy-1",
        "created_at": "2026-09-14T10:02:00+00:00",
        "updated_at": "2026-09-14T10:02:00+00:00",
        "instrument": "Flute",
        "instrument_family": "flute",
        "target_note": "A4",
        "detected_note": "A4",
        "median_note": "A4",
        "concert_note": "A4",
        "duration_seconds": 6.2,
        "mean_cents": -4.0,
        "average_cents": -4.0,
        "max_cents_drift": 18.0,
        "pitch_stability_score": 62.0,
        "pitch_stability": 62.0,
        "volume_stability_score": 71.0,
        "sustain_steadiness": 71.0,
        "sustain_seconds": 5.4,
        "tone_consistency_score": 66.5,
        "feedback": ["Moderate pitch movement - try a slower, steadier long tone."],
        "coach_summary": "Moderate pitch movement",
        "notes": "warm-up, before breakfast",
        "user_notes": "warm-up, before breakfast",
        "local_path": "media/tone/legacy-1.wav",
        "playback_status": "local_only",
        "mime_type": "audio/wav",
    },
    {
        # One with the old scoring's signature failure: a steady note that scored 0 because the
        # recording had silence around it. It must keep its 0 and its label, not be re-scored.
        "tone_take_id": "legacy-2",
        "created_at": "2026-10-02T18:40:00+00:00",
        "updated_at": "2026-10-02T18:40:00+00:00",
        "instrument": "Tenor Saxophone",
        "instrument_family": "saxophone",
        "transposing_type": "Tenor saxophone (Bb)",
        "target_note": "C4",
        "written_note": "C4",
        "concert_note": "A#3",
        "detected_note": "A#3",
        "duration_seconds": 8.0,
        "mean_cents": 11.0,
        "max_cents_drift": 25.0,
        "pitch_stability_score": 0.0,
        "volume_stability_score": 0.0,
        "sustain_seconds": 7.1,
        "tone_consistency_score": 0.0,
        "feedback": ["Pitch was unstable - shorten the note and reset breath support."],
        "notes": "long tones on the low end",
        "storage_ref": "supabase://media/u/daniel/recordings/legacy-2.wav",
        "playback_status": "cloud_only",
    },
]


def main() -> int:
    before = {r["tone_take_id"]: copy.deepcopy(r) for r in LEGACY_ROWS}
    rows_list = normalize_tone_takes(copy.deepcopy(LEGACY_ROWS))
    # normalize_tone_takes SORTS (newest first), so rows must be matched by id. Zipping the two
    # lists compared each row with the other one and reported thirteen "changes" that were simply
    # the two takes differing from each other.
    rows = {str(r.get("tone_take_id")): r for r in rows_list}
    print(f"rows in: {len(before)}  rows out: {len(rows)}")
    print(f"ids preserved: {sorted(before) == sorted(rows)}")
    failures = 0 if sorted(before) == sorted(rows) else 1

    for take_id, original in sorted(before.items()):
        row = rows.get(take_id, {})
        migrated = migrate_tone_take(row)
        print(f"\n--- {take_id} ---")
        lost = [k for k in original if k not in migrated]
        changed = {
            k: (original[k], migrated.get(k))
            for k in original
            if k in migrated and migrated.get(k) != original[k]
        }
        print(f"fields lost:    {lost or 'none'}")
        print(f"fields changed: {json.dumps(changed, default=str) if changed else 'none'}")
        if lost or changed:
            failures += 1
        print(f"legacy label:   {tone_take_scoring_is_legacy(migrated)}")
        print(f"quality:        {tone_take_quality(migrated)}")
        print(f"summary line:   {tone_take_row_summary(migrated)}")
        ami = compact_tone_take_for_ami(migrated)
        same = ami.get("pitch_stability_score") == original["pitch_stability_score"]
        print(f"AMI sees score: {ami.get('pitch_stability_score')} (unchanged: {same})")
        if not same:
            failures += 1
        if not tone_take_scoring_is_legacy(migrated):
            print("  !! a pre-Issue-79 row is NOT labelled legacy")
            failures += 1

    # And the audio pointers, notes and timestamps a musician would miss.
    for take_id, original in sorted(before.items()):
        row = rows.get(take_id, {})
        for key in ("local_path", "storage_ref", "notes", "user_notes", "created_at", "updated_at"):
            if key in original and row.get(key) != original[key]:
                print(f"  !! {take_id}: {key} changed ({original[key]!r} -> {row.get(key)!r})")
                failures += 1

    print(f"\n{'PRESERVED' if failures == 0 else 'CHANGED - ' + str(failures) + ' problem(s)'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
