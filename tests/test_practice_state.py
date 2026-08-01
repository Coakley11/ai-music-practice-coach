"""Tests for canonical Practice page state (Phase C acceptance A–E)."""



from __future__ import annotations



import unittest

from unittest.mock import MagicMock



from music_persistent_state import apply_music_disk_state, build_music_disk_state

from active_song_state import prepare_active_song_context
from practice_state import (

    PRACTICE_DIRTY_KEY,

    apply_cloud_practice_state_if_allowed,

    apply_practice_source_state_from_ami,

    coerce_practice_focus_for_widget,

    coerce_practice_groove_for_widget,

    flush_practice_edits,

    is_practice_locally_dirty,

    mark_practice_local_edit,

    normalize_practice_focus_section,

    normalize_practice_groove,

    normalize_practice_minutes,

    prepare_practice_page,

    write_canonical_practice_state,

)



_SAMPLE = {

    "practice_focus_section": "Chorus",

    "practice_groove_style": "Pop groove",

    "practice_minutes": 45,

    "practice_notation_lines": 3,

    "practice_notation_difficulty": "medium",

    "last_practice_mode": "section",

}





class TestPracticeState(unittest.TestCase):

    def test_a_local_persist_prepare_preserves_edits(self) -> None:

        session: dict = {}

        write_canonical_practice_state(session, _SAMPLE, reason="setup")

        session["practice_groove_style"] = "Jazz swing"

        session["practice_minutes"] = 75

        mark_practice_local_edit(session)

        flush_practice_edits(session, reason="practice_edit")

        prepare_practice_page(session)

        self.assertEqual(session["practice_groove_style"], "Jazz swing")

        self.assertEqual(session["practice_minutes"], 75)

        self.assertEqual(session["practice_state"]["practice_groove_style"], "Jazz swing")

        self.assertEqual(session["practice_state"]["practice_minutes"], 75)

        self.assertTrue(is_practice_locally_dirty(session))



    def test_a_prepare_seeds_from_canonical(self) -> None:

        session = {"practice_state": {**_SAMPLE, "last_write_reason": "cloud"}}

        prepare_practice_page(session)

        self.assertEqual(session["practice_groove_style"], "Pop groove")

        self.assertEqual(session["practice_minutes"], 45)

        self.assertEqual(session["practice_notation_lines"], 3)



    def test_b_cross_device_cloud_restore(self) -> None:

        session: dict = {"practice_groove_style": "Auto", "practice_minutes": 30}

        cloud = {

            "practice_state": {**_SAMPLE, "practice_groove_style": "Bossa Nova", "practice_minutes": 75},

            "music_workspace_state": {

                "practice_filters": {

                    **_SAMPLE,

                    "practice_groove_style": "Bossa Nova",

                    "practice_minutes": 75,

                }

            },

        }

        self.assertTrue(apply_cloud_practice_state_if_allowed(session, cloud))

        self.assertEqual(session["practice_groove_style"], "Bossa nova")

        self.assertEqual(session["practice_minutes"], 75)

        self.assertFalse(is_practice_locally_dirty(session))



    def test_b_disk_blob_round_trip(self) -> None:

        st = MagicMock()

        st.session_state = dict(_SAMPLE)

        write_canonical_practice_state(st.session_state, _SAMPLE, reason="setup")

        blob = build_music_disk_state(st)

        self.assertIn("practice_state", blob)

        meta = blob.get("music_workspace_state") or {}

        self.assertEqual(meta.get("practice_filters", {}).get("practice_groove_style"), "Pop groove")

        self.assertEqual(meta.get("practice_filters", {}).get("practice_minutes"), 45)



        st2 = MagicMock()

        st2.session_state = {}

        apply_music_disk_state(st2, blob, song_picker_catalog={}, song_library={})

        self.assertEqual(st2.session_state.get("practice_groove_style"), "Pop groove")

        self.assertEqual(st2.session_state.get("practice_minutes"), 45)

        self.assertEqual(st2.session_state.get("practice_state", {}).get("practice_focus_section"), "Chorus")



    def test_c_stale_cloud_blocked_when_locally_dirty(self) -> None:

        session = {**_SAMPLE, "practice_groove_style": "Rock groove", "practice_minutes": 60}

        mark_practice_local_edit(session)

        cloud = {"practice_state": dict(_SAMPLE)}

        self.assertFalse(apply_cloud_practice_state_if_allowed(session, cloud))

        self.assertEqual(session["practice_groove_style"], "Rock groove")

        self.assertEqual(session["practice_minutes"], 60)



    def test_d_navigation_does_not_clear_practice_filters(self) -> None:

        session = dict(_SAMPLE)

        write_canonical_practice_state(session, _SAMPLE, reason="setup")

        session["studio_page"] = "backing"

        prepare_practice_page(session)

        self.assertEqual(session["practice_groove_style"], "Pop groove")

        self.assertEqual(session["practice_minutes"], 45)



    def test_e_ami_return_restores_practice_filters(self) -> None:

        session: dict = {}

        source = {

            "source_page": "practice",

            "widget_params": {

                "practice_focus_section": "Verse",

                "practice_groove_style": "Ballad",

                "practice_minutes": 90,

                "practice_notation_lines": 4,

                "practice_notation_difficulty": "easy",

            },

        }

        apply_practice_source_state_from_ami(session, source)

        self.assertEqual(session["practice_focus_section"], "Verse")

        self.assertEqual(session["practice_groove_style"], "Ballad")

        self.assertEqual(session["practice_minutes"], 90)

        self.assertEqual(session["practice_notation_lines"], 4)

        self.assertFalse(session.get(PRACTICE_DIRTY_KEY))



    def test_practice_edit_bypasses_post_restore_block(self) -> None:

        from suite_user_persistence import _cloud_autosave_blocked_reason



        st = MagicMock()

        st.session_state = {}

        state = {"practice_state": dict(_SAMPLE)}

        self.assertIsNone(

            _cloud_autosave_blocked_reason(st, "music", state, save_reason="practice_edit")

        )



    def test_groove_normalization_maps_aliases(self) -> None:

        self.assertEqual(normalize_practice_groove("Bossa Nova"), "Bossa nova")

        self.assertEqual(normalize_practice_groove("bossa nova"), "Bossa nova")

        self.assertEqual(normalize_practice_groove("Jewish groove"), "Jewish groove")



    def test_coerce_groove_for_widget_uses_canonical_choices(self) -> None:

        session = {"practice_groove_style": "Bossa Nova"}

        groove = coerce_practice_groove_for_widget(session, default_groove="Auto")

        self.assertEqual(groove, "Bossa nova")

        self.assertEqual(session["practice_groove_style"], "Bossa nova")

    def test_resolve_groove_prefers_backing_studio_override(self) -> None:
        from practice_state import resolve_practice_groove_style

        session = {"backing_groove_style": "Jazz swing", "practice_groove_style": "Pop groove"}
        groove = resolve_practice_groove_style(session, default_groove="Ballad")
        self.assertEqual(groove, "Jazz swing")
        self.assertEqual(session["practice_groove_style"], "Jazz swing")



    def test_practice_minutes_clamped_to_slider_range(self) -> None:

        self.assertEqual(normalize_practice_minutes(73), 75)

        self.assertEqual(normalize_practice_minutes(8), 10)

        self.assertEqual(normalize_practice_minutes(130), 120)

        self.assertIsNone(normalize_practice_minutes(None))



    def test_autosave_preserves_canonical_groove_minutes_without_dirty(self) -> None:

        from practice_state import commit_practice_state_from_session



        session = {

            "practice_state": {

                **_SAMPLE,

                "practice_groove_style": "Bossa nova",

                "practice_minutes": 50,

                "last_write_reason": "practice_edit",

            },

            "practice_groove_style": "Ballad",

            "practice_minutes": 30,

        }

        commit_practice_state_from_session(session, reason="autosave")

        self.assertEqual(session["practice_state"]["practice_groove_style"], "Bossa nova")

        self.assertEqual(session["practice_state"]["practice_minutes"], 50)

        self.assertEqual(session["practice_groove_style"], "Bossa nova")

        self.assertEqual(session["practice_minutes"], 50)



    def test_normalize_full_song_casing(self) -> None:
        self.assertEqual(normalize_practice_focus_section("Full song"), "Full Song")
        self.assertEqual(normalize_practice_focus_section("full song"), "Full Song")
        self.assertEqual(normalize_practice_focus_section("Verse"), "Verse")

    def test_prepare_session_section_wins_over_stale_canonical_full_song(self) -> None:
        """Section focus selector: live Verse must not revert to canonical Full Song."""
        session = {
            "practice_focus_section": "Verse",
            "practice_state": {
                **_SAMPLE,
                "practice_focus_section": "Full Song",
                "last_write_reason": "cloud_restore",
            },
        }
        prepare_practice_page(session)
        self.assertEqual(session["practice_focus_section"], "Verse")
        self.assertEqual(session["practice_state"]["practice_focus_section"], "Verse")
        self.assertEqual(session["practice_state"]["last_write_reason"], "session_section_wins")
        self.assertTrue(is_practice_locally_dirty(session))

    def test_coerce_practice_focus_for_widget_normalizes_legacy_full_song(self) -> None:
        session = {"practice_focus_section": "Full song"}
        choices = ["Full Song", "Verse", "Chorus"]
        section = coerce_practice_focus_for_widget(session, choices)
        self.assertEqual(section, "Full Song")
        self.assertEqual(session["practice_focus_section"], "Full Song")

    def test_active_song_prepare_does_not_clobber_practice_section(self) -> None:
        song_sample = {
            "pick_key": "Pop|Test",
            "display_key": "C",
            "instrument": "Guitar",
            "practice_focus_section": "Full Song",
        }
        session = {
            "practice_focus_section": "Verse",
            "practice_state": {**_SAMPLE, "practice_focus_section": "Verse"},
            "active_song_state": {**song_sample, "last_write_reason": "cloud"},
        }
        prepare_active_song_context(session)
        prepare_practice_page(session)
        self.assertEqual(session["practice_focus_section"], "Verse")

    def test_coerce_prefers_canonical_over_song_default(self) -> None:

        session = {

            "practice_state": {

                **_SAMPLE,

                "practice_groove_style": "Jazz swing",

                "practice_minutes": 75,

                "last_write_reason": "cloud_restore",

            }

        }

        apply_cloud_practice_state_if_allowed(

            session,

            {

                "practice_state": session["practice_state"],

                "music_workspace_state": {"practice_filters": session["practice_state"]},

            },

        )

        session.pop("practice_groove_style", None)

        groove = coerce_practice_groove_for_widget(session, default_groove="Ballad")

        self.assertEqual(groove, "Jazz swing")

        self.assertEqual(session["practice_groove_style"], "Jazz swing")





if __name__ == "__main__":

    unittest.main()


