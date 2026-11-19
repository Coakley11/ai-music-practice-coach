"""Now Editing and Now Singing stay separate (Cloud report, 2026-11-18).

Measured on dev 611ad477 in a real browser with Blackbird (Catalog, set key E), Jazz tune
(Composition, C) and Trial Song (Custom, D):

* a setlist tap opened the Lyrics & Cues editor and scrolled the setlist off a phone screen
  ("Karaoke disappears"), and saved the setlist key as the song's own Practice Key;
* Add Lyrics under a Jazz tune card opened Blackbird: it followed Now Singing, which End Set
  rewinds to the setlist's first entry;
* during a set the Backing card said "I'm playing in C" for Blackbird (audio correctly in E),
  because the Practice Key control belongs to the song being edited;
* the countdown ran inside the Karaoke panel ~1800 px below the top of Backing, unseen.
"""
from __future__ import annotations

import copy
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_APP = (_ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = _APP.index(f"def {name}(")
    nxt = _APP.find("\n    def ", start + 10)
    nxt_top = _APP.find("\ndef ", start + 10)
    ends = [e for e in (nxt, nxt_top) if e > 0]
    return _APP[start : min(ends)]


class AddLyricsTargetsTheCardSong(unittest.TestCase):
    def test_it_reads_the_cards_song_not_now_singing(self) -> None:
        body = _fn("_open_lyrics_editor_from_backing")
        self.assertIn("st.session_state.get(ACTIVE_CATALOG_PICK_KEY)", body)
        self.assertNotIn("now_singing_pick_key", body)
        self.assertNotIn("current_session_entry", body)

    def test_a_composition_opens_composition_studio_on_its_lyrics(self) -> None:
        body = _fn("_open_lyrics_editor_from_backing")
        self.assertIn('_card_pk.startswith("composition::")', body)
        self.assertIn('open_saved_composition_for_studio_edit(st, _card_pk, phase="lyrics")', body)

    def test_no_setlist_key_rides_along(self) -> None:
        body = _fn("_open_lyrics_editor_from_backing")
        self.assertIn('"practice_key": ""', body)
        self.assertIn('"entry_id": ""', body)


class CompositionHandoffOpensTheRequestedStep(unittest.TestCase):
    # Loading a library song checkpoints the workspace to disk (force_disk). Without its own data
    # dir this test wrote into the checkout's data/, and every later test that imports the app
    # restored that workspace and stopped early.
    def setUp(self) -> None:
        import os
        import tempfile

        from unittest import mock

        self._tmp = tempfile.TemporaryDirectory(prefix="kedit-test-")
        self._prev = os.environ.get("MUSIC_APP_DATA_DIR")
        os.environ["MUSIC_APP_DATA_DIR"] = self._tmp.name
        self._no_disk = mock.patch(
            "composition_workspace_state_persistence.checkpoint_composition_workspace", lambda *a, **k: None
        )
        self._no_disk.start()

    def tearDown(self) -> None:
        import os

        if self._prev is None:
            os.environ.pop("MUSIC_APP_DATA_DIR", None)
        else:
            os.environ["MUSIC_APP_DATA_DIR"] = self._prev
        self._no_disk.stop()
        self._tmp.cleanup()

    def _session(self):
        from composition_document import new_composition_document
        from composition_session_state import COMPOSER_LIBRARY_KEY

        jazz = new_composition_document(title="Jazz tune")
        other = new_composition_document(title="Other song")
        return {COMPOSER_LIBRARY_KEY: {jazz["id"]: copy.deepcopy(jazz), other["id"]: copy.deepcopy(other)}}, jazz, other

    def test_the_exact_song_is_loaded_on_its_lyrics_step(self) -> None:
        from composition_session_state import get_active_document
        from composition_songs_bridge import (
            PENDING_COMPOSER_OPEN_PHASE_KEY,
            PENDING_COMPOSER_STUDIO_EDIT_ID_KEY,
            apply_pending_composer_studio_edit,
        )

        session, jazz, _other = self._session()
        session[PENDING_COMPOSER_STUDIO_EDIT_ID_KEY] = jazz["id"]
        session[PENDING_COMPOSER_OPEN_PHASE_KEY] = "lyrics"
        self.assertTrue(apply_pending_composer_studio_edit(session))
        active = get_active_document(session)
        self.assertEqual(active["id"], jazz["id"])
        self.assertEqual(active["title"], "Jazz tune")
        self.assertEqual((active.get("workflow") or {}).get("current_phase"), "lyrics")
        # One-shot: nothing is left to re-apply on the next run.
        self.assertNotIn(PENDING_COMPOSER_OPEN_PHASE_KEY, session)
        self.assertNotIn(PENDING_COMPOSER_STUDIO_EDIT_ID_KEY, session)

    def test_without_a_phase_the_handoff_is_unchanged(self) -> None:
        from composition_session_state import get_active_document
        from composition_songs_bridge import PENDING_COMPOSER_STUDIO_EDIT_ID_KEY, apply_pending_composer_studio_edit

        session, jazz, _ = self._session()
        session[PENDING_COMPOSER_STUDIO_EDIT_ID_KEY] = jazz["id"]
        self.assertTrue(apply_pending_composer_studio_edit(session))
        # Loading fills the song's own default step; nothing forces Lyrics without a request.
        self.assertNotEqual((get_active_document(session).get("workflow") or {}).get("current_phase"), "lyrics")

    def test_a_stale_phase_without_a_song_does_nothing(self) -> None:
        from composition_session_state import get_active_document
        from composition_songs_bridge import PENDING_COMPOSER_OPEN_PHASE_KEY, apply_pending_composer_studio_edit

        session, _, _ = self._session()
        session[PENDING_COMPOSER_OPEN_PHASE_KEY] = "lyrics"
        self.assertFalse(apply_pending_composer_studio_edit(session))
        self.assertIsNone(get_active_document(session))
        self.assertNotIn(PENDING_COMPOSER_OPEN_PHASE_KEY, session)


class BackingCardKeyDuringASet(unittest.TestCase):
    def test_the_singing_key_is_shown_when_another_song_is_being_edited(self) -> None:
        body = _APP[_APP.index("def _render_backing_card_practice_key("):]
        body = body[: body.index("\ndef ")]
        self.assertIn("km.is_karaoke_session_active(st.session_state)", body)
        self.assertIn("_sing_pick != str(st.session_state.get(ACTIVE_CATALOG_PICK_KEY)", body)
        self.assertIn("km.current_session_practice_key(st.session_state)", body)
        self.assertIn("_backing_card_key_text_row(original_key, _sing_key", body)

    def test_the_retune_control_stays_when_the_sung_song_is_the_edited_song(self) -> None:
        """Issue 69: the card's Practice Key control retunes the performance; only the
        editing-differs case swaps it for text, and it must come before the owner widget."""
        body = _APP[_APP.index("def _render_backing_card_practice_key("):]
        body = body[: body.index("\ndef ")]
        self.assertLess(body.index("_sing_pick != "), body.index('proxy = globals().get("_sidebar_pk_proxy")'))


class SetStartBringsThePanelIntoView(unittest.TestCase):
    def test_once_per_take_through_the_one_controller(self) -> None:
        self.assertIn("km.render_generation(st.session_state) if km.is_karaoke_session_active(st.session_state)", _APP)
        js = _APP[_APP.index("function bringKaraokePanelIntoView()"):]
        js = js[: js.index("function frameInView()")]
        self.assertIn("__karaokePanelShownTake === KARAOKE_TAKE_TOKEN", js)
        self.assertIn('getAttribute("data-karaoke-session") !== "true"', js)
        self.assertIn("if (leadSheetOpenOnPage())", js)
        self.assertIn('window.top.__lsFollow.request("karaoke-lyrics", el', js)
        self.assertIn('document.getElementById("karaoke-lyric-panel")', js)
        self.assertNotIn("scrollIntoView", js)
        self.assertNotIn("scrollTo", js)

    def test_only_while_a_set_is_shown_with_the_hold_install(self) -> None:
        block = _APP[_APP.index("    if (KARAOKE_HOLD) {{"):]
        block = block[: block.index("    }}")]
        self.assertIn("bringKaraokePanelIntoView();", block)


if __name__ == "__main__":
    unittest.main()
