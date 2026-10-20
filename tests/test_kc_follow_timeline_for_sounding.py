"""Key Cycling: the Lead Sheet's follow timeline belongs to the key that is sounding.

The player command took the sounding key's prepared timeline and, without one
(a cold Next key, a refresh mid-cycle), fell back to the last rendered/audible
timeline whatever key it was in. The Lead Sheet then labelled the audible take
with the saved Practice Key's chords (or the previous cycle key's).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import backing_key_cycle as kc


def _tl(*chords: str) -> list[dict]:
    return [
        {"chord": c, "start_time": i * 2.0, "end_time": i * 2.0 + 2.0, "event_index": i}
        for i, c in enumerate(chords)
    ]


def _sig(key: str) -> tuple:
    return ("Perfect", key, "Intermediate", "Pop", 95, "4/4", 1)


class FollowTimelineForSoundingTests(unittest.TestCase):
    def chords(self, tl: list[dict]) -> list[str]:
        return [e["chord"] for e in tl]

    def test_prepared_timeline_for_the_sounding_key_wins(self) -> None:
        s = {
            kc.BACKING_KEY_CYCLE_PREPARED_KEY: {"A": {"timeline": _tl("A", "E/G#", "F#m7")}},
            "_last_backing_timeline": _tl("G", "D/F#", "Em7"),
            "_last_backing_timeline_signature": _sig("G"),
        }
        self.assertEqual(self.chords(kc.follow_timeline_for_sounding(s, "A")), ["A", "E/G#", "F#m7"])

    def test_saved_key_timeline_is_moved_into_the_cycling_key(self) -> None:
        # Cold Next key: A sounds, only the saved-key (G) render exists.
        s = {"_last_backing_timeline": _tl("G", "D/F#", "Em7", "C"), "_last_backing_timeline_signature": _sig("G")}
        tl = kc.follow_timeline_for_sounding(s, "A")
        self.assertEqual(self.chords(tl), ["A", "E/G#", "F#m7", "D"])
        self.assertEqual([(e["start_time"], e["end_time"]) for e in tl],
                         [(e["start_time"], e["end_time"]) for e in s["_last_backing_timeline"]])

    def test_previous_cycle_key_timeline_is_moved_into_the_restored_key(self) -> None:
        # Refresh mid-cycle: G sounds again, the last audible timeline is A's.
        s = {"_kc_audible_follow_timeline": _tl("A", "E/G#", "F#m7"), "_kc_audible_follow_timeline_signature": _sig("A")}
        self.assertEqual(self.chords(kc.follow_timeline_for_sounding(s, "G")), ["G", "D/F#", "Em7"])

    def test_same_key_is_used_as_is(self) -> None:
        s = {"_last_backing_timeline": _tl("Em", "B7"), "_last_backing_timeline_signature": _sig("Em")}
        self.assertEqual(self.chords(kc.follow_timeline_for_sounding(s, "Em")), ["Em", "B7"])

    def test_minor_keys_move_too(self) -> None:
        s = {"_last_backing_timeline": _tl("Em", "B7", "Am"), "_last_backing_timeline_signature": _sig("Em")}
        self.assertEqual(self.chords(kc.follow_timeline_for_sounding(s, "F#m")), ["F#m", "C#7", "Bm"])

    def test_a_timeline_of_unknown_key_is_never_handed_over(self) -> None:
        s = {"_last_backing_timeline": _tl("G", "D"), "_last_backing_timeline_signature": None, "_last_backing_signature": _sig("A"),
             "backing_lead_sheet_open": True, "_kc_follow_timeline": _tl("G", "D")}
        self.assertEqual(kc.follow_timeline_for_sounding(s, "A"), [])

    def test_a_promoted_take_does_not_relabel_the_last_timeline(self) -> None:
        # promote_prepared_cycle_audio moves _last_backing_signature to G; the
        # last timeline is still the A render's. It must be read as A, not G.
        s = {"_last_backing_timeline": _tl("A", "E/G#", "F#m7"),
             "_last_backing_timeline_signature": _sig("A"), "_last_backing_signature": _sig("G")}
        self.assertEqual(self.chords(kc.follow_timeline_for_sounding(s, "G")), ["G", "D/F#", "Em7"])

    def test_prepared_store_never_files_another_keys_timeline(self) -> None:
        s = {"_last_backing_timeline": _tl("A", "E/G#", "F#m7"),
             "_last_backing_timeline_signature": _sig("A"), "_last_backing_signature": _sig("G")}
        kc.store_prepared_cycle_audio(s, sounding_key="G", signature=_sig("G"))
        stored = ((s.get(kc.BACKING_KEY_CYCLE_PREPARED_KEY) or {}).get("G") or {}).get("timeline") or []
        self.assertNotEqual([e.get("chord") for e in stored][:3], ["A", "E/G#", "F#m7"])

    def test_generate_records_each_timelines_own_signature(self) -> None:
        s: dict = {}
        kc.stash_audible_arrangement_after_generate(s, timeline=_tl("Bb", "F/A"), signature=_sig("Bb"))
        self.assertEqual(s["_last_backing_timeline_signature"], _sig("Bb"))
        self.assertEqual(s["_kc_audible_follow_timeline_signature"], _sig("Bb"))

    def test_player_command_uses_the_sounding_key_authority(self) -> None:
        src = Path(kc.__file__).read_text(encoding="utf-8")
        self.assertIn("current_follow_tl = follow_timeline_for_sounding(session, sounding", src)


class NextChordAtCycleBoundaryContractTests(unittest.TestCase):
    """On the last chord of a pass, Next Chord is the upcoming cycle key's first chord."""

    def test_sheet_takes_next_from_the_upcoming_key_at_the_wrap(self) -> None:
        app = (Path(kc.__file__).resolve().parent / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        block = app[app.index("const nextIdx = (Number(event.event_index) + 1)"):]
        block = block[: block.index("const displayChord")]
        self.assertIn("nextIdx === 0", block)
        self.assertIn("cycleOwnsAudio()", block)
        self.assertIn("upcomingCycleStart()", block)
        self.assertIn("nextProjection", block)
        fn = app[app.index("function upcomingCycleStart()"):]
        fn = fn[: fn.index("function followClockAudio()")]
        self.assertIn("nextSounding", fn)
        self.assertIn("__kcTimelineByKey", fn)
        self.assertIn("nextDisplayProjection", fn)
        # Only a next key the latest command still names (not on the final key).
        self.assertIn("cmdNext !== key", fn)

    def test_label_projection_accepts_the_next_keys_projection(self) -> None:
        src = Path(kc.__file__).read_text(encoding="utf-8")
        self.assertRegex(src, re.escape("__kcProjectChordLabel = function projectChordLabel(chord, eventSpace, projection)"))


if __name__ == "__main__":
    unittest.main()


class OffRetiresCycleTimelinesContractTests(unittest.TestCase):
    """KCLEAD6: after Off the sheet followed __kcFollowTimeline while
    __kcLastSounding stayed set, labelling saved-key audio with the last cycle key."""

    def test_off_teardown_clears_the_cycle_timelines(self) -> None:
        src = Path(kc.__file__).read_text(encoding="utf-8")
        fn = src[src.index("function retireAllKcElements()"):]
        fn = fn[: fn.index("function kcUrlIsLive")]
        for clear in ("__kcLastSounding = ''", "__kcFollowTimeline = []", "__kcTimelineByKey = {{}}"):
            self.assertIn(clear, fn)
