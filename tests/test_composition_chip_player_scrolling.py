"""The chord-chip player never scrolls the page (2026-11-19).

Measured with a browser probe at 390/1366/1440 px: setChordChip called cur.scrollIntoView({block:"nearest"}),
which walks up to the nearest scrollable ancestor -- on Streamlit that is the page container. With the player
scrolled off screen during playback, the first chord change pulled the page 376-399 px back to the player and
then held it there for every chord after that, while the user was trying to read something else.

The chord row now scrolls itself, and only when its own contents overflow (the Custom Lab "Entire song preview"
caps the row at 220 px; elsewhere every chip fits and nothing scrolls at all). Nothing in this player may move
the page: that belongs to the shared page-follow controller alone.
"""

import io
import re
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


def _html(*, scroll_px: int = 0, chords=("D", "Bm", "G", "A")) -> str:
    bundle = build_playback_bundle(chord_syms=list(chords), bpm=100, meter="4/4")
    if scroll_px:
        bundle["chips_scroll_px"] = scroll_px
    return render_synced_score_playback_html(wav_bytes=_wav(), bundle=bundle, dom_id="t1")


class TestNoPageScrolling(unittest.TestCase):
    def test_the_player_never_calls_scroll_into_view(self) -> None:
        html_out = _html()
        code = re.sub(r"//[^\n]*", "", html_out)  # comments may name it; code may not call it
        self.assertNotIn("scrollIntoView", code)

    def test_nothing_the_player_scrolls_is_outside_its_own_chord_row(self) -> None:
        """Every line that mentions scrolling must name the chip box and nothing else.

        (window.top does appear in this player, for the "only one playback at a time" registry. That is not
        scrolling, so the check is line by line rather than a blanket ban on the word.)
        """
        code = re.sub(r"//[^\n]*", "", _html())
        scroll_lines = [ln.strip() for ln in code.splitlines() if "scroll" in ln.lower()]
        self.assertTrue(scroll_lines)
        for line in scroll_lines:
            with self.subTest(line=line):
                self.assertIn("box", line)
                for reach in ("window", "parent", "document", "top", "stMain", "stAppViewContainer"):
                    self.assertNotIn(reach, line.replace("scrollTop", ""))

    def test_the_only_thing_it_scrolls_is_its_own_chord_row(self) -> None:
        code = re.sub(r"//[^\n]*", "", _html())
        self.assertIn("keepChipVisible", code)
        self.assertEqual(code.count("scrollTop +="), 2)  # the two branches, above and below the row

    def test_it_only_scrolls_when_the_row_actually_overflows(self) -> None:
        code = re.sub(r"//[^\n]*", "", _html())
        self.assertIn("scrollHeight <= box.clientHeight + 1", code)


class TestChipRowStillWorks(unittest.TestCase):
    def test_the_highlight_still_moves_chip_by_chip(self) -> None:
        html_out = _html()
        self.assertEqual(html_out.count('class="cplay-chord-chip"'), 4)
        self.assertIn('classList.toggle("is-active", idx === i)', html_out)
        self.assertIn("setChordChip", html_out)

    def test_the_scrolling_row_exists_only_when_a_height_cap_is_asked_for(self) -> None:
        self.assertNotIn("overflow-y:auto", _html())
        capped = _html(scroll_px=220, chords=[f"C{i}" for i in range(24)])
        self.assertIn("max-height:220px;overflow-y:auto", capped)
        self.assertIn('id="t1-chips"', capped)

    def test_the_row_is_found_inside_this_player_only(self) -> None:
        """Two players on one page must not scroll each other's row."""
        code = _html()
        self.assertIn('root.querySelector("#t1-chips")', code)


class TestTheRealOverflowSurface(unittest.TestCase):
    """Custom Progression Lab, "Preview entire song": the one surface whose chord row is height-capped."""

    def _song_html(self, n_sections: int = 6) -> str:
        import custom_progression_preview as cpp

        sections = {
            f"Verse {i}": [{"chord": c, "bars": 1} for c in ("C", "Am", "F", "G")]
            for i in range(1, n_sections + 1)
        }
        inputs = {
            "sections": sections,
            "key": "C",
            "time_signature": "4/4",
            "bpm": 120,
            "arrangement": list(sections),
        }
        html_doc, height, _meta = cpp.build_player_html(inputs, "song", "", 1)
        return html_doc

    def test_the_entire_song_row_is_capped_and_overflows(self) -> None:
        html_doc = self._song_html()
        self.assertIn("max-height:220px;overflow-y:auto", html_doc)
        chips = html_doc.count('class="cplay-chord-chip"')
        self.assertGreaterEqual(chips, 24)  # 6 rows of 4 at ~50 px each: taller than the 220 px cap

    def test_that_surface_scrolls_its_row_and_not_the_page(self) -> None:
        code = re.sub(r"//[^\n]*", "", self._song_html())
        self.assertNotIn("scrollIntoView", code)
        self.assertIn("keepChipVisible", code)
        self.assertIn('root.querySelector("#cplprev-song-1-chips")', code)

    def test_a_single_section_preview_has_no_scrolling_row_at_all(self) -> None:
        import custom_progression_preview as cpp

        inputs = {
            "sections": {"Verse": [{"chord": "C", "bars": 1}, {"chord": "G", "bars": 1}]},
            "key": "C",
            "time_signature": "4/4",
            "bpm": 120,
            "arrangement": None,
        }
        html_doc, _h, _m = cpp.build_player_html(inputs, "section", "Verse", 1)
        self.assertNotIn("overflow-y:auto", html_doc)


if __name__ == "__main__":
    unittest.main()
