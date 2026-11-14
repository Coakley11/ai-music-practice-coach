"""Second browser pass on composition-quality-v2: regression tests for the defects it found.

C. highlighted chord must clear when playback ends.
A. manual chord editor stays open while it holds unapplied edits.
B. library delete needs an explicit confirmation; Cancel changes nothing.
Roman labels: a closing A7 in Dm7 G7 Cmaj7 A7 is V7/ii (progressions loop).
"""
from __future__ import annotations

import io
import struct
import unittest
import wave

from composition_playback_sync import build_playback_bundle, render_synced_score_playback_html


def _wav() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(struct.pack("<" + "h" * 800, *([0] * 800)))
    return buf.getvalue()


class TestHighlightClearsWhenPlaybackEnds(unittest.TestCase):
    def test_tick_resets_everything_once_audio_has_ended(self) -> None:
        bundle = build_playback_bundle(chord_syms=["Am", "F", "C", "Gm"], bpm=96, meter="4/4")
        html_out = render_synced_score_playback_html(wav_bytes=_wav(), bundle=bundle, dom_id="t2")
        tick = html_out[html_out.index("function tick()") :]
        guard = tick.index("audio.ended")
        # the ended guard comes first, before the 'hold the last chord' logic that re-lit it
        self.assertLess(guard, tick.index("found = cursorSpans.length - 1"))
        self.assertIn("resetAll(); return;", tick[guard : guard + 80])


class TestManualEditorStaysOpen(unittest.TestCase):
    def _fn(self):
        from composition_studio_page import _manual_chord_editor_needs_attention

        return _manual_chord_editor_needs_attention

    def test_closed_when_nothing_pending(self) -> None:
        f = self._fn()
        sec = {"id": "s1", "chords": [{"chord": "C"}, {"chord": "G"}]}
        self.assertFalse(f({}, sec))
        self.assertFalse(f({"composer_manual_chord_draft_s1": [{"chord": "C"}, {"chord": "G"}]}, sec))

    def test_open_when_draft_differs_from_saved(self) -> None:
        from composition_chord_manual_editor import draft_key

        f = self._fn()
        sec = {"id": "s1", "chords": [{"chord": "C"}, {"chord": "G"}]}
        state = {draft_key("s1"): [{"chord": "Dm7"}, {"chord": "G7"}]}
        self.assertTrue(f(state, sec))

    def test_open_mid_edit_even_for_chord_index_zero(self) -> None:
        f = self._fn()
        sec = {"id": "s1", "chords": [{"chord": "C"}]}
        self.assertTrue(f({"composer_chord_edit_idx_s1": 0}, sec))
        self.assertTrue(f({"composer_chord_insert_at_s1": 1}, sec))
        self.assertTrue(f({"composer_chord_split_idx_s1": 0}, sec))


class _Btn:
    def __init__(self, log: list, clicked: set):
        self.log, self.clicked = log, clicked


class _FakeSt:
    """Just enough of streamlit for render_library_rows."""

    def __init__(self, session: dict, clicks: set[str]):
        self.session, self.clicks = session, clicks
        self.buttons: list[str] = []
        self.warnings: list[str] = []

    def caption(self, *a, **k): ...
    def markdown(self, *a, **k): ...
    def error(self, *a, **k): ...

    def warning(self, msg, **k):
        self.warnings.append(str(msg))

    def container(self, **k):
        import contextlib

        return contextlib.nullcontext()

    def button(self, label, key=None, on_click=None, args=(), **k):
        self.buttons.append(key)
        if key in self.clicks:
            if on_click:
                on_click(*args)
            return True
        return False


class TestLibraryDeleteConfirmation(unittest.TestCase):
    def _session(self) -> dict:
        return {
            "composer_saved_compositions": {"d1": {"id": "d1", "metadata": {"title": "Song One"}, "sections": []}},
            "composer_library_initialized": True,
        }

    def test_first_click_only_asks_for_confirmation(self) -> None:
        from composition_library_ui import PENDING_DELETE_KEY, render_library_rows

        sess = self._session()
        st = _FakeSt(sess, {"composer_lib_del_d1"})
        render_library_rows(st, sess, "")
        self.assertEqual(sess.get(PENDING_DELETE_KEY), "d1")
        self.assertIn("d1", sess["composer_saved_compositions"])  # nothing deleted yet
        st2 = _FakeSt(sess, set())
        render_library_rows(st2, sess, "")
        self.assertIn("composer_lib_delyes_d1", st2.buttons)
        self.assertIn("composer_lib_delcancel_d1", st2.buttons)
        self.assertTrue(st2.warnings and "permanently" in st2.warnings[0])

    def test_cancel_leaves_everything_unchanged(self) -> None:
        from composition_library_ui import PENDING_DELETE_KEY, render_library_rows

        sess = self._session()
        sess[PENDING_DELETE_KEY] = "d1"
        render_library_rows(_FakeSt(sess, {"composer_lib_delcancel_d1"}), sess, "")
        self.assertNotIn(PENDING_DELETE_KEY, sess)
        self.assertIn("d1", sess["composer_saved_compositions"])
        self.assertFalse(sess.get("composer_deleted_document_ids"))

    def test_confirm_deletes(self) -> None:
        from composition_library_ui import PENDING_DELETE_KEY, render_library_rows

        sess = self._session()
        sess[PENDING_DELETE_KEY] = "d1"
        out = render_library_rows(_FakeSt(sess, {"composer_lib_delyes_d1"}), sess, "")
        self.assertEqual(out, "deleted:d1")
        self.assertIn("d1", sess["composer_deleted_document_ids"])


class TestClosingDominantLabel(unittest.TestCase):
    def test_last_chord_wraps_to_first_for_the_label(self) -> None:
        from composition_chord_refinements import functional_label, propose_chord_refinement  # noqa: F401

        self.assertEqual(functional_label("A7", "C", "Dm7"), "V7/ii")

    def test_card_reason_agrees_with_roman_line(self) -> None:
        from composition_chord_refinements import _loop_next

        self.assertEqual(_loop_next(["Dm7", "G7", "Cmaj7", "A7"], 3), "Dm7")
        self.assertIsNone(_loop_next(["C"], 0))


if __name__ == "__main__":
    unittest.main()
