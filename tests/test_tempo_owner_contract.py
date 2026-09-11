"""Owner-specific tempo contract: Catalog / Style Jam / Custom isolation."""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace

from backing_context import (
    BackingContext,
    format_backing_context_banner,
    get_backing_context,
    open_backing_from_creative,
    refresh_backing_context_from_session,
    set_backing_context,
)
from backing_play_session import (
    BACKING_PLAY_SESSION_EXPIRED_KEY,
    BACKING_PLAY_SESSION_KEY,
    capture_backing_play_session_overrides,
    current_backing_play_bpm,
    get_backing_play_session,
    promote_live_slider_bpm_to_current,
    seal_live_backing_tempo_for_persist,
    sync_backing_play_session_on_backing_page,
)
from music_workflow_generated_session import commit_style_jam_generation
from songs.bpm_state import BPM_WIDGET_KEY
from songs.playback_defaults import backing_bpm_slider_widget_key
from song_catalog.catalog import format_pick_key


SHAPE_PICK = format_pick_key("Pop", "Shape of You — Ed Sheeran")
SAY_PICK = format_pick_key("Pop", "Say — John Mayer")
SAY_SLIDER = backing_bpm_slider_widget_key(f"pk::{SAY_PICK}")
SHAPE_SLIDER = backing_bpm_slider_widget_key(f"pk::{SHAPE_PICK}")
STYLE_SECTIONS = {
    "Head (Jazz Swing)": ["Gm7", "C7", "Fmaj7", "D7"],
    "Bridge (Jazz Swing)": ["Gm7", "C7", "Am7", "D7", "Gm7", "C7", "Fmaj7", "Fmaj7"],
}


class _FakeSt:
    def __init__(self, session: dict):
        self.session_state = session


def _style_jam_with_say_leftover(*, jam_bpm: int = 60) -> dict:
    session = {
        "studio_page": "creative",
        "improv_entry_mode": "Style Jam Mode",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_style": "Jazz Swing",
        "improv_mood": "Bright",
        "improv_groove": "Light",
        "improv_style_bpm": jam_bpm,
        "improv_difficulty": "Beginner",
        "improv_style_key": "F",
        "improv_generated_sections": copy.deepcopy(STYLE_SECTIONS),
        "improv_style_meta": {
            "style": "Jazz Swing",
            "bpm": jam_bpm,
            "groove": "Light",
            "key": "F",
            "mood": "Bright",
            "entry_mode": "Style Jam Mode",
        },
        "active_catalog_pick_key": SHAPE_PICK,
        "song": "Shape of You",
        "display_key": "F",
        "concert_key": "F",
        "instrument": "Piano",
        "backing_track_bpm": 82,
        BPM_WIDGET_KEY: 82,
        "bpm": 82,
        "_backing_catalog_default_bpm": 96,
        "_active_bpm_sync_id": f"pk::{SAY_PICK}",
        "_backing_page_bpm_sync_id": f"pk::{SAY_PICK}",
        SAY_SLIDER: 82,
        SHAPE_SLIDER: 96,
        BACKING_PLAY_SESSION_EXPIRED_KEY: False,
        BACKING_PLAY_SESSION_KEY: {
            "play_session_id": "catalog-say",
            "launch_id": "catalog-launch",
            "source_identity": f"pk::{SAY_PICK}",
            "expired": False,
            "defaults": {"bpm": 82, "groove": "Ballad", "meter": "4/4"},
            "overrides": {},
        },
    }
    commit_style_jam_generation(
        session,
        key_center="F",
        style="Jazz Swing",
        section_map=copy.deepcopy(STYLE_SECTIONS),
        mood="Bright",
        groove="Light",
        tempo_bpm=jam_bpm,
        new_session=True,
    )
    return session


def _trial_custom() -> dict:
    return {
        "id": "custom::trial",
        "name": "Trial Song",
        "original_key_center": "D",
        "original_sections": {
            "Verse": [{"chord": "D", "bars": 4}, {"chord": "A", "bars": 4}],
        },
        "bpm": 100,
        "progression_style": "Pop",
        "groove_style": "Pop groove",
    }


class TestStyleJamTempoDoesNotInheritCatalog(unittest.TestCase):
    def test_catalog_cannot_initialize_style_jam_after_ownership(self) -> None:
        session = _style_jam_with_say_leftover(jam_bpm=60)
        st = _FakeSt(session)
        open_backing_from_creative(session, source="entry_jam", st_like=st)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        self.assertEqual(str(ctx.source), "entry_jam")
        self.assertEqual(str(ctx.entry_mode), "Style Jam Mode")
        self.assertEqual(str(ctx.concert_key or ctx.key), "F")
        self.assertIn("Fmaj7", list(ctx.progression or []))
        session["studio_page"] = "backing"
        sync_backing_play_session_on_backing_page(session)
        promote_live_slider_bpm_to_current(session)
        current = int(current_backing_play_bpm(session, default=0) or 0)
        self.assertEqual(current, 60)
        self.assertEqual(int(session.get("backing_track_bpm") or 0), 60)
        self.assertEqual(int(session.get("improv_style_bpm") or 0), 60)
        banner = format_backing_context_banner(ctx, applied_bpm=current)
        self.assertIn("60 BPM", banner)
        self.assertNotIn("82 BPM", banner)
        self.assertEqual(int(session.get(SAY_SLIDER) or 0), 82)

    def test_style_jam_bpm_does_not_overwrite_catalog_say(self) -> None:
        session = _style_jam_with_say_leftover(jam_bpm=60)
        st = _FakeSt(session)
        open_backing_from_creative(session, source="entry_jam", st_like=st)
        self.assertEqual(int(session.get(SAY_SLIDER) or 0), 82)
        self.assertEqual(int(session.get(SHAPE_SLIDER) or 0), 96)
        self.assertEqual(int(current_backing_play_bpm(session, default=0) or 0), 60)

    def test_style_jam_tempo_change_does_not_change_owner_key_progression(self) -> None:
        session = _style_jam_with_say_leftover(jam_bpm=60)
        st = _FakeSt(session)
        open_backing_from_creative(session, source="entry_jam", st_like=st)
        session["studio_page"] = "backing"
        sync_backing_play_session_on_backing_page(session)
        before_prog = list((get_backing_context(session) or BackingContext(source="entry_jam")).progression or [])
        capture_backing_play_session_overrides(session, bpm=72)
        ctx = get_backing_context(session)
        self.assertEqual(str(ctx.source), "entry_jam")
        self.assertEqual(str(ctx.concert_key or ctx.key), "F")
        self.assertEqual(list(ctx.progression or []), before_prog)
        self.assertEqual(int(current_backing_play_bpm(session, default=0) or 0), 72)
        self.assertEqual(int(session.get(SAY_SLIDER) or 0), 82)


class TestCustomTempoPersistsThroughRefresh(unittest.TestCase):
    def test_custom_edited_bpm_persists_and_rejects_catalog_or_jam(self) -> None:
        from songs.music_source import custom_pick_key_for, custom_selected_song_record
        from songs.state import apply_saved_custom_pick_key_context

        active = _trial_custom()
        pick = custom_pick_key_for(active)
        selected = custom_selected_song_record(active)
        session = {
            "studio_page": "backing",
            "active_music_source": "custom_progression",
            "active_catalog_pick_key": pick,
            "selected_song": selected,
            "song": "Trial Song",
            "display_key": "D",
            "concert_key": "D",
            "cpl_active_progression": copy.deepcopy(active),
            "backing_track_bpm": 100,
            "improv_style_bpm": 60,
            "improv_jam_bpm": 60,
            SAY_SLIDER: 82,
            SHAPE_SLIDER: 96,
            "backing_track_bpm::style_jam::x": 60,
        }
        set_backing_context(
            session,
            BackingContext(
                source="custom_progression",
                source_label="Custom progression",
                active_song_id=pick,
                bound_pick_key=pick,
                song_title="Trial Song",
                key="D",
                display_key="D",
                concert_key="D",
                bpm=100,
                style="Pop",
                groove="Pop groove",
                custom_revision_id=str(active.get("id") or ""),
            ),
        )
        starting = int(current_backing_play_bpm(session, default=100) or 0)
        self.assertGreater(starting, 0)
        capture_backing_play_session_overrides(session, bpm=128)
        self.assertEqual(int(current_backing_play_bpm(session, default=0) or 0), 128)
        capture_backing_play_session_overrides(session, bpm=104)
        self.assertEqual(int(current_backing_play_bpm(session, default=0) or 0), 104)
        sync_backing_play_session_on_backing_page(session)
        promote_live_slider_bpm_to_current(session)
        self.assertEqual(int(current_backing_play_bpm(session, default=0) or 0), 104)
        st = SimpleNamespace(session_state=session)
        apply_saved_custom_pick_key_context(
            st,
            pick,
            {"display_key": "D", "pick_key": pick},
            song_picker_catalog={},
        )
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        self.assertEqual(str(ctx.source), "custom_progression")
        self.assertEqual(str(ctx.song_title), "Trial Song")
        self.assertEqual(int(current_backing_play_bpm(session, default=0) or 0), 104)
        refreshed = refresh_backing_context_from_session(session)
        self.assertIsNotNone(refreshed)
        self.assertEqual(str(refreshed.source), "custom_progression")
        self.assertEqual(int(current_backing_play_bpm(session, default=0) or 0), 104)
        self.assertEqual(int(refreshed.bpm), 104)
        self.assertEqual(int(session.get("cpl_active_progression", {}).get("bpm") or 0), 100)
        self.assertEqual(int(session.get(SAY_SLIDER) or 0), 82)
        self.assertEqual(int(session.get("backing_track_bpm::style_jam::x") or 0), 60)
        self.assertEqual(session["cpl_active_progression"]["original_sections"]["Verse"][0]["chord"], "D")

    def test_stale_override_cannot_win_over_live_current_on_persist(self) -> None:
        """First Custom divergence: live 104 must seal over leftover override 128."""
        from songs.music_source import custom_pick_key_for, custom_selected_song_record
        from studio_page_persistence import save_page_snapshot

        active = _trial_custom()
        pick = custom_pick_key_for(active)
        slider = backing_bpm_slider_widget_key(f"custom::{pick}")
        session = {
            "studio_page": "backing",
            "active_music_source": "custom_progression",
            "active_catalog_pick_key": pick,
            "selected_song": custom_selected_song_record(active),
            "song": "Trial Song",
            "display_key": "D",
            "concert_key": "D",
            "cpl_active_progression": copy.deepcopy(active),
            "backing_track_bpm": 100,
            SAY_SLIDER: 82,
            "improv_style_bpm": 60,
        }
        set_backing_context(
            session,
            BackingContext(
                source="custom_progression",
                source_label="Custom progression",
                active_song_id=pick,
                bound_pick_key=pick,
                song_title="Trial Song",
                key="D",
                display_key="D",
                concert_key="D",
                bpm=100,
                style="Pop",
                groove="Pop groove",
                custom_revision_id=str(active.get("id") or ""),
            ),
        )
        capture_backing_play_session_overrides(session, bpm=128)
        session["backing_track_bpm"] = 104
        session["bpm"] = 104
        session[slider] = 104
        session["_backing_current_bpm_lock"] = 128
        bag = get_backing_play_session(session) or {}
        ov = dict(bag.get("overrides") or {})
        ov["bpm"] = 128
        bag["overrides"] = ov
        session[BACKING_PLAY_SESSION_KEY] = bag
        self.assertEqual(int(current_backing_play_bpm(session, default=0) or 0), 104)
        save_page_snapshot(session, "backing")
        sealed = int(
            ((get_backing_play_session(session) or {}).get("overrides") or {}).get("bpm") or 0
        )
        self.assertEqual(sealed, 104)
        self.assertEqual(int(seal_live_backing_tempo_for_persist(session) or 0), 104)
        session.pop(slider, None)
        session.pop(BPM_WIDGET_KEY, None)
        session["backing_track_bpm"] = 0
        session["bpm"] = 0
        refreshed = refresh_backing_context_from_session(session)
        self.assertIsNotNone(refreshed)
        self.assertEqual(str(refreshed.source), "custom_progression")
        self.assertEqual(str(refreshed.song_title), "Trial Song")
        self.assertEqual(str(refreshed.concert_key or refreshed.key), "D")
        self.assertEqual(int(current_backing_play_bpm(session, default=0) or 0), 104)
        self.assertEqual(int(refreshed.bpm), 104)
        self.assertEqual(int(session.get(SAY_SLIDER) or 0), 82)
        self.assertEqual(int(session.get("improv_style_bpm") or 0), 60)
        self.assertEqual(int(session.get("cpl_active_progression", {}).get("bpm") or 0), 100)

        session["backing_track_bpm"] = 96
        session["bpm"] = 96
        session["_backing_catalog_default_bpm"] = 96
        session[SHAPE_SLIDER] = 96
        session["_backing_current_bpm_lock"] = 104
        self.assertEqual(int(seal_live_backing_tempo_for_persist(session) or 0), 104)
        self.assertEqual(
            int(((get_backing_play_session(session) or {}).get("overrides") or {}).get("bpm") or 0),
            104,
        )

    def test_custom_tempo_change_does_not_change_owner_key_progression(self) -> None:
        from songs.music_source import custom_pick_key_for, custom_selected_song_record

        active = _trial_custom()
        pick = custom_pick_key_for(active)
        session = {
            "studio_page": "backing",
            "active_music_source": "custom_progression",
            "active_catalog_pick_key": pick,
            "selected_song": custom_selected_song_record(active),
            "display_key": "D",
            "concert_key": "D",
            "cpl_active_progression": copy.deepcopy(active),
            "backing_track_bpm": 100,
        }
        set_backing_context(
            session,
            BackingContext(
                source="custom_progression",
                source_label="Custom progression",
                active_song_id=pick,
                bound_pick_key=pick,
                song_title="Trial Song",
                key="D",
                display_key="D",
                concert_key="D",
                bpm=100,
                style="Pop",
                groove="Pop groove",
                custom_revision_id=str(active.get("id") or ""),
            ),
        )
        prog = copy.deepcopy(session["cpl_active_progression"]["original_sections"])
        capture_backing_play_session_overrides(session, bpm=104)
        ctx = get_backing_context(session)
        self.assertEqual(str(ctx.source), "custom_progression")
        self.assertEqual(str(ctx.concert_key or ctx.key), "D")
        self.assertEqual(session["cpl_active_progression"]["original_sections"], prog)
        self.assertEqual(str(session.get("active_music_source")), "custom_progression")


if __name__ == "__main__":
    unittest.main()
