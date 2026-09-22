"""Practice Key lifecycle: same-song nav preserves; song switch resets to Original."""

from __future__ import annotations

import unittest

from composition_document import (
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
from composition_session_state import save_document_to_library, set_active_document
from composition_songs_bridge import (
    composition_home_key,
    composition_pick_key_for,
    commit_composition_active_song,
    activate_composition_by_pick_key,
)
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    SOURCE_CATALOG,
    SOURCE_COMPOSITION,
    USER_CATALOG_SOURCE_CHOICE_KEY,
    commit_catalog_active_song,
    commit_explicit_music_source_choice,
)
from songs.practice_key_state import get_practice_concert_key, set_practice_concert_key
from music_source_ownership import _finalize_catalog_backing_context


class _FakeSt:
    def __init__(self, ss: dict):
        self.session_state = ss

    def rerun(self) -> None:
        return None


def _g_doc(title: str = "Pending Key Test") -> dict:
    doc = bootstrap_from_vision(
        genre="Pop",
        song_idea="lifecycle",
        title=title,
        key="G major",
        bpm=100,
    )
    apply_structure_template(doc, "simple")
    apply_section_chords(doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste("G C Em D"))
    return doc


class TestPracticeKeyLifecycle(unittest.TestCase):
    def test_fresh_composition_practice_is_home(self) -> None:
        ss: dict = {}
        doc = _g_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        pick = composition_pick_key_for(doc)
        self.assertEqual(composition_home_key(doc), "G")
        self.assertEqual(get_practice_concert_key(ss, pick) or "G", "G")
        self.assertEqual(str(ss.get("display_key") or ""), "G")

    def test_same_song_nav_keeps_practice_a(self) -> None:
        ss: dict = {}
        doc = _g_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=pick)
        ss["display_key"] = "A"
        ss["concert_key"] = "A"
        ss["studio_page"] = "backing"
        # Same pick remount / ensure without reset oneshot.
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=False)
        self.assertEqual(get_practice_concert_key(ss, pick), "A")
        self.assertEqual(composition_home_key(doc), "G")

    def test_composition_to_shape_resets_to_bm(self) -> None:
        ss: dict = {}
        doc = _g_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=pick)
        ss["display_key"] = "A"
        ss["concert_key"] = "A"

        shape_pick = "Pop\x1fShape of You"
        shape_sel = {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": shape_pick,
            "sections": {"Verse": ["Bm", "Em"]},
        }
        commit_explicit_music_source_choice(ss, SOURCE_CATALOG)
        ss[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=shape_pick,
            selected_song=shape_sel,
            original_key="Bm",
            display_key="A",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        self.assertEqual(str(ss.get("display_key") or ""), "Bm")
        self.assertNotEqual(get_practice_concert_key(ss, shape_pick) or "Bm", "A")
        # Old Composition sticky cleared so return does not resurrect A.
        self.assertFalse(bool(get_practice_concert_key(ss, pick)))

    def test_shape_practice_cm_does_not_overwrite_original_bm(self) -> None:
        from types import SimpleNamespace

        ctx = SimpleNamespace(
            bound_pick_key="",
            active_song_id="",
            song_title="",
            key="",
            concert_key="",
            display_key="",
            bpm=96,
            groove="Auto",
            source="",
        )
        selected = {"title": "Shape of You", "key": "Bm"}
        out = _finalize_catalog_backing_context(
            ctx,
            pick_key="Pop\x1fShape of You",
            selected=selected,
            original_key="Bm",
            practice_key="Cm",
            bpm=96,
            groove="Auto",
        )
        self.assertEqual(out.key, "Bm")
        self.assertEqual(out.concert_key, "Cm")
        self.assertEqual(out.display_key, "Cm")

    def test_return_to_composition_resets_to_g_not_a(self) -> None:
        ss: dict = {}
        doc = _g_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=pick)

        shape_pick = "Pop\x1fShape of You"
        ss["active_catalog_pick_key"] = shape_pick
        ss[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG
        commit_explicit_music_source_choice(ss, SOURCE_CATALOG)
        # Explicit re-select Composition after Catalog.
        activate_composition_by_pick_key(_FakeSt(ss), pick)
        self.assertEqual(str(ss.get("display_key") or ""), "A")
        self.assertEqual(get_practice_concert_key(ss, pick) or "", "A")

    def test_catalog_say_to_shape_resets_shape_to_bm(self) -> None:
        ss: dict = {}
        say_pick = "Pop\x1fSay — John Mayer"
        say_sel = {
            "title": "Say",
            "artist": "John Mayer",
            "key": "G",
            "pick_key": say_pick,
            "sections": {"Verse": ["G", "C"]},
        }
        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=say_pick,
            selected_song=say_sel,
            original_key="G",
            display_key="G",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        set_practice_concert_key(ss, "A", pick_key=say_pick)
        ss["display_key"] = "A"

        shape_pick = "Pop\x1fShape of You"
        shape_sel = {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": shape_pick,
            "sections": {"Verse": ["Bm", "Em"]},
        }
        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=shape_pick,
            selected_song=shape_sel,
            original_key="Bm",
            display_key="A",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        self.assertEqual(str(ss.get("display_key") or ""), "Bm")
        self.assertFalse(bool(get_practice_concert_key(ss, say_pick)))

    def test_shape_then_say_resets_say_to_g(self) -> None:
        ss: dict = {}
        shape_pick = "Pop\x1fShape of You"
        shape_sel = {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": shape_pick,
            "sections": {"Verse": ["Bm", "Em"]},
        }
        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=shape_pick,
            selected_song=shape_sel,
            original_key="Bm",
            display_key="Bm",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        set_practice_concert_key(ss, "Cm", pick_key=shape_pick)
        ss["display_key"] = "Cm"

        say_pick = "Pop\x1fSay — John Mayer"
        say_sel = {
            "title": "Say",
            "artist": "John Mayer",
            "key": "G",
            "pick_key": say_pick,
            "sections": {"Verse": ["G", "C"]},
        }
        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=say_pick,
            selected_song=say_sel,
            original_key="G",
            display_key="Cm",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        self.assertEqual(str(ss.get("display_key") or ""), "G")
        self.assertFalse(bool(get_practice_concert_key(ss, shape_pick)))

    def test_composition_radio_outranks_stale_catalog_hub_stamp(self) -> None:
        from songs.music_source import (
            USER_CATALOG_SOURCE_CHOICE_KEY,
            music_picker_shows_composition_hub,
            song_picker_composition_option_label,
            SONG_PICKER_ACTIVE_SOURCE_KEY,
        )

        ss = {
            SONG_PICKER_ACTIVE_SOURCE_KEY: song_picker_composition_option_label(),
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
        }
        commit_explicit_music_source_choice(ss, SOURCE_CATALOG)
        ss[SONG_PICKER_ACTIVE_SOURCE_KEY] = song_picker_composition_option_label()
        self.assertTrue(music_picker_shows_composition_hub(ss))

    def test_explicit_practice_change_writes_shape_sticky(self) -> None:
        from backing_practice_key_control import commit_backing_practice_key
        from backing_context import BackingContext, set_backing_context, get_backing_context

        ss: dict = {}
        shape_pick = "Pop\x1fShape of You"
        shape_sel = {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": shape_pick,
            "sections": {"Verse": ["Bm", "Em"]},
        }
        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=shape_pick,
            selected_song=shape_sel,
            original_key="Bm",
            display_key="Bm",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        ctx = BackingContext(
            source="regular_song",
            source_label="Catalog song",
            active_song_id=shape_pick,
            song_title="Shape of You",
            key="Bm",
            concert_key="Bm",
            display_key="Bm",
            bpm=96,
            style="Pop",
            groove="Auto",
            bound_pick_key=shape_pick,
        )
        set_backing_context(ss, ctx)
        ss["studio_page"] = "backing"
        commit_backing_practice_key(ss, "C#m")
        self.assertEqual(get_practice_concert_key(ss, shape_pick), "C#m")
        self.assertEqual(str(ss.get("display_key") or ""), "C#m")
        live = get_backing_context(ss)
        self.assertIsNotNone(live)
        assert live is not None
        self.assertEqual(str(live.key or ""), "Bm")
        self.assertEqual(str(live.concert_key or ""), "C#m")

    def test_same_pick_catalog_remount_preserves_c_sharp_m(self) -> None:
        ss: dict = {}
        shape_pick = "Pop\x1fShape of You"
        shape_sel = {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": shape_pick,
            "sections": {"Verse": ["Bm", "Em"]},
        }
        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=shape_pick,
            selected_song=shape_sel,
            original_key="Bm",
            display_key="Bm",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        set_practice_concert_key(ss, "C#m", pick_key=shape_pick, allow_restore_original=True)
        ss["display_key"] = "C#m"
        ss["concert_key"] = "C#m"
        # Same-pick remount (Backing → Songs) must not reset to Bm.
        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=shape_pick,
            selected_song=shape_sel,
            original_key="Bm",
            display_key="Bm",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        self.assertEqual(get_practice_concert_key(ss, shape_pick), "C#m")
        self.assertEqual(str(ss.get("display_key") or ""), "C#m")

    def test_backing_musical_state_prefers_sticky_over_sealed_original(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from backing_musical_state import resolve_current_backing_musical_state

        ss: dict = {}
        shape_pick = "Pop\x1fShape of You"
        ss["active_catalog_pick_key"] = shape_pick
        ss[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG
        ss["display_key"] = "C#m"
        ss["concert_key"] = "C#m"
        set_practice_concert_key(ss, "C#m", pick_key=shape_pick, allow_restore_original=True)
        ctx = BackingContext(
            source="regular_song",
            source_label="Catalog song",
            active_song_id=shape_pick,
            song_title="Shape of You",
            key="Bm",
            concert_key="Bm",
            display_key="Bm",
            bpm=96,
            style="Pop",
            groove="Auto",
            bound_pick_key=shape_pick,
        )
        set_backing_context(ss, ctx)
        state = resolve_current_backing_musical_state(
            ss,
            rec={"title": "Shape of You", "key": "Bm", "pick_key": shape_pick},
        )
        self.assertEqual(state.practice_concert_key, "C#m")

    def test_finalize_keeps_original_bm_when_practice_c_sharp_m(self) -> None:
        from types import SimpleNamespace

        ctx = SimpleNamespace(
            bound_pick_key="",
            active_song_id="",
            song_title="",
            key="",
            concert_key="",
            display_key="",
            bpm=96,
            groove="Auto",
            source="",
        )
        out = _finalize_catalog_backing_context(
            ctx,
            pick_key="Pop\x1fShape of You",
            selected={"title": "Shape of You", "key": "Bm"},
            original_key="Bm",
            practice_key="C#m",
            bpm=96,
            groove="Auto",
        )
        self.assertEqual(out.key, "Bm")
        self.assertEqual(out.concert_key, "C#m")


if __name__ == "__main__":
    unittest.main()
