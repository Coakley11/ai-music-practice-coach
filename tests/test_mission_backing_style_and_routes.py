"""Mission Jam style resolution, backing route separation, upload route precedence."""

from __future__ import annotations

import struct
import unittest
from typing import Any
from unittest.mock import patch

from backing_context import build_mission_context, open_backing_from_creative, set_backing_context
from backing_session_route import (
    deactivate_mission_backing_ui_state,
    mission_backing_ui_allowed,
    on_creative_backing_handoff,
    sync_backing_session_route_from_context,
)
from mission_song_backing_style import (
    NEUTRAL_FALLBACK_GROOVE,
    clear_mission_jam_style_user_override,
    resolve_mission_jam_backing_style,
    set_mission_jam_style_user_override,
    sync_mission_style_from_song,
    use_song_style_for_mission_jam,
)
from pending_upload_route_precedence import (
    pending_upload_should_restore_analysis_page,
    resolve_pending_upload_studio_page,
)
from improvisation_missions import MISSION_PRACTICE_LICK_KEY


def _hevenu_song_data() -> dict[str, Any]:
    return {
        "title": "Hevenu Shalom Aleichem",
        "genre": "Jewish",
        "extensions": {
            "default_bpm": 72,
            "default_groove": "Jewish ballad",
            "time_signature": "4/4",
        },
        "sections": {"Melody A": ["Dm"]},
    }


def _tone_wav() -> bytes:
    pcm = b"\x00\x01" * 200
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(pcm),
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        44100,
        88200,
        2,
        16,
        b"data",
        len(pcm),
    )
    return header + pcm


class TestMissionSongBackingStyle(unittest.TestCase):
    def test_hevenu_not_jazz_swing_from_stale_session(self) -> None:
        session: dict[str, Any] = {
            "improv_style": "Jazz Swing",
            "improv_groove": "Jazz swing",
            "active_catalog_pick_key": "Jewish|Hevenu Shalom Aleichem",
        }
        with patch(
            "mission_song_backing_style._song_row_for_mission",
            return_value=(_hevenu_song_data(), "catalog", session["active_catalog_pick_key"]),
        ):
            resolved = sync_mission_style_from_song(session)
        self.assertEqual(resolved.groove, "Jewish ballad")
        self.assertEqual(resolved.source, "song_metadata")
        self.assertNotEqual(resolved.groove.lower(), "jazz swing")
        self.assertTrue(resolved.stale_replaced)

    def test_two_songs_different_styles(self) -> None:
        a = _hevenu_song_data()
        b = {
            "title": "Blue Bossa",
            "genre": "Jazz",
            "extensions": {"default_groove": "Bossa nova", "default_bpm": 120},
        }
        session: dict[str, Any] = {"active_catalog_pick_key": "k1"}
        with patch("mission_song_backing_style._song_row_for_mission", return_value=(a, "catalog", "k1")):
            g1 = resolve_mission_jam_backing_style(session).groove
        with patch("mission_song_backing_style._song_row_for_mission", return_value=(b, "catalog", "k2")):
            g2 = resolve_mission_jam_backing_style({**session, "active_catalog_pick_key": "k2"}).groove
        self.assertNotEqual(g1, g2)

    def test_user_override_and_use_song_style(self) -> None:
        session: dict[str, Any] = {"active_catalog_pick_key": "k1", "improv_style": "Jazz Swing"}
        with patch(
            "mission_song_backing_style._song_row_for_mission",
            return_value=(_hevenu_song_data(), "catalog", "k1"),
        ):
            set_mission_jam_style_user_override(session, style="Funk groove", groove="Funk groove")
            r1 = resolve_mission_jam_backing_style(session)
            self.assertEqual(r1.source, "explicit_user_override")
            use_song_style_for_mission_jam(session)
            r2 = resolve_mission_jam_backing_style(session)
        self.assertEqual(r2.source, "song_metadata")
        self.assertEqual(r2.groove, "Jewish ballad")

    def test_missing_metadata_uses_neutral_fallback(self) -> None:
        session: dict[str, Any] = {"active_catalog_pick_key": "k", "improv_style": "Jazz Swing"}
        with patch(
            "mission_song_backing_style._song_row_for_mission",
            return_value=({"title": "Unknown"}, "catalog", "k"),
        ):
            r = resolve_mission_jam_backing_style(session)
        self.assertEqual(r.source, "fallback")
        self.assertEqual(r.groove, NEUTRAL_FALLBACK_GROOVE)
        self.assertNotEqual(r.groove.lower(), "jazz swing")


class TestBackingSessionRoute(unittest.TestCase):
    def _session_with_lick(self) -> dict[str, Any]:
        return {
            MISSION_PRACTICE_LICK_KEY: {"motif": {"notes": ["C"]}, "song_title": "Test"},
            "backing_context": {
                "source": "entry_jam",
                "source_label": "Entry Style Jam",
                "entry_mode": "Style Jam Mode",
                "bpm": 100,
                "groove": "Pop groove",
                "style": "Pop",
                "meter": "4/4",
                "progression": ["C"],
                "progression_label": "C",
            },
        }

    def test_entry_jam_hides_mission_ui_with_stored_lick(self) -> None:
        session = self._session_with_lick()
        on_creative_backing_handoff(session, source="entry_jam")
        self.assertFalse(mission_backing_ui_allowed(session))

    def test_mission_backing_shows_mission_ui(self) -> None:
        session = self._session_with_lick()
        session["backing_context"]["source"] = "mission"
        on_creative_backing_handoff(session, source="mission")
        self.assertTrue(mission_backing_ui_allowed(session))

    def test_route_types(self) -> None:
        session = self._session_with_lick()
        sync_backing_session_route_from_context(session)
        route = session.get("backing_session_route") or {}
        self.assertEqual(route.get("backing_session_type"), "entry_jam")


class TestPendingUploadRoutePrecedence(unittest.TestCase):
    def test_prepared_envelope_wins_over_backing_blob(self) -> None:
        env = {
            "take_id": "t1",
            "analysis_status": "prepared",
            "active_destination_page": "analysis",
            "navigation": {
                "resume_upload_analysis": True,
                "studio_page": "analysis",
                "route_lock": True,
            },
        }
        session: dict[str, Any] = {
            "studio_page": "backing",
            "pending_upload_analysis_envelope": env,
        }
        blob = {"music_workspace_state": {"studio_page": "backing"}}
        self.assertTrue(pending_upload_should_restore_analysis_page(session, blob))
        page, reason = resolve_pending_upload_studio_page(session, blob) or ("", "")
        self.assertEqual(page, "analysis")
        self.assertEqual(reason, "pending_upload_analysis")

    def test_handoff_persists_navigation_block(self) -> None:
        from mission_upload_handoff import handoff_mission_take_to_upload_analysis

        session: dict[str, Any] = {
            "improv_active_mission": "Develop one motif",
            "ii_selected_chord": "Em",
            "creative_workspace_state": {},
        }
        wav = _tone_wav()

        def _fake_persist(_st, _rid, audio, **kwargs):
            return {
                "ok": True,
                "storage_ref": "x",
                "local_path": "y.wav",
                "playback_status": "playable",
            }

        with patch("media_storage.persist_recording_audio", side_effect=_fake_persist), patch(
            "music_persistent_state.force_save_music_state",
            side_effect=lambda st, reason="": (
                st.session_state.__setitem__("_suite_persist_last_save_cloud", True) or True
            ),
        ):
            with patch("media_storage.load_recording_audio", return_value=(wav, "ok")):
                st_like = type("St", (), {"session_state": session})()
                ok, _ = handoff_mission_take_to_upload_analysis(
                    session, audio_bytes=wav, filename="t.wav", source="live", st=st_like
                )
                self.assertTrue(ok)
        nav = (session.get("pending_upload_analysis_envelope") or {}).get("navigation") or {}
        self.assertTrue(nav.get("resume_upload_analysis"))
        self.assertEqual(nav.get("studio_page"), "analysis")
        self.assertTrue(nav.get("route_lock"))


class TestBuildMissionContextStyle(unittest.TestCase):
    def test_build_mission_context_uses_song_groove(self) -> None:
        session: dict[str, Any] = {
            "improv_style": "Jazz Swing",
            "improv_groove": "Jazz swing",
            "improv_active_mission": "m1",
            "active_catalog_pick_key": "Jewish|Hevenu Shalom Aleichem",
            "ii_selected_chord": "Dm",
            "ii_selected_chord_index": 0,
            "song": "Hevenu Shalom Aleichem",
        }
        with patch(
            "mission_song_backing_style._song_row_for_mission",
            return_value=(_hevenu_song_data(), "catalog", session["active_catalog_pick_key"]),
        ):
            ctx = build_mission_context(session)
        self.assertEqual(ctx.groove, "Jewish ballad")


if __name__ == "__main__":
    unittest.main()
