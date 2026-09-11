"""Catalog Gravity must stay owner across Songs → Creative → Upload.

Stale composition:: bound ids / last-catalog snaps must not re-project
My Composition after an explicit Catalog leave + Gravity pick.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

GRAVITY_PICK = "Pop\x1fGravity — John Mayer"
GRAVITY_SEL = {
    "pick_key": GRAVITY_PICK,
    "title": "Gravity",
    "artist": "John Mayer",
    "genre": "Pop",
    "label": "Gravity — John Mayer",
    "key": "G",
}
COMPOSITION_PICK = "composition::f4bf4a14-784d-464f-8394-7b7fcaaa29e3"


class TestCatalogGravityCreativeUploadOwnership(unittest.TestCase):
    def test_catalog_snapshot_rejects_composition_pick(self) -> None:
        from songs.music_source import LAST_CATALOG_STATE_KEY, _catalog_snapshot_from_session

        ss = {
            "active_catalog_pick_key": COMPOSITION_PICK,
            "selected_song": {
                "pick_key": COMPOSITION_PICK,
                "title": "My Composition",
                "artist": "Composition",
                "key": "C",
            },
            "display_key": "C",
        }
        self.assertIsNone(_catalog_snapshot_from_session(ss))
        ss["active_catalog_pick_key"] = GRAVITY_PICK
        ss["selected_song"] = dict(GRAVITY_SEL)
        ss["display_key"] = "G"
        snap = _catalog_snapshot_from_session(ss)
        assert snap is not None
        self.assertEqual(snap["pick_key"], GRAVITY_PICK)
        self.assertEqual(snap["selected_song"]["title"], "Gravity")
        ss[LAST_CATALOG_STATE_KEY] = {
            "pick_key": COMPOSITION_PICK,
            "selected_song": {"title": "My Composition", "pick_key": COMPOSITION_PICK},
        }
        from source_session_state import sync_catalog_session

        synced = sync_catalog_session(ss)
        assert synced is not None
        self.assertEqual(synced["pick_key"], GRAVITY_PICK)
        self.assertNotIn("composition::", str(synced.get("pick_key") or ""))

    def test_get_song_context_catalog_leave_beats_stale_composition_pick(self) -> None:
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY,
            SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY,
        )
        from songs.state import get_song_context

        catalog = {
            "Pop": {
                "Gravity — John Mayer": {
                    "title": "Gravity",
                    "artist": "John Mayer",
                    "key": "G",
                    "sections": {"Verse": ["G", "C"]},
                }
            }
        }
        ss: dict = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "active_catalog_pick_key": COMPOSITION_PICK,
            "selected_song": dict(GRAVITY_SEL),
            "active_song_state": {
                "pick_key": GRAVITY_PICK,
                "music_source": SOURCE_CATALOG,
                "selected_song": dict(GRAVITY_SEL),
                "display_key": "G",
            },
            "display_key": "G",
            "instrument": "Piano",
            "composer_saved_compositions": {},
            "composer_active_document": {
                "id": "f4bf4a14-784d-464f-8394-7b7fcaaa29e3",
                "title": "My Composition",
            },
            "_last_catalog_song_state": {
                "pick_key": COMPOSITION_PICK,
                "selected_song": {
                    "pick_key": COMPOSITION_PICK,
                    "title": "My Composition",
                    "artist": "Composition",
                    "key": "C",
                },
            },
            "_music_restore_phase": "complete",
            "_music_workspace_blob_hydrated": True,
        }
        st = MagicMock()
        st.session_state = ss
        genre, title, data = get_song_context(
            st, song_library=catalog, song_picker_catalog=catalog
        )
        self.assertNotEqual(title, "My Composition")
        self.assertEqual(title, "Gravity")
        self.assertFalse(bool(data.get("is_composition")))

    def test_apply_pick_key_clears_composition_bound_ids(self) -> None:
        from backing_context import get_backing_context, set_backing_context, BackingContext
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY,
            LAST_CATALOG_STATE_KEY,
            SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY,
        )
        from songs.state import apply_pick_key

        catalog = {
            "Pop": {
                "Gravity — John Mayer": {
                    "title": "Gravity",
                    "artist": "John Mayer",
                    "key": "G",
                    "sections": {"Verse": ["G", "C"]},
                    "bpm": 100,
                }
            }
        }
        ss: dict = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "active_catalog_pick_key": COMPOSITION_PICK,
            "selected_song": {
                "pick_key": COMPOSITION_PICK,
                "title": "My Composition",
                "artist": "Composition",
                "key": "C",
            },
            "active_song_state": {
                "pick_key": COMPOSITION_PICK,
                "music_source": "composition_song",
                "display_key": "C",
            },
            "display_key": "C",
            "instrument": "Piano",
            LAST_CATALOG_STATE_KEY: {
                "pick_key": COMPOSITION_PICK,
                "selected_song": {
                    "pick_key": COMPOSITION_PICK,
                    "title": "My Composition",
                },
            },
            "improv_mission_practice_context": {
                "pick_key": COMPOSITION_PICK,
                "song_title": "My Composition",
                "display_key": "C",
            },
        }
        set_backing_context(
            ss,
            BackingContext(
                source="regular_song",
                source_label="Catalog song",
                active_song_id=COMPOSITION_PICK,
                song_title="My Composition",
                key="C",
                display_key="C",
                concert_key="C",
                bpm=96,
                style="",
                groove="Auto",
                section="",
                sections=[],
                scope="Full song",
                loops=2,
                progression=[],
                progression_label="",
                loop=True,
                bound_pick_key=COMPOSITION_PICK,
            ),
        )
        st = SimpleNamespace(session_state=ss)
        data = apply_pick_key(
            st,
            GRAVITY_PICK,
            catalog,
            song_library=catalog,
            skip_activity_log=True,
            persist=False,
        )
        self.assertEqual(data.get("title"), "Gravity")
        self.assertEqual(ss.get("active_catalog_pick_key"), GRAVITY_PICK)
        last = ss.get(LAST_CATALOG_STATE_KEY) or {}
        self.assertEqual(last.get("pick_key"), GRAVITY_PICK)
        ctx = get_backing_context(ss)
        assert ctx is not None
        self.assertEqual(ctx.song_title, "Gravity")
        self.assertFalse(str(ctx.bound_pick_key or "").startswith("composition::"))
        self.assertFalse(str(ctx.active_song_id or "").startswith("composition::"))

    def test_switch_to_catalog_skips_poisoned_last_catalog(self) -> None:
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            LAST_CATALOG_STATE_KEY,
            SOURCE_COMPOSITION,
            CATALOG_RECENT_PICK_KEYS,
            switch_to_catalog_from_custom,
        )

        catalog = {
            "Pop": {
                "Gravity — John Mayer": {
                    "title": "Gravity",
                    "artist": "John Mayer",
                    "key": "G",
                    "sections": {"Verse": ["G"]},
                    "bpm": 100,
                }
            }
        }
        ss: dict = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            "active_catalog_pick_key": COMPOSITION_PICK,
            LAST_CATALOG_STATE_KEY: {
                "pick_key": COMPOSITION_PICK,
                "selected_song": {
                    "pick_key": COMPOSITION_PICK,
                    "title": "My Composition",
                    "key": "C",
                },
                "original_key": "C",
                "display_key": "C",
            },
            CATALOG_RECENT_PICK_KEYS: [GRAVITY_PICK],
            "display_key": "C",
            "instrument": "Piano",
        }
        st = SimpleNamespace(session_state=ss)
        ok = switch_to_catalog_from_custom(
            st,
            song_picker_catalog=catalog,
            song_library=catalog,
            invalidate_backing=lambda _s: None,
        )
        self.assertTrue(ok)
        self.assertEqual(ss.get("active_catalog_pick_key"), GRAVITY_PICK)
        self.assertNotEqual(
            (ss.get(LAST_CATALOG_STATE_KEY) or {}).get("pick_key"),
            COMPOSITION_PICK,
        )


if __name__ == "__main__":
    unittest.main()
