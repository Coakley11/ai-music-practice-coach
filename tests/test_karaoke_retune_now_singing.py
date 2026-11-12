"""Issue 69C: an explicit key change re-keys the song being sung, and nothing else.

The reported symptom was a performance that disagreed with itself - ``Dsus4`` on the
chord tiles, ``Csus4/D`` in the Current Chord and in the audio. The cause was two
authorities: the global Practice Concert Key, and the karaoke entry's own key, frozen
when the song was queued.

The frozen key is not a bug. It stops a song that is merely being *edited* in another
key elsewhere from re-keying a live performance, and it stops reruns, hydration, page
navigation and backing updates from moving one. What was missing was the single case
where the musician themselves asks for a different key while singing.

So the re-key is deliberately narrow. It is reached only from the sidebar's own
``on_change`` - a callback that fires for a musician's action and nothing else - and it
moves the Now Singing row only, through ``_write_queue``, exactly as
``record_entry_feel_override`` already does for an explicit Feel change.
"""

from __future__ import annotations

import unittest

import karaoke_mode as km


def session(*, entry_key="C", instrument="Voice", active=True, entries=1):
    state: dict = {}
    queue = []
    for i in range(entries):
        queue.append({
            "entry_id": f"e{i + 1}",
            "pick_key": f"Pop\u001fSong{i + 1} — Artist",
            "title": f"Song{i + 1}",
            "artist": "Artist",
            "practice_key": entry_key,
            "play_count": 1,
        })
    state[km.KARAOKE_QUEUE_KEY] = queue
    state[km.KARAOKE_SESSION_ACTIVE_KEY] = active
    state[km.KARAOKE_SESSION_INDEX_KEY] = 0
    state["instrument"] = instrument
    return state


class TheExplicitChangeRekeysThePerformance(unittest.TestCase):
    def test_the_now_singing_entry_moves_to_the_chosen_key(self):
        state = session(entry_key="C")
        out = km.retune_now_singing_entry(state, "D")
        self.assertTrue(out["changed"])
        self.assertEqual(out["previous"], "C")
        self.assertEqual(km.current_session_practice_key(state), "D")

    def test_the_outgoing_take_is_retired(self):
        """Otherwise a build already in flight installs the old key's audio."""
        state = session()
        before = int(state.get(km.KARAOKE_PLAYBACK_GENERATION_KEY) or 0)
        km.retune_now_singing_entry(state, "D")
        self.assertGreater(int(state[km.KARAOKE_PLAYBACK_GENERATION_KEY]), before)

    def test_audio_describing_the_old_key_is_dropped(self):
        """Nothing may go on playing in C under chords labelled in D."""
        state = session()
        state.update({
            "_last_backing_wav": b"old",
            "_last_backing_wav_b64": "old",
            "_last_backing_wav_path": "/tmp/old.wav",
            "_last_backing_signature": ("Say", "C"),
            "_backing_wav_building_signature": ("Say", "C"),
            "_kc_current_static_url": "/static/old.wav",
            "_kc_arrangement_url": "/static/old-arr.wav",
        })
        km.retune_now_singing_entry(state, "D")
        for key in ("_last_backing_wav", "_last_backing_wav_b64",
                    "_last_backing_wav_path", "_last_backing_signature",
                    "_backing_wav_building_signature", "_kc_current_static_url",
                    "_kc_arrangement_url"):
            with self.subTest(key=key):
                self.assertNotIn(key, state)

    def test_only_the_now_singing_entry_moves(self):
        state = session(entry_key="C", entries=3)
        km.retune_now_singing_entry(state, "D")
        keys = [row["practice_key"] for row in km.get_queue(state)]
        self.assertEqual(keys, ["D", "C", "C"])

    def test_the_rest_of_the_entry_is_untouched(self):
        state = session(entry_key="C")
        before = dict(km.get_queue(state)[0])
        km.retune_now_singing_entry(state, "D")
        after = dict(km.get_queue(state)[0])
        for field in ("entry_id", "pick_key", "title", "artist", "play_count"):
            with self.subTest(field=field):
                self.assertEqual(after[field], before[field])


class WhatMustNotRekeyAPerformance(unittest.TestCase):
    """The protection the frozen key was built for, kept intact."""

    def test_not_while_the_instrument_is_not_voice(self):
        state = session(instrument="Guitar")
        self.assertEqual(
            km.retune_now_singing_entry(state, "D")["reason"], "not performing")
        self.assertEqual(km.get_queue(state)[0]["practice_key"], "C")

    def test_not_when_no_karaoke_session_is_running(self):
        state = session(active=False)
        self.assertEqual(
            km.retune_now_singing_entry(state, "D")["reason"], "not performing")
        self.assertEqual(km.get_queue(state)[0]["practice_key"], "C")

    def test_not_on_an_empty_key(self):
        state = session()
        for blank in ("", "   ", None):
            with self.subTest(blank=blank):
                self.assertEqual(
                    km.retune_now_singing_entry(state, blank)["reason"], "no key")
        self.assertEqual(km.get_queue(state)[0]["practice_key"], "C")

    def test_not_with_nothing_queued(self):
        state = session()
        state[km.KARAOKE_QUEUE_KEY] = []
        self.assertEqual(km.retune_now_singing_entry(state, "D")["reason"], "no entry")

    def test_the_same_key_twice_does_not_transpose_twice(self):
        state = session(entry_key="C")
        self.assertTrue(km.retune_now_singing_entry(state, "D")["changed"])
        again = km.retune_now_singing_entry(state, "D")
        self.assertFalse(again["changed"])
        self.assertEqual(again["reason"], "already in key")
        self.assertEqual(km.current_session_practice_key(state), "D")

    def test_an_already_matching_key_is_a_no_op(self):
        """The guard against double transposition when the chart is already there."""
        state = session(entry_key="D")
        out = km.retune_now_singing_entry(state, "D")
        self.assertFalse(out["changed"])
        self.assertNotIn(km.KARAOKE_PLAYBACK_GENERATION_KEY, state)

    def test_a_refused_retune_leaves_the_audio_alone(self):
        """A no-op must not silence a performance that is playing correctly."""
        state = session(entry_key="D")
        state["_last_backing_wav"] = b"current"
        km.retune_now_singing_entry(state, "D")
        self.assertEqual(state["_last_backing_wav"], b"current")


class ARetuneIsAControlledTransition(unittest.TestCase):
    def test_a_rollback_record_is_kept(self):
        state = session(entry_key="C")
        km.retune_now_singing_entry(state, "D")
        pending = km.pending_now_singing_retune(state)
        self.assertEqual(pending["previous_key"], "C")
        self.assertEqual(pending["requested_key"], "D")
        self.assertEqual(pending["entry_id"], "e1")

    def test_a_failed_regeneration_puts_the_performance_back(self):
        state = session(entry_key="C")
        km.retune_now_singing_entry(state, "D")
        out = km.rollback_now_singing_retune(state)
        self.assertTrue(out["restored"])
        self.assertEqual(km.current_session_practice_key(state), "C")
        self.assertEqual(km.pending_now_singing_retune(state), {})

    def test_a_successful_regeneration_commits_it(self):
        state = session(entry_key="C")
        km.retune_now_singing_entry(state, "D")
        record = km.confirm_now_singing_retune(state)
        self.assertEqual(record["requested_key"], "D")
        self.assertEqual(km.pending_now_singing_retune(state), {})
        self.assertEqual(km.current_session_practice_key(state), "D")

    def test_a_rollback_retires_the_failed_take_too(self):
        """The new key's take must not install after the performance went back."""
        state = session(entry_key="C")
        km.retune_now_singing_entry(state, "D")
        gen = int(state[km.KARAOKE_PLAYBACK_GENERATION_KEY])
        km.rollback_now_singing_retune(state)
        self.assertGreater(int(state[km.KARAOKE_PLAYBACK_GENERATION_KEY]), gen)

    def test_rolling_back_nothing_is_harmless(self):
        state = session()
        self.assertFalse(km.rollback_now_singing_retune(state)["restored"])

    def test_confirming_nothing_is_harmless(self):
        self.assertEqual(km.confirm_now_singing_retune(session()), {})

    def test_a_retune_cannot_be_rolled_back_twice(self):
        state = session(entry_key="C")
        km.retune_now_singing_entry(state, "D")
        km.rollback_now_singing_retune(state)
        self.assertFalse(km.rollback_now_singing_retune(state)["restored"])
        self.assertEqual(km.current_session_practice_key(state), "C")


class SavedRecordingsAreNotTouched(unittest.TestCase):
    """A key change must not relabel a take that was recorded in another key."""

    def test_an_entry_carries_no_recording_identity_to_relabel(self):
        """The reason this is safe, asserted rather than assumed."""
        state = session()
        entry = km.get_queue(state)[0]
        for forbidden in ("recording_concert_key", "recording_identity", "take_id",
                          "multitrack_id", "local_path", "storage_ref"):
            with self.subTest(field=forbidden):
                self.assertNotIn(forbidden, entry)

    def test_the_media_catalog_is_not_reached_from_a_retune(self):
        """The function's *code* imports and calls nothing that owns stored audio.

        Checked on the parsed body rather than the text: an earlier version of this
        test matched the word "recording" in the docstring, which proved nothing.
        """
        import ast
        import inspect
        import textwrap

        tree = ast.parse(textwrap.dedent(inspect.getsource(km.retune_now_singing_entry)))
        fn = tree.body[0]
        imported: list[str] = []
        called: list[str] = []
        for node in ast.walk(fn):
            if isinstance(node, ast.Import):
                imported += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
            elif isinstance(node, ast.Call):
                target = node.func
                if isinstance(target, ast.Name):
                    called.append(target.id)
                elif isinstance(target, ast.Attribute):
                    called.append(target.attr)

        self.assertEqual(imported, [], f"a retune must import nothing: {imported}")
        for name in called:
            with self.subTest(call=name):
                for forbidden in ("delete", "remove", "unlink", "save", "store",
                                  "catalog", "media"):
                    self.assertNotIn(forbidden, name.lower())

    def test_only_the_queue_and_playback_generation_are_written(self):
        """Whatever a retune touches, it is not stored audio."""
        state = session(entry_key="C")
        state["mt_tracks"] = {"Vocals": b"a saved take"}
        state["_media_catalog_cache"] = {"multitrack_sessions": [{"item_key": "mt-1"}]}
        km.retune_now_singing_entry(state, "D")
        self.assertEqual(state["mt_tracks"], {"Vocals": b"a saved take"})
        self.assertEqual(state["_media_catalog_cache"],
                         {"multitrack_sessions": [{"item_key": "mt-1"}]})


if __name__ == "__main__":
    unittest.main()


class TheNoticeExplainsWhatHappened(unittest.TestCase):
    """A re-key leaves a moment of silence. Silence under a changed key needs words."""

    class FakeSt:
        def __init__(self, session_state):
            self.session_state = session_state
            self.infos: list[str] = []
            self.errors: list[str] = []

        def info(self, text):
            self.infos.append(str(text))

        def error(self, text):
            self.errors.append(str(text))

    def _st(self, **over):
        state = {"instrument": "Voice"}
        state.update(over)
        return self.FakeSt(state)

    def test_a_successful_move_is_announced_with_both_keys(self):
        from karaoke_ui import KARAOKE_RETUNE_NOTICE_KEY, render_karaoke_retune_notice

        st = self._st(**{KARAOKE_RETUNE_NOTICE_KEY: {"from": "C", "to": "D"}})
        self.assertTrue(render_karaoke_retune_notice(st))
        self.assertEqual(len(st.infos), 1)
        self.assertIn("C", st.infos[0])
        self.assertIn("D", st.infos[0])
        self.assertEqual(st.errors, [])

    def test_a_failure_says_which_key_it_is_still_in(self):
        """The sidebar must never be left claiming D while the performance is in C."""
        from karaoke_ui import KARAOKE_RETUNE_NOTICE_KEY, render_karaoke_retune_notice

        st = self._st(**{KARAOKE_RETUNE_NOTICE_KEY: {
            "from": "C", "to": "D", "error": "Backing could not be built."}})
        self.assertTrue(render_karaoke_retune_notice(st))
        self.assertEqual(st.infos, [])
        self.assertEqual(len(st.errors), 1)
        self.assertIn("D", st.errors[0])
        self.assertIn("Still performing in C", st.errors[0])

    def test_it_shows_once(self):
        from karaoke_ui import KARAOKE_RETUNE_NOTICE_KEY, render_karaoke_retune_notice

        st = self._st(**{KARAOKE_RETUNE_NOTICE_KEY: {"from": "C", "to": "D"}})
        render_karaoke_retune_notice(st)
        self.assertFalse(render_karaoke_retune_notice(st))
        self.assertEqual(len(st.infos), 1)

    def test_nothing_is_shown_without_a_notice(self):
        from karaoke_ui import render_karaoke_retune_notice

        st = self._st()
        self.assertFalse(render_karaoke_retune_notice(st))

    def test_a_stale_notice_is_dropped_outside_voice_mode(self):
        """It must not surface later when the musician switches back to Voice."""
        from karaoke_ui import KARAOKE_RETUNE_NOTICE_KEY, render_karaoke_retune_notice

        st = self._st(instrument="Guitar",
                      **{KARAOKE_RETUNE_NOTICE_KEY: {"from": "C", "to": "D"}})
        self.assertFalse(render_karaoke_retune_notice(st))
        self.assertNotIn(KARAOKE_RETUNE_NOTICE_KEY, st.session_state)
        self.assertEqual(st.infos, [])


class TheChordsOnScreenGoWithTheAudio(unittest.TestCase):
    """The gap the Part D data-flow map found in the first version of this fix.

    ``stash_audible_arrangement_after_generate`` records the arrangement that was
    actually installed - its chord-event timeline, its chart markup, and the signature it
    was rendered under, noting that "each timeline carries the signature (and so the key)
    it was rendered in". The first retune cleared only the WAV, so the tiles and the
    Current / Next Chord could have gone on reading the old key's timeline: exactly the
    defect being fixed, reintroduced by the fix.
    """

    STALE = {
        "_kc_audible_follow_timeline": [{"chord": "Csus4/D"}],
        "_kc_audible_follow_timeline_signature": ("Say", "C"),
        "_kc_audible_follow_timeline_space": "concert",
        "_kc_audible_signature": ("Say", "C"),
        "_kc_audible_chart_html": "<b>C</b>",
        "_kc_last_open_chart_html": "<b>C</b>",
        "_last_backing_timeline": [{"chord": "Csus4/D"}],
        "_last_backing_timeline_signature": ("Say", "C"),
    }
    #: Facts about the arrangement that a key change does not alter.
    KEPT = {
        "_kc_audible_bpm": 96,
        "_kc_audible_groove": "ballad",
        "_kc_audible_meter": "4/4",
        "_kc_audible_section_names": ["Verse"],
    }

    def test_old_key_timeline_and_chart_are_dropped(self):
        state = session(entry_key="C")
        state.update(self.STALE)
        km.retune_now_singing_entry(state, "D")
        for key in self.STALE:
            with self.subTest(key=key):
                self.assertNotIn(key, state)

    def test_tempo_feel_meter_and_sections_survive(self):
        """A key change happens inside one song; it must not reset the arrangement."""
        state = session(entry_key="C")
        state.update(self.STALE | self.KEPT)
        km.retune_now_singing_entry(state, "D")
        for key, value in self.KEPT.items():
            with self.subTest(key=key):
                self.assertEqual(state[key], value)

    def test_a_refused_retune_keeps_the_chords_on_screen(self):
        """A no-op must not blank the chart of a performance that is already correct."""
        state = session(entry_key="D")
        state.update(self.STALE)
        km.retune_now_singing_entry(state, "D")
        for key, value in self.STALE.items():
            with self.subTest(key=key):
                self.assertEqual(state[key], value)

    def test_the_song_change_resets_are_not_borrowed(self):
        """Scope, play session and Backing context belong to a *song* change."""
        state = session(entry_key="C")
        untouched = {
            "backing_track_bpm": 96,
            "backing_track_single_section": "Verse",
            "_pending_backing_scope": "Verse only",
            "backing_context": {"source": "catalog"},
        }
        state.update(untouched)
        km.retune_now_singing_entry(state, "D")
        for key, value in untouched.items():
            with self.subTest(key=key):
                self.assertEqual(state[key], value)
