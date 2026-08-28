"""Regressions from the broader Creative live-draft sweep (A–I).

Covers:
- leftover Custom active_song_state must not seize catalog GA
- Active SBI card must not show Trial title + Shape chords
- Missions concert map rebuilds when Songs Practice Key moved
- Missions caption must not respell LAST_CUSTOM D as catalog Dm
"""

from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from improvisation_intelligence_ui import _catalog_live_key_or_empty
from music_workflow_song_practice import (
    ensure_missions_parent_practice_key_hydrated,
    ensure_song_practice_blob_for_active_song,
    rebuild_concert_map_if_practice_key_mismatch,
)
from songs.music_source import (
    LAST_CUSTOM_STATE_KEY,
    SOURCE_CATALOG,
    SOURCE_CUSTOM,
    custom_progression_is_active,
)
from songs.practice_key_state import set_practice_concert_key
from source_session_state import resolve_sbi_preview


PK_SHAPE = "Pop\x1fShape of You"
BM = {"Verse": ["C#m", "F#m", "A", "B"]}
FM = {"Verse": ["Fm", "Bbm", "Db", "Eb"]}


def _trial() -> dict:
    return {
        "id": "trial-live-1",
        "name": "Trial Song",
        "original_key_center": "D",
        "original_sections": {
            "Verse": [
                {"chord": "Em", "bars": 1},
                {"chord": "Em", "bars": 1},
                {"chord": "D", "bars": 1},
                {"chord": "D", "bars": 1},
            ],
        },
    }


def _shape_session(*, practice_key: str = "Fm") -> dict:
    trial = _trial()
    return {
        "studio_page": "creative",
        "improv_intelligence_tab": "Missions",
        "active_catalog_pick_key": PK_SHAPE,
        "song": "Shape of You",
        "display_key": practice_key,
        "concert_key": practice_key,
        "selected_song": {
            "pick_key": PK_SHAPE,
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "sections": copy.deepcopy(BM),
        },
        "home_sections": copy.deepcopy(BM),
        "practice_key_by_source": {PK_SHAPE: practice_key},
        "catalog_session": {
            "pick_key": PK_SHAPE,
            "selected_song": {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "key": "Bm",
                "sections": copy.deepcopy(BM),
            },
            "display_key": practice_key,
            "original_key": "Bm",
        },
        LAST_CUSTOM_STATE_KEY: {
            "name": "Trial Song",
            "pick_key": "custom::trial-live-1",
            "custom_home_key": "D",
            "active": trial,
        },
        "improv_song_source": "Active song",
        "sbi_preview_source": "Active song",
        "active_song_state": {
            "music_source": SOURCE_CUSTOM,
            "pick_key": "custom::trial-live-1",
        },
    }


class TestCatalogPickOutranksLeftoverCustomState(unittest.TestCase):
    def test_unset_source_plus_catalog_pick_is_not_custom_ga(self) -> None:
        session = _shape_session()
        # Visiting Custom Lab left active_song_state on custom:: but never
        # Set as Active — source key is unset, live pick is Shape.
        session.pop("active_music_source", None)
        self.assertFalse(custom_progression_is_active(session))

    def test_explicit_catalog_source_still_false(self) -> None:
        session = _shape_session()
        session["active_music_source"] = SOURCE_CATALOG
        self.assertFalse(custom_progression_is_active(session))

    def test_explicit_custom_ga_still_true(self) -> None:
        session = _shape_session()
        session["active_music_source"] = SOURCE_CUSTOM
        session["active_catalog_pick_key"] = "custom::trial-live-1"
        self.assertTrue(custom_progression_is_active(session))


class TestActiveSbiPreviewNotTrialTitle(unittest.TestCase):
    def test_active_radio_plus_catalog_pick_is_shape_not_trial(self) -> None:
        session = _shape_session(practice_key="Bm")
        session.pop("active_music_source", None)
        session["improv_song_concert_sections"] = copy.deepcopy(BM)
        preview = resolve_sbi_preview(session)
        self.assertEqual(preview.get("title"), "Shape of You")
        self.assertNotEqual(preview.get("title"), "Trial Song")
        flat = [c for chs in (preview.get("sections") or {}).values() for c in chs]
        self.assertTrue(flat)
        self.assertNotIn("184", str(len(flat)))


class TestMissionMapFollowsSongsPracticeKey(unittest.TestCase):
    def test_rebuild_fm_blob_when_store_moved_to_dm(self) -> None:
        session = _shape_session(practice_key="Dm")
        session["active_music_source"] = SOURCE_CATALOG
        session["improv_song_concert_sections"] = copy.deepcopy(FM)
        set_practice_concert_key(session, "Dm", pick_key=PK_SHAPE)
        ensure_song_practice_blob_for_active_song(
            session, practice_key="Dm", original_key="Bm"
        )
        # Pollute the blob map at the previous Fm visit.
        from music_workflow_song_practice import song_practice_blob

        blob = song_practice_blob(session)
        self.assertIsNotNone(blob)
        assert blob is not None
        blob.section_map = copy.deepcopy(FM)
        from music_workflow_state_store import save_workflow_blob

        save_workflow_blob(session, blob, source="test_stale_fm")
        session["improv_song_concert_sections"] = copy.deepcopy(FM)

        with patch(
            "songs.music_source.catalog_chart_sections_for_pick",
            return_value=copy.deepcopy(BM),
        ):
            rebuilt = rebuild_concert_map_if_practice_key_mismatch(session, "Dm")
        first = ""
        for chs in rebuilt.values():
            if chs:
                first = str(chs[0])
                break
        self.assertIn(first, {"Em", "Dm"})
        self.assertNotEqual(first, "Fm")

    def test_hydrate_does_not_keep_fm_map_after_songs_dm(self) -> None:
        session = _shape_session(practice_key="Dm")
        session["active_music_source"] = SOURCE_CATALOG
        session["improv_song_concert_sections"] = copy.deepcopy(FM)
        set_practice_concert_key(session, "Dm", pick_key=PK_SHAPE)
        ensure_song_practice_blob_for_active_song(
            session, practice_key="Dm", original_key="Bm"
        )
        from music_workflow_song_practice import song_practice_blob
        from music_workflow_state_store import save_workflow_blob

        blob = song_practice_blob(session)
        assert blob is not None
        blob.section_map = copy.deepcopy(FM)
        save_workflow_blob(session, blob, source="test_stale_fm_hydrate")

        with patch(
            "songs.music_source.catalog_chart_sections_for_pick",
            return_value=copy.deepcopy(BM),
        ):
            token = ensure_missions_parent_practice_key_hydrated(session)
        self.assertTrue(str(token or "").upper().startswith("D"))
        raw = session.get("improv_song_concert_sections") or {}
        first = ""
        for chs in raw.values():
            if isinstance(chs, list) and chs:
                first = str(chs[0])
                break
        self.assertNotEqual(first, "Fm")


class TestMissionCaptionIgnoresLastCustomD(unittest.TestCase):
    def test_trial_d_is_not_adopted_as_catalog_live_key(self) -> None:
        session = _shape_session(practice_key="Fm")
        session["active_music_source"] = SOURCE_CATALOG
        session["display_key"] = "D"
        self.assertEqual(_catalog_live_key_or_empty(session, "D"), "")
        self.assertEqual(_catalog_live_key_or_empty(session, "D major"), "")

    def test_shape_dm_is_not_treated_as_trial_leak(self) -> None:
        session = _shape_session(practice_key="Dm")
        session["active_music_source"] = SOURCE_CATALOG
        self.assertEqual(_catalog_live_key_or_empty(session, "Dm"), "Dm")
        self.assertEqual(_catalog_live_key_or_empty(session, "Fm"), "Fm")


class TestLiveDraftWalkPredicates(unittest.TestCase):
    """Static guard: computed key/owner flags must be required for PASS."""

    def _src(self) -> str:
        from pathlib import Path

        return Path("scripts/_walk_cbs_live_draft.py").read_text(encoding="utf-8")

    def test_key_hits_rejects_lone_letter_e(self) -> None:
        import importlib.util
        from pathlib import Path

        path = Path("scripts/_walk_cbs_live_draft.py")
        spec = importlib.util.spec_from_file_location("_walk_cbs_live_draft", path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        key_hits = mod.key_hits
        self.assertFalse(key_hits("Practice / Concert Key\nEm", "E", "Eb"))
        self.assertTrue(key_hits("Practice / Concert Key\nEb", "Eb", "D#"))
        self.assertTrue(key_hits("F minor", "Fm", "F minor"))
        self.assertFalse(key_hits("A minor", "A major"))

    def test_restore_gates_require_computed_key_flags(self) -> None:
        src = self._src()
        self.assertIn('"PASS" if restored and pk_restored else "RED"', src)
        self.assertIn('"PASS" if ga_ok and ga_pk else "RED"', src)
        self.assertIn('"PASS" if ej_ok and sbi_after and pk_dm else "RED"', src)
        self.assertIn('"PASS" if inst_ok and written_moved else "RED"', src)
        self.assertIn(
            '"PASS" if reboot_songs and reboot_pk and reboot_custom else "RED"', src
        )
        self.assertNotRegex(src, r'has_any\([^)]*"E",\s*"Eb"')
        self.assertNotIn("written_val(page) != written_val", src)
        self.assertNotIn('has_any(body_rbs, "D minor", "Dm", "Shape of You")', src)


if __name__ == "__main__":
    unittest.main()
