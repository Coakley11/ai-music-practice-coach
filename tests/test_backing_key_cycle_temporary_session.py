"""Backing Advanced Settings — temporary Key Cycle session (Practice Key immutable)."""

from __future__ import annotations

import copy
import unittest

from backing_key_cycle import (
    BACKING_KEY_CYCLE_SESSIONS_KEY,
    OWNER_CATALOG,
    OWNER_CUSTOM,
    OWNER_JAM_GENERATOR,
    OWNER_STYLE_JAM,
    STATUS_HELD,
    STATUS_RUNNING,
    advance_key_cycle_now,
    assert_practice_key_unchanged,
    cycle_concert_practice_key,
    default_spelling_prefs,
    effective_backing_playback_key,
    get_owner_cycle_session,
    is_cycle_active,
    note_backing_pass_finished,
    pause_key_cycle,
    resolve_cycle_owner,
    resume_key_cycle,
    start_key_cycle,
    stop_key_cycle,
    temporary_playback_key,
)
from music_theory import split_key_center


SHAPE_PICK = "Pop|Shape of You"


def _catalog_shape_session(**extra):
    session = {
        "studio_page": "backing",
        "active_catalog_pick_key": SHAPE_PICK,
        "display_key": "Bm",
        "concert_key": "Bm",
        "practice_key_by_source": {SHAPE_PICK: "Bm"},
        "_backing_explicit_handoff_source": "regular_song",
        "backing_key_cycle_step": "semitone",
        "backing_key_cycle_direction": "up",
    }
    session.update(extra)
    return session


class TestCycleTheorySpelling(unittest.TestCase):
    def test_semitone_up_preserves_minor_and_preferred_spelling(self) -> None:
        prefs = default_spelling_prefs()
        # Defaults prefer Db over C# → Cm +1 = Dbm
        self.assertEqual(cycle_concert_practice_key("Bm", semitones=1, spelling_prefs=prefs), "Cm")
        self.assertEqual(cycle_concert_practice_key("Cm", semitones=1, spelling_prefs=prefs), "Dbm")
        self.assertEqual(cycle_concert_practice_key("Dbm", semitones=1, spelling_prefs=prefs), "Dm")
        # Explicit C# preference matches musician example Bm→Cm→C#m→Dm
        prefs_cs = dict(prefs)
        prefs_cs["C#/Db"] = "C#"
        self.assertEqual(cycle_concert_practice_key("Cm", semitones=1, spelling_prefs=prefs_cs), "C#m")

    def test_whole_tone_and_down(self) -> None:
        prefs = default_spelling_prefs()
        self.assertEqual(cycle_concert_practice_key("Bm", semitones=2, spelling_prefs=prefs), "Dbm")
        prefs_cs = dict(prefs)
        prefs_cs["C#/Db"] = "C#"
        self.assertEqual(cycle_concert_practice_key("Bm", semitones=2, spelling_prefs=prefs_cs), "C#m")
        self.assertEqual(cycle_concert_practice_key("Bm", semitones=-1, spelling_prefs=prefs), "Bbm")


class TestShapeOfYouTemporaryCycle(unittest.TestCase):
    def test_saved_practice_key_unchanged_through_cycle(self) -> None:
        session = _catalog_shape_session()
        # Match Shape example spelling: C#m not Dbm
        session["backing_key_spelling_prefs"] = {
            **default_spelling_prefs(),
            "C#/Db": "C#",
        }
        start_key_cycle(session, start_key="Bm")
        self.assertTrue(is_cycle_active(session))
        self.assertEqual(temporary_playback_key(session), "Bm")
        self.assertTrue(assert_practice_key_unchanged(session, "Bm"))

        # Pass 1 complete → Cm
        self.assertTrue(note_backing_pass_finished(session, pass_signature="pass-1"))
        self.assertEqual(temporary_playback_key(session), "Cm")
        self.assertEqual(session["practice_key_by_source"][SHAPE_PICK], "Bm")
        self.assertEqual(effective_backing_playback_key(session, "Bm"), "Cm")

        # Pass 2 → C#m
        self.assertTrue(note_backing_pass_finished(session, pass_signature="pass-2"))
        self.assertEqual(temporary_playback_key(session), "C#m")

        # Pass 3 → Dm
        self.assertTrue(note_backing_pass_finished(session, pass_signature="pass-3"))
        self.assertEqual(temporary_playback_key(session), "Dm")
        self.assertEqual(session["practice_key_by_source"][SHAPE_PICK], "Bm")

        stop_key_cycle(session)
        self.assertFalse(is_cycle_active(session))
        self.assertEqual(effective_backing_playback_key(session, "Bm"), "Bm")
        self.assertEqual(session["practice_key_by_source"][SHAPE_PICK], "Bm")

    def test_late_audio_end_after_stop_does_not_advance(self) -> None:
        from backing_key_cycle import BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY

        session = _catalog_shape_session()
        session["backing_key_spelling_prefs"] = {
            **default_spelling_prefs(),
            "C#/Db": "C#",
        }
        start_key_cycle(session, start_key="Bm")
        self.assertTrue(note_backing_pass_finished(session, pass_signature="p1"))
        self.assertEqual(temporary_playback_key(session), "Cm")
        self.assertTrue(session.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))
        stop_key_cycle(session)
        self.assertFalse(session.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))
        session["_last_backing_signature"] = ("late", "Bm", 1)
        self.assertFalse(note_backing_pass_finished(session, pass_signature="audio_ended::late"))
        self.assertFalse(is_cycle_active(session))
        self.assertEqual(session["practice_key_by_source"][SHAPE_PICK], "Bm")
        self.assertEqual(effective_backing_playback_key(session, "Bm"), "Bm")

    def test_pass_finished_sets_continue_play_flag(self) -> None:
        from backing_key_cycle import (
            BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY,
            consume_cycle_continue_play,
        )

        session = _catalog_shape_session()
        start_key_cycle(session, start_key="Bm")
        self.assertFalse(consume_cycle_continue_play(session))
        self.assertTrue(note_backing_pass_finished(session, pass_signature="cont-1"))
        self.assertTrue(session.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))
        self.assertTrue(consume_cycle_continue_play(session))
        self.assertFalse(session.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))
        # One-shot
        self.assertFalse(consume_cycle_continue_play(session))

    def test_duplicate_pass_signature_and_wav_sig_do_not_double_advance(self) -> None:
        session = _catalog_shape_session()
        start_key_cycle(session, start_key="Bm")
        session["_last_backing_signature"] = ("sig", "Bm", 1)
        self.assertTrue(note_backing_pass_finished(session, pass_signature="audio_ended::tok"))
        self.assertEqual(temporary_playback_key(session), "Cm")
        # Same pass signature
        self.assertFalse(note_backing_pass_finished(session, pass_signature="audio_ended::tok"))
        # Same wav signature even with new pass signature string
        session["_last_backing_signature"] = ("sig", "Bm", 1)
        self.assertFalse(note_backing_pass_finished(session, pass_signature="audio_ended::other"))
        self.assertEqual(temporary_playback_key(session), "Cm")

        session = _catalog_shape_session()
        start_key_cycle(session, start_key="Bm")
        note_backing_pass_finished(session, pass_signature="pass-1")
        self.assertEqual(temporary_playback_key(session), "Cm")
        # Simulated Streamlit rerun: re-read session without calling pass finished.
        snap = copy.deepcopy(session)
        self.assertEqual(temporary_playback_key(snap), "Cm")
        self.assertEqual(get_owner_cycle_session(snap, OWNER_CATALOG)["passes_completed"], 1)
        # Duplicate signature must not advance again.
        self.assertFalse(note_backing_pass_finished(session, pass_signature="pass-1"))
        self.assertEqual(temporary_playback_key(session), "Cm")

    def test_pause_hold_and_resume(self) -> None:
        session = _catalog_shape_session()
        session["backing_key_spelling_prefs"] = {
            **default_spelling_prefs(),
            "C#/Db": "C#",
        }
        start_key_cycle(session, start_key="Bm")
        note_backing_pass_finished(session, pass_signature="p1")
        self.assertEqual(temporary_playback_key(session), "Cm")
        pause_key_cycle(session)
        self.assertEqual(get_owner_cycle_session(session)["status"], STATUS_HELD)
        self.assertFalse(note_backing_pass_finished(session, pass_signature="p2-held"))
        self.assertEqual(temporary_playback_key(session), "Cm")
        resume_key_cycle(session)
        self.assertEqual(get_owner_cycle_session(session)["status"], STATUS_RUNNING)
        self.assertTrue(note_backing_pass_finished(session, pass_signature="p2"))
        self.assertEqual(temporary_playback_key(session), "C#m")

    def test_manual_advance_from_hold(self) -> None:
        session = _catalog_shape_session()
        start_key_cycle(session, start_key="Bm")
        pause_key_cycle(session)
        advance_key_cycle_now(session)
        self.assertEqual(temporary_playback_key(session), "Cm")
        self.assertEqual(get_owner_cycle_session(session)["status"], STATUS_RUNNING)


class TestOwnerIsolation(unittest.TestCase):
    def test_custom_cycle_does_not_touch_catalog(self) -> None:
        catalog = _catalog_shape_session()
        start_key_cycle(catalog, start_key="Bm")
        note_backing_pass_finished(catalog, pass_signature="c1")
        self.assertEqual(temporary_playback_key(catalog), "Cm")

        custom = {
            "studio_page": "backing",
            "_backing_explicit_handoff_source": "custom_progression",
            "display_key": "G",
            "concert_key": "G",
            "backing_key_cycle_step": "semitone",
            "backing_key_cycle_direction": "up",
            BACKING_KEY_CYCLE_SESSIONS_KEY: copy.deepcopy(
                catalog.get(BACKING_KEY_CYCLE_SESSIONS_KEY) or {}
            ),
        }
        self.assertEqual(resolve_cycle_owner(custom), OWNER_CUSTOM)
        start_key_cycle(custom, start_key="G")
        self.assertEqual(temporary_playback_key(custom), "G")
        # Catalog bag still at Cm temporary; Custom at G.
        cat_bag = get_owner_cycle_session(custom, OWNER_CATALOG)
        self.assertEqual(str(cat_bag.get("current_playback_key") or ""), "Cm")
        self.assertEqual(temporary_playback_key(custom, OWNER_CUSTOM), "G")
        note_backing_pass_finished(custom, pass_signature="cu1")
        self.assertEqual(temporary_playback_key(custom), "Ab")
        # Catalog bag unchanged by Custom advance.
        self.assertEqual(
            str(get_owner_cycle_session(custom, OWNER_CATALOG).get("current_playback_key") or ""),
            "Cm",
        )

    def test_style_jam_isolated_from_jam_generator(self) -> None:
        session = {
            "studio_page": "backing",
            "_backing_explicit_handoff_source": "entry_jam",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style_key": "F",
            "display_key": "F",
            "concert_key": "F",
            "backing_key_cycle_step": "semitone",
            "backing_key_cycle_direction": "up",
        }
        self.assertEqual(resolve_cycle_owner(session), OWNER_STYLE_JAM)
        start_key_cycle(session, start_key="F")
        note_backing_pass_finished(session, pass_signature="sj1")
        self.assertEqual(temporary_playback_key(session), "F#")

        jam = {
            "studio_page": "backing",
            "_backing_explicit_handoff_source": "entry_jam",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "C",
            "display_key": "C",
            "concert_key": "C",
            "backing_key_cycle_step": "whole",
            "backing_key_cycle_direction": "up",
            BACKING_KEY_CYCLE_SESSIONS_KEY: copy.deepcopy(
                session.get(BACKING_KEY_CYCLE_SESSIONS_KEY) or {}
            ),
        }
        self.assertEqual(resolve_cycle_owner(jam), OWNER_JAM_GENERATOR)
        start_key_cycle(jam, start_key="C")
        self.assertEqual(temporary_playback_key(jam), "C")
        self.assertEqual(
            str(get_owner_cycle_session(jam, OWNER_STYLE_JAM).get("current_playback_key") or ""),
            "F#",
        )


class TestProjectionsFollowTemporaryKey(unittest.TestCase):
    def test_written_and_shape_use_sounding_key(self) -> None:
        from guitar_capo import shape_chart_key_for_concert
        from instrument_transposition import written_key_for_instrument

        session = _catalog_shape_session()
        session["backing_key_spelling_prefs"] = {
            **default_spelling_prefs(),
            "C#/Db": "C#",
        }
        session["show_chart_in_instrument_key"] = True
        session["instrument"] = "Clarinet"
        start_key_cycle(session, start_key="Bm")
        note_backing_pass_finished(session, pass_signature="proj1")
        sound = temporary_playback_key(session)
        self.assertEqual(sound, "Cm")
        written = written_key_for_instrument(sound, "Clarinet", session)
        self.assertTrue(str(written or "").startswith("D"))  # concert C → written D for Bb
        shape = shape_chart_key_for_concert(sound, "G")
        self.assertEqual(shape, "Gm")
        self.assertEqual(session["practice_key_by_source"][SHAPE_PICK], "Bm")

    def test_progression_audio_follows_temporary_not_practice(self) -> None:
        session = _catalog_shape_session()
        session["backing_key_spelling_prefs"] = {
            **default_spelling_prefs(),
            "C#/Db": "C#",
        }
        start_key_cycle(session, start_key="Bm")
        note_backing_pass_finished(session, pass_signature="m1")
        self.assertEqual(temporary_playback_key(session), "Cm")
        self.assertEqual(effective_backing_playback_key(session, "Bm"), "Cm")
        self.assertEqual(session["practice_key_by_source"][SHAPE_PICK], "Bm")
        # Overlay must not rewrite Practice Key storage.
        self.assertTrue(assert_practice_key_unchanged(session, "Bm"))


if __name__ == "__main__":
    unittest.main()
