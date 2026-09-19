"""Backing unified source context + Practice Key isolation regressions."""

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
)
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    SOURCE_CATALOG,
    SOURCE_COMPOSITION,
    SONG_PICKER_ACTIVE_SOURCE_KEY,
    USER_CATALOG_SOURCE_CHOICE_KEY,
    commit_catalog_active_song,
    commit_explicit_music_source_choice,
    song_picker_composition_option_label,
)
from songs.practice_key_state import get_practice_concert_key, set_practice_concert_key
from songs.key_state import note_display_key_change


class _FakeSt:
    def __init__(self, ss: dict):
        self.session_state = ss

    def rerun(self) -> None:
        return None


def _g_doc(title: str = "Pending Key Test") -> dict:
    doc = bootstrap_from_vision(
        genre="Pop",
        song_idea="unified context",
        title=title,
        key="G major",
        bpm=100,
    )
    apply_structure_template(doc, "simple")
    apply_section_chords(doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste("G C Em D"))
    return doc


class TestCompositionStickyNotC(unittest.TestCase):
    def test_remount_c_does_not_overwrite_sticky_a(self) -> None:
        ss: dict = {}
        doc = _g_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=pick)
        self.assertEqual(get_practice_concert_key(ss, pick), "A")
        # Remount / hydrate projects generic C — must not wipe sticky A.
        ss["display_key"] = "C"
        ss["concert_key"] = "C"
        ss["_last_app_display_key"] = "A"
        note_display_key_change(_FakeSt(ss), "C")
        self.assertEqual(get_practice_concert_key(ss, pick), "A")
        self.assertEqual(composition_home_key(doc), "G")

    def test_set_practice_c_without_oneshot_refused(self) -> None:
        ss: dict = {}
        doc = _g_doc(title="Refuse C")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=pick)
        set_practice_concert_key(ss, "C", pick_key=pick)
        self.assertEqual(get_practice_concert_key(ss, pick), "A")

    def test_empty_display_apply_does_not_become_c_over_sticky_a(self) -> None:
        """A→C root cause: empty target defaulted to C in _apply_display_key_before_widget."""
        from songs.key_state import (
            IDENTITY_KEY,
            _apply_display_key_before_widget,
            apply_display_key_for_active_song,
            song_display_identity,
        )

        ss: dict = {}
        doc = _g_doc(title="Empty To C")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=pick)
        ss["display_key"] = "A"
        ss["concert_key"] = "A"
        ss["active_catalog_pick_key"] = pick
        st = _FakeSt(ss)
        _apply_display_key_before_widget(st, "", source="active_song_change")
        self.assertEqual(str(ss.get("display_key") or ""), "A")
        self.assertEqual(get_practice_concert_key(ss, pick), "A")
        # Identity remount with blank original must not project C.
        ss[IDENTITY_KEY] = ("other", "", "G")
        apply_display_key_for_active_song(
            st,
            "G",
            song_display_identity("Empty To C", "Composition", "G", pick_key=pick),
        )
        self.assertEqual(get_practice_concert_key(ss, pick), "A")
        self.assertNotEqual(str(ss.get("display_key") or ""), "C")


class TestCatalogDoesNotInheritCompositionA(unittest.TestCase):
    def test_catalog_say_gets_home_not_composition_a(self) -> None:
        ss: dict = {}
        doc = _g_doc(title="Leave A")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=pick)
        ss["display_key"] = "A"
        ss["concert_key"] = "A"

        say_pick = "Pop\x1fSay — John Mayer"
        say_sel = {
            "title": "Say",
            "artist": "John Mayer",
            "key": "G",
            "pick_key": say_pick,
            "sections": {"Verse": ["G", "C"]},
        }
        commit_explicit_music_source_choice(ss, SOURCE_CATALOG)
        ss[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=say_pick,
            selected_song=say_sel,
            original_key="G",
            display_key="A",  # poisoned caller display — must not stick
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        self.assertFalse(bool(get_practice_concert_key(ss, pick)))
        self.assertNotEqual(get_practice_concert_key(ss, say_pick), "A")
        self.assertEqual(str(ss.get("display_key") or ""), "G")


class TestBackingCtxOutranksCompositionStamp(unittest.TestCase):
    def test_open_backing_catalog_ctx_not_overwritten_by_composition_card_path(self) -> None:
        """Simulate the dual-context bug: ctx=regular_song while Composition stamps linger."""
        from backing_context import BackingContext, get_backing_context, set_backing_context
        from backing_source_navigation import open_backing_for_practice_source

        ss: dict = {}
        doc = _g_doc(title="Dual Ctx")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=pick)

        shape_pick = "Pop\x1fShape of You"
        ss[SONG_PICKER_ACTIVE_SOURCE_KEY] = song_picker_composition_option_label()
        ss["active_song_state"] = {"music_source": SOURCE_COMPOSITION, "pick_key": pick}
        ss["active_catalog_pick_key"] = shape_pick
        ss[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        commit_explicit_music_source_choice(ss, SOURCE_CATALOG)
        ss[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG
        ss["display_key"] = "Cm"
        ss["concert_key"] = "Cm"
        set_practice_concert_key(ss, "Cm", pick_key=shape_pick)
        ss["selected_song"] = {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "C#m",
            "pick_key": shape_pick,
        }
        ss["_reconcile_song_picker_catalog"] = {
            "Pop": {
                "Shape of You": {
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "C#m",
                    "sections": {"Verse": ["C#m", "F#m"]},
                }
            }
        }
        ctx = open_backing_for_practice_source(ss, st_like=_FakeSt(ss))
        self.assertIsNotNone(ctx)
        self.assertEqual(getattr(ctx, "source", ""), "regular_song")
        self.assertIn("Shape", str(getattr(ctx, "song_title", "") or ""))
        # Card-path must not rebuild Composition over a Catalog ctx.
        live = get_backing_context(ss)
        self.assertEqual(getattr(live, "source", ""), "regular_song")
        # Simulate what the fixed card gate checks.
        ctx_blocks = getattr(live, "source", "") in {
            "regular_song",
            "custom_progression",
            "song_improv",
            "entry_jam",
            "mission",
        }
        self.assertTrue(ctx_blocks)
        self.assertEqual(get_practice_concert_key(ss, pick), "A")
        self.assertEqual(get_practice_concert_key(ss, shape_pick), "Cm")

    def test_stale_composition_meta_does_not_steal_catalog_chart(self) -> None:
        """Header Catalog + body Composition: chart must follow Catalog pick, not stale meta."""
        from songs.music_source import _session_requests_composition_chart, build_active_chart_bundle

        ss: dict = {}
        doc = _g_doc(title="Pending Key Test")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=pick)

        shape_pick = "Pop\x1fShape of You"
        # Stale Composition identity left behind after Catalog switch.
        ss["selected_song"] = {
            "title": "Pending Key Test",
            "is_composition": True,
            "source": SOURCE_COMPOSITION,
            "pick_key": pick,
        }
        ss["active_song_state"] = {
            "music_source": SOURCE_COMPOSITION,
            "pick_key": pick,
        }
        ss["active_catalog_pick_key"] = shape_pick
        ss[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        commit_explicit_music_source_choice(ss, SOURCE_CATALOG)
        ss[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG
        ss["studio_page"] = "backing"
        ss["display_key"] = "Cm"
        ss["_reconcile_song_picker_catalog"] = {
            "Pop": {
                "Shape of You": {
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "C#m",
                    "sections": {"Verse": ["C#m", "F#m"]},
                }
            }
        }
        self.assertFalse(_session_requests_composition_chart(ss))
        bundle = build_active_chart_bundle(
            ss,
            catalog_genre="Pop",
            catalog_song="Shape of You",
            catalog_song_data={
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "C#m",
                "sections": {"Verse": ["C#m", "F#m"]},
            },
            level="Intermediate",
            display_key="Cm",
            cpl_active_key="cpl_active",
            sections_for_level=lambda sd, _lv: dict(sd.get("sections") or {}),
            transpose_sections=lambda sd, _dk: dict(sd.get("sections") or {}),
            song_picker_catalog=ss["_reconcile_song_picker_catalog"],
            song_library=ss["_reconcile_song_picker_catalog"],
        )
        self.assertEqual(bundle.get("source"), SOURCE_CATALOG)
        self.assertIn("Shape", str(bundle.get("song") or ""))
        self.assertNotIn("Pending", str(bundle.get("song") or ""))
        # Inactive Composition sticky must survive Catalog chart build.
        self.assertEqual(get_practice_concert_key(ss, pick), "A")


if __name__ == "__main__":
    unittest.main()
