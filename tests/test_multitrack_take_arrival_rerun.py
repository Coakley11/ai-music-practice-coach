"""Issue 64: a layer that has audio must not keep saying EMPTY.

Found by driving the real app. A take was uploaded, the slot header went on reporting
``EMPTY``, and only a page reload revealed that the audio had been in the session all
along. Three takes in one run were scored as failed uploads before the reload showed
otherwise.

The cause is render order inside the slot block, not the upload:

    _slot_ready = bool(st.session_state.mt_tracks.get(slot))   # read
    ... multitrack_layer_badge_html(ready=_slot_ready) ...      # EMPTY / HAS AUDIO drawn
    with st.expander(..., expanded=_slot_ready):               # panel state decided
        ...
        st.session_state.mt_tracks[slot] = _mt_bytes            # take arrives

Everything the musician looks at was decided earlier in the same script run. Streamlit
reran to deliver the file, so the audio is really there - but the header for that run was
already written from the stale value, and nothing asks for another pass. The sibling
*Save layer* branch has always ended in ``st.rerun()``; the arrival branch did not.

This is a source-level test because the behaviour lives in a 28k-line Streamlit script
with no seam to call: the arrival branch cannot be invoked without a script run. What it
pins is the ordering fact that makes the rerun necessary, so removing the rerun fails
here rather than in a browser weeks later.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "streamlit_music_practice_app.py"


def app_lines() -> list[str]:
    return APP.read_text(encoding="utf-8", errors="replace").splitlines()


class TheSlotHeaderIsDrawnBeforeTheTakeArrives(unittest.TestCase):
    """The ordering that makes a rerun necessary. If this stops being true, say so."""

    def setUp(self):
        self.lines = app_lines()

    def _line_of(self, needle: str) -> int:
        for n, line in enumerate(self.lines, 1):
            if needle in line:
                return n
        self.fail(f"no line containing {needle!r} - the slot block has been rewritten")

    def test_the_badge_is_rendered_before_the_upload_is_read(self):
        ready = self._line_of("_slot_ready = bool(st.session_state.mt_tracks.get(slot))")
        badge = self._line_of("multitrack_layer_badge_html(ready=_slot_ready)")
        store = self._line_of("st.session_state.mt_tracks[slot] = _mt_bytes")
        self.assertLess(ready, badge, "the badge should read _slot_ready")
        self.assertLess(
            badge, store,
            "the badge is now drawn after the take is stored - if the slot block was "
            "reordered so the header sees the new audio, the rerun below may no longer "
            "be needed; check before deleting it",
        )

    def test_the_expander_state_is_also_decided_before_the_take_arrives(self):
        expander = self._line_of('with st.expander(f"Layer controls')
        store = self._line_of("st.session_state.mt_tracks[slot] = _mt_bytes")
        self.assertLess(expander, store)


class ANewTakeAsksForARerun(unittest.TestCase):
    def setUp(self):
        self.text = APP.read_text(encoding="utf-8", errors="replace")

    def _arrival_block(self) -> str:
        """The branch that runs when recorded or uploaded audio is new for a slot."""
        start = self.text.index("st.session_state.mt_tracks[slot] = _mt_bytes")
        end = self.text.index("_take_line = take_status_line(st.session_state, slot)",
                              start)
        return self.text[start:end]

    def test_the_arrival_branch_reruns(self):
        block = self._arrival_block()
        self.assertIn(
            "st.rerun()", block,
            "a take that arrives must trigger a rerun, or the slot header keeps "
            "reporting EMPTY about audio already in the session",
        )

    def test_the_rerun_comes_after_the_take_is_persisted(self):
        """Rerunning first would throw away the save and the identity stamp."""
        block = self._arrival_block()
        persisted = block.index('force_save_music_state(st, reason="multitrack_upload")')
        rerun = block.index("st.rerun()")
        self.assertLess(persisted, rerun)

    def test_the_identity_stamp_happens_before_the_rerun(self):
        block = self._arrival_block()
        self.assertLess(block.index("note_layer_recorded("), block.index("st.rerun()"))

    def test_the_take_is_marked_unsaved_before_the_rerun(self):
        """Otherwise the guard would see a saved project where a fresh take sits."""
        block = self._arrival_block()
        self.assertLess(block.index("mark_take_unsaved("), block.index("st.rerun()"))

    def test_the_rerun_only_fires_for_audio_that_is_actually_new(self):
        """A rerun on every pass would loop: the branch is guarded by a change check."""
        guard = "if st.session_state.mt_tracks.get(slot) != _mt_bytes:"
        self.assertIn(guard, self.text)
        self.assertLess(
            self.text.index(guard),
            self.text.index("st.session_state.mt_tracks[slot] = _mt_bytes"),
        )

    def test_the_sibling_save_layer_branch_still_reruns(self):
        """The precedent this follows. If it goes, the two paths have diverged again."""
        saved = self.text.index("mark_take_saved(st.session_state, slot)")
        tail = self.text[saved:saved + 1200]
        self.assertIn("st.rerun()", tail)


class TheRerunIsNotLoadBearingForState(unittest.TestCase):
    """The audio reaches the session with or without it; only the display needed fixing.

    Worth stating plainly, because the first reading of the browser evidence was that
    uploads were being dropped. They were not - the take was in `mt_tracks` and survived
    a reload. Nothing about storage, stamping or saving changed here.
    """

    def test_storing_the_take_does_not_depend_on_the_rerun(self):
        text = APP.read_text(encoding="utf-8", errors="replace")
        start = text.index("st.session_state.mt_tracks[slot] = _mt_bytes")
        rerun = text.index("st.rerun()", start)
        between = text[start:rerun]
        for required in ("note_layer_recorded(", "mark_take_unsaved(",
                         "mt_track_filenames[slot]"):
            self.assertIn(required, between,
                          f"{required} must happen whether or not the rerun fires")


if __name__ == "__main__":
    unittest.main()
