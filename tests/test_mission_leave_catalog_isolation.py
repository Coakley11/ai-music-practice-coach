"""Leave Mission Backing → Songs: leftover Mission PK must not become Shape PK."""

from __future__ import annotations

import unittest

from backing_context import BackingContext, set_backing_context
from creative_key_sync import (
    leftover_mission_token_on_catalog_surface,
    mission_owns_left_panel_key,
    retire_mission_left_panel_for_catalog_surface,
    sync_sidebar_creative_concert_key,
)
from generated_jam_key_context import release_generated_jam_key_for_catalog_surface
from song_catalog.catalog import format_pick_key
from songs.key_state import (
    DISPLAY_KEY_OWNER_TRANSITION_KEY,
    apply_display_key_owner_transition_if_needed,
    clear_display_key_owner_transition,
    resolve_display_key_widget_owner_id,
)
from songs.music_source import LAST_CUSTOM_STATE_KEY
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
    set_practice_concert_key,
)


SHAPE = format_pick_key("Pop", "Shape of You — Ed Sheeran")
CUSTOM_TRIAL = "custom::Trial Song"


def _shape_song() -> dict:
    return {
        "title": "Shape of You",
        "artist": "Ed Sheeran",
        "key": "Bm",
        "pick_key": SHAPE,
    }


def _mission_ctx(**keys: str) -> BackingContext:
    tok = str(keys.get("key") or "Cm")
    return BackingContext(
        source="mission",
        source_label="Mission",
        active_song_id=SHAPE,
        bound_pick_key=SHAPE,
        song_title="Shape of You",
        key=tok,
        display_key=tok,
        concert_key=tok,
        bpm=96,
        style="",
        groove="",
        mission_id="Improvise using only chord tones",
    )


def _failing_leave_session(*, page: str, live: str = "Cm") -> dict:
    """Full-history gate-12 leftover: Mission Cm, Shape sticky Dm."""
    session = {
        "studio_page": page,
        "active_catalog_pick_key": SHAPE,
        "selected_song": _shape_song(),
        "display_key": live,
        "concert_key": live,
        "improv_mission_concert_key": "Cm",
        "improv_mission_pick": "Improvise using only chord tones",
        "improv_active_mission": "Improvise using only chord tones",
        "ii_selected_chord": "F",
        "improv_entry_mode": "Song-Based Improvisation",
        "improv_intelligence_tab": "Missions",
        "creative_improv_intelligence_tab": "Missions",
        "improv_song_source": "Active song",
        PRACTICE_KEY_BY_SOURCE_KEY: {SHAPE: "Dm"},
        "_backing_explicit_handoff_source": "mission",
        LAST_CUSTOM_STATE_KEY: {
            "title": "Trial Song",
            "display_key": "D",
            "pick_key": CUSTOM_TRIAL,
        },
        "display_key_mission_backing": live,
    }
    set_backing_context(session, _mission_ctx(key=live))
    return session


class MissionLeaveCatalogIsolationTests(unittest.TestCase):
    def test_a_mission_backing_cm_does_not_stamp_shape_dm(self) -> None:
        session = _failing_leave_session(page="backing", live="Cm")
        self.assertTrue(mission_owns_left_panel_key(session))
        set_practice_concert_key(session, "Cm", pick_key=SHAPE)
        self.assertEqual(get_practice_concert_key(session, SHAPE), "Dm")

    def test_a_creative_missions_cm_does_not_stamp_shape_dm(self) -> None:
        session = _failing_leave_session(page="creative", live="Cm")
        self.assertTrue(mission_owns_left_panel_key(session))
        set_practice_concert_key(session, "Cm", pick_key=SHAPE)
        sync_sidebar_creative_concert_key(session)
        self.assertEqual(get_practice_concert_key(session, SHAPE), "Dm")
        self.assertEqual(session.get("improv_mission_concert_key"), "Cm")

    def test_c_d_picker_leave_seeds_shape_sticky_not_mission_cm(self) -> None:
        session = _failing_leave_session(page="picker", live="Cm")
        self.assertFalse(mission_owns_left_panel_key(session))
        self.assertEqual(leftover_mission_token_on_catalog_surface(session), "Cm")
        self.assertTrue(retire_mission_left_panel_for_catalog_surface(session))
        self.assertEqual(get_practice_concert_key(session, SHAPE), "Dm")
        self.assertEqual(str(session.get("display_key") or ""), "Dm")
        self.assertEqual(str(session.get("concert_key") or ""), "Dm")
        set_practice_concert_key(session, "Cm", pick_key=SHAPE)
        self.assertEqual(get_practice_concert_key(session, SHAPE), "Dm")
        self.assertEqual(session.get("improv_mission_concert_key"), "Cm")

    def test_picker_leftover_mission_ctx_is_catalog_widget_owner(self) -> None:
        session = _failing_leave_session(page="picker", live="Cm")
        self.assertEqual(
            resolve_display_key_widget_owner_id(session), f"catalog::{SHAPE}"
        )

    def test_e_shape_dm_to_bm_after_leave_is_same_owner_edit(self) -> None:
        session = _failing_leave_session(page="picker", live="Cm")
        retire_mission_left_panel_for_catalog_surface(session)
        apply_display_key_owner_transition_if_needed(session)
        clear_display_key_owner_transition(session)
        session["display_key"] = "Bm"
        session["concert_key"] = "Bm"
        session["display_key_change_source"] = "sidebar_on_change"
        set_practice_concert_key(session, "Bm", pick_key=SHAPE)
        self.assertEqual(get_practice_concert_key(session, SHAPE), "Bm")
        self.assertFalse(bool(leftover_mission_token_on_catalog_surface(session)))

    def test_f_second_catalog_rerun_does_not_reopen_cm_transition(self) -> None:
        session = _failing_leave_session(page="picker", live="Cm")
        retire_mission_left_panel_for_catalog_surface(session)
        clear_display_key_owner_transition(session)
        session["display_key"] = "Bm"
        session["concert_key"] = "Bm"
        session["display_key_change_source"] = "sidebar_on_change"
        set_practice_concert_key(session, "Bm", pick_key=SHAPE)
        self.assertFalse(retire_mission_left_panel_for_catalog_surface(session))
        self.assertEqual(get_practice_concert_key(session, SHAPE), "Bm")
        self.assertEqual(str(session.get("display_key") or ""), "Bm")

    def test_g_h_i_mission_and_custom_sbi_workspace_survive_leave(self) -> None:
        session = _failing_leave_session(page="picker", live="Cm")
        retire_mission_left_panel_for_catalog_surface(session)
        custom = session.get(LAST_CUSTOM_STATE_KEY)
        self.assertIsInstance(custom, dict)
        self.assertEqual(str(custom.get("title") or ""), "Trial Song")
        self.assertEqual(session.get("improv_mission_pick"), "Improvise using only chord tones")
        self.assertEqual(session.get("improv_mission_concert_key"), "Cm")
        self.assertEqual(session.get("ii_selected_chord"), "F")

    def test_jam_release_mission_handoff_keeps_shape_dm(self) -> None:
        session = _failing_leave_session(page="picker", live="Cm")
        retire_mission_left_panel_for_catalog_surface(session)
        release_generated_jam_key_for_catalog_surface(session)
        self.assertEqual(get_practice_concert_key(session, SHAPE), "Dm")
        self.assertNotEqual(str(session.get("display_key") or ""), "Bm")
        rec = session.get(DISPLAY_KEY_OWNER_TRANSITION_KEY)
        if isinstance(rec, dict):
            self.assertEqual(str(rec.get("canonical") or ""), "Dm")
            self.assertEqual(str(rec.get("stale") or ""), "Cm")

    def test_seal_on_leave_backing_blocks_creative_catalog_stamp(self) -> None:
        session = _failing_leave_session(page="backing", live="Cm")
        from creative_key_sync import seal_mission_pk_on_leave_backing
        from studio_nav_history import navigate_studio_page

        self.assertTrue(seal_mission_pk_on_leave_backing(session))
        self.assertEqual(session.get("_specialized_practice_token_leaving"), "Cm")
        self.assertEqual(session.get("_specialized_leave_catalog_pk"), "Dm")
        navigate_studio_page(session, "creative")
        self.assertEqual(session.get("studio_page"), "creative")
        self.assertTrue(mission_owns_left_panel_key(session))
        set_practice_concert_key(session, "Cm", pick_key=SHAPE)
        sync_sidebar_creative_concert_key(session)
        self.assertEqual(get_practice_concert_key(session, SHAPE), "Dm")
        session["studio_page"] = "picker"
        self.assertTrue(retire_mission_left_panel_for_catalog_surface(session))
        self.assertEqual(str(session.get("display_key") or ""), "Dm")
        self.assertEqual(get_practice_concert_key(session, SHAPE), "Dm")

    def test_j_explicit_shape_sticky_survives_when_not_leaving_mission(self) -> None:
        session = {
            "studio_page": "picker",
            "active_catalog_pick_key": SHAPE,
            "selected_song": _shape_song(),
            "display_key": "Dm",
            "concert_key": "Dm",
            PRACTICE_KEY_BY_SOURCE_KEY: {SHAPE: "Dm"},
        }
        self.assertFalse(retire_mission_left_panel_for_catalog_surface(session))
        self.assertEqual(get_practice_concert_key(session, SHAPE), "Dm")
        session["display_key"] = "Bm"
        session["display_key_change_source"] = "sidebar_on_change"
        set_practice_concert_key(session, "Bm", pick_key=SHAPE)
        self.assertEqual(get_practice_concert_key(session, SHAPE), "Bm")


if __name__ == "__main__":
    unittest.main()
