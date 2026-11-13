"""Slice 2 — Active Song activation and navigation from Composition Studio.

Tests that:
- _global_active_composition_id returns the right id
- _editing_composition_is_global_active uses the refactored helper
- Library sidebar has Set as Active Song and all nav buttons
- SBI and Jam buttons navigate to Creative
- Activation gating works for Practice / Backing / SBI / Jam
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock


class TestGlobalActiveCompositionId(unittest.TestCase):
    def test_returns_id_when_composition_is_active(self) -> None:
        from composition_document import bootstrap_from_vision
        from composition_songs_bridge import composition_pick_key_for
        from composition_studio_page import _global_active_composition_id
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        doc = bootstrap_from_vision(genre="Pop", song_idea="x", title="T", key="C major", bpm=100)
        doc_id = str(doc.get("id") or "")
        pick = composition_pick_key_for(doc)
        ss: dict = {ACTIVE_CATALOG_PICK_KEY: pick}
        with mock.patch("songs.music_source.composition_song_is_active", return_value=True):
            self.assertEqual(_global_active_composition_id(ss), doc_id)

    def test_returns_empty_when_no_composition_active(self) -> None:
        from composition_studio_page import _global_active_composition_id

        ss: dict = {}
        self.assertEqual(_global_active_composition_id(ss), "")

    def test_returns_empty_when_different_source_active(self) -> None:
        from composition_studio_page import _global_active_composition_id
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        ss: dict = {ACTIVE_CATALOG_PICK_KEY: "catalog::some-song"}
        with mock.patch("songs.music_source.composition_song_is_active", return_value=False):
            self.assertEqual(_global_active_composition_id(ss), "")


class TestEditingGateRefactored(unittest.TestCase):
    def test_editing_active_uses_global_helper(self) -> None:
        from composition_document import bootstrap_from_vision
        from composition_session_state import set_active_document
        from composition_songs_bridge import composition_pick_key_for
        from composition_studio_page import _editing_composition_is_global_active
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        doc = bootstrap_from_vision(genre="Pop", song_idea="x", title="T", key="C major", bpm=100)
        ss: dict = {}
        set_active_document(ss, doc, checkpoint=False)
        self.assertFalse(_editing_composition_is_global_active(ss))

        pick = composition_pick_key_for(doc)
        ss[ACTIVE_CATALOG_PICK_KEY] = pick
        with mock.patch("songs.music_source.composition_song_is_active", return_value=True):
            self.assertTrue(_editing_composition_is_global_active(ss))

    def test_false_when_different_composition_is_active(self) -> None:
        from composition_document import bootstrap_from_vision
        from composition_session_state import set_active_document
        from composition_studio_page import _editing_composition_is_global_active
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        doc = bootstrap_from_vision(genre="Pop", song_idea="x", title="T", key="C major", bpm=100)
        ss: dict = {}
        set_active_document(ss, doc, checkpoint=False)
        ss[ACTIVE_CATALOG_PICK_KEY] = "composition::other-doc-id"
        with mock.patch("songs.music_source.composition_song_is_active", return_value=True):
            self.assertFalse(_editing_composition_is_global_active(ss))


class TestNavButtonKeys(unittest.TestCase):
    def test_all_nav_buttons_present_in_source(self) -> None:
        src = Path("composition_studio_page.py").read_text(encoding="utf-8")
        for key in (
            "composer_nav_practice",
            "composer_nav_songs",
            "composer_nav_backing",
            "composer_nav_sbi",
            "composer_nav_jam",
        ):
            self.assertIn(f'key="{key}"', src, f"Missing nav button key: {key}")

    def test_set_active_song_button_in_source(self) -> None:
        src = Path("composition_studio_page.py").read_text(encoding="utf-8")
        self.assertIn('key="composer_set_active_song"', src)

    def test_review_set_active_song_in_source(self) -> None:
        src = Path("composition_studio_page.py").read_text(encoding="utf-8")
        self.assertIn('key="composer_review_set_active"', src)

    def test_sbi_sets_entry_mode(self) -> None:
        src = Path("composition_studio_page.py").read_text(encoding="utf-8")
        sbi_block_start = src.index('key="composer_nav_sbi"')
        sbi_block_end = src.index('key="composer_nav_jam"')
        block = src[sbi_block_start:sbi_block_end]
        self.assertIn('"Song-Based Improvisation"', block)
        self.assertIn('navigate_studio_page(session_state, "creative")', block)

    def test_jam_sets_entry_mode(self) -> None:
        src = Path("composition_studio_page.py").read_text(encoding="utf-8")
        jam_start = src.index('key="composer_nav_jam"')
        jam_block = src[jam_start:jam_start + 500]
        self.assertIn('"Style Jam Mode"', jam_block)
        self.assertIn('navigate_studio_page(session_state, "creative")', jam_block)

    def test_sbi_jam_disabled_when_not_active(self) -> None:
        src = Path("composition_studio_page.py").read_text(encoding="utf-8")
        sbi_start = src.index('key="composer_nav_sbi"')
        sbi_block = src[sbi_start - 400:sbi_start + 50]
        self.assertIn("disabled=not active_comp", sbi_block)

        jam_start = src.index('key="composer_nav_jam"')
        jam_block = src[jam_start - 400:jam_start + 50]
        self.assertIn("disabled=not active_comp", jam_block)

    def test_active_song_banner_attribute(self) -> None:
        src = Path("composition_studio_page.py").read_text(encoding="utf-8")
        self.assertIn('data-composer-active-song="1"', src)

    def test_library_item_shows_active_song_badge(self) -> None:
        src = Path("composition_studio_page.py").read_text(encoding="utf-8")
        # Library rows moved to composition_library_ui/composition_library (P9): the
        # statuses are now independent "Now Editing" and "Active Song" badges.
        self.assertIn("render_library_rows", src)
        block = Path("composition_library.py").read_text(encoding="utf-8")
        self.assertIn("Active Song", block)
        self.assertIn("Now Editing", block)


class TestActivationPipeline(unittest.TestCase):
    def test_activate_composition_song_from_library_callable(self) -> None:
        from composition_songs_bridge import activate_composition_song_from_library
        import inspect

        sig = inspect.signature(activate_composition_song_from_library)
        self.assertIn("doc_id", sig.parameters)

    def test_activation_saves_before_activating(self) -> None:
        src = Path("composition_studio_page.py").read_text(encoding="utf-8")
        set_active_start = src.index('key="composer_set_active_song"')
        block = src[set_active_start:set_active_start + 800]
        save_pos = block.index("save_document_to_library(")
        activate_pos = block.index("activate_composition_song_from_library(st,")
        self.assertLess(save_pos, activate_pos, "Save should happen before activation")


class TestActiveSongSnapshotIgnoresEditedDocument(unittest.TestCase):
    """Browser QA: opening another composition for editing re-pointed the saved Active Song."""

    def test_snapshot_uses_live_pick_not_the_document_being_edited(self) -> None:
        from composition_document import bootstrap_from_vision
        from composition_session_state import save_document_to_library, set_active_document
        from composition_songs_bridge import composition_pick_key_for
        from songs.state import ACTIVE_CATALOG_PICK_KEY
        import active_song_state

        song_a = bootstrap_from_vision(genre="Pop", song_idea="x", title="Song A", key="C major", bpm=100)
        song_b = bootstrap_from_vision(genre="Pop", song_idea="y", title="Song B", key="G major", bpm=90)
        ss: dict = {}
        save_document_to_library(ss, song_a)
        set_active_document(ss, song_b)  # Studio is editing B ...
        ss[ACTIVE_CATALOG_PICK_KEY] = composition_pick_key_for(song_a)  # ... but A is the Active Song
        with mock.patch("songs.music_source.composition_song_is_active", return_value=True):
            ctx = active_song_state.gather_active_song_context(ss)
        self.assertEqual(ctx["pick_key"], composition_pick_key_for(song_a))
        self.assertEqual(ctx["composition_title"], "Song A")


class TestLibraryRowsFitPhones(unittest.TestCase):
    def test_rows_are_stacked_so_delete_stays_reachable(self) -> None:
        from pathlib import Path

        src = Path("composition_library_ui.py").read_text(encoding="utf-8")
        body = src.split("def render_library_rows", 1)[1].split("def render_save_recovery", 1)[0]
        self.assertNotIn("st.columns", body)  # side-by-side columns overflowed the list at 390 px
        self.assertIn('key=f"composer_lib_del_{rid}"', body)
        self.assertIn('key=f"composer_lib_open_{rid}"', body)


if __name__ == "__main__":
    unittest.main()
