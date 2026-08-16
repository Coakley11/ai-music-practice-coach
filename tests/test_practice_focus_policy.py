"""Practice Focus policy, context, snapshot, and instrument compatibility."""

from __future__ import annotations

import copy
import unittest

from practice_focus_context import resolve_practice_focus_context
from practice_focus_policy import (
    CATEGORY_HARMONY,
    CATEGORY_MELODY,
    CATEGORY_RHYTHM_GROOVE,
    CATEGORY_TONE,
    category_for_focus,
    coarse_log_focus_area,
    focus_is_compatible,
    format_focus_prompt_block,
    profiles_differ_meaningfully,
    resolve_compatible_focus,
    resolve_focus_profile,
)
from practice_focus_snapshot import (
    capture_practice_focus_snapshot,
    historical_focus_prompt_block,
    read_practice_focus_snapshot,
    snapshot_from_historical_fields,
    stamp_analysis_result_with_focus,
)
from practice_setup_controls import FOCUS_OPTIONS_BY_INSTRUMENT, focus_options_for_instrument
from practice_setup_globals import set_active_focus, set_active_instrument, valid_focus_for


class TestFocusOptionDefaults(unittest.TestCase):
    def test_instrument_defaults_unchanged(self) -> None:
        self.assertEqual(FOCUS_OPTIONS_BY_INSTRUMENT["Guitar"][0], "Strumming")
        self.assertEqual(FOCUS_OPTIONS_BY_INSTRUMENT["Saxophone"][0], "Tone")
        self.assertEqual(focus_options_for_instrument("Guitar")[0], "Strumming")
        self.assertEqual(focus_options_for_instrument("Saxophone")[0], "Tone")
        self.assertEqual(focus_options_for_instrument("Piano")[0], "Voicings")

    def test_shared_coaching_focuses_appended(self) -> None:
        guitar = focus_options_for_instrument("Guitar")
        sax = focus_options_for_instrument("Saxophone")
        for label in ("Timing", "Melody", "Harmony", "Improvisation", "Technique", "Phrasing"):
            self.assertIn(label, guitar)
            self.assertIn(label, sax)
        self.assertIn("Strumming", guitar)
        self.assertNotIn("Strumming", sax)


class TestFocusProfiles(unittest.TestCase):
    def test_guitar_strumming_is_rhythm_groove(self) -> None:
        profile = resolve_focus_profile("Guitar", "Strumming")
        self.assertEqual(profile.category, CATEGORY_RHYTHM_GROOVE)
        blob = " ".join(profile.coaching_priorities + profile.practice_suggestions).lower()
        self.assertIn("strum", blob)
        self.assertIn("timing_groove", profile.preferred_metric_ids)
        self.assertTrue(any("chord" in s.lower() and "strum" in s.lower() for s in profile.practice_suggestions))

    def test_sax_tone_is_air_and_embouchure(self) -> None:
        profile = resolve_focus_profile("Saxophone", "Tone")
        self.assertEqual(profile.category, CATEGORY_TONE)
        blob = " ".join(profile.coaching_priorities + profile.practice_suggestions).lower()
        self.assertTrue("air" in blob or "embouchure" in blob)
        self.assertIn("instrument_tone", profile.preferred_metric_ids)

    def test_guitar_tone_differs_from_sax_tone(self) -> None:
        guitar = resolve_focus_profile("Guitar", "Tone")
        sax = resolve_focus_profile("Saxophone", "Tone")
        self.assertEqual(guitar.category, sax.category)
        guitar_blob = " ".join(guitar.coaching_priorities).lower()
        sax_blob = " ".join(sax.coaching_priorities).lower()
        self.assertTrue("pick" in guitar_blob or "muting" in guitar_blob or "attack" in guitar_blob)
        self.assertTrue("embouchure" in sax_blob or "air" in sax_blob)
        self.assertNotEqual(guitar.coaching_priorities[:2], sax.coaching_priorities[:2])

    def test_harmony_vs_melody_differ(self) -> None:
        harmony = resolve_focus_profile("Guitar", "Harmony")
        melody = resolve_focus_profile("Guitar", "Melody")
        self.assertEqual(harmony.category, CATEGORY_HARMONY)
        self.assertEqual(melody.category, CATEGORY_MELODY)
        self.assertTrue(profiles_differ_meaningfully(harmony, melody))
        self.assertIn("chord_tone_targeting", harmony.preferred_metric_ids)
        self.assertIn("melodic_diversity_goal", melody.preferred_metric_ids)
        self.assertNotEqual(harmony.preferred_metric_ids, melody.preferred_metric_ids)

    def test_timing_is_cross_instrument_but_aware(self) -> None:
        guitar = resolve_focus_profile("Guitar", "Timing")
        sax = resolve_focus_profile("Saxophone", "Timing")
        self.assertEqual(guitar.category, sax.category)
        self.assertIn("timing_groove", guitar.preferred_metric_ids)
        self.assertIn("timing_groove", sax.preferred_metric_ids)
        self.assertTrue(any("subdivision" in s.lower() or "beat" in s.lower() for s in guitar.practice_suggestions))

    def test_ami_prompt_is_bias_not_prison(self) -> None:
        block = format_focus_prompt_block("Guitar", "Strumming", role="ami")
        self.assertIn("Strumming", block)
        self.assertIn("Guitar", block)
        low = block.lower()
        self.assertIn("not a prison", low)
        self.assertTrue("unrelated" in low or "factual" in low)


class TestInstrumentCompatibility(unittest.TestCase):
    def test_strumming_incompatible_with_saxophone(self) -> None:
        self.assertTrue(focus_is_compatible("Guitar", "Strumming"))
        self.assertFalse(focus_is_compatible("Saxophone", "Strumming"))

    def test_guitar_strumming_falls_back_to_sax_tone(self) -> None:
        self.assertEqual(valid_focus_for("Saxophone", "Strumming"), "Tone")
        self.assertEqual(resolve_compatible_focus("Saxophone", "Strumming"), "Tone")

    def test_set_instrument_clamps_strumming_to_tone(self) -> None:
        session: dict = {"instrument": "Guitar", "focus": "Strumming", "level": "Intermediate"}
        set_active_instrument(session, "Saxophone", source="test")
        self.assertEqual(session["instrument"], "Saxophone")
        self.assertEqual(session["focus"], "Tone")

    def test_compatible_focus_is_preserved(self) -> None:
        session: dict = {"instrument": "Guitar", "focus": "Timing", "level": "Intermediate"}
        set_active_instrument(session, "Saxophone", source="test")
        self.assertEqual(session["focus"], "Timing")


class TestPracticeFocusContext(unittest.TestCase):
    def test_context_is_coaching_only(self) -> None:
        session = {
            "instrument": "Guitar",
            "focus": "Strumming",
            "level": "Intermediate",
            "display_key": "G",
            "selected_song": {"title": "Shape of You"},
        }
        ctx = resolve_practice_focus_context(session)
        self.assertEqual(ctx.focus, "Strumming")
        self.assertEqual(ctx.instrument, "Guitar")
        self.assertEqual(ctx.category, CATEGORY_RHYTHM_GROOVE)
        payload = ctx.to_dict()
        self.assertNotIn("display_key", payload)
        self.assertNotIn("song", payload)
        self.assertNotIn("selected_song", payload)
        self.assertIn("ami_prompt_block", payload)
        self.assertIn("Strumming", ctx.ami_prompt_block)

    def test_visible_difference_when_only_focus_changes(self) -> None:
        session = {"instrument": "Guitar", "focus": "Strumming", "level": "Intermediate"}
        strum = resolve_practice_focus_context(session)
        set_active_focus(session, "Harmony", source="test")
        harmony = resolve_practice_focus_context(session)
        self.assertTrue(profiles_differ_meaningfully(strum.profile, harmony.profile))
        self.assertNotEqual(strum.ami_prompt_block, harmony.ami_prompt_block)
        self.assertNotEqual(
            strum.profile.practice_suggestions[:2],
            harmony.profile.practice_suggestions[:2],
        )


class TestHistoricalSnapshot(unittest.TestCase):
    def test_snapshot_does_not_follow_later_focus_change(self) -> None:
        session = {"instrument": "Saxophone", "focus": "Tone", "level": "Intermediate"}
        snap = capture_practice_focus_snapshot(session, captured_at="2026-08-11T12:00:00Z")
        self.assertEqual(snap["practice_focus"], "Tone")
        frozen = copy.deepcopy(snap)
        set_active_focus(session, "Articulation", source="test")
        self.assertEqual(session["focus"], "Articulation")
        self.assertEqual(frozen["practice_focus"], "Tone")
        self.assertEqual(read_practice_focus_snapshot(frozen)["practice_focus"], "Tone")

    def test_missing_historical_focus_is_not_invented(self) -> None:
        self.assertIsNone(snapshot_from_historical_fields(instrument="Saxophone", practice_focus=""))
        self.assertIsNone(read_practice_focus_snapshot({}))
        self.assertIsNone(read_practice_focus_snapshot({"instrument": "Guitar"}))

    def test_historical_prompt_distinguishes_current_focus(self) -> None:
        snap = snapshot_from_historical_fields(
            instrument="Saxophone",
            practice_focus="Tone",
            captured_at="2026-08-11",
        )
        block = historical_focus_prompt_block(snap, current_focus="Articulation")
        self.assertIn("Tone", block)
        self.assertIn("Articulation", block)

    def test_analysis_stamp_copies_focus(self) -> None:
        session = {"instrument": "Guitar", "focus": "Strumming", "level": "Beginner"}
        stamped = stamp_analysis_result_with_focus({"ok": True, "coach_summary": "x"}, session)
        self.assertEqual(stamped["practice_focus_at_analysis"], "Strumming")
        self.assertEqual(stamped["practice_focus_snapshot"]["practice_focus"], "Strumming")
        set_active_focus(session, "Melody", source="test")
        self.assertEqual(stamped["practice_focus_at_analysis"], "Strumming")

    def test_strumming_maps_to_timing_rhythm_log_area(self) -> None:
        self.assertEqual(coarse_log_focus_area("Strumming"), "timing/rhythm")
        self.assertEqual(coarse_log_focus_area("Tone"), "tone")
        self.assertIsNone(coarse_log_focus_area(""))
        self.assertEqual(category_for_focus("Breath Support"), CATEGORY_TONE)

    def test_log_prefill_snapshots_current_focus(self) -> None:
        from practice_log_state import build_practice_log_prefill

        ss = {"instrument": "Guitar", "focus": "Strumming", "level": "Beginner"}
        prefill = build_practice_log_prefill(ss)
        self.assertEqual(prefill.get("focus"), "Strumming")
        self.assertEqual(prefill.get("practice_focus"), "Strumming")
        self.assertEqual(prefill.get("focus_area"), "timing/rhythm")
        snap = prefill.get("practice_focus_snapshot") or {}
        self.assertEqual(snap.get("practice_focus"), "Strumming")

    def test_log_migrate_does_not_invent_missing_focus(self) -> None:
        from practice_log_state import migrate_practice_log_entry

        row = migrate_practice_log_entry(
            {"session_id": "hist-1", "notes": "old row", "instrument": "Saxophone"}
        )
        self.assertFalse(str(row.get("focus") or "").strip())
        self.assertNotIn("practice_focus_snapshot", row)

    def test_log_migrate_wraps_existing_focus_without_using_current_session(self) -> None:
        from practice_log_state import migrate_practice_log_entry

        row = migrate_practice_log_entry(
            {
                "session_id": "hist-2",
                "instrument": "Saxophone",
                "focus": "Tone",
                "notes": "long tones",
            }
        )
        self.assertEqual(row.get("focus"), "Tone")
        self.assertEqual((row.get("practice_focus_snapshot") or {}).get("practice_focus"), "Tone")



if __name__ == "__main__":
    unittest.main()
