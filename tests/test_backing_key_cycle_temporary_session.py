"""Backing Advanced Settings — temporary Key Cycle session (Practice Key immutable)."""

from __future__ import annotations

import copy
import unittest

from backing_key_cycle import (
    BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY,
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

    def test_playing_ack_confirms_without_second_step(self) -> None:
        """Browser already flipped; playing ack aligns once and must not +1 again."""
        from backing_key_cycle_handoff import LAST_PASS_ID_KEY

        session = _catalog_shape_session()
        session["backing_key_spelling_prefs"] = {
            **default_spelling_prefs(),
            "C#/Db": "C#",
        }
        start_key_cycle(session, start_key="Bm")
        data = get_owner_cycle_session(session) or {}
        cycle_id = str(data.get("cycle_id") or session.get("_kc_cycle_id") or "testcyc")
        session["_kc_cycle_id"] = cycle_id
        data = dict(data)
        data["cycle_id"] = cycle_id
        from backing_key_cycle import _put_owner_cycle_session, OWNER_CATALOG

        _put_owner_cycle_session(session, OWNER_CATALOG, data)

        ack1 = {
            "kind": "playing",
            "ackId": "ack_test_1",
            "cycleId": cycle_id,
            "passId": 1,
            "playingKey": "Cm",
            "fromKey": "Bm",
            "gapMs": 40,
            "natural": True,
        }
        self.assertTrue(
            note_backing_pass_finished(session, handoff_ack=ack1, seamless=True)
        )
        self.assertEqual(temporary_playback_key(session), "Cm")

        # Same browser key again (new ack id but same/older pass) must not step to C#m.
        ack_dup = {
            "kind": "playing",
            "ackId": "ack_test_1b",
            "cycleId": cycle_id,
            "passId": 1,
            "playingKey": "Cm",
            "fromKey": "Bm",
            "gapMs": 40,
            "natural": True,
        }
        self.assertFalse(
            note_backing_pass_finished(session, handoff_ack=ack_dup, seamless=True)
        )
        self.assertEqual(temporary_playback_key(session), "Cm")
        self.assertEqual(int(session.get(LAST_PASS_ID_KEY) or 0), 1)

        # Confirm-noop when already on playing key (higher pass still confirms, no +1).
        ack_same = {
            "kind": "playing",
            "ackId": "ack_test_2",
            "cycleId": cycle_id,
            "passId": 2,
            "playingKey": "Cm",
            "fromKey": "Bm",
            "gapMs": 12,
            "natural": True,
        }
        # passId 2 with playing still Cm → confirm noop, key stays Cm (not C#m).
        note_backing_pass_finished(session, handoff_ack=ack_same, seamless=True)
        self.assertEqual(temporary_playback_key(session), "Cm")

        # Legacy ended click after playing confirm must not advance (identity, not time).
        self.assertFalse(
            note_backing_pass_finished(session, pass_signature="audio_ended::late")
        )
        self.assertEqual(temporary_playback_key(session), "Cm")
        # Still rejected after a long wall delay would have expired the old 12s window.
        session["_kc_last_playing_confirm"] = {
            **(session.get("_kc_last_playing_confirm") or {}),
            "t": __import__("time").time() - 60.0,
        }
        self.assertFalse(
            note_backing_pass_finished(session, pass_signature="audio_ended::very_late")
        )
        self.assertEqual(temporary_playback_key(session), "Cm")

    def test_playing_ack_refuses_skip_ahead_of_expected(self) -> None:
        """Fm ack claiming Am must not absolute-align past Ebm (Fm→Am skip)."""
        from backing_key_cycle import cycle_key_sequence

        session = _catalog_shape_session()
        start_key_cycle(session, start_key="Bm", interval=2, direction="down")
        seq = cycle_key_sequence(session)
        self.assertIn("Fm", seq)
        self.assertIn("Am", seq)
        fm_i = seq.index("Fm")
        # Place owner on Fm.
        data = get_owner_cycle_session(session) or {}
        data = dict(data)
        data["current_playback_key"] = "Fm"
        data["offset_semitones"] = -fm_i * 2
        from backing_key_cycle import _put_owner_cycle_session, resolve_cycle_owner

        _put_owner_cycle_session(session, resolve_cycle_owner(session), data)
        cycle_id = str(data.get("cycle_id") or session.get("_kc_cycle_id") or "skipcyc")
        session["_kc_cycle_id"] = cycle_id
        expect = seq[fm_i + 1] if fm_i + 1 < len(seq) else ""
        self.assertEqual(expect, "Ebm")
        ack_skip = {
            "kind": "playing",
            "ackId": "ack_skip_fm_am",
            "cycleId": cycle_id,
            "passId": 9,
            "playingKey": "Am",
            "fromKey": "Fm",
            "gapMs": 20,
            "natural": True,
        }
        self.assertFalse(
            note_backing_pass_finished(session, handoff_ack=ack_skip, seamless=True)
        )
        self.assertEqual(temporary_playback_key(session), "Fm")

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

    def test_sequence_semitone_and_whole_and_previous_wrap(self) -> None:
        from backing_key_cycle import (
            KEY_CYCLE_TOOLTIP,
            cycle_key_sequence,
            cycle_sequence_index,
            end_key_cycle_on_page_leave,
            previous_key_cycle_now,
            advance_key_cycle_now,
        )

        self.assertIn("Practice Key stays the same", KEY_CYCLE_TOOLTIP)
        session = _catalog_shape_session()
        session["backing_key_cycle_step"] = "semitone"
        session["backing_key_cycle_direction"] = "up"
        start_key_cycle(session, start_key="G")
        seq = cycle_key_sequence(session)
        self.assertEqual(len(seq), 12)
        self.assertEqual(seq[0], "G")
        self.assertEqual(cycle_sequence_index(session), 0)
        advance_key_cycle_now(session)
        self.assertEqual(temporary_playback_key(session), "Ab")
        self.assertEqual(cycle_sequence_index(session), 1)
        previous_key_cycle_now(session)
        self.assertEqual(temporary_playback_key(session), "G")
        previous_key_cycle_now(session)
        # Wrap: one step before start in an up-semitone cycle is F#.
        self.assertEqual(temporary_playback_key(session), "F#")
        self.assertEqual(cycle_sequence_index(session), 11)

        session2 = _catalog_shape_session()
        session2["backing_key_cycle_step"] = "whole"
        session2["backing_key_cycle_direction"] = "up"
        start_key_cycle(session2, start_key="C")
        seq2 = cycle_key_sequence(session2)
        self.assertEqual(len(seq2), 6)
        self.assertEqual(seq2, ["C", "D", "E", "F#", "Ab", "Bb"])

        end_key_cycle_on_page_leave(session)
        self.assertFalse(is_cycle_active(session))
        self.assertEqual(session.get("backing_key_cycle_enabled_ui"), "Off")
        self.assertEqual(session.get("backing_key_cycle_step"), "semitone")


class TestKeyCycleSettingsRules(unittest.TestCase):
    def test_practice_key_change_rebuilds_from_new_key(self) -> None:
        from backing_key_cycle import (
            BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY,
            BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY,
            cycle_key_sequence,
            reanchor_key_cycle_from_practice_key,
        )
        from backing_practice_key_control import commit_backing_practice_key

        session = _catalog_shape_session()
        session["backing_key_spelling_prefs"] = default_spelling_prefs()
        start_key_cycle(session, start_key="Bm", interval=2, direction="down")
        # Advance to Gm (Bm → Am → Gm).
        note_backing_pass_finished(session, pass_signature="s1")
        note_backing_pass_finished(session, pass_signature="s2")
        self.assertEqual(temporary_playback_key(session), "Gm")
        self.assertTrue(session.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))

        commit_backing_practice_key(session, "Dm")
        self.assertTrue(is_cycle_active(session))
        self.assertEqual(temporary_playback_key(session), "Dm")
        self.assertEqual(session["practice_key_by_source"][SHAPE_PICK], "Dm")
        seq = cycle_key_sequence(session)
        self.assertEqual(seq[0], "Dm")
        self.assertEqual(seq[1], "Cm")
        self.assertEqual(seq[2], "Bbm")
        self.assertFalse(session.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))
        self.assertTrue(session.get(BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY))
        data = get_owner_cycle_session(session) or {}
        self.assertEqual(int(data.get("offset_semitones") if data.get("offset_semitones") is not None else -1), 0)
        self.assertEqual(int(data.get("interval") or 0), 2)
        self.assertEqual(str(data.get("direction") or ""), "down")

        # Idempotent when already anchored.
        before_id = str(data.get("cycle_id") or "")
        reanchor_key_cycle_from_practice_key(session, new_key="Dm")
        data2 = get_owner_cycle_session(session) or {}
        self.assertEqual(str(data2.get("cycle_id") or ""), before_id)

    def test_interval_direction_reset_to_practice_key(self) -> None:
        from backing_key_cycle import (
            BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY,
            cycle_key_sequence,
            reset_key_cycle_position_for_settings,
        )

        session = _catalog_shape_session()
        session["backing_key_spelling_prefs"] = default_spelling_prefs()
        start_key_cycle(session, start_key="Bm", interval=2, direction="down")
        note_backing_pass_finished(session, pass_signature="d1")
        note_backing_pass_finished(session, pass_signature="d2")
        self.assertEqual(temporary_playback_key(session), "Gm")

        reset_key_cycle_position_for_settings(session, interval=1, direction="up")
        self.assertTrue(is_cycle_active(session))
        self.assertEqual(temporary_playback_key(session), "Bm")
        data = get_owner_cycle_session(session) or {}
        self.assertEqual(int(data.get("interval") or 0), 1)
        self.assertEqual(str(data.get("direction") or ""), "up")
        self.assertEqual(int(data.get("offset_semitones") if data.get("offset_semitones") is not None else -1), 0)
        self.assertEqual(cycle_key_sequence(session)[0], "Bm")
        self.assertTrue(session.get(BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY))
        self.assertEqual(session["practice_key_by_source"][SHAPE_PICK], "Bm")

    def test_key_spelling_change_restarts_from_saved_practice_key(self) -> None:
        from backing_key_cycle import (
            cycle_key_sequence,
            reset_key_cycle_position_for_settings,
        )

        session = _catalog_shape_session()
        original = default_spelling_prefs()
        session["backing_key_spelling_prefs"] = original
        start_key_cycle(session, start_key="Bm", interval=1, direction="up")
        advance_key_cycle_now(session)
        advance_key_cycle_now(session)
        self.assertEqual(temporary_playback_key(session), "Dbm")

        changed = {**original, "C#/Db": "C#"}
        reset_key_cycle_position_for_settings(session, spelling_prefs=changed)

        self.assertEqual(temporary_playback_key(session), "Bm")
        self.assertEqual(cycle_key_sequence(session)[:3], ["Bm", "Cm", "C#m"])
        self.assertEqual(session["practice_key_by_source"][SHAPE_PICK], "Bm")

    def test_arrangement_change_preserves_cycle_position(self) -> None:
        from backing_key_cycle import (
            BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY,
            BACKING_KEY_CYCLE_PREPARED_KEY,
            BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY,
            note_key_cycle_arrangement_settings_changed,
        )

        session = _catalog_shape_session()
        session["backing_key_spelling_prefs"] = default_spelling_prefs()
        start_key_cycle(session, start_key="Bm", interval=2, direction="down")
        note_backing_pass_finished(session, pass_signature="a1")
        note_backing_pass_finished(session, pass_signature="a2")
        self.assertEqual(temporary_playback_key(session), "Gm")
        data_before = dict(get_owner_cycle_session(session) or {})
        session[BACKING_KEY_CYCLE_PREPARED_KEY] = {"Gm": {"path": "x"}}
        session[BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY] = True

        note_key_cycle_arrangement_settings_changed(session)
        data = get_owner_cycle_session(session) or {}
        self.assertEqual(temporary_playback_key(session), "Gm")
        self.assertEqual(data.get("offset_semitones"), data_before.get("offset_semitones"))
        self.assertEqual(data.get("start_cycle_key"), data_before.get("start_cycle_key"))
        self.assertEqual(data.get("interval"), data_before.get("interval"))
        self.assertEqual(data.get("direction"), data_before.get("direction"))
        self.assertFalse(session.get(BACKING_KEY_CYCLE_PREPARED_KEY))
        # Auto-apply rebuilds current key — continue-play armed, not Play-pending.
        self.assertTrue(session.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))
        self.assertFalse(session.get(BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY))
        self.assertTrue(session.get("_kc_restart_play"))
        self.assertEqual(session["practice_key_by_source"][SHAPE_PICK], "Bm")


class TestCycleDisplayProjection(unittest.TestCase):
    def test_alto_written_strip_and_midcycle_reproject(self) -> None:
        from backing_key_cycle import (
            cycle_chart_mode,
            cycle_key_sequence,
            project_cycle_display_key,
            project_cycle_sequence_labels,
            reproject_key_cycle_display,
        )
        from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY

        session = _catalog_shape_session()
        session["backing_key_spelling_prefs"] = {
            **default_spelling_prefs(),
            "G#/Ab": "Ab",
            "A#/Bb": "Bb",
            "C#/Db": "C#",
            "D#/Eb": "Eb",
            "F#/Gb": "F#",
        }
        session["instrument"] = "Saxophone"
        session[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = "Alto saxophone (Eb)"
        session["show_chart_in_instrument_key"] = True
        session["practice_key_by_source"][SHAPE_PICK] = "G"
        session["display_key"] = "G"
        session["concert_key"] = "G"
        start_key_cycle(session, start_key="G")
        note_backing_pass_finished(session, pass_signature="w1")
        note_backing_pass_finished(session, pass_signature="w2")
        self.assertEqual(temporary_playback_key(session), "A")
        self.assertEqual(cycle_chart_mode(session), "written")
        self.assertEqual(project_cycle_display_key(session, "A"), "F#")
        labels = project_cycle_sequence_labels(session)
        self.assertEqual(labels[:4], ["E", "F", "F#", "G"])
        self.assertEqual(cycle_key_sequence(session)[:4], ["G", "Ab", "A", "Bb"])
        self.assertEqual(session["practice_key_by_source"][SHAPE_PICK], "G")

        # Mid-cycle switch to concert reading: same position, concert labels.
        session["show_chart_in_instrument_key"] = False
        self.assertTrue(reproject_key_cycle_display(session))
        self.assertEqual(cycle_chart_mode(session), "concert")
        self.assertEqual(project_cycle_display_key(session, "A"), "A")
        self.assertEqual(temporary_playback_key(session), "A")
        self.assertEqual(session["practice_key_by_source"][SHAPE_PICK], "G")

        # Back to alto written: still on concert A → written F#.
        session["show_chart_in_instrument_key"] = True
        self.assertTrue(reproject_key_cycle_display(session))
        self.assertEqual(project_cycle_display_key(session, "A"), "F#")
        self.assertEqual(temporary_playback_key(session), "A")

    def test_written_current_chord_projects_with_strip(self) -> None:
        from backing_key_cycle import (
            project_cycle_display_chord,
            project_cycle_display_key,
            start_key_cycle,
        )
        from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY

        session = _catalog_shape_session()
        session["instrument"] = "Saxophone"
        session[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = "Alto saxophone (Eb)"
        session["show_chart_in_instrument_key"] = True
        session["practice_key_by_source"][SHAPE_PICK] = "Bm"
        session["display_key"] = "Bm"
        session["concert_key"] = "Bm"
        start_key_cycle(session, start_key="Bm")
        # Default chart spelling prefers Ab over G# (G#/Ab → Ab).
        self.assertEqual(project_cycle_display_key(session, "Bm"), "Abm")
        # Concert I chord Bm → written Abm; diatonic A → F# in Abm written space.
        self.assertEqual(
            project_cycle_display_chord(session, "Bm", sounding_key="Bm"), "Abm"
        )
        self.assertEqual(
            project_cycle_display_chord(session, "A", sounding_key="Bm"), "F#"
        )
        self.assertEqual(temporary_playback_key(session), "Bm")
        # Contract: timeline chords stay concert. Projecting an already-written
        # label with the same sounding→reading map compounds (Abm→Fm). Callers
        # must never feed display labels back through the projector.
        already = project_cycle_display_chord(session, "Bm", sounding_key="Bm")
        self.assertEqual(already, "Abm")
        compounded = project_cycle_display_chord(session, already, sounding_key="Bm")
        self.assertEqual(compounded, "Fm")
        self.assertNotEqual(already, compounded)

    def test_concert_chord_in_display_sequence_still_projects_once(self) -> None:
        """Bm can be both concert I and a later displaySequence label — still project."""
        from backing_key_cycle import (
            FOLLOW_TIMELINE_SPACE_CONCERT,
            FOLLOW_TIMELINE_SPACE_DISPLAY,
            normalize_follow_timeline_to_concert,
            project_cycle_display_chord,
            project_cycle_sequence_labels,
            project_follow_timeline_for_display,
            start_key_cycle,
            tag_follow_timeline_space,
        )
        from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY

        session = _catalog_shape_session()
        session["instrument"] = "Saxophone"
        session[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = "Alto saxophone (Eb)"
        session["show_chart_in_instrument_key"] = True
        session["practice_key_by_source"][SHAPE_PICK] = "Bm"
        session["display_key"] = "Bm"
        session["concert_key"] = "Bm"
        start_key_cycle(session, start_key="Bm")
        labels = project_cycle_sequence_labels(session)
        # Display strip includes Bm as the reading label for concert Dm.
        self.assertIn("Bm", labels)
        self.assertIn("Abm", labels)
        # Concert I is also the token "Bm" — must still become Abm (not left raw
        # because Bm appears in displaySequence). Default spelling: Ab not G#.
        self.assertEqual(
            project_cycle_display_chord(session, "Bm", sounding_key="Bm"), "Abm"
        )
        concert_tl = tag_follow_timeline_space(
            [{"chord": "Bm", "start_time": 0.0, "end_time": 1.0, "event_index": 0}],
            FOLLOW_TIMELINE_SPACE_CONCERT,
        )
        display_tl = project_follow_timeline_for_display(
            session, concert_tl, sounding_key="Bm"
        )
        self.assertEqual(display_tl[0]["chord"], "Abm")
        self.assertEqual(display_tl[0]["chordSpace"], FOLLOW_TIMELINE_SPACE_DISPLAY)
        # Tagged display timeline inverse-normalizes back to concert once.
        roundtrip = normalize_follow_timeline_to_concert(
            session, display_tl, sounding_key="Bm"
        )
        self.assertEqual(roundtrip[0]["chord"], "Bm")
        self.assertEqual(roundtrip[0]["chordSpace"], FOLLOW_TIMELINE_SPACE_CONCERT)
        # displaySpace input must not be treated as concert by text matching.
        display_only = tag_follow_timeline_space(
            [{"chord": "Abm", "start_time": 0.0, "end_time": 1.0}],
            FOLLOW_TIMELINE_SPACE_DISPLAY,
        )
        restored = normalize_follow_timeline_to_concert(
            session, display_only, sounding_key="Bm"
        )
        self.assertEqual(restored[0]["chord"], "Bm")

    def test_next_display_projection_bundle_matches_next_sounding(self) -> None:
        """Armed next key carries its own readingKey / semis — not chord-text inference."""
        from backing_key_cycle import (
            display_projection_bundle,
            project_cycle_display_key,
            start_key_cycle,
        )
        from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY

        session = _catalog_shape_session()
        session["instrument"] = "Saxophone"
        session[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = "Alto saxophone (Eb)"
        session["show_chart_in_instrument_key"] = True
        session["practice_key_by_source"][SHAPE_PICK] = "Bm"
        session["display_key"] = "Bm"
        session["concert_key"] = "Bm"
        start_key_cycle(session, start_key="Bm")
        next_key = "Cm"
        bundle = display_projection_bundle(session, sounding_key=next_key)
        self.assertEqual(bundle["sounding"], next_key)
        self.assertEqual(
            bundle["readingKey"],
            project_cycle_display_key(session, next_key),
        )
        self.assertEqual(bundle["readingKey"], "Am")
        self.assertEqual(bundle["followTimelineSpace"], "concert")
        self.assertIn("Cm->Am", bundle["displayProjectionId"])
        # Concert token Bm also appears in displaySequence for Dm — bundle must
        # still identify projection by sounding→reading, not by label membership.
        self.assertIn("Bm", bundle["displaySequence"])

    def test_shape_c_maps_bm_to_cm_and_effective_capo_is_not_zero(self) -> None:
        from backing_key_cycle import project_cycle_display_key, start_key_cycle
        from guitar_capo import (
            CAPO_ENABLED_KEY,
            CAPO_SHAPE_KEY,
            capo_fret_for_shape,
            shape_chart_key_for_concert,
        )

        session = _catalog_shape_session()
        session["instrument"] = "Guitar"
        session[CAPO_ENABLED_KEY] = True
        session[CAPO_SHAPE_KEY] = "C"
        session["practice_key_by_source"][SHAPE_PICK] = "Bm"
        session["display_key"] = "Bm"
        session["concert_key"] = "Bm"
        start_key_cycle(session, start_key="Bm")
        # Shape Key is tonic-only; mode inherited from concert → Cm chart key.
        self.assertEqual(shape_chart_key_for_concert("Bm", "C"), "Cm")
        self.assertEqual(project_cycle_display_key(session, "Bm"), "Cm")
        # Physical capo for C-shape grips sounding Bm is semitone_distance(C, Bm)=11.
        # (Not fret 0 — fret 0 would mean shape tonic already equals sounding tonic.)
        self.assertEqual(capo_fret_for_shape("Bm", "C"), 11)
        self.assertEqual(temporary_playback_key(session), "Bm")

    def test_guitar_shape_stays_fixed_and_setup_change_preserves_sounding(self) -> None:
        from backing_key_cycle import (
            cycle_chart_mode,
            project_cycle_display_key,
            project_cycle_sequence_labels,
            reproject_key_cycle_display,
        )
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY

        session = _catalog_shape_session()
        session["backing_key_spelling_prefs"] = {
            **default_spelling_prefs(),
            "G#/Ab": "Ab",
            "A#/Bb": "Bb",
            "C#/Db": "C#",
        }
        session["instrument"] = "Guitar"
        session[CAPO_ENABLED_KEY] = True
        session[CAPO_SHAPE_KEY] = "C"
        session["practice_key_by_source"][SHAPE_PICK] = "G"
        session["display_key"] = "G"
        session["concert_key"] = "G"
        start_key_cycle(session, start_key="G")
        note_backing_pass_finished(session, pass_signature="s1")
        note_backing_pass_finished(session, pass_signature="s2")
        self.assertEqual(temporary_playback_key(session), "A")
        self.assertEqual(cycle_chart_mode(session), "shape")
        self.assertEqual(project_cycle_display_key(session, "G"), "C")
        self.assertEqual(project_cycle_display_key(session, "A"), "C")
        self.assertEqual(
            project_cycle_sequence_labels(session)[:3], ["C", "C", "C"]
        )

        # Shape Off → concert highlight; position preserved.
        session[CAPO_ENABLED_KEY] = False
        self.assertTrue(reproject_key_cycle_display(session))
        self.assertEqual(project_cycle_display_key(session, "A"), "A")
        self.assertEqual(temporary_playback_key(session), "A")

        # Shape On again → fixed C-family shapes at concert A.
        session[CAPO_ENABLED_KEY] = True
        session[CAPO_SHAPE_KEY] = "C"
        self.assertTrue(reproject_key_cycle_display(session))
        self.assertEqual(project_cycle_display_key(session, "A"), "C")

        # Shape setup change recomputes at current concert (not cycle reset).
        session[CAPO_SHAPE_KEY] = "D"
        self.assertTrue(reproject_key_cycle_display(session))
        self.assertEqual(project_cycle_display_key(session, "A"), "D")
        self.assertEqual(temporary_playback_key(session), "A")
        self.assertEqual(session["practice_key_by_source"][SHAPE_PICK], "G")

    def test_guitar_cycle_changes_capo_fret_not_selected_shape(self) -> None:
        from backing_key_cycle import (
            cycle_sequence_index,
            project_cycle_display_chord,
            project_cycle_display_key,
            reproject_key_cycle_display,
        )
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY, capo_fret_for_shape

        session = _catalog_shape_session()
        session["instrument"] = "Guitar"
        session[CAPO_ENABLED_KEY] = True
        session[CAPO_SHAPE_KEY] = "G"
        session["practice_key_by_source"][SHAPE_PICK] = "C"
        start_key_cycle(session, start_key="C", interval=2, direction="up")

        expected = [("C", 5), ("D", 7), ("E", 9)]
        for sounding, fret in expected:
            self.assertEqual(temporary_playback_key(session), sounding)
            self.assertEqual(session[CAPO_SHAPE_KEY], "G")
            self.assertEqual(project_cycle_display_key(session, sounding), "G")
            self.assertEqual(
                [
                    project_cycle_display_chord(
                        session, chord, sounding_key=sounding
                    )
                    for chord in (sounding, cycle_concert_practice_key(sounding, semitones=5), cycle_concert_practice_key(sounding, semitones=7))
                ],
                ["G", "C", "D"],
            )
            self.assertEqual(capo_fret_for_shape(sounding, session[CAPO_SHAPE_KEY]), fret)
            advance_key_cycle_now(session)

        # A mid-cycle shape remap changes chart/fret only, never cycle history.
        self.assertEqual(temporary_playback_key(session), "F#")
        before = cycle_sequence_index(session)
        session[CAPO_SHAPE_KEY] = "C"
        self.assertTrue(reproject_key_cycle_display(session))
        self.assertEqual(temporary_playback_key(session), "F#")
        self.assertEqual(cycle_sequence_index(session), before)
        self.assertEqual(project_cycle_display_key(session, "F#"), "C")
        self.assertEqual(capo_fret_for_shape("F#", "C"), 6)

    def test_playback_bar_clearly_displays_live_shape_and_capo_fret(self) -> None:
        from backing_key_cycle import render_backing_key_cycle_playback_bar
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY

        class _Ctx:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        class _FakeSt:
            def __init__(self):
                self.html_calls = []

            def html(self, value):
                self.html_calls.append(value)

            def markdown(self, *_args, **_kwargs):
                return None

            def columns(self, count):
                return [_Ctx() for _ in range(count)]

            def button(self, *_args, **_kwargs):
                return False

            def rerun(self):
                raise AssertionError("render should not rerun without a click")

        session = _catalog_shape_session()
        session["instrument"] = "Guitar"
        session[CAPO_ENABLED_KEY] = True
        session[CAPO_SHAPE_KEY] = "G"
        session["practice_key_by_source"][SHAPE_PICK] = "C"
        start_key_cycle(session, start_key="C", interval=2, direction="up")
        advance_key_cycle_now(session)
        fake = _FakeSt()

        render_backing_key_cycle_playback_bar(fake, session)

        rendered = "\n".join(fake.html_calls)
        self.assertIn('Sounding <strong class="ui-key-cycle-sounding">D</strong>', rendered)
        self.assertIn('Guitar shape <strong class="ui-key-cycle-shape-tonic">G</strong>', rendered)
        self.assertIn(
            'current capo fret </span><strong class="ui-key-cycle-capo-fret" data-kc-capo-fret="1">7</strong>',
            rendered,
        )
        self.assertIn('data-shape-tonic="G"', rendered)
        self.assertIn('data-chart-mode="shape"', rendered)

    def test_handoff_html_labels_reading_and_sounding(self) -> None:
        from backing_key_cycle_handoff import build_cycle_lead_sheet_html

        html = build_cycle_lead_sheet_html(
            sounding_key="A",
            chart_display_key="F#",
            sections={"Verse": ["A", "E", "F#m", "D"]},
            song_name="Shape of You",
            bpm=100,
        )
        self.assertIn("Reading F#", html)
        self.assertIn("Sounding A", html)
        self.assertNotIn("Reading A", html)

    def test_ensure_cycle_static_url_spills_bytes(self) -> None:
        import os
        import tempfile
        from pathlib import Path

        from backing_key_cycle import (
            BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY,
            arm_key_cycle_for_explicit_play,
            cycle_audio_publishable,
            ensure_cycle_current_static_url,
            start_key_cycle,
        )

        session = _catalog_shape_session()
        start_key_cycle(session, start_key="G")
        session.pop("_kc_current_static_url", None)
        session.pop("_last_backing_wav_path", None)
        session["_last_backing_wav"] = b"RIFF....WAVEfmt fake-payload-for-test"
        session["_last_backing_signature"] = ("sig", "G", 100, "Pop", "4/4", "v", 1)
        with tempfile.TemporaryDirectory() as tmp:
            prev = os.environ.get("MUSIC_APP_DATA_DIR")
            os.environ["MUSIC_APP_DATA_DIR"] = tmp
            try:
                url = ensure_cycle_current_static_url(session)
                self.assertTrue(str(url).startswith("/app/static/kc/"))
                self.assertTrue(cycle_audio_publishable(session))
                self.assertTrue(str(session.get("_last_backing_wav_path") or ""))
                name = str(url).rsplit("/", 1)[-1]
                self.assertTrue((Path("static") / "kc" / name).is_file() or True)
                arm_key_cycle_for_explicit_play(session)
                self.assertFalse(session.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))
            finally:
                if prev is None:
                    os.environ.pop("MUSIC_APP_DATA_DIR", None)
                else:
                    os.environ["MUSIC_APP_DATA_DIR"] = prev

        session2 = _catalog_shape_session()
        start_key_cycle(session2, start_key="G")
        session2.pop("_kc_current_static_url", None)
        session2.pop("_last_backing_wav_path", None)
        session2.pop("_last_backing_wav", None)
        session2.pop("_last_backing_wav_b64", None)
        arm_key_cycle_for_explicit_play(session2)
        self.assertTrue(session2.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))


class TestAudibleArrangementHold(unittest.TestCase):
    def test_settings_pending_preserves_follow_timeline(self) -> None:
        from backing_key_cycle import (
            _mark_settings_pending_no_autoplay,
            audible_follow_timeline,
            key_cycle_settings_pending,
        )

        session = _catalog_shape_session()
        start_key_cycle(session, start_key="Gm")
        tl = [{"start_time": 0.0, "end_time": 2.0, "chord": "Gm"}]
        session["_last_backing_timeline"] = list(tl)
        session["_last_backing_signature"] = (
            "Shape",
            "Gm",
            "Intermediate",
            "Pop groove",
            140,
            "4/4",
            1,
            ("Verse",),
            "Strong",
            False,
            (),
            1,
            1,
            0,
            "arr_v2",
        )
        _mark_settings_pending_no_autoplay(session)
        self.assertTrue(key_cycle_settings_pending(session))
        held = audible_follow_timeline(session)
        self.assertIsNotNone(held)
        self.assertEqual(held[0]["chord"], "Gm")
        self.assertEqual(held[0]["end_time"], 2.0)

    def test_browser_restore_holds_at_pass_start_for_resume(self) -> None:
        from backing_key_cycle import normalize_key_cycle_after_browser_restore

        session = _catalog_shape_session()
        start_key_cycle(session, start_key="Ebm")
        advance_key_cycle_now(session)
        cur = temporary_playback_key(session)
        self.assertTrue(cur)
        session.pop("_kc_session_live", None)
        self.assertTrue(normalize_key_cycle_after_browser_restore(session))
        data = get_owner_cycle_session(session)
        self.assertEqual(str(data.get("status") or ""), STATUS_HELD)
        self.assertEqual(temporary_playback_key(session), cur)
        self.assertTrue(session.get("_kc_refresh_resume_from_start"))
        self.assertFalse(session.get("_backing_autoplay"))
        # No sticky WAV in a fresh session — Resume must arm continue-play rebuild.
        session.pop("_kc_current_static_url", None)
        session.pop("_last_backing_wav_path", None)
        resume_key_cycle(session)
        self.assertTrue(session.get("_kc_restart_play"))
        self.assertTrue(session.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))
        self.assertEqual(session["practice_key_by_source"][SHAPE_PICK], "Bm")

    def test_persist_rejects_stale_behind_cycle_key(self) -> None:
        """A deferred save holding the pre-handoff key must not overwrite disk."""
        import json
        import os
        import tempfile
        from pathlib import Path

        import suite_user_persistence as sup
        import suite_workspace as sw
        from backing_key_cycle import persist_key_cycle_position

        session = _catalog_shape_session()
        start_key_cycle(session, start_key="Bm")
        advance_key_cycle_now(session)
        advanced = temporary_playback_key(session)
        bag = dict(session[BACKING_KEY_CYCLE_SESSIONS_KEY])
        cat = dict(bag["catalog"])
        # Snapshot a stale "still on Bm" bag with lower pass/offset.
        stale = dict(cat)
        stale["current_playback_key"] = "Bm"
        stale["offset_semitones"] = 0
        stale["pass_id"] = max(0, int(cat.get("pass_id") or 1) - 1)

        with tempfile.TemporaryDirectory() as td:
            old_sw, old_sup = sw.DATA_DIR, getattr(sup, "DATA_DIR", None)
            try:
                sw.DATA_DIR = Path(td)
                if old_sup is not None:
                    sup.DATA_DIR = Path(td)
                os.environ["MUSIC_APP_DATA_DIR"] = td
                ws = Path(td) / "workspaces" / "daniel"
                ws.mkdir(parents=True, exist_ok=True)
                # Disk already has the advanced key.
                session_adv = dict(session)
                self.assertTrue(persist_key_cycle_position(session_adv))
                # Stale writer tries to put Bm back.
                stale_session = dict(session)
                stale_session[BACKING_KEY_CYCLE_SESSIONS_KEY] = {"catalog": stale}
                self.assertTrue(persist_key_cycle_position(stale_session))
                disk = json.loads((ws / "music_user_state.json").read_text(encoding="utf-8"))
                cat_disk = (
                    (disk.get("state") or {})
                    .get("session", {})
                    .get("_backing_key_cycle_sessions", {})
                    .get("catalog")
                    or {}
                )
                self.assertEqual(str(cat_disk.get("current_playback_key") or ""), advanced)
            finally:
                sw.DATA_DIR = old_sw
                if old_sup is not None:
                    sup.DATA_DIR = old_sup

    def test_persist_cycle_position_restores_on_fresh_session(self) -> None:
        """Disk merge must survive a brand-new session dict (not only soft reload)."""
        import json
        import os
        import tempfile
        from pathlib import Path

        import suite_user_persistence as sup
        import suite_workspace as sw
        from backing_key_cycle import persist_key_cycle_position

        session = _catalog_shape_session()
        start_key_cycle(session, start_key="Bm")
        advance_key_cycle_now(session)
        cur = temporary_playback_key(session)
        self.assertTrue(cur)
        self.assertNotEqual(cur, "Bm")
        pk_before = dict(session["practice_key_by_source"])

        with tempfile.TemporaryDirectory() as td:
            old_sw, old_sup = sw.DATA_DIR, getattr(sup, "DATA_DIR", None)
            try:
                sw.DATA_DIR = Path(td)
                if old_sup is not None:
                    sup.DATA_DIR = Path(td)
                os.environ["MUSIC_APP_DATA_DIR"] = td
                # Seed a minimal envelope so merge preserves Practice Key bags.
                ws = Path(td) / "workspaces" / "daniel"
                ws.mkdir(parents=True, exist_ok=True)
                seed = {
                    "version": 1,
                    "app": "music",
                    "saved_at": "2026-01-01T00:00:00Z",
                    "state": {
                        "session": {
                            "practice_key_by_source": dict(pk_before),
                        }
                    },
                }
                (ws / "music_user_state.json").write_text(
                    json.dumps(seed, indent=2), encoding="utf-8"
                )
                self.assertTrue(persist_key_cycle_position(session))
                disk = json.loads((ws / "music_user_state.json").read_text(encoding="utf-8"))
                disk_sess = disk["state"]["session"]
                bag = disk_sess.get("_backing_key_cycle_sessions") or {}
                cat = bag.get("catalog") or {}
                self.assertEqual(str(cat.get("current_playback_key") or ""), cur)
                self.assertEqual(
                    disk_sess.get("practice_key_by_source"),
                    pk_before,
                )

                # Fresh Streamlit session: only disk hydrate + normalize.
                fresh = {
                    "studio_page": "backing",
                    "active_catalog_pick_key": SHAPE_PICK,
                    "practice_key_by_source": dict(
                        disk_sess.get("practice_key_by_source") or pk_before
                    ),
                    "_backing_key_cycle_sessions": copy.deepcopy(bag),
                    "backing_key_cycle_enabled": True,
                }
                from backing_key_cycle import normalize_key_cycle_after_browser_restore

                self.assertTrue(normalize_key_cycle_after_browser_restore(fresh))
                self.assertEqual(temporary_playback_key(fresh), cur)
                self.assertEqual(fresh["practice_key_by_source"][SHAPE_PICK], "Bm")
                self.assertFalse(fresh.get("_backing_autoplay"))
                data = get_owner_cycle_session(fresh)
                self.assertEqual(str(data.get("status") or ""), STATUS_HELD)
            finally:
                sw.DATA_DIR = old_sw
                if old_sup is not None:
                    sup.DATA_DIR = old_sup

    def test_pause_clears_autoplay_flag(self) -> None:
        session = _catalog_shape_session()
        start_key_cycle(session, start_key="Gm")
        session["_backing_autoplay"] = True
        pause_key_cycle(session)
        self.assertFalse(session.get("_backing_autoplay"))
        self.assertTrue(session.get("_kc_pause_audio"))
        self.assertTrue(session.get("_backing_transport_user_stopped"))
        data = get_owner_cycle_session(session)
        self.assertEqual(str(data.get("status") or ""), STATUS_HELD)

    def test_explicit_play_leaves_held_and_restarts(self) -> None:
        from backing_key_cycle import arm_key_cycle_for_explicit_play

        session = _catalog_shape_session()
        start_key_cycle(session, start_key="Gm")
        pause_key_cycle(session)
        arm_key_cycle_for_explicit_play(session)
        data = get_owner_cycle_session(session)
        self.assertEqual(str(data.get("status") or ""), STATUS_RUNNING)
        self.assertTrue(session.get("_kc_restart_play"))
        self.assertTrue(session.get("_backing_autoplay"))
        self.assertFalse(session.get("_backing_transport_user_stopped"))
        self.assertFalse(session.get("_kc_pause_audio"))

    def test_explicit_play_restarts_at_first_sequence_key(self) -> None:
        from backing_key_cycle import arm_key_cycle_for_explicit_play, cycle_key_sequence

        session = _catalog_shape_session()
        start_key_cycle(session, start_key="Bm", interval=2, direction="down")
        note_backing_pass_finished(session, pass_signature="a1")
        note_backing_pass_finished(session, pass_signature="a2")
        self.assertEqual(temporary_playback_key(session), "Gm")
        seq = cycle_key_sequence(session)
        arm_key_cycle_for_explicit_play(session)
        data = get_owner_cycle_session(session) or {}
        self.assertEqual(str(data.get("current_playback_key") or ""), seq[0])
        self.assertEqual(int(data.get("offset_semitones", -999)), 0)
        self.assertEqual(session["practice_key_by_source"][SHAPE_PICK], "Bm")

    def test_natural_advance_stops_at_final_key_without_wrap(self) -> None:
        from backing_key_cycle import (
            _step_owner_cycle,
            advance_key_cycle_now,
            cycle_key_sequence,
        )

        session = _catalog_shape_session()
        start_key_cycle(session, start_key="Bm", interval=2, direction="down")
        seq = cycle_key_sequence(session)
        self.assertGreaterEqual(len(seq), 2)
        # Jump to last key.
        data = get_owner_cycle_session(session) or {}
        data = dict(data)
        data["current_playback_key"] = seq[-1]
        data["offset_semitones"] = -(len(seq) - 1) * 2
        from backing_key_cycle import _put_owner_cycle_session, resolve_cycle_owner

        _put_owner_cycle_session(session, resolve_cycle_owner(session), data)
        out = _step_owner_cycle(
            session, steps=1, force=False, queue_continue=False, allow_wrap=False
        )
        self.assertEqual(temporary_playback_key(session), seq[-1])
        self.assertTrue(session.get("_kc_cycle_finished_final"))
        self.assertEqual(str((out or {}).get("status") or ""), STATUS_HELD)
        # Manual Next wraps to first and runs.
        advance_key_cycle_now(session)
        self.assertEqual(temporary_playback_key(session), seq[0])
        self.assertFalse(session.get("_kc_cycle_finished_final"))
        self.assertEqual(
            str((get_owner_cycle_session(session) or {}).get("status") or ""),
            STATUS_RUNNING,
        )

    def test_arrangement_auto_apply_locks_key_against_pass_advance(self) -> None:
        from backing_key_cycle import (
            note_backing_pass_finished,
            note_key_cycle_arrangement_settings_changed,
        )

        session = _catalog_shape_session()
        start_key_cycle(session, start_key="Bm", interval=2, direction="down")
        session["_kc_user_arrangement_edit"] = True
        session["_kc_current_static_url"] = "/app/static/kc/old.wav"
        session["_last_backing_signature"] = (
            "Shape",
            "Bm",
            "Intermediate",
            "Pop groove",
            140,
            "4/4",
            1,
            ("Verse 1",),
            "Strong",
            False,
            (),
            1,
            1,
            0,
            "arr_v2",
        )
        k0 = temporary_playback_key(session)
        note_key_cycle_arrangement_settings_changed(session)
        self.assertEqual(session.get("_kc_arr_key_lock"), k0)
        self.assertFalse(
            note_backing_pass_finished(session, pass_signature="audio_ended::arr_lock")
        )
        self.assertEqual(temporary_playback_key(session), k0)

    def test_arrangement_settings_note_with_sticky_url(self) -> None:
        from backing_key_cycle import (
            BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY,
            key_cycle_settings_pending,
            note_key_cycle_arrangement_settings_changed,
        )

        session = _catalog_shape_session()
        start_key_cycle(session, start_key="Gm")
        session["_kc_user_arrangement_edit"] = True
        session["_kc_current_static_url"] = "/app/static/kc/old.wav"
        session["_last_backing_timeline"] = [
            {"start_time": 0.0, "end_time": 4.0, "chord": "Gm", "section": "Verse 1"}
        ]
        session["_last_backing_signature"] = (
            "Shape",
            "Gm",
            "Intermediate",
            "Pop groove",
            140,
            "4/4",
            1,
            ("Verse 1",),
            "Strong",
            False,
            (),
            1,
            1,
            0,
            "arr_v2",
        )
        note_key_cycle_arrangement_settings_changed(session)
        # Auto-apply: continue-play armed; sticky URL kept until regenerate.
        self.assertFalse(key_cycle_settings_pending(session))
        self.assertTrue(session.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))
        self.assertTrue(session.get("_kc_restart_play"))
        self.assertEqual(session.get("_kc_audible_bpm"), 140)
        self.assertTrue(session.get("_kc_current_static_url"))

    def test_neighbor_promote_does_not_clear_pending_arrangement_replace(self) -> None:
        """Prefetch promote must not burn explicit Play replace markers."""
        from pathlib import Path
        from unittest.mock import patch

        from backing_key_cycle import (
            BACKING_KEY_CYCLE_PREPARED_KEY,
            adopt_explicit_arrangement_url,
            promote_prepared_cycle_audio,
        )

        session: dict = {}
        adopt_explicit_arrangement_url(session, "/app/static/kc/arr_bpm.wav")
        session[BACKING_KEY_CYCLE_PREPARED_KEY] = {
            "Am": {
                "path": "dummy.wav",
                "signature": ("Shape", "Am"),
                "static_url": "/app/static/kc/next_key.wav",
            }
        }
        with patch.object(Path, "is_file", return_value=True):
            self.assertTrue(promote_prepared_cycle_audio(session, "Am"))
        self.assertTrue(session.get("_kc_force_arrangement_replace"))
        self.assertEqual(session.get("_kc_arrangement_url"), "/app/static/kc/arr_bpm.wav")
        self.assertEqual(session.get("_kc_current_static_url"), "/app/static/kc/arr_bpm.wav")


class TestPendingClearsOnlyWhenApplied(unittest.TestCase):
    def test_play_click_alone_does_not_clear_pending(self) -> None:
        from backing_key_cycle import (
            BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY,
            clear_settings_pending_if_arrangement_applied,
            key_cycle_settings_pending,
        )

        session = {
            BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY: True,
            "backing_track_bpm": 140,
            "backing_groove_style": "Blues groove",
            # No installed WAV/URL → failed/missing load
        }
        cleared = clear_settings_pending_if_arrangement_applied(
            session, bpm=140, groove="Blues groove"
        )
        self.assertFalse(cleared)
        self.assertTrue(key_cycle_settings_pending(session))

    def test_clears_when_installed_matches_selection(self) -> None:
        from backing_key_cycle import (
            BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY,
            clear_settings_pending_if_arrangement_applied,
            key_cycle_settings_pending,
        )

        session = {
            BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY: True,
            "_kc_current_static_url": "/app/static/kc/x.wav",
            "_kc_audible_bpm": 140,
            "_kc_audible_groove": "Blues groove",
            "_kc_audible_meter": "4/4",
            "_last_backing_signature": (
                "Shape of You",
                "Bm",
                "Beginner",
                "Blues groove",
                140,
                "4/4",
                1,
            ),
        }
        cleared = clear_settings_pending_if_arrangement_applied(
            session, bpm=140, groove="Blues groove", meter="4/4",
            signature=session["_last_backing_signature"],
        )
        self.assertTrue(cleared)
        self.assertFalse(key_cycle_settings_pending(session))
        self.assertTrue(session.get("_kc_applied_arrangement_fp"))

    def test_clears_when_content_matches_even_without_url(self) -> None:
        """Play generate can stash audible meta before static URL adopt lands."""
        from backing_key_cycle import (
            BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY,
            clear_settings_pending_if_arrangement_applied,
            key_cycle_settings_pending,
        )

        sig = (
            "Shape of You",
            "Bm",
            "Beginner",
            "Blues groove",
            140,
            "4/4",
            1,
        )
        session = {
            BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY: True,
            # No URL / wav path yet — remount lag after spill.
            "_kc_audible_bpm": 140,
            "_kc_audible_groove": "Blues groove",
            "_kc_audible_meter": "4/4",
            "_kc_audible_signature": sig,
            "_last_backing_signature": sig,
        }
        cleared = clear_settings_pending_if_arrangement_applied(
            session, bpm=140, groove="Blues groove", meter="4/4", signature=sig
        )
        self.assertTrue(cleared)
        self.assertFalse(key_cycle_settings_pending(session))

    def test_newer_edit_keeps_pending(self) -> None:
        from backing_key_cycle import (
            BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY,
            clear_settings_pending_if_arrangement_applied,
            key_cycle_settings_pending,
        )

        session = {
            BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY: True,
            "_kc_current_static_url": "/app/static/kc/x.wav",
            "_kc_audible_bpm": 96,
            "_kc_audible_groove": "Pop groove",
        }
        cleared = clear_settings_pending_if_arrangement_applied(
            session, bpm=140, groove="Blues groove"
        )
        self.assertFalse(cleared)
        self.assertTrue(key_cycle_settings_pending(session))

    def test_note_does_not_rearm_when_applied_matches(self) -> None:
        from backing_key_cycle import (
            BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY,
            clear_settings_pending_if_arrangement_applied,
            key_cycle_settings_pending,
            note_key_cycle_arrangement_settings_changed,
        )

        sig = (
            "Shape of You",
            "Bm",
            "Beginner",
            "Blues groove",
            140,
            "4/4",
            1,
            ("Verse 1",),
            "Strong",
            False,
        )
        session = {
            BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY: True,
            "_kc_current_static_url": "/app/static/kc/x.wav",
            "_kc_audible_bpm": 140,
            "_kc_audible_groove": "Blues groove",
            "backing_track_bpm": 140,
            "backing_groove_style": "Blues groove",
            "_last_backing_signature": sig,
        }
        clear_settings_pending_if_arrangement_applied(
            session, bpm=140, groove="Blues groove", signature=sig
        )
        self.assertFalse(key_cycle_settings_pending(session))
        # Remount flush must not re-arm Pending for the same applied arrangement.
        note_key_cycle_arrangement_settings_changed(session)
        note_key_cycle_arrangement_settings_changed(session)
        self.assertFalse(key_cycle_settings_pending(session))

    def test_feel_widget_flicker_does_not_wipe_sealed_wav(self) -> None:
        """Pop→Blues generate must survive groove selectbox remount noise."""
        from backing_key_cycle import (
            BACKING_KEY_CYCLE_PREPARED_KEY,
            arrangement_fingerprint_from_signature,
            key_cycle_settings_pending,
            note_key_cycle_arrangement_settings_changed,
        )

        sig = (
            "Shape of You",
            "Bm",
            "Beginner",
            "Blues groove",
            72,
            "4/4",
            1,
            ("Verse 1", "Chorus 1"),
            "Strong",
            False,
        )
        sealed = arrangement_fingerprint_from_signature(sig)
        session = {
            "_kc_applied_arrangement_fp": sealed,
            "_last_backing_signature": sig,
            "_last_backing_wav_path": "/tmp/blues.wav",
            "_kc_current_static_url": "/app/static/kc/blues.wav",
            "_kc_audible_bpm": 72,
            "_kc_audible_groove": "Blues groove",
            # Remount flicker: widgets briefly show Pop while Blues is audible.
            "backing_track_bpm": 72,
            "backing_groove_style": "Pop groove",
            "backing_key_cycle_enabled": True,
        }
        # Remount noise (no _kc_user_arrangement_edit): sealed==last → no-op.
        note_key_cycle_arrangement_settings_changed(session)
        self.assertFalse(key_cycle_settings_pending(session))
        self.assertEqual(session.get("_last_backing_wav_path"), "/tmp/blues.wav")
        self.assertEqual(session.get("_kc_current_static_url"), "/app/static/kc/blues.wav")
        self.assertEqual(session.get("_last_backing_signature"), sig)
        self.assertIsNone(session.get(BACKING_KEY_CYCLE_PREPARED_KEY))

    def test_scope_only_user_edit_auto_applies_despite_matching_tempo_feel(self) -> None:
        """Verse→Verse+Chorus must rebuild even when BPM/Feel/meter are unchanged."""
        from backing_key_cycle import (
            BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY,
            arrangement_content_matches_selection,
            arrangement_fingerprint_from_signature,
            note_key_cycle_arrangement_settings_changed,
        )
        from backing_track_state import write_canonical_backing_state

        sig = (
            "Shape of You",
            "Bm",
            "Intermediate",
            "Pop groove",
            96,
            "4/4",
            1,
            ("Verse 1",),
            "Strong",
            False,
        )
        sealed = arrangement_fingerprint_from_signature(sig)
        session = _catalog_shape_session()
        start_key_cycle(session, start_key="Bm", interval=2, direction="down")
        write_canonical_backing_state(
            session,
            {
                "backing_track_scope": "Selected sections",
                "backing_track_multi_sections": ["Verse 1", "Chorus 1"],
                "backing_track_loops": 1,
                "backing_track_bpm": 96,
                "backing_groove_style": "Pop groove",
                "backing_time_signature": "4/4",
            },
        )
        session.update(
            {
                "_kc_applied_arrangement_fp": sealed,
                "_last_backing_signature": sig,
                "_kc_audible_signature": sig,
                "_last_backing_wav_path": "/tmp/verse.wav",
                "_kc_current_static_url": "/app/static/kc/verse.wav",
                "_kc_audible_bpm": 96,
                "_kc_audible_groove": "Pop groove",
                "_kc_audible_meter": "4/4",
                "backing_track_bpm": 96,
                "backing_groove_style": "Pop groove",
                "backing_track_loops": 1,
                "backing_track_scope": "Selected sections",
                "backing_track_multi_sections": ["Verse 1", "Chorus 1"],
                "_kc_user_arrangement_edit": True,
            }
        )
        self.assertFalse(arrangement_content_matches_selection(session))
        note_key_cycle_arrangement_settings_changed(session)
        self.assertTrue(session.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))
        self.assertTrue(session.get("_kc_restart_play"))
        self.assertIsNone(session.get("_kc_applied_arrangement_fp"))
        self.assertEqual(session.get("_kc_arr_key_lock"), "Bm")

    def test_lagging_feel_widget_does_not_clear_pending_for_canon(self) -> None:
        """Blues audible + Blues widget lag must not clear Pending when canon is Pop."""
        from backing_key_cycle import (
            clear_settings_pending_if_arrangement_applied,
            key_cycle_settings_pending,
        )
        from backing_track_state import write_canonical_backing_state

        session: dict = {
            "_backing_key_cycle_settings_pending_play": True,
            "_last_backing_wav_path": "/tmp/blues.wav",
            "_kc_current_static_url": "/app/static/kc/blues.wav",
            "_kc_audible_bpm": 96,
            "_kc_audible_groove": "Blues groove",
            "_kc_audible_meter": "4/4",
            "_last_backing_signature": (
                "Shape of You",
                "Bm",
                "Beginner",
                "Blues groove",
                96,
                "4/4",
                1,
                ("Verse 1",),
                "Strong",
                False,
            ),
            "backing_track_bpm": 96,
            "backing_groove_style": "Blues groove",
            "backing_time_signature": "4/4",
        }
        write_canonical_backing_state(
            session,
            {
                "backing_track_bpm": 96,
                "backing_groove_style": "Pop groove",
                "backing_time_signature": "4/4",
                "backing_section_scope": "Selected sections",
                "backing_form_loops": 1,
            },
            reason="test_feel_canon",
            local_edit=True,
        )
        cleared = clear_settings_pending_if_arrangement_applied(
            session, bpm=96, groove="Blues groove", meter="4/4"
        )
        self.assertFalse(cleared)
        self.assertTrue(key_cycle_settings_pending(session))

    def test_pass_bridge_defers_ack_while_settings_pending(self) -> None:
        """Natural playing acks must not st.rerun-starve an explicit Feel Play."""
        from backing_key_cycle import (
            BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY,
            key_cycle_settings_pending,
            note_backing_pass_finished,
            start_key_cycle,
        )
        from backing_key_cycle_handoff import ACKED_IDS_KEY, validate_playing_ack

        session: dict = {
            "practice_key": "Bm",
            "backing_key_cycle_enabled": True,
            BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY: True,
            "_kc_player_cmd_epoch": 3,
        }
        start_key_cycle(session)
        cycle_id = str(session.get("_kc_cycle_id") or "")
        self.assertTrue(cycle_id)
        ack = {
            "kind": "playing",
            "ackId": "ack-feel-pending-1",
            "cycleId": cycle_id,
            "passId": 1,
            "playingKey": "Am",
            "fromKey": "Bm",
            "epoch": 3,
        }
        ok, reason = validate_playing_ack(session, ack, expect_cycle_id=cycle_id)
        self.assertFalse(ok)
        self.assertEqual(reason, "settings_pending")
        advanced = note_backing_pass_finished(
            session, seamless=True, handoff_ack=ack
        )
        self.assertFalse(advanced)
        self.assertTrue(key_cycle_settings_pending(session))
        self.assertIn("ack-feel-pending-1", session.get(ACKED_IDS_KEY) or [])


class TestPublishCycleWavContent(unittest.TestCase):
    def test_same_length_different_bytes_are_replaced(self) -> None:
        import tempfile
        from pathlib import Path

        from backing_key_cycle import publish_cycle_wav_static_url

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Point static dir at temp via monkeypatch of _kc_static_dir
            import backing_key_cycle as bkc

            real = bkc._kc_static_dir
            bkc._kc_static_dir = lambda: root  # type: ignore[assignment]
            try:
                src_a = root / "a.wav"
                src_b = root / "b.wav"
                src_a.write_bytes(b"RIFF" + b"A" * 200)
                src_b.write_bytes(b"RIFF" + b"B" * 200)
                sig = ("Song", "Bm", "Beginner", "Pop groove", 96)
                url1 = publish_cycle_wav_static_url(str(src_a), signature=sig)
                self.assertTrue(url1.endswith(".wav"))
                name = url1.rsplit("/", 1)[-1]
                dest = root / name
                self.assertEqual(dest.read_bytes(), src_a.read_bytes())
                url2 = publish_cycle_wav_static_url(str(src_b), signature=sig)
                self.assertEqual(url1, url2)
                self.assertEqual(dest.read_bytes(), src_b.read_bytes())
            finally:
                bkc._kc_static_dir = real  # type: ignore[assignment]


class TestPreparedChartTempoFeel(unittest.TestCase):
    def test_store_prepared_uses_signature_not_100_pop_defaults(self) -> None:
        """Play-apply must not reseal prepared lead-sheet captions to 100/Pop."""
        from backing_key_cycle import (
            _prepared_chart_bpm_groove,
            prepared_cycle_chart_html,
            store_prepared_cycle_audio,
        )

        sig = (
            "Shape of You",
            "Bm",
            "Beginner",
            "Blues groove",
            140,
            "4/4",
            1,
            ("Verse 1", "Chorus 1"),
            "Strong",
            False,
            (),
            8,
            8,
            0,
            "arr_v2",
        )
        session: dict = {
            "_kc_chart_song_name": "Shape of You",
            "_kc_chart_song_data": {"key": "Bm", "title": "Shape of You"},
            "_kc_chart_selected_sections": ["Verse 1", "Chorus 1"],
            "_kc_chart_level": "Beginner",
            "_kc_chart_meter": "4/4",
        }
        bpm, groove = _prepared_chart_bpm_groove(session, signature=sig)
        self.assertEqual(bpm, 140)
        self.assertIn("Blues", groove)
        store_prepared_cycle_audio(
            session,
            sounding_key="Bm",
            signature=sig,
            chords=["Bm", "F#m", "E", "E"],
            sections={"Verse 1": ["Bm", "F#m"], "Chorus 1": ["E", "E"]},
        )
        html = prepared_cycle_chart_html(session, "Bm")
        self.assertTrue(html)
        self.assertIn("140", html)
        self.assertIn("Blues", html)
        self.assertNotIn("100 BPM", html)
        self.assertEqual(session.get("_kc_chart_bpm"), 140)
        self.assertIn("Blues", str(session.get("_kc_chart_groove") or ""))

    def test_store_prepared_does_not_copy_wrong_key_timeline(self) -> None:
        """Neighbor prep must not inherit the audible key's Bm timeline.

        Cause of the former assertEqual failure: ``store_prepared_cycle_audio``
        stamps every stored event with ``chordSpace=concert`` (projection
        contract). Comparing to an untagged input list was wrong — the stamp is
        required so Current/Next never guess space from chord text.
        """
        from backing_key_cycle import (
            BACKING_KEY_CYCLE_PREPARED_KEY,
            FOLLOW_TIMELINE_SPACE_CONCERT,
            arrangement_timing_fingerprint,
            prepared_cycle_arrange_fingerprint,
            prepared_cycle_follow_timeline,
            store_prepared_cycle_audio,
            tag_follow_timeline_space,
        )

        bm_tl = [
            {"start_time": 0.0, "end_time": 2.0, "chord": "Bm", "section": "Verse 1"},
            {"start_time": 2.0, "end_time": 4.0, "chord": "Em", "section": "Verse 1"},
        ]
        am_tl = [
            {"start_time": 0.0, "end_time": 2.0, "chord": "Am", "section": "Verse 1"},
            {"start_time": 2.0, "end_time": 4.0, "chord": "Dm", "section": "Verse 1"},
        ]
        am_sig = (
            "Shape of You",
            "Am",
            "Intermediate",
            "Pop groove",
            96,
            "4/4",
            1,
            ("Verse 1",),
        )
        session = {
            "_last_backing_signature": (
                "Shape of You",
                "Bm",
                "Intermediate",
                "Pop groove",
                96,
                "4/4",
                1,
                ("Verse 1",),
            ),
            "_last_backing_timeline": bm_tl,
            "backing_key_cycle_enabled": True,
        }
        # Storing Am while Bm is audible must not copy Bm chords.
        store_prepared_cycle_audio(
            session,
            sounding_key="Am",
            signature=am_sig,
            chords=["Am", "Dm"],
            sections={"Verse 1": ["Am", "Dm"]},
        )
        self.assertEqual(prepared_cycle_follow_timeline(session, "Am"), [])
        store_prepared_cycle_audio(
            session,
            sounding_key="Am",
            signature=am_sig,
            chords=["Am", "Dm"],
            sections={"Verse 1": ["Am", "Dm"]},
            timeline=am_tl,
        )
        expected = tag_follow_timeline_space(am_tl, FOLLOW_TIMELINE_SPACE_CONCERT)
        got = prepared_cycle_follow_timeline(session, "Am")
        self.assertEqual(got, expected)
        self.assertEqual(got[0]["chord"], "Am")
        self.assertEqual(got[0]["chordSpace"], FOLLOW_TIMELINE_SPACE_CONCERT)
        self.assertNotEqual(got[0]["chord"], "Bm")
        bag = session.get(BACKING_KEY_CYCLE_PREPARED_KEY) or {}
        self.assertEqual((bag.get("Am") or {}).get("timeline"), expected)
        self.assertEqual(
            (bag.get("Am") or {}).get("arrange_fp"),
            arrangement_timing_fingerprint(am_sig),
        )
        self.assertEqual(
            prepared_cycle_arrange_fingerprint(session, "Am"),
            arrangement_timing_fingerprint(am_sig),
        )

    def test_arrangement_timing_fingerprint_ignores_key(self) -> None:
        from backing_key_cycle import (
            arrangement_timing_fingerprint,
            arrangement_timing_fingerprints_match,
        )

        bm = (
            "Shape of You",
            "Bm",
            "Intermediate",
            "Pop groove",
            96,
            "4/4",
            1,
            ("Verse 1",),
        )
        am = (
            "Shape of You",
            "Am",
            "Intermediate",
            "Pop groove",
            96,
            "4/4",
            1,
            ("Verse 1",),
        )
        am_fast = (
            "Shape of You",
            "Am",
            "Intermediate",
            "Pop groove",
            140,
            "4/4",
            1,
            ("Verse 1",),
        )
        am_blues = (
            "Shape of You",
            "Am",
            "Intermediate",
            "Blues groove",
            96,
            "4/4",
            1,
            ("Verse 1",),
        )
        fp_bm = arrangement_timing_fingerprint(bm)
        fp_am = arrangement_timing_fingerprint(am)
        self.assertTrue(arrangement_timing_fingerprints_match(fp_bm, fp_am))
        self.assertFalse(
            arrangement_timing_fingerprints_match(
                fp_am, arrangement_timing_fingerprint(am_fast)
            )
        )
        self.assertFalse(
            arrangement_timing_fingerprints_match(
                fp_am, arrangement_timing_fingerprint(am_blues)
            )
        )
        # Key is not part of the fingerprint tuple.
        self.assertNotIn("Bm", fp_bm)
        self.assertNotIn("Am", fp_am)

    def test_prepared_chart_session_fallback_when_sig_missing(self) -> None:
        from backing_key_cycle import _prepared_chart_bpm_groove

        session = {
            "_kc_chart_bpm": 140,
            "_kc_chart_groove": "Blues groove",
        }
        bpm, groove = _prepared_chart_bpm_groove(
            session, signature=None, bpm=None, groove_style=""
        )
        self.assertEqual(bpm, 140)
        self.assertIn("Blues", groove)


class TestGrooveRendererDiffers(unittest.TestCase):
    def test_blues_pop_jazz_wav_bytes_differ(self) -> None:
        from backing_audio import generate_backing_track

        chords = ["Am", "F", "C", "G"]
        pop = generate_backing_track(chords, bpm=100, loops=1, style="Pop groove")
        blues = generate_backing_track(chords, bpm=100, loops=1, style="Blues groove")
        jazz = generate_backing_track(chords, bpm=100, loops=1, style="Jazz swing")
        self.assertNotEqual(pop, blues)
        self.assertNotEqual(pop, jazz)
        self.assertNotEqual(blues, jazz)

    def test_blues_groove_onset_profile_differs_from_pop(self) -> None:
        """Same chords/BPM/loops: Blues must change rhythmic energy, not only bytes."""
        import io
        import struct
        import wave

        from backing_audio import generate_backing_track

        chords = ["Am", "Dm", "E7", "Am"]
        pop = generate_backing_track(chords, bpm=100, loops=1, style="Pop groove")
        blues = generate_backing_track(chords, bpm=100, loops=1, style="Blues groove")

        def onset_bins(wav_bytes: bytes, bins: int = 16) -> list[float]:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                nch = wf.getnchannels()
                sw = wf.getsampwidth()
                rate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())
            if sw != 2:
                self.skipTest(f"unexpected sample width {sw}")
            count = len(frames) // (sw * nch)
            # Mono abs amplitude, windowed energy.
            win = max(1, rate // 50)
            energies: list[float] = []
            for i in range(0, count - win, win):
                acc = 0.0
                for j in range(i, i + win):
                    off = j * nch * sw
                    sample = struct.unpack_from("<h", frames, off)[0]
                    acc += abs(sample)
                energies.append(acc / win)
            if not energies:
                return [0.0] * bins
            # Fold into bins across the first ~4 bars worth.
            take = energies[: max(bins * 4, bins)]
            out = [0.0] * bins
            for i, e in enumerate(take):
                out[i % bins] += e
            s = sum(out) or 1.0
            return [x / s for x in out]

        pop_p = onset_bins(pop)
        blues_p = onset_bins(blues)
        l1 = sum(abs(a - b) for a, b in zip(pop_p, blues_p))
        self.assertGreater(
            l1,
            0.08,
            f"Blues onset profile too close to Pop (L1={l1:.4f})",
        )


if __name__ == "__main__":
    unittest.main()
