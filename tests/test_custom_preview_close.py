"""Custom Progression Lab previews can be closed (2026-11-20).

Preview Section and Preview Entire Song mounted a player that stayed on the page: the module had an arm path
(request_preview) and an auto-drop when the draft changed, but no close. The player's own Stop only stops and
rewinds; nothing removed it, so a finished preview kept its space and its audio element.

close_preview drops the single transient key, so the component is not rendered again and its audio element goes
with it. Nothing about the song is touched.
"""

import copy
import unittest

import custom_progression_preview as cpp


def _state(sections=None, **kw):
    s = {
        "cpl_saved_progressions": {},
        "custom_session": {"sections": sections or {"Verse": ["C", "Am", "F", "G"]}},
        "cpl_active_progression": {
            "title": "Trial",
            "sections": sections or {"Verse": [{"chord": "C", "bars": 1}, {"chord": "G", "bars": 1}]},
            "key": "C",
            "time_signature": "4/4",
            "bpm": 100,
        },
    }
    s.update(kw)
    return s


class TestCloseLifecycle(unittest.TestCase):
    def test_close_removes_the_armed_preview(self) -> None:
        s = _state()
        cpp.request_preview(s, cpp.PREVIEW_KIND_SECTION, "Verse")
        self.assertIsNotNone(cpp.active_preview(s, cpp.PREVIEW_KIND_SECTION, "Verse"))
        self.assertTrue(cpp.close_preview(s))
        self.assertIsNone(s.get(cpp.PREVIEW_STATE_KEY))
        self.assertIsNone(cpp.active_preview(s, cpp.PREVIEW_KIND_SECTION, "Verse"))

    def test_close_works_for_the_entire_song_preview_too(self) -> None:
        s = _state()
        cpp.request_preview(s, cpp.PREVIEW_KIND_SONG)
        self.assertIsNotNone(cpp.active_preview(s, cpp.PREVIEW_KIND_SONG))
        self.assertTrue(cpp.close_preview(s))
        self.assertIsNone(cpp.active_preview(s, cpp.PREVIEW_KIND_SONG))

    def test_closing_when_nothing_is_open_is_harmless(self) -> None:
        s = _state()
        self.assertFalse(cpp.close_preview(s))
        self.assertIsNone(s.get(cpp.PREVIEW_STATE_KEY))

    def test_reopening_after_a_close_arms_a_fresh_player(self) -> None:
        s = _state()
        cpp.request_preview(s, cpp.PREVIEW_KIND_SECTION, "Verse")
        first = dict(s[cpp.PREVIEW_STATE_KEY])
        cpp.close_preview(s)
        cpp.request_preview(s, cpp.PREVIEW_KIND_SECTION, "Verse")
        second = s[cpp.PREVIEW_STATE_KEY]
        self.assertIsNotNone(cpp.active_preview(s, cpp.PREVIEW_KIND_SECTION, "Verse"))
        # A fresh nonce means a new iframe rather than a resurrected one holding stale audio.
        self.assertGreater(int(second["nonce"]), int(first["nonce"]))

    def test_only_one_preview_can_be_open_at_a_time(self) -> None:
        s = _state()
        cpp.request_preview(s, cpp.PREVIEW_KIND_SECTION, "Verse")
        cpp.request_preview(s, cpp.PREVIEW_KIND_SONG)
        self.assertIsNotNone(cpp.active_preview(s, cpp.PREVIEW_KIND_SONG))
        self.assertIsNone(cpp.active_preview(s, cpp.PREVIEW_KIND_SECTION, "Verse"))

    def test_close_changes_nothing_about_the_song(self) -> None:
        """Closing is compared against the state WITH the preview armed: arming itself normalises the active
        progression record (pre-existing behaviour of preview_inputs), and that is not what close touches."""
        s = _state()
        cpp.request_preview(s, cpp.PREVIEW_KIND_SECTION, "Verse")
        before = copy.deepcopy({k: v for k, v in s.items() if k not in (cpp.PREVIEW_STATE_KEY, cpp.PREVIEW_NONCE_KEY)})
        cpp.close_preview(s)
        after = {k: v for k, v in s.items() if k not in (cpp.PREVIEW_STATE_KEY, cpp.PREVIEW_NONCE_KEY)}
        self.assertEqual(after, before)

    def test_the_only_key_touched_is_the_transient_preview_key(self) -> None:
        s = _state()
        cpp.request_preview(s, cpp.PREVIEW_KIND_SONG)
        keys_before = set(s)
        cpp.close_preview(s)
        self.assertEqual(keys_before - set(s), {cpp.PREVIEW_STATE_KEY})


class TestPreviewDoesNotWriteSongData(unittest.TestCase):
    """Arming a preview normalises the in-session draft (legacy ``sections`` -> ``original_sections``).

    That is a shape migration, not a song-data write: it must not mark the draft dirty, must not reach the save
    path, and must never edit a record in the saved library. The chords, key and bar lengths come out identical.
    """

    def _state_with_library(self):
        from custom_progression_lab import CPL_ACTIVE_KEY, CPL_SAVED_KEY

        entries = [{"chord": "C", "bars": 2}, {"chord": "G", "bars": 1}, {"repeat": True, "bars": 1}]
        record = {
            "id": "song-1", "title": "Trial", "key": "C", "time_signature": "4/4", "bpm": 100,
            "original_sections": {"Verse": [dict(e) for e in entries]}, "original_key_center": "C",
        }
        return {CPL_SAVED_KEY: {"song-1": record}, CPL_ACTIVE_KEY: copy.deepcopy(record)}, entries

    def test_arming_a_preview_does_not_mark_the_draft_dirty(self) -> None:
        from custom_progression_lab import CPL_DRAFT_DIRTY_KEY

        s, _ = self._state_with_library()
        cpp.request_preview(s, cpp.PREVIEW_KIND_SECTION, "Verse")
        self.assertFalse(s.get(CPL_DRAFT_DIRTY_KEY))
        cpp.close_preview(s)
        self.assertFalse(s.get(CPL_DRAFT_DIRTY_KEY))

    def test_arming_a_preview_leaves_the_saved_library_record_untouched(self) -> None:
        from custom_progression_lab import CPL_SAVED_KEY

        s, _ = self._state_with_library()
        saved_before = copy.deepcopy(s[CPL_SAVED_KEY])
        cpp.request_preview(s, cpp.PREVIEW_KIND_SONG)
        cpp.close_preview(s)
        self.assertEqual(s[CPL_SAVED_KEY], saved_before)

    def test_the_draft_is_never_the_saved_record_itself(self) -> None:
        """Even when the draft starts as the SAME object as the library record, previewing detaches it."""
        from custom_progression_lab import CPL_ACTIVE_KEY, CPL_SAVED_KEY

        s, _ = self._state_with_library()
        s[CPL_ACTIVE_KEY] = s[CPL_SAVED_KEY]["song-1"]  # the install path that used to alias them
        saved_before = copy.deepcopy(s[CPL_SAVED_KEY])
        cpp.request_preview(s, cpp.PREVIEW_KIND_SECTION, "Verse")
        self.assertIsNot(s[CPL_ACTIVE_KEY], s[CPL_SAVED_KEY]["song-1"])
        self.assertEqual(s[CPL_SAVED_KEY], saved_before)

    def test_the_migration_keeps_every_chord_and_bar_length(self) -> None:
        from custom_progression_lab import CPL_ACTIVE_KEY

        s, entries = self._state_with_library()
        s[CPL_ACTIVE_KEY] = {  # legacy shape: loose "sections", no original_*
            "id": "song-1", "title": "Trial", "key": "C", "time_signature": "4/4", "bpm": 100,
            "sections": {"Verse": [dict(e) for e in entries]},
        }
        cpp.request_preview(s, cpp.PREVIEW_KIND_SECTION, "Verse")
        after = s[CPL_ACTIVE_KEY]["original_sections"]["Verse"]
        self.assertEqual(
            [(e.get("chord"), e.get("bars"), e.get("repeat")) for e in after],
            [(e.get("chord"), e.get("bars"), e.get("repeat")) for e in entries],
        )
        self.assertEqual(s[CPL_ACTIVE_KEY]["original_key_center"], "C")

    def test_nothing_on_the_preview_path_calls_the_save_path(self) -> None:
        """cpl_save_draft is the only writer; previewing must not reach it."""
        import custom_progression_lab as lab

        calls = []
        real = lab.cpl_save_draft
        lab.cpl_save_draft = lambda *a, **k: calls.append(a) or {}
        try:
            s, _ = self._state_with_library()
            cpp.request_preview(s, cpp.PREVIEW_KIND_SONG)
            cpp.close_preview(s)
        finally:
            lab.cpl_save_draft = real
        self.assertEqual(calls, [])


class TestCloseButton(unittest.TestCase):
    class _St:
        """Minimal stand-in: records the button that would be drawn."""

        def __init__(self, state):
            self.session_state = state
            self.buttons = []

        def button(self, label, **kw):
            self.buttons.append((label, kw))
            return False

        def caption(self, *_a, **_k):
            pass

    def test_the_button_is_offered_for_both_surfaces_and_calls_close(self) -> None:
        for kind, section in ((cpp.PREVIEW_KIND_SECTION, "Verse 1"), (cpp.PREVIEW_KIND_SONG, "")):
            with self.subTest(kind=kind):
                st = self._St(_state())
                cpp.render_close_button(st, kind, section)
                self.assertEqual(len(st.buttons), 1)
                label, kw = st.buttons[0]
                self.assertEqual(label, "✕ Close Preview")
                self.assertIs(kw["on_click"], cpp.close_preview)
                self.assertEqual(kw["args"], (st.session_state,))

    def test_section_and_song_buttons_have_distinct_keys(self) -> None:
        a = self._St(_state())
        cpp.render_close_button(a, cpp.PREVIEW_KIND_SECTION, "Verse 1")
        b = self._St(_state())
        cpp.render_close_button(b, cpp.PREVIEW_KIND_SONG, "")
        self.assertNotEqual(a.buttons[0][1]["key"], b.buttons[0][1]["key"])

    def test_two_sections_do_not_share_one_close_button(self) -> None:
        a = self._St(_state())
        cpp.render_close_button(a, cpp.PREVIEW_KIND_SECTION, "Verse 1")
        b = self._St(_state())
        cpp.render_close_button(b, cpp.PREVIEW_KIND_SECTION, "Chorus")
        self.assertNotEqual(a.buttons[0][1]["key"], b.buttons[0][1]["key"])

    def test_the_key_survives_awkward_section_names(self) -> None:
        st = self._St(_state())
        cpp.render_close_button(st, cpp.PREVIEW_KIND_SECTION, "Verse 2 / reprise (x2)")
        key = st.buttons[0][1]["key"]
        self.assertTrue(key.startswith("cpl_preview_close_section_"))
        self.assertNotIn(" ", key)
        self.assertNotIn("/", key)


if __name__ == "__main__":
    unittest.main()
