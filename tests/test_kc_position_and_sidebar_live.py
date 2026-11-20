"""Key Cycling position + the sidebar's current readouts (user rules 2026-11-19).

Position: only a deliberate Pause is resumed.
* A newly opened song starts at 1/12; a different song never inherits a position, even in the same key.
* A refresh / reopen starts at the first key unless the musician paused this cycle (then Resume continues).
* Resume, Stop, and every new cycle clear the deliberate-Pause mark; Stop -> Play keeps the first-key rule.

Sidebar: while Key Cycling is On on Backing, Sounding Key and Capo Fret show the key the cycle plays
now (the console's labels) and the page script moves them with the key; the saved Practice Key and
the fixed Shape Key are never written. Off: the saved-song context.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import backing_card_commands as cards
import backing_key_cycle as kc
from backing_card_transport import BACKING_CARD_TRANSPORT_KEY
from backing_transport_intent import begin_playback

_ROOT = Path(kc.__file__).resolve().parent
FOURTHS = kc.CYCLE_STEP_FOURTH


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.song = "song-A"
        for p in (
            mock.patch("monetization_entitlements.can_use", return_value=True),
            mock.patch.object(kc, "persist_key_cycle_position", return_value=True),
            mock.patch.object(kc, "_active_song_cycle_identity", side_effect=lambda _s: self.song),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.nonce = 0
        self.ss: dict = {"display_key": "D", "concert_key": "D", "studio_page": "backing"}

    def _start(self, key: str = "D") -> None:
        self.ss["display_key"] = self.ss["concert_key"] = key
        begin_playback(self.ss, reason="test", command="t0")  # Play: a playback session exists
        kc.start_key_cycle(self.ss, start_key=key, interval=5, direction="down")  # D A E B ...

    def _go(self, n: int) -> None:
        for _ in range(n):
            kc._step_owner_cycle(self.ss, steps=1, force=False, queue_continue=False, allow_wrap=False)

    def _data(self) -> dict:
        return kc.get_owner_cycle_session(self.ss) or {}

    def _index(self) -> int:
        seq = list(kc.cycle_key_sequence(self.ss))
        return seq.index(kc.temporary_playback_key(self.ss)) + 1

    def _card(self, action: str) -> None:
        self.nonce += 1
        self.ss[BACKING_CARD_TRANSPORT_KEY] = {"action": action, "nonce": self.nonce, "session": "s"}
        got, token = cards.pending_card_command(self.ss)
        cards.apply_card_command(self.ss, got, token, has_chords=True, stop_backing=lambda _i: False)
        cards.commit_card_command(self.ss, token)

    def _refresh(self) -> None:
        """A new Streamlit session restored from disk: ephemeral flags are gone."""
        self.ss = {k: v for k, v in self.ss.items() if not k.startswith("_kc_session_live")}
        kc.normalize_key_cycle_after_browser_restore(self.ss)


class DeliberatePauseMark(_Base):
    def test_the_cards_pause_marks_it_and_resume_clears_it(self) -> None:
        self._start()
        self._go(2)
        self._card("pause")
        self.assertTrue(self._data().get(kc.CYCLE_USER_PAUSED))
        self._card("resume")
        self.assertFalse(self._data().get(kc.CYCLE_USER_PAUSED))

    def test_an_automatic_hold_is_not_a_deliberate_pause(self) -> None:
        self._start()
        kc.hard_stop_key_cycle_audio(self.ss)  # Stop's silence, page leave, Karaoke
        self.assertFalse(self._data().get(kc.CYCLE_USER_PAUSED))
        kc.pause_key_cycle(self.ss)
        self.assertFalse(self._data().get(kc.CYCLE_USER_PAUSED))

    def test_stops_rewind_clears_it(self) -> None:
        self._start()
        self._go(3)
        self._card("pause")
        kc.rewind_key_cycle_to_first_key(self.ss)
        self.assertFalse(self._data().get(kc.CYCLE_USER_PAUSED))
        self.assertEqual(self._index(), 1)


class RefreshAndReopen(_Base):
    def test_a_playing_cycle_restarts_at_the_first_key_after_a_refresh(self) -> None:
        self._start()
        self._go(1)
        self.assertEqual(self._index(), 2)
        self._refresh()
        self.assertEqual(self._index(), 1)
        self.assertTrue(self._data().get(kc.CYCLE_SESSION_OVER))  # the card offers Play
        self.assertEqual(self._data().get("interval"), 5)
        self.assertEqual(self._data().get("direction"), "down")

    def test_a_deliberately_paused_cycle_continues_after_a_refresh(self) -> None:
        self._start()
        self._go(3)
        self._card("pause")
        self._refresh()
        self.assertEqual(self._index(), 4)
        self.assertEqual(str(self._data().get("status")), kc.STATUS_HELD)
        self.assertFalse(self._data().get(kc.CYCLE_SESSION_OVER))

    def test_a_pause_then_resume_then_refresh_starts_again(self) -> None:
        self._start()
        self._go(2)
        self._card("pause")
        self._card("resume")
        self._refresh()
        self.assertEqual(self._index(), 1)

    def test_a_saved_practice_key_is_not_touched(self) -> None:
        self._start()
        self._go(2)
        self._refresh()
        self.assertEqual((self.ss["display_key"], self.ss["concert_key"]), ("D", "D"))


class AnotherSong(_Base):
    def test_a_different_song_in_the_same_key_starts_at_1_of_12_with_defaults(self) -> None:  # I
        self._start("D")
        self._go(1)
        old = str(self._data().get("cycle_id"))
        self.song = "song-B"  # another song, also in D
        self.assertTrue(kc.ensure_key_cycle_follows_active_song(self.ss))
        self.assertEqual(self._index(), 1)
        self.assertEqual(kc.temporary_playback_key(self.ss), "D")
        self.assertNotEqual(str(self._data().get("cycle_id")), old)
        self.assertEqual(self._data().get(kc.CYCLE_SONG_ID), "song-B")
        self.assertEqual((self._data().get("interval"), self._data().get("direction")), (1, "up"))

    def test_a_different_song_starts_from_its_own_key(self) -> None:
        self._start("D")
        self._go(2)
        self.song = "song-C"
        self.ss["display_key"] = self.ss["concert_key"] = "F"
        kc.ensure_key_cycle_follows_active_song(self.ss)
        self.assertEqual(kc.temporary_playback_key(self.ss), "F")
        self.assertEqual(self._index(), 1)

    def test_a_paused_cycle_is_not_carried_to_another_song(self) -> None:
        self._start("D")
        self._go(3)
        self._card("pause")
        self.song = "song-B"
        kc.ensure_key_cycle_follows_active_song(self.ss)
        self.assertEqual(self._index(), 1)
        self.assertFalse(self._data().get(kc.CYCLE_USER_PAUSED))

    def test_the_same_song_keeps_its_position(self) -> None:
        self._start("D")
        self._go(2)
        self.assertFalse(kc.ensure_key_cycle_follows_active_song(self.ss))
        self.assertEqual(self._index(), 3)

    def test_a_cycle_saved_before_songs_were_recorded_is_adopted(self) -> None:
        self._start("D")
        self._go(2)
        bag = self.ss[kc.BACKING_KEY_CYCLE_SESSIONS_KEY]
        for v in bag.values():
            v.pop(kc.CYCLE_SONG_ID, None)
        self.assertFalse(kc.ensure_key_cycle_follows_active_song(self.ss))
        self.assertEqual(self._data().get(kc.CYCLE_SONG_ID), "song-A")
        self.assertEqual(self._index(), 3)

    def test_key_cycling_off_is_left_alone(self) -> None:
        self.song = "song-B"
        self.assertFalse(kc.ensure_key_cycle_follows_active_song(self.ss))
        self.assertFalse(self.ss.get("backing_key_cycle_enabled"))


class SettingsBelongToOneSongActivation(_Base):
    """User spec 2026-11-19 tests A, B, C, G, H, I (the Key Cycling parts)."""

    def setUp(self) -> None:
        super().setUp()
        import active_song_transition as ast_mod

        self.ast = ast_mod
        p = mock.patch("songs.music_source.resolve_active_song_identity", side_effect=lambda _s: self.song)
        p.start()
        self.addCleanup(p.stop)

    def _run(self, page: str = "backing") -> None:
        """One script run: the activation stamp (every page), then Backing's own check."""
        self.ss["studio_page"] = page
        self.ast.note_active_song_activation(self.ss)
        if page == "backing":
            kc.ensure_key_cycle_follows_active_song(self.ss)

    def _choose(self, step: str, direction: str, spelling: dict | None = None) -> None:
        self.ss[kc.BACKING_KEY_CYCLE_STEP_KEY] = step
        self.ss[kc.BACKING_KEY_CYCLE_DIRECTION_KEY] = direction
        if spelling:
            self.ss[kc.BACKING_KEY_SPELLING_PREFS_KEY] = dict(kc.default_spelling_prefs(), **spelling)

    def _settings(self) -> tuple:
        return (kc.normalize_cycle_step_name(self.ss.get(kc.BACKING_KEY_CYCLE_STEP_KEY)) or kc.CYCLE_STEP_SEMITONE,
                str(self.ss.get(kc.BACKING_KEY_CYCLE_DIRECTION_KEY) or "up"),
                kc.spelling_prefs_from_session(self.ss))

    def test_A_same_song_visit_multitrack_and_back_keeps_the_settings(self) -> None:
        self._run()
        self._choose(FOURTHS, "down", {"F#/Gb": "Gb"})
        want = self._settings()
        for page in ("multitrack", "practice", "backing", "backing"):
            self._run(page)
        self.assertEqual(self._settings(), want)

    def test_B_switching_to_a_custom_song_resets_to_ascending_semitone(self) -> None:
        self._run()
        self._choose(FOURTHS, "down", {"F#/Gb": "Gb"})
        self.song = "custom::trial-song"
        self._run()
        self.assertEqual(self._settings(), (kc.CYCLE_STEP_SEMITONE, "up", kc.default_spelling_prefs()))
        self.assertEqual(self.ss.get("_backing_key_cycle_step_ui_seed"), kc.CYCLE_STEP_SEMITONE)
        self.assertEqual(self.ss.get("_backing_key_cycle_direction_ui_seed"), "up")

    def test_C_returning_to_the_first_song_starts_from_defaults_again(self) -> None:
        self._run()
        self._choose(FOURTHS, "down")
        self.song = "custom::trial-song"
        self._run("picker")        # switched on the Songs page, Backing never shown for it
        self.song = "song-A"
        self._run("picker")        # the first song chosen again
        self._run()
        self.assertEqual(self._settings()[:2], (kc.CYCLE_STEP_SEMITONE, "up"))

    def test_G_changing_song_without_leaving_backing_restarts_a_running_cycle(self) -> None:
        self._run()
        self._choose(FOURTHS, "down")
        self._start("D")
        self._go(2)
        self.song = "song-B"
        self._run()
        self.assertEqual(self._index(), 1)
        self.assertEqual((self._data().get("interval"), self._data().get("direction")), (1, "up"))

    def test_H_reruns_pause_resume_next_and_a_rebuild_are_not_a_song_change(self) -> None:
        self._run()
        self._choose(FOURTHS, "down")
        self._start("D")
        for _ in range(3):
            self._run()
        self._card("pause")
        self._run()
        self._card("resume")
        self._go(1)
        self._run()
        self.ss.pop("backing_key_cycle_step_ui", None)  # controls recreated
        self._run()
        self.assertEqual(self._settings()[:2], (FOURTHS, "down"))
        self.assertEqual(self._index(), 2)
        self.assertEqual(self.ast.active_song_activation_epoch(self.ss), 0)

    def test_I_two_songs_in_the_same_key_still_count_as_a_change(self) -> None:
        self._run()
        self._choose(FOURTHS, "down")
        self.song = "song-B"  # both in D
        self._run()
        self.assertEqual(self.ast.active_song_activation_epoch(self.ss), 1)
        self.assertEqual(self._settings()[:2], (kc.CYCLE_STEP_SEMITONE, "up"))

    def test_a_refresh_is_not_a_change_but_landing_on_another_song_is(self) -> None:
        self._run()
        self._choose(FOURTHS, "down")
        saved = dict(self.ss)
        self.ss = dict(saved)      # refresh on the same song: the saved stamp matches
        self._run()
        self.assertEqual(self._settings()[:2], (FOURTHS, "down"))
        self.ss = dict(saved)
        self.song = "song-B"       # another tab switched the song before this refresh
        self._run()
        self.assertEqual(self._settings()[:2], (kc.CYCLE_STEP_SEMITONE, "up"))

    def test_a_temporary_creative_visit_or_an_editing_page_is_not_a_change(self) -> None:
        self._run()
        self._choose(FOURTHS, "down")
        self.song = "custom::being-edited"
        self._run("custom")
        self._run("creative")
        self.song = "song-A"
        self._run()
        self.assertEqual(self.ast.active_song_activation_epoch(self.ss), 0)
        self.assertEqual(self._settings()[:2], (FOURTHS, "down"))

    def test_the_first_stamp_ever_is_not_a_change(self) -> None:
        self._choose(FOURTHS, "down")
        self._run()
        self.assertEqual(self._settings()[:2], (FOURTHS, "down"))


class SidebarFollowsTheLiveCycle(_Base):
    def test_live_key_while_cycling_on_backing(self) -> None:
        self._start("D")
        self._go(1)
        live = kc.key_cycle_live_sidebar(self.ss)
        self.assertEqual(live["key"], "A")
        self.assertEqual(live["label"], "A major")

    def test_none_when_off_or_off_backing(self) -> None:
        self.assertIsNone(kc.key_cycle_live_sidebar(self.ss))
        self._start("D")
        self.ss["studio_page"] = "practice"
        self.assertIsNone(kc.key_cycle_live_sidebar(self.ss))

    def test_the_capo_line_uses_the_live_key_and_matches_the_console(self) -> None:
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY, _capo_fret_caption

        self.ss.update({"instrument": "Guitar", CAPO_ENABLED_KEY: True, CAPO_SHAPE_KEY: "E"})
        self._start("D")
        self._go(1)  # A: E shape, capo 5
        live = kc.key_cycle_live_sidebar(self.ss)
        line = _capo_fret_caption("D", "E", live)
        self.assertIn('data-kc-live="capo">5<', line)
        self.assertEqual(int(kc.cycle_shape_projection(self.ss, "A")["capo_fret"]), 5)
        self.assertIn("Capo Fret:</strong> 10<", _capo_fret_caption("D", "E", None))  # saved song: D
        self.assertEqual(self.ss[CAPO_SHAPE_KEY], "E")  # the fixed shape is unchanged
        self.assertEqual(self.ss["display_key"], "D")

    def test_the_page_script_moves_the_marked_readouts_with_the_console(self) -> None:
        src = (_ROOT / "backing_key_cycle.py").read_text(encoding="utf-8")
        i = src.index("put('.kc-console-position'")
        block = src[i:i + 900]
        self.assertIn("[data-kc-live=\"sounding\"]", block)
        self.assertIn("[data-kc-live=\"capo\"]", block)
        self.assertIn("sounds[ix]", block)
        self.assertIn("capos[ix]", block)

    def test_a_refresh_rewinds_the_cycle_before_the_sidebar_is_drawn(self) -> None:
        # Browser 2026-11-19: a no-Pause refresh left the sidebar on the old key (A-flat / Fret 1)
        # while the console had already rewound to 1/12 -- the restore ran after the sidebar.
        src = (_ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        sidebar = src.index("render_guitar_capo_sidebar(")
        first = src.index("ensure_key_cycle_follows_active_song(st.session_state)")
        for call in ("ensure_key_cycle_follows_active_song(st.session_state)",
                     "normalize_key_cycle_after_browser_restore(st.session_state)"):
            self.assertEqual(src.count(call), 1, call)
            self.assertLess(src.index(call), sidebar, call)
        # Still Backing-only: the guard sits just above the calls.
        guard = src.rindex('if _studio_page == "backing":', 0, first)
        self.assertLess(first - guard, 1200)


if __name__ == "__main__":
    unittest.main()
