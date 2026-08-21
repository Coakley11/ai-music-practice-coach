"""Creative Experience polish — catalog/custom picker + mission backing handoff."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backing_context import build_mission_context, open_backing_from_creative
from songs.music_source import (
    LAST_CATALOG_STATE_KEY,
    LAST_CUSTOM_STATE_KEY,
    PENDING_CATALOG_FROM_PICKER_KEY,
    SONG_PICKER_SOURCE_CATALOG,
    SONG_PICKER_SOURCE_CUSTOM,
    SOURCE_CUSTOM,
    apply_pending_catalog_from_picker_before_widgets,
    music_picker_shows_custom_hub,
    reconcile_music_picker_source_widget,
    switch_to_catalog_from_custom,
)


class TestCatalogCustomPickerSwitch(unittest.TestCase):
    def test_stale_catalog_radio_does_not_auto_queue_pending_without_user_flip(self) -> None:
        """Songs page must not treat refresh stale radio as Custom→Catalog flip (E5)."""
        from songs.music_source import LAST_RECONCILED_SONG_PICKER_SOURCE_KEY

        session = {
            "active_music_source": SOURCE_CUSTOM,
            "active_catalog_pick_key": "custom::trial",
            "song_picker_active_source": SONG_PICKER_SOURCE_CATALOG,
            # No LAST_RECONCILED Custom — this is restore/refresh, not a user flip.
            LAST_RECONCILED_SONG_PICKER_SOURCE_KEY: SONG_PICKER_SOURCE_CATALOG,
        }
        reconcile_music_picker_source_widget(session)
        self.assertFalse(session.get(PENDING_CATALOG_FROM_PICKER_KEY))
        self.assertEqual(session.get("song_picker_active_source"), SONG_PICKER_SOURCE_CUSTOM)
        self.assertEqual(session.get("active_music_source"), SOURCE_CUSTOM)

    def test_user_catalog_flag_blocks_lagging_custom_radio_reclaim(self) -> None:
        """After hub catalog switch, lagging Custom radio must not undo Country Roads (E5 reverse)."""
        from songs.music_source import (
            SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            reconcile_picker_music_source,
        )

        session = {
            "studio_page": "picker",
            "active_music_source": SOURCE_CATALOG,
            "active_catalog_pick_key": "Country\x1fTake Me Home, Country Roads — John Denver",
            "song_picker_active_source": SONG_PICKER_SOURCE_CUSTOM,
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
        }
        reconcile_picker_music_source(session)
        self.assertTrue(session.get(USER_CATALOG_SOURCE_CHOICE_KEY))
        self.assertEqual(session.get("active_music_source"), SOURCE_CATALOG)
        self.assertEqual(session.get("song_picker_active_source"), SONG_PICKER_SOURCE_CATALOG)
        self.assertFalse(str(session.get("active_catalog_pick_key") or "").startswith("custom::"))

    def test_reconcile_queues_catalog_switch_on_user_flip_custom_to_catalog(self) -> None:
        """Explicit PENDING/USER_CATALOG keeps Catalog; lagging radio alone must not reclaim."""
        from songs.music_source import (
            LAST_RECONCILED_SONG_PICKER_SOURCE_KEY,
            USER_CATALOG_SOURCE_CHOICE_KEY,
        )

        # Lag after custom activate: heal to Custom, do not queue PENDING.
        session = {
            "active_music_source": SOURCE_CUSTOM,
            "active_catalog_pick_key": "custom::my-song",
            "song_picker_active_source": SONG_PICKER_SOURCE_CATALOG,
            LAST_RECONCILED_SONG_PICKER_SOURCE_KEY: SONG_PICKER_SOURCE_CUSTOM,
        }
        reconcile_music_picker_source_widget(session)
        self.assertFalse(session.get(PENDING_CATALOG_FROM_PICKER_KEY))
        self.assertEqual(session.get("song_picker_active_source"), SONG_PICKER_SOURCE_CUSTOM)

        # Deliberate flip already queued.
        session = {
            "active_music_source": SOURCE_CUSTOM,
            "active_catalog_pick_key": "custom::my-song",
            "song_picker_active_source": SONG_PICKER_SOURCE_CATALOG,
            LAST_RECONCILED_SONG_PICKER_SOURCE_KEY: SONG_PICKER_SOURCE_CUSTOM,
            PENDING_CATALOG_FROM_PICKER_KEY: True,
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
        }
        reconcile_music_picker_source_widget(session)
        self.assertTrue(session.get(PENDING_CATALOG_FROM_PICKER_KEY))
        self.assertEqual(session.get("song_picker_active_source"), SONG_PICKER_SOURCE_CATALOG)

    def test_music_picker_shows_catalog_when_radio_catalog(self) -> None:
        session = {
            "active_music_source": SOURCE_CUSTOM,
            "song_picker_active_source": SONG_PICKER_SOURCE_CATALOG,
        }
        self.assertFalse(music_picker_shows_custom_hub(session))

    def test_switch_to_catalog_restores_last_catalog_state(self) -> None:
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

        active = {"name": "My Custom", "original_sections": {"Verse": []}, "id": "c1"}
        st = SimpleNamespace(
            session_state={
                "active_music_source": SOURCE_CUSTOM,
                "cpl_active_progression": active,
                ACTIVE_CATALOG_PICK_KEY: "custom::my-song",
                LAST_CUSTOM_STATE_KEY: {"name": "My Custom", "active": active},
                LAST_CATALOG_STATE_KEY: {
                    "pick_key": "Pop::Perfect — Ed Sheeran",
                    "original_key": "G",
                    "display_key": "G",
                    "selected_song": {
                        "pick_key": "Pop::Perfect — Ed Sheeran",
                        "title": "Perfect",
                        "artist": "Ed Sheeran",
                        "key": "G",
                    },
                },
                "song_picker_active_source": SONG_PICKER_SOURCE_CATALOG,
            }
        )
        catalog = {
            "Pop": {
                "Perfect — Ed Sheeran": {"title": "Perfect", "artist": "Ed Sheeran", "key": "G"},
            }
        }

        def _apply_pick_key(_st, pick_key, song_picker_catalog, **kwargs):
            genre, title = pick_key.split("::", 1)
            data = song_picker_catalog[genre][title]
            _st.session_state[SELECTED_SONG_STATE_KEY] = {"pick_key": pick_key, **data}
            return dict(data)

        with patch("songs.state.apply_pick_key", side_effect=_apply_pick_key):
            with patch("songs.state.persist_music_local_state"):
                with patch("songs.music_source.on_active_song_identity_changed"):
                    with patch("songs.music_source.note_active_source_change"):
                        ok = switch_to_catalog_from_custom(
                            st,
                            song_picker_catalog=catalog,
                            invalidate_backing=lambda _s: None,
                        )
        self.assertTrue(ok)
        self.assertEqual(
            st.session_state[ACTIVE_CATALOG_PICK_KEY],
            "Pop::Perfect — Ed Sheeran",
        )


class TestMissionSingleChordBacking(unittest.TestCase):
    def test_mission_context_uses_selected_chord_only(self) -> None:
        session = {
            "active_catalog_pick_key": "pop::Song — Artist",
            "song": "Song",
            "display_key": "G",
            "improv_active_mission": "Target tone drill",
            "ii_selected_chord": "Am7",
            "II_SELECTED_SECTION": "Verse",
            "improv_style_meta": {"bpm": 92, "groove": "Pop groove", "style": "Pop"},
            "improv_mission_progression": ["Dm7", "G7", "Cmaj7"],
        }
        ctx = build_mission_context(session)
        self.assertEqual(ctx.progression, ["Am7"])
        self.assertEqual(session.get("improv_mission_progression"), ["Am7"])
        self.assertEqual(ctx.section, "Verse")
        self.assertEqual(ctx.scope, "Mission chord")

    def test_mission_context_uses_chord_index_when_names_repeat(self) -> None:
        session = {
            "active_catalog_pick_key": "pop::Shape — Artist",
            "song": "Shape of You",
            "display_key": "F#m",
            "improv_active_mission": "Target tone drill",
            "ii_selected_chord": "A",
            "ii_selected_section": "Chorus",
            "ii_selected_chord_index": 7,
            "improv_mission_chord_options": ["Bm", "Em", "G", "A"] * 2,
            "improv_style_meta": {"bpm": 96, "groove": "Pop groove", "style": "Pop"},
        }
        ctx = build_mission_context(session)
        self.assertEqual(ctx.progression, ["A"])
        self.assertEqual(ctx.section, "Chorus")
        self.assertEqual(ctx.progression_label, "Chorus · A")

    def test_open_backing_from_mission_loops_one_chord(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "G",
            "improv_active_mission": "ii–V–I drill",
            "ii_selected_chord": "G7",
            "II_SELECTED_SECTION": "Chorus",
            "improv_style_meta": {"bpm": 90, "groove": "Medium", "style": "Pop"},
        }
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            ctx = open_backing_from_creative(session, source="mission", st_like=st_like)
        self.assertEqual(ctx.progression, ["G7"])
        self.assertEqual(ctx.scope, "Mission chord")


class TestMissionCreativeBackingSections(unittest.TestCase):
    def test_resolve_creative_sections_single_chord_for_mission(self) -> None:
        from creative_session_state import resolve_creative_backing_sections, sync_creative_session_from_session

        session = {
            "active_catalog_pick_key": "pop::Song — Artist",
            "song": "Shape of You",
            "display_key": "F#m",
            "improv_active_mission": "Target tone drill",
            "ii_selected_chord": "A",
            "ii_selected_section": "Chorus",
            "ii_selected_chord_index": 3,
            "improv_mission_chord_options": ["Bm", "Em", "G", "A"],
            "improv_intelligence_tab": "Missions",
            "improv_style_meta": {"bpm": 96, "groove": "Pop groove", "style": "Pop"},
        }
        with patch("backing_track_state.write_canonical_backing_state"):
            open_backing_from_creative(session, source="mission")
        sync_creative_session_from_session(session)
        sections = resolve_creative_backing_sections(session)
        self.assertEqual(list(sections.values()), [["A"]])
