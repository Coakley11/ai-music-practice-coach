"""True activation Practice-Key lifetime: reset Original; Case C parks underneath."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from song_catalog.catalog import format_pick_key
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    CATALOG_BEFORE_CUSTOM_KEY,
    LAST_CATALOG_STATE_KEY,
    LAST_CUSTOM_STATE_KEY,
    SOURCE_CATALOG,
    SOURCE_CUSTOM,
    commit_catalog_active_song,
    commit_custom_active_song,
    forget_catalog_visit_practice_key,
    switch_to_catalog_from_custom,
)
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
    set_practice_concert_key,
)
from source_session_state import (
    EXPLICIT_SBI_SOURCE_CLICK_KEY,
    SBI_ACTIVE_LEAVE_INTENT_KEY,
    set_sbi_preview_source,
)


DAUGHTERS = format_pick_key("Pop", "Daughters — John Mayer")
SHAPE = format_pick_key("Pop", "Shape of You — Ed Sheeran")
TRIAL_ID = "trial-activation-lifetime"
TRIAL_PICK = f"custom::{TRIAL_ID}"


class _FakeSt:
    def __init__(self, ss: dict) -> None:
        self.session_state = ss

    def rerun(self) -> None:
        return None


def _daughters_session(practice: str = "D") -> dict:
    return {
        "studio_page": "picker",
        "instrument": "Guitar",
        "selected_song": {
            "title": "Daughters",
            "artist": "John Mayer",
            "genre": "Pop",
            "key": "D",
            "pick_key": DAUGHTERS,
        },
        "active_catalog_pick_key": DAUGHTERS,
        ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
        "original_key": "D",
        "display_key": practice,
        "concert_key": practice,
        PRACTICE_KEY_BY_SOURCE_KEY: {DAUGHTERS: practice, TRIAL_PICK: "F"},
        LAST_CUSTOM_STATE_KEY: {
            "name": "Trial Song",
            "pick_key": TRIAL_PICK,
            "custom_home_key": "D",
            "active": {
                "id": TRIAL_ID,
                "name": "Trial Song",
                "original_key_center": "D",
                "original_sections": {"Verse": [{"chord": "D", "bars": 4}]},
                "bpm": 100,
            },
        },
        "cpl_active_progression": {
            "id": TRIAL_ID,
            "name": "Trial Song",
            "original_key_center": "D",
            "original_sections": {"Verse": [{"chord": "D", "bars": 4}]},
            "bpm": 100,
        },
        CATALOG_BEFORE_CUSTOM_KEY: {
            "pick_key": DAUGHTERS,
            "original_key": "D",
            "selected_song": {
                "title": "Daughters",
                "artist": "John Mayer",
                "key": "D",
                "pick_key": DAUGHTERS,
            },
        },
        LAST_CATALOG_STATE_KEY: {
            "pick_key": DAUGHTERS,
            "original_key": "D",
            "selected_song": {
                "title": "Daughters",
                "artist": "John Mayer",
                "key": "D",
                "pick_key": DAUGHTERS,
            },
        },
        "improv_entry_mode": "Song-Based Improvisation",
        "improv_song_source": "Active song",
        "sbi_preview_source": "Active song",
    }


def _catalog_with_pick(pick: str, title: str, key: str, practice: str) -> dict:
    ss = _daughters_session(practice=practice)
    ss["active_catalog_pick_key"] = pick
    ss["selected_song"] = {
        "title": title,
        "artist": "Ed Sheeran" if "Shape" in title else "John Mayer",
        "genre": "Pop",
        "key": key,
        "pick_key": pick,
    }
    ss["original_key"] = key
    ss["display_key"] = practice
    ss["concert_key"] = practice
    store = dict(ss.get(PRACTICE_KEY_BY_SOURCE_KEY) or {})
    store[pick] = practice
    ss[PRACTICE_KEY_BY_SOURCE_KEY] = store
    return ss


class TestContinuousOwnerManualEditPersists(unittest.TestCase):
    def test_journey1_daughters_e_survives_page_nav_without_source_change(self) -> None:
        ss = _daughters_session(practice="E")
        set_practice_concert_key(ss, "E", pick_key=DAUGHTERS, allow_restore_original=True)
        for page in ("practice", "backing", "creative", "picker"):
            ss["studio_page"] = page
            self.assertEqual(get_practice_concert_key(ss, DAUGHTERS), "E")
            self.assertEqual(str(ss.get("display_key") or ""), "E")
            self.assertEqual(str(ss.get("original_key") or ""), "D")


class TestTemporarySbiPreservesParkedCatalog(unittest.TestCase):
    def test_journey2_custom_sbi_keeps_daughters_e(self) -> None:
        from music_source_ownership import maybe_reset_practice_key_on_source_activation

        ss = _daughters_session(practice="E")
        ss[EXPLICIT_SBI_SOURCE_CLICK_KEY] = "Custom progression"
        set_sbi_preview_source(ss, "Custom progression")
        self.assertFalse(maybe_reset_practice_key_on_source_activation(ss, surface="sbi_custom"))
        self.assertEqual(get_practice_concert_key(ss, DAUGHTERS), "E")
        # Temporary SBI must not run forget_catalog.
        self.assertEqual(str(ss.get(ACTIVE_MUSIC_SOURCE_KEY) or ""), SOURCE_CATALOG)
        ss.pop(EXPLICIT_SBI_SOURCE_CLICK_KEY, None)
        ss[SBI_ACTIVE_LEAVE_INTENT_KEY] = True
        set_sbi_preview_source(ss, "Active song")
        self.assertEqual(get_practice_concert_key(ss, DAUGHTERS), "E")
        self.assertEqual(str(ss.get("display_key") or ""), "E")


class TestTrueSourceSwitchResets(unittest.TestCase):
    def test_journey3_catalog_to_custom_drops_e(self) -> None:
        ss = _daughters_session(practice="E")
        set_practice_concert_key(ss, "E", pick_key=DAUGHTERS, allow_restore_original=True)
        active = dict(ss["cpl_active_progression"])
        commit_custom_active_song(
            _FakeSt(ss),
            active,
            invalidate_backing=lambda *_a, **_k: None,
            reset_practice_to_original=True,
        )
        forget_catalog_visit_practice_key(ss)
        self.assertEqual(str(ss.get(ACTIVE_MUSIC_SOURCE_KEY) or ""), SOURCE_CUSTOM)
        self.assertEqual(str(ss.get("display_key") or ""), "D")
        self.assertEqual(get_practice_concert_key(ss, TRIAL_PICK) or "D", "D")
        self.assertFalse(bool(get_practice_concert_key(ss, DAUGHTERS)))

    def test_journey4_custom_to_catalog_reactivates_daughters_at_d(self) -> None:
        ss = _daughters_session(practice="E")
        set_practice_concert_key(ss, "E", pick_key=DAUGHTERS, allow_restore_original=True)
        active = dict(ss["cpl_active_progression"])
        commit_custom_active_song(
            _FakeSt(ss),
            active,
            invalidate_backing=lambda *_a, **_k: None,
            reset_practice_to_original=True,
        )
        # Simulate poisoned same-pick restore: catalog pick already synced, sticky E leftover.
        ss["active_catalog_pick_key"] = DAUGHTERS
        ss["active_song_state"] = {
            "pick_key": DAUGHTERS,
            "music_source": SOURCE_CATALOG,
        }
        set_practice_concert_key(ss, "E", pick_key=DAUGHTERS, allow_restore_original=True)
        ss["display_key"] = "E"
        ss["concert_key"] = "E"
        # Identity still looks Custom via source flag before switch stamps Catalog.
        ss[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CUSTOM
        ss["active_catalog_pick_key"] = TRIAL_PICK
        ss["active_song_state"] = {"pick_key": TRIAL_PICK, "music_source": SOURCE_CUSTOM}

        catalog = {
            "Pop": {
                "Say — John Mayer": {
                    "title": "Say",
                    "artist": "John Mayer",
                    "key": "G",
                    "sections": {"Verse": ["G", "C"]},
                },
                "Daughters — John Mayer": {
                    "title": "Daughters",
                    "artist": "John Mayer",
                    "key": "D",
                    "sections": {"Verse": ["D", "A"]},
                },
            }
        }
        # Use the real switch path with a stub apply that stamps pick early.
        def _fake_apply(st, pick_key, *args, **kwargs):
            st.session_state["active_catalog_pick_key"] = pick_key
            st.session_state["active_song_state"] = {
                "pick_key": pick_key,
                "music_source": SOURCE_CATALOG,
            }
            return {
                "title": "Daughters",
                "artist": "John Mayer",
                "key": "D",
                "sections": {"Verse": ["D", "A"]},
            }

        with patch("songs.state.apply_pick_key", side_effect=_fake_apply):
            ok = switch_to_catalog_from_custom(
                _FakeSt(ss),
                song_picker_catalog=catalog,
                song_library=catalog,
                invalidate_backing=lambda *_a, **_k: None,
                force=True,
            )
        self.assertTrue(ok)
        self.assertEqual(str(ss.get("display_key") or ""), "D")
        self.assertEqual(get_practice_concert_key(ss, DAUGHTERS) or "D", "D")
        self.assertNotEqual(str(ss.get("display_key") or ""), "E")

    def test_journey5_catalog_song_change_and_reactivation(self) -> None:
        ss = _catalog_with_pick(DAUGHTERS, "Daughters", "D", "E")
        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=DAUGHTERS,
            selected_song=dict(ss["selected_song"]),
            original_key="D",
            display_key="E",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        set_practice_concert_key(ss, "E", pick_key=DAUGHTERS, allow_restore_original=True)
        ss["display_key"] = "E"

        shape_sel = {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": SHAPE,
            "sections": {"Verse": ["Bm", "Em"]},
        }
        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=SHAPE,
            selected_song=shape_sel,
            original_key="Bm",
            display_key="Bm",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        self.assertEqual(str(ss.get("display_key") or ""), "Bm")
        self.assertFalse(bool(get_practice_concert_key(ss, DAUGHTERS)))

        daughters_sel = {
            "title": "Daughters",
            "artist": "John Mayer",
            "key": "D",
            "pick_key": DAUGHTERS,
            "sections": {"Verse": ["D", "A"]},
        }
        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=DAUGHTERS,
            selected_song=daughters_sel,
            original_key="D",
            display_key="D",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        self.assertEqual(str(ss.get("display_key") or ""), "D")
        self.assertEqual(get_practice_concert_key(ss, DAUGHTERS) or "D", "D")


class TestCompositionTrueActivationResets(unittest.TestCase):
    def test_journey7_activate_composition_ignores_prior_sticky(self) -> None:
        from composition_document import (
            apply_section_chords,
            apply_structure_template,
            bootstrap_from_vision,
            ordered_sections,
            parse_chord_paste,
        )
        from composition_session_state import save_document_to_library, set_active_document
        from composition_songs_bridge import (
            activate_composition_by_pick_key,
            composition_home_key,
            composition_pick_key_for,
            commit_composition_active_song,
        )

        ss: dict = {"instrument": "Piano", "display_key": "D", "concert_key": "D"}
        doc = bootstrap_from_vision(
            genre="Pop",
            song_idea="sharp",
            title="Sharp Major Comp",
            key="C# major",
            bpm=100,
        )
        apply_structure_template(doc, "simple")
        apply_section_chords(
            doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste("C# F# G#m B")
        )
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        pick = composition_pick_key_for(doc)
        # Seed stale sticky from a prior activation lifetime.
        set_practice_concert_key(ss, "D", pick_key=pick, allow_restore_original=True)
        # Prior owner looks like Catalog so this is a true source change.
        ss["active_catalog_pick_key"] = DAUGHTERS
        ss[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG

        ok = activate_composition_by_pick_key(_FakeSt(ss), pick)
        self.assertTrue(ok)
        self.assertEqual(composition_home_key(doc), "C#")
        self.assertEqual(str(ss.get("display_key") or ""), "C#")
        self.assertEqual(get_practice_concert_key(ss, pick) or "C#", "C#")

        # Manual edit while continuously active persists.
        set_practice_concert_key(ss, "D", pick_key=pick, allow_restore_original=True)
        ss["display_key"] = "D"
        ss["concert_key"] = "D"
        ok2 = activate_composition_by_pick_key(_FakeSt(ss), pick)
        self.assertTrue(ok2)
        self.assertEqual(str(ss.get("display_key") or ""), "D")

        # True leave to Catalog then reactivate → Original C# again.
        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=DAUGHTERS,
            selected_song={
                "title": "Daughters",
                "artist": "John Mayer",
                "key": "D",
                "pick_key": DAUGHTERS,
            },
            original_key="D",
            display_key="D",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        ok3 = activate_composition_by_pick_key(_FakeSt(ss), pick)
        self.assertTrue(ok3)
        self.assertEqual(str(ss.get("display_key") or ""), "C#")


# Keep import grouping tidy for unittest discovery.


if __name__ == "__main__":
    unittest.main()
