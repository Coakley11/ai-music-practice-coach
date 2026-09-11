"""H4 owner-switch vs same-owner display_key authority."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backing_context import BackingContext, restore_regular_song_backing, set_backing_context
from song_catalog.catalog import format_pick_key
from songs.key_state import (
    DISPLAY_KEY_OWNER_TRANSITION_KEY,
    DISPLAY_KEY_WIDGET_OWNER_ID_KEY,
    apply_display_key_owner_transition_if_needed,
    begin_display_key_owner_transition,
    note_display_key_widget_owner,
    resolve_display_key_widget_owner_id,
)
from songs.practice_key_state import get_practice_concert_key, set_practice_concert_key
from source_session_state import bind_sidebar_practice_key_to_backing_owner
from tests.test_human_h1_h9_authority import TestH3StaleSnapshotDoesNotOutrankUuidBlob, _St

SAY_PICK = format_pick_key("Pop", "Say — John Mayer")


def _say_song() -> dict:
    return {
        "title": "Say",
        "artist": "John Mayer",
        "key": "G",
        "pick_key": SAY_PICK,
        "bpm": 82,
        "sections": {"Verse": ["G", "C", "Em", "D"]},
    }


class TestH4OwnerTransitionBoundary(unittest.TestCase):
    def test_a_jam_eb_to_catalog_say_is_g(self) -> None:
        helper = TestH3StaleSnapshotDoesNotOutrankUuidBlob()
        session, jam_id = helper._session_uuid_eb_stale_snap_c()
        session["active_catalog_pick_key"] = SAY_PICK
        session["selected_song"] = _say_song()
        session["display_key"] = "Eb"
        session["concert_key"] = "Eb"
        session["practice_key_by_source"] = {SAY_PICK: "G"}
        session[DISPLAY_KEY_WIDGET_OWNER_ID_KEY] = f"entry_jam::{jam_id}"
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            with patch(
                "songs.music_source.resolve_catalog_song_for_pick",
                return_value=(_say_song(), "G"),
            ):
                ctx = restore_regular_song_backing(session, st_like=st_like)
        self.assertEqual(ctx.source, "regular_song")
        rec = session.get(DISPLAY_KEY_OWNER_TRANSITION_KEY)
        self.assertIsInstance(rec, dict)
        self.assertTrue(str(rec.get("canonical") or "").startswith("G"), rec)
        self.assertTrue(str(rec.get("stale") or "").startswith("Eb"), rec)
        tok = bind_sidebar_practice_key_to_backing_owner(_St(session), session)
        self.assertTrue(str(tok).startswith("G"), tok)
        self.assertTrue(str(session.get("display_key") or "").startswith("G"))
        self.assertEqual(str(get_practice_concert_key(session, SAY_PICK) or ""), "G")

    def test_b_jam_uuid_remains_eb(self) -> None:
        from music_workflow_state_store import get_workflow_blob

        helper = TestH3StaleSnapshotDoesNotOutrankUuidBlob()
        session, jam_id = helper._session_uuid_eb_stale_snap_c()
        session["active_catalog_pick_key"] = SAY_PICK
        session["selected_song"] = _say_song()
        session["display_key"] = "Eb"
        session["practice_key_by_source"] = {SAY_PICK: "G"}
        session[DISPLAY_KEY_WIDGET_OWNER_ID_KEY] = f"entry_jam::{jam_id}"
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            with patch(
                "songs.music_source.resolve_catalog_song_for_pick",
                return_value=(_say_song(), "G"),
            ):
                restore_regular_song_backing(session, st_like=st_like)
        live = get_workflow_blob(session, "jam_session_generator", jam_id)
        assert live is not None
        self.assertEqual(str(live.keys.practice_tonic), "Eb")

    def test_next_run_remounted_eb_does_not_stamp_say(self) -> None:
        helper = TestH3StaleSnapshotDoesNotOutrankUuidBlob()
        session, jam_id = helper._session_uuid_eb_stale_snap_c()
        session["active_catalog_pick_key"] = SAY_PICK
        session["selected_song"] = _say_song()
        session["display_key"] = "Eb"
        session["practice_key_by_source"] = {SAY_PICK: "G"}
        session[DISPLAY_KEY_WIDGET_OWNER_ID_KEY] = f"entry_jam::{jam_id}"
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            with patch(
                "songs.music_source.resolve_catalog_song_for_pick",
                return_value=(_say_song(), "G"),
            ):
                restore_regular_song_backing(session, st_like=st_like)
        session["display_key"] = "Eb"
        session["concert_key"] = "Eb"
        applied = apply_display_key_owner_transition_if_needed(session)
        self.assertTrue(str(applied).startswith("G"), applied)
        set_practice_concert_key(session, "Eb", pick_key=SAY_PICK)
        self.assertEqual(str(get_practice_concert_key(session, SAY_PICK) or ""), "G")
        tok = bind_sidebar_practice_key_to_backing_owner(_St(session), session)
        self.assertTrue(str(tok).startswith("G"), tok)
        self.assertFalse(str(session.get("display_key") or "").startswith("Eb"))

    def test_d_same_owner_catalog_g_to_a_wins(self) -> None:
        session = {
            "studio_page": "backing",
            "display_key": "A",
            "concert_key": "A",
            "active_catalog_pick_key": SAY_PICK,
            "practice_key_by_source": {SAY_PICK: "G"},
            "selected_song": _say_song(),
        }
        set_backing_context(
            session,
            BackingContext(
                source="regular_song",
                source_label="Catalog song",
                active_song_id=SAY_PICK,
                bound_pick_key=SAY_PICK,
                song_title="Say",
                key="G",
                display_key="A",
                concert_key="A",
                bpm=82,
                style="",
                groove="Pop groove",
            ),
        )
        note_display_key_widget_owner(session)
        self.assertEqual(resolve_display_key_widget_owner_id(session), f"catalog::{SAY_PICK}")
        self.assertIsNone(session.get(DISPLAY_KEY_OWNER_TRANSITION_KEY))
        from backing_context import BACKING_PREF_CATALOG, set_backing_source_preference
        from songs.practice_key_state import CREATIVE_JAM_SESSION_PICK

        set_backing_source_preference(session, BACKING_PREF_CATALOG)
        session["improv_entry_mode"] = "Jam Session Generator"
        session["practice_key_by_source"][CREATIVE_JAM_SESSION_PICK] = "Eb"
        set_practice_concert_key(session, "A", pick_key=SAY_PICK, allow_restore_original=True)
        self.assertEqual(str(get_practice_concert_key(session, SAY_PICK) or ""), "A")
        self.assertEqual(str(get_practice_concert_key(session, CREATIVE_JAM_SESSION_PICK) or ""), "Eb")

    def test_stale_eb_is_not_catalog_input_during_transition(self) -> None:
        session = {
            "studio_page": "backing",
            "display_key": "Eb",
            "active_catalog_pick_key": SAY_PICK,
            "practice_key_by_source": {SAY_PICK: "G"},
            "selected_song": _say_song(),
        }
        set_backing_context(
            session,
            BackingContext(
                source="regular_song",
                source_label="Catalog song",
                active_song_id=SAY_PICK,
                bound_pick_key=SAY_PICK,
                song_title="Say",
                key="G",
                display_key="Eb",
                concert_key="Eb",
                bpm=82,
                style="",
                groove="Pop groove",
            ),
        )
        begin_display_key_owner_transition(
            session,
            new_owner_id=f"catalog::{SAY_PICK}",
            canonical="G",
            stale="Eb",
        )
        set_practice_concert_key(session, "Eb", pick_key=SAY_PICK)
        self.assertEqual(str(get_practice_concert_key(session, SAY_PICK) or ""), "G")

    def test_e_mission_key_does_not_leak_to_catalog(self) -> None:
        session = {
            "studio_page": "backing",
            "display_key": "Cm",
            "concert_key": "Cm",
            "improv_mission_concert_key": "Cm",
            "improv_active_mission": "chord-tones",
            "active_catalog_pick_key": SAY_PICK,
            "selected_song": _say_song(),
            "practice_key_by_source": {SAY_PICK: "G"},
            DISPLAY_KEY_WIDGET_OWNER_ID_KEY: "mission::chord-tones",
            "backing_context": {
                "source": "mission",
                "display_key": "Cm",
                "concert_key": "Cm",
                "key": "Cm",
                "mission_id": "chord-tones",
            },
        }
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            with patch(
                "songs.music_source.resolve_catalog_song_for_pick",
                return_value=(_say_song(), "G"),
            ):
                ctx = restore_regular_song_backing(session, st_like=st_like)
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(str(get_practice_concert_key(session, SAY_PICK) or ""), "G")
        tok = bind_sidebar_practice_key_to_backing_owner(_St(session), session)
        self.assertTrue(str(tok).startswith("G"), tok)
        self.assertFalse(str(tok).startswith("C"), tok)

    def test_f_sbi_temporary_key_does_not_leak_to_catalog(self) -> None:
        session = {
            "studio_page": "backing",
            "display_key": "F",
            "concert_key": "F",
            "active_catalog_pick_key": SAY_PICK,
            "selected_song": _say_song(),
            "practice_key_by_source": {SAY_PICK: "G"},
            DISPLAY_KEY_WIDGET_OWNER_ID_KEY: f"song_improv::{SAY_PICK}",
            "backing_context": {
                "source": "song_improv",
                "display_key": "F",
                "concert_key": "F",
                "key": "F",
                "bound_pick_key": SAY_PICK,
            },
        }
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            with patch(
                "songs.music_source.resolve_catalog_song_for_pick",
                return_value=(_say_song(), "G"),
            ):
                ctx = restore_regular_song_backing(session, st_like=st_like)
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(str(get_practice_concert_key(session, SAY_PICK) or ""), "G")
        tok = bind_sidebar_practice_key_to_backing_owner(_St(session), session)
        self.assertTrue(str(tok).startswith("G"), tok)

    def test_return_regular_clears_sbi_handoff_so_hydrate_does_not_reclaim(self) -> None:
        from backing_context import get_backing_context
        from backing_session_route import navigate_to_regular_backing
        from backing_source_navigation import hydrate_backing_source_for_page
        from song_catalog.catalog import format_pick_key

        shape_pick = format_pick_key("Pop", "Shape of You")
        shape_song = {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": shape_pick,
            "bpm": 82,
            "sections": {"Verse": ["Bm", "Em", "G", "A"]},
        }
        session = {
            "studio_page": "backing",
            "display_key": "Bm",
            "concert_key": "Bm",
            "active_catalog_pick_key": shape_pick,
            "selected_song": dict(shape_song),
            "practice_key_by_source": {shape_pick: "Bm"},
            "_backing_explicit_handoff_source": "song_improv",
            "_last_valid_backing_source": "song_improv",
            DISPLAY_KEY_WIDGET_OWNER_ID_KEY: f"song_improv::{shape_pick}",
        }
        set_backing_context(
            session,
            BackingContext(
                source="song_improv",
                source_label="Song-Based Improvisation",
                active_song_id=shape_pick,
                bound_pick_key=shape_pick,
                song_title="Shape of You",
                key="Bm",
                display_key="Bm",
                concert_key="Bm",
                bpm=82,
                style="Pop groove",
                groove="Pop groove",
            ),
        )
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            with patch(
                "songs.music_source.resolve_catalog_song_for_pick",
                return_value=(shape_song, "Bm"),
            ):
                navigate_to_regular_backing(session, st_like=st_like)
                hydrate_backing_source_for_page(session, st_like=st_like)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        self.assertEqual(str(getattr(ctx, "source", "") or ""), "regular_song")
        self.assertNotEqual(str(session.get("_backing_explicit_handoff_source") or ""), "song_improv")
        self.assertEqual(str(session.get("_last_valid_backing_source") or ""), "regular_song")
        self.assertTrue(str(session.get("display_key") or "").startswith("B"))

    def test_g_catalog_to_jam_uses_jam_key(self) -> None:
        helper = TestH3StaleSnapshotDoesNotOutrankUuidBlob()
        session, jam_id = helper._session_uuid_eb_stale_snap_c()
        session["display_key"] = "G"
        session["concert_key"] = "G"
        session["practice_key_by_source"] = {SAY_PICK: "G"}
        session["active_catalog_pick_key"] = SAY_PICK
        session[DISPLAY_KEY_WIDGET_OWNER_ID_KEY] = f"catalog::{SAY_PICK}"
        applied = apply_display_key_owner_transition_if_needed(session)
        self.assertTrue(str(applied).startswith("Eb"), applied)
        self.assertTrue(str(session.get("display_key") or "").startswith("Eb"))
        self.assertEqual(str(get_practice_concert_key(session, SAY_PICK) or ""), "G")

    def test_h_jam_catalog_jam_keeps_separate_keys(self) -> None:
        from music_workflow_state_store import get_workflow_blob

        helper = TestH3StaleSnapshotDoesNotOutrankUuidBlob()
        session, jam_id = helper._session_uuid_eb_stale_snap_c()
        session["active_catalog_pick_key"] = SAY_PICK
        session["selected_song"] = _say_song()
        session["display_key"] = "Eb"
        session["practice_key_by_source"] = {SAY_PICK: "G"}
        session[DISPLAY_KEY_WIDGET_OWNER_ID_KEY] = f"entry_jam::{jam_id}"
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            with patch(
                "songs.music_source.resolve_catalog_song_for_pick",
                return_value=(_say_song(), "G"),
            ):
                restore_regular_song_backing(session, st_like=st_like)
        self.assertEqual(str(get_practice_concert_key(session, SAY_PICK) or ""), "G")
        session.pop(DISPLAY_KEY_OWNER_TRANSITION_KEY, None)
        session.pop("_specialized_practice_token_leaving", None)
        session.pop("_specialized_leave_catalog_pk", None)
        set_backing_context(
            session,
            BackingContext(
                source="entry_jam",
                source_label="Jam Session Generator",
                entry_mode="Jam Session Generator",
                jam_id=jam_id,
                active_song_id=jam_id,
                song_title="Jam Session",
                key="Eb",
                display_key="G",
                concert_key="G",
                bpm=70,
                style="Bossa Nova",
                groove="Ballad",
            ),
        )
        applied = apply_display_key_owner_transition_if_needed(session)
        self.assertTrue(str(applied).startswith("Eb"), applied)
        live = get_workflow_blob(session, "jam_session_generator", jam_id)
        assert live is not None
        self.assertEqual(str(live.keys.practice_tonic), "Eb")
        self.assertEqual(str(get_practice_concert_key(session, SAY_PICK) or ""), "G")

    def test_i_catalog_refresh_after_return_does_not_reopen_jam(self) -> None:
        from backing_context import (
            BACKING_PREF_CATALOG,
            creative_nested_backing_should_override_catalog,
            get_backing_context,
            set_backing_source_preference,
        )
        from backing_source_navigation import hydrate_backing_source_for_page
        from music_workflow_state_store import get_workflow_blob

        helper = TestH3StaleSnapshotDoesNotOutrankUuidBlob()
        session, jam_id = helper._session_uuid_eb_stale_snap_c()
        session["active_catalog_pick_key"] = SAY_PICK
        session["selected_song"] = _say_song()
        session["display_key"] = "Eb"
        session["concert_key"] = "Eb"
        session["practice_key_by_source"] = {SAY_PICK: "G"}
        session[DISPLAY_KEY_WIDGET_OWNER_ID_KEY] = f"entry_jam::{jam_id}"
        session["improv_intelligence_tab"] = "Entry & Jam"
        session["improv_entry_mode"] = "Jam Session Generator"
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            with patch(
                "songs.music_source.resolve_catalog_song_for_pick",
                return_value=(_say_song(), "G"),
            ):
                restore_regular_song_backing(session, st_like=st_like)
        set_backing_source_preference(session, BACKING_PREF_CATALOG)
        # Browser refresh drops one-shot latches; leftover Jam tab/session remain.
        session.pop("_backing_released_specialized_context", None)
        session.pop("_backing_open_intent", None)
        session.pop("_backing_explicit_handoff_source", None)
        session.pop(DISPLAY_KEY_OWNER_TRANSITION_KEY, None)
        session.pop("backing_context", None)
        self.assertFalse(creative_nested_backing_should_override_catalog(session))
        with patch("backing_track_state.write_canonical_backing_state"):
            hydrate_backing_source_for_page(session, st_like=st_like)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        self.assertEqual(str(getattr(ctx, "source", "") or ""), "regular_song")
        self.assertTrue(str(session.get("display_key") or "").startswith("G"))
        self.assertEqual(str(get_practice_concert_key(session, SAY_PICK) or ""), "G")
        live = get_workflow_blob(session, "jam_session_generator", jam_id)
        assert live is not None
        self.assertEqual(str(live.keys.practice_tonic), "Eb")


class TestOwner13SameOwnerStickyBeatsStaleCanonical(unittest.TestCase):
    """Leftover landing rec (Original Bm) must not reseed after Shape sticky Dm."""

    def _shape_session(self, *, live: str, sticky: str, canonical: str = "Bm", stale: str = "C") -> dict:
        shape_pick = format_pick_key("Pop", "Shape of You")
        shape_song = {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": shape_pick,
            "bpm": 96,
            "sections": {"Verse": ["Bm", "Em", "G", "A"]},
        }
        return {
            "studio_page": "picker",
            "display_key": live,
            "concert_key": live,
            "active_catalog_pick_key": shape_pick,
            "selected_song": shape_song,
            "practice_key_by_source": {shape_pick: sticky},
            DISPLAY_KEY_WIDGET_OWNER_ID_KEY: f"catalog::{shape_pick}",
            DISPLAY_KEY_OWNER_TRANSITION_KEY: {
                "from": "custom::trial",
                "to": f"catalog::{shape_pick}",
                "canonical": canonical,
                "stale": stale,
            },
            "backing_context": {
                "source": "regular_song",
                "bound_pick_key": shape_pick,
                "display_key": live,
                "concert_key": live,
                "key": live,
            },
            "_shape_pick": shape_pick,
        }

    def test_sticky_dm_clears_stale_bm_rec_and_keeps_dm(self) -> None:
        session = self._shape_session(live="Dm", sticky="Dm")
        returned = apply_display_key_owner_transition_if_needed(session)
        self.assertEqual(returned, "Dm")
        self.assertIsNone(session.get(DISPLAY_KEY_OWNER_TRANSITION_KEY))
        self.assertEqual(str(session.get("display_key") or ""), "Dm")
        self.assertEqual(str(get_practice_concert_key(session, session["_shape_pick"]) or ""), "Dm")

    def test_bad_seed_bm_widget_is_corrected_from_sticky_dm(self) -> None:
        session = self._shape_session(live="Bm", sticky="Dm")
        returned = apply_display_key_owner_transition_if_needed(session)
        self.assertEqual(returned, "Dm")
        self.assertIsNone(session.get(DISPLAY_KEY_OWNER_TRANSITION_KEY))
        self.assertEqual(str(session.get("display_key") or ""), "Dm")

    def test_user_widget_dm_before_sticky_write_is_not_reseeded_to_bm(self) -> None:
        session = self._shape_session(live="Dm", sticky="Bm")
        returned = apply_display_key_owner_transition_if_needed(session)
        self.assertEqual(returned, "")
        self.assertIsNone(session.get(DISPLAY_KEY_OWNER_TRANSITION_KEY))
        self.assertEqual(str(session.get("display_key") or ""), "Dm")
        self.assertEqual(str(get_practice_concert_key(session, session["_shape_pick"]) or ""), "Bm")

    def test_stale_jam_token_still_seeds_catalog_canonical(self) -> None:
        session = self._shape_session(live="C#", sticky="Bm", canonical="Bm", stale="C#")
        session["_specialized_practice_token_leaving"] = "C#"
        returned = apply_display_key_owner_transition_if_needed(session)
        self.assertEqual(returned, "Bm")
        self.assertEqual(str(session.get("display_key") or ""), "Bm")
        rec = session.get(DISPLAY_KEY_OWNER_TRANSITION_KEY)
        self.assertIsInstance(rec, dict)
        self.assertEqual(str(rec.get("canonical") or ""), "Bm")


if __name__ == "__main__":
    unittest.main()
