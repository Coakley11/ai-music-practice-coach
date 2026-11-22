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
        # Queued, never loaded mid-script: loading there wrote Backing widget keys after their widgets
        # existed (measured: StreamlitAPIException on backing_groove_style).
        self.assertIn("st.session_state[PENDING_KARAOKE_COMPOSITION_LYRICS_KEY] = _card_pk", body)
        self.assertNotIn("open_saved_composition_for_studio_edit(", body)
        consumer = _APP[_APP.index("_pending_comp_lyrics = str(st.session_state.pop(PENDING_KARAOKE_COMPOSITION_LYRICS_KEY"):]
        consumer = consumer[:600]
        self.assertIn('_open_comp_edit(st, _pending_comp_lyrics, phase="lyrics")', consumer)
        self.assertLess(_APP.index("_pending_comp_lyrics = str("), _APP.index('_pk_widget_key = "display_key"'))

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
        # 2026-11-19: for the WHOLE set - also when the sung song is the edited song, whose sidebar
        # key can differ from its setlist key (the card read E while D played).
        self.assertNotIn("_sing_pick != str(st.session_state.get(ACTIVE_CATALOG_PICK_KEY)", body)
        self.assertIn("and _sing_pick\n    ):", body)
        self.assertIn("km.current_session_practice_key(st.session_state)", body)
        self.assertIn("_render_backing_card_performance_key(original_key, _sing_key", body)

    def test_the_card_control_retunes_this_performance_only(self) -> None:
        """Test A needs a way to retune the sung song from the card even while another song is
        edited: its own control, seeded with the entry's effective key, through the one retune path."""
        body = _APP[_APP.index("def _render_backing_card_performance_key("):]
        body = body[: body.index("\ndef ")]
        self.assertIn("_karaoke_retune_after_explicit_key_change(", body)
        self.assertIn("km.render_generation(st.session_state)", body)
        self.assertIn("index=options.index(sing_key)", body)
        self.assertNotIn("set_practice_concert_key", body)
        self.assertNotIn("commit_entry_practice_key", body)
        self.assertNotIn("_write_queue", body)

    def test_the_retune_control_stays_when_the_sung_song_is_the_edited_song(self) -> None:
        """Issue 69: during a set the card's key control retunes the performance - the card's own
        performance control (seeded with the sung entry's key) in every case, edited song or not,
        decided before the owner widget."""
        body = _APP[_APP.index("def _render_backing_card_practice_key("):]
        body = body[: body.index("\ndef ")]
        self.assertLess(body.index("_render_backing_card_performance_key(original_key, _sing_key"),
                        body.index('proxy = globals().get("_sidebar_pk_proxy")'))


class SetStartBringsThePanelIntoView(unittest.TestCase):
    def test_once_per_take_through_the_one_controller(self) -> None:
        self.assertIn("km.render_generation(st.session_state) if km.is_karaoke_session_active(st.session_state)", _APP)
        js = _APP[_APP.index("function bringKaraokePanelIntoView()"):]
        js = js[: js.index("function frameInView()")]
        self.assertIn("__karaokePanelShownTake === KARAOKE_TAKE_TOKEN", js)
        # The token itself is the set gate (empty outside a set): the page attribute it used to
        # check is not set on Backing (measured null), which silently skipped every request.
        self.assertNotIn("data-karaoke-session", js)
        # User rule 2026-11-21: the singing panel leads with the Lead Sheet open too, so set start brings it in.
        self.assertNotIn("if (leadSheetOpenOnPage())", js)
        self.assertIn('window.top.__lsFollow.request("karaoke-lyrics", el', js)
        self.assertIn('document.getElementById("karaoke-lyric-panel")', js)
        self.assertNotIn("scrollIntoView", js)
        self.assertNotIn("scrollTo", js)
        # Never overrides a manual hold: a singer scrolling at set start keeps the page for 3 s.
        self.assertNotIn("force", js)

    def test_only_while_a_set_is_shown_with_the_hold_install(self) -> None:
        block = _APP[_APP.index("    if (KARAOKE_HOLD) {{"):]
        block = block[: block.index("    }}")]
        self.assertIn("bringKaraokePanelIntoView();", block)


class NowEditingKeepsTheSungTake(unittest.TestCase):
    def test_a_mid_set_now_editing_change_does_not_drop_the_backing_take(self) -> None:
        """Measured: a mid-set setlist tap cleared the Backing cache - which during a set holds the
        Now Singing take - and Backing came back with no Karaoke panel and "Press Play"."""
        fn = _APP[_APP.index("def _activate_karaoke_entry("):]
        fn = fn[: fn.index("\n# === ")]
        self.assertIn("km.is_karaoke_session_active(st.session_state)", fn)
        self.assertIn("(lambda _st: None)", fn)
        # Shared code inside the identity change clears the cache too (tempo priming, Backing
        # defaults): the sung take is saved before and put back after, and the debt recorded.
        self.assertIn('if _ks in _take_keys or _ks.startswith(("backing_", "_backing_")):', fn)
        self.assertLess(fn.index("_kept_take[_ks] = st.session_state[_k]"), fn.index("_activate_pk("))
        self.assertIn("km.now_editing_change_spares_sung_take(st.session_state)", fn)
        self.assertNotIn("invalidate_backing=invalidate_backing_cache", fn)
        self.assertNotIn("    invalidate_backing_cache(st)", fn)


class SungTakeSurvivesNowEditingChangesAndTheDebtIsPaid(unittest.TestCase):
    def _set_running_on_blackbird(self):
        import karaoke_mode as km

        state: dict = {"instrument": "Voice", "karaoke_mode_instrument": "Voice"}
        km.add_to_queue(state, "RockBlackbird — The Beatles", practice_key="E", title="Blackbird")
        km.add_to_queue(state, "custom::trial-song-1", practice_key="D", title="Trial Song")
        km.start_session(state)
        state["_last_backing_wav"] = b"RIFF-blackbird-E"
        state["_last_backing_signature"] = "blackbird|E"
        return km, state

    def test_a_now_editing_key_change_keeps_the_sung_take(self) -> None:
        from songs.key_state import BACKING_NEEDS_REGEN, _karaoke_spares_sung_take

        km, state = self._set_running_on_blackbird()
        self.assertTrue(km.is_voice_mode(state) and km.is_karaoke_session_active(state))
        # Trial Song (Custom D) becomes Now Editing: both shared PK sites ask this first.
        self.assertTrue(_karaoke_spares_sung_take(state))
        self.assertEqual(state["_last_backing_wav"], b"RIFF-blackbird-E")
        self.assertTrue(state.get(km.KARAOKE_EDIT_REGEN_OWED_KEY))
        self.assertFalse(state.get(BACKING_NEEDS_REGEN))

    def test_end_set_pays_it_so_backing_regenerates_for_the_edited_song(self) -> None:
        from songs.key_state import BACKING_NEEDS_REGEN, _karaoke_spares_sung_take

        km, state = self._set_running_on_blackbird()
        _karaoke_spares_sung_take(state)
        km.stop_session(state)
        self.assertNotIn("_last_backing_wav", state)
        self.assertNotIn("_last_backing_signature", state)
        self.assertTrue(state.get(BACKING_NEEDS_REGEN))
        self.assertNotIn(km.KARAOKE_EDIT_REGEN_OWED_KEY, state)

    def test_outside_a_set_nothing_is_spared(self) -> None:
        import karaoke_mode as km
        from songs.key_state import _karaoke_spares_sung_take

        state: dict = {"instrument": "Voice", "_last_backing_wav": b"x"}
        self.assertFalse(_karaoke_spares_sung_take(state))
        self.assertNotIn(km.KARAOKE_EDIT_REGEN_OWED_KEY, state)

    def test_end_set_without_a_spared_change_leaves_backing_alone(self) -> None:
        from songs.key_state import BACKING_NEEDS_REGEN

        km, state = self._set_running_on_blackbird()
        km.stop_session(state)
        self.assertEqual(state.get("_last_backing_wav"), b"RIFF-blackbird-E")
        self.assertFalse(state.get(BACKING_NEEDS_REGEN))

    def test_both_shared_sites_ask_before_invalidating(self) -> None:
        src = (_ROOT / "songs" / "key_state.py").read_text(encoding="utf-8")
        self.assertEqual(src.count("if not _karaoke_spares_sung_take(st.session_state):"), 2)


class BackingFollowsTheSungEntryDuringASet(unittest.TestCase):
    def test_the_backing_source_identity_is_the_sung_entrys(self) -> None:
        """Measured: with Trial Song (Custom) as Now Editing while Blackbird was sung, the Backing
        source id was built as a Custom one, so Backing found no presentation and hid the player."""
        block = _APP[_APP.index("_kr_sync_pick = km.effective_catalog_pick_key(st.session_state)"):]
        block = block[: block.index("_creative_backing_ctx = None")]
        self.assertIn('_kr_sync_custom = _kr_sync_pick.startswith("custom::")', block)
        self.assertIn("is_custom=_kr_sync_custom", block)
        self.assertIn("pick_key=_kr_sync_pick", block)
        # Outside a set it is exactly what it was.
        self.assertIn("_kr_sync_custom = cpl_session_is_active(st.session_state)", block)


class CustomSongsSayThereIsNoLyricsEditor(unittest.TestCase):
    def test_the_prompt_says_so_instead_of_a_dead_button(self) -> None:
        ui = (_ROOT / "karaoke_ui.py").read_text(encoding="utf-8")
        fn = ui[ui.index("def render_karaoke_missing_lyrics_cta("):]
        fn = fn[: fn.index("\ndef ")]
        self.assertLess(fn.index("if editor_unavailable_note:"), fn.index('key="karaoke_open_lyrics_editor"'))
        self.assertIn('if str(st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").startswith("custom::")', _APP)


class TheSharedSongChangeLeavesBackingToTheSetDuringASet(unittest.TestCase):
    """Measured in the browser: the shared active-song handler re-set Backing for the EDITED song
    mid-set (Trial Song's 100 BPM / Pop groove, the take dropped) - no Karaoke panel after a tap.
    During a Voice set it now applies identity and Practice Key only; End Set pays the rest."""

    def test_the_backing_side_reset_is_skipped_during_a_set(self) -> None:
        src = (_ROOT / "songs" / "music_source.py").read_text(encoding="utf-8")
        block = src[src.index("_karaoke_set_owns_backing = False"):]
        block = block[: block.index("active_song_meter=str(default_meter),")]
        self.assertIn("_km.now_editing_change_spares_sung_take(session)", block)
        skipped = block[block.index("else:"):]
        for step in ("retarget_backing_tempo_ownership(", "invalidate_backing(st)", "prime_active_song_bpm(",
                     "canonicalize_backing_defaults_for_song(", 'session.pop("last_backing_defaults_song_id", None)'):
            self.assertIn(step, skipped)
        self.assertLess(src.index("_karaoke_set_owns_backing = False"), src.index("retarget_backing_tempo_ownership(session, sync_id)"))

    def test_end_set_clears_the_markers_so_backing_sets_up_for_the_edited_song(self) -> None:
        import karaoke_mode as km

        state: dict = {"instrument": "Voice"}
        km.add_to_queue(state, "RockBlackbird — The Beatles", practice_key="E", title="Blackbird")
        km.start_session(state)
        state.update({"last_backing_defaults_song_id": "blackbird", "_last_bpm_song": "blackbird",
                      "_active_bpm_sync_id": "pk::blackbird", "_last_backing_wav_path": "x.wav"})
        self.assertTrue(km.now_editing_change_spares_sung_take(state))
        km.stop_session(state)
        for key in ("last_backing_defaults_song_id", "_last_bpm_song", "_active_bpm_sync_id", "_last_backing_wav_path"):
            self.assertNotIn(key, state)


class SetLevelLeadSheetChoiceIsSetScoped(unittest.TestCase):
    """The Lead Sheet choice made during a set carries across its songs (Backing reads it); a fresh
    set and End Set both start clean, so last night's choice never opens tonight's first song."""

    def _queue(self):
        import karaoke_mode as km

        state: dict = {}
        km.add_to_queue(state, "RockBlackbird — The Beatles", practice_key="E", title="Blackbird")
        km.add_to_queue(state, "PopSay — John Mayer", practice_key="D", title="Say")
        return km, state

    def test_start_and_stop_clear_it_and_advance_does_not(self) -> None:
        km, state = self._queue()
        state[km.KARAOKE_SET_LEAD_SHEET_OPEN_KEY] = True
        km.start_session(state)
        # 2026-11-19: a fresh set starts with the Lead Sheet OFF (explicit False, not "no choice",
        # which let the pre-set state show).
        self.assertIs(state.get(km.KARAOKE_SET_LEAD_SHEET_OPEN_KEY), False)
        state[km.KARAOKE_SET_LEAD_SHEET_OPEN_KEY] = True
        km.advance_session(state) if hasattr(km, "advance_session") else None
        self.assertTrue(state.get(km.KARAOKE_SET_LEAD_SHEET_OPEN_KEY))
        km.stop_session(state)
        self.assertNotIn(km.KARAOKE_SET_LEAD_SHEET_OPEN_KEY, state)


if __name__ == "__main__":
    unittest.main()
