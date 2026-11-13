"""Cluster B / P4: one chord row per suggestion card; highlightable chips; compact transport."""

from __future__ import annotations

import os
import re
import unittest

from composition_playback_sync import (
    build_playback_bundle,
    render_synced_score_playback_html,
)

_HARNESS = os.path.join(os.path.dirname(__file__), "_cs_b_card_harness.py")


def _wav() -> bytes:
    import io
    import struct
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(struct.pack("<" + "h" * 800, *([0] * 800)))
    return buf.getvalue()


def _chords_html(chords: list[str], romans: list[str] | None = None) -> str:
    bundle = build_playback_bundle(chord_syms=chords, bpm=100, meter="4/4")
    return render_synced_score_playback_html(
        wav_bytes=_wav(), bundle=bundle, chord_roman_labels=romans, dom_id="t1"
    )


class TestChordPlayerHtml(unittest.TestCase):
    def test_chips_are_the_only_chord_row(self) -> None:
        html_out = _chords_html(["Cmaj7", "Em7", "D7", "G7"], ["Imaj7", "iii7", "V7/V", "V7"])
        self.assertEqual(html_out.count('class="cplay-chord-chip"'), 4)
        for sym in ("Cmaj7", "Em7", "D7", "G7"):
            self.assertIn(f'<span class="cplay-chip-sym">{sym}</span>', html_out)
        self.assertIn('<span class="cplay-chip-rn">V7/V</span>', html_out)
        # no second strip of context labels, no <button> chord chips
        self.assertNotIn('class="cplay-chords"', html_out)
        self.assertNotIn('<button type="button" class="cplay-chord-chip"', html_out)

    def test_compact_transport_replaces_native_audio_controls(self) -> None:
        html_out = _chords_html(["C", "G"])
        self.assertIn('id="t1-play"', html_out)
        self.assertIn('id="t1-stop"', html_out)
        self.assertIn("Resume", html_out)  # pause <-> resume label logic
        self.assertIn("Pause", html_out)
        audio_tag = re.search(r"<audio[^>]*>", html_out).group(0)
        self.assertNotIn("controls", audio_tag)
        self.assertIn("autoplay", audio_tag)

    def test_single_timeline_drives_chip_highlight(self) -> None:
        html_out = _chords_html(["Cmaj7", "Em7", "D7", "G7"])
        # chip highlight is computed from audio.currentTime against the bundle spans
        self.assertIn("audio.currentTime", html_out)
        self.assertIn("setChordChip(found)", html_out)
        spans = re.search(r"const cursorSpans = (\[.*?\]);", html_out, re.S).group(1)
        self.assertEqual(spans.count('"chord": "'), 4)
        self.assertIn("is-active", html_out)

    def test_stop_resets_highlight_and_position(self) -> None:
        html_out = _chords_html(["C", "G"])
        stop = html_out.split('stopBtn.addEventListener("click"')[1].split("});")[0]
        self.assertIn("audio.pause()", stop)
        self.assertIn("audio.currentTime = 0", stop)
        self.assertIn("setChordChip(-1)", stop)

    def test_compact_frame_height(self) -> None:
        from unittest import mock

        import composition_playback_sync as cps

        seen: dict = {}

        def _fake_html(doc, height=None, scrolling=False):
            seen["height"] = height

        bundle = build_playback_bundle(chord_syms=["C", "G", "Am", "F"], bpm=100)
        with mock.patch("streamlit.components.v1.html", _fake_html):
            cps.mount_synced_score_playback(
                mock.MagicMock(), wav_bytes=_wav(), bundle=bundle, dom_id="x"
            )
        self.assertLessEqual(seen["height"], 160)


class TestSlotOwnership(unittest.TestCase):
    def test_chord_row_moves_to_player_only_for_the_armed_chords_only_slot(self) -> None:
        from composition_studio_page import COMPOSER_PREVIEW_WAV_KEY, _chord_row_lives_in_player

        ss = {COMPOSER_PREVIEW_WAV_KEY: b"wav", "composer_preview_slot": "chords:s1:a"}
        self.assertTrue(_chord_row_lives_in_player(ss, "chords:s1:a", has_melody=False))
        # switching candidates: the previous card gets its static chord row back
        self.assertFalse(_chord_row_lives_in_player(ss, "chords:s1:b", has_melody=False))
        # with a melody the score is shown, the card keeps its chord line
        self.assertFalse(_chord_row_lives_in_player(ss, "chords:s1:a", has_melody=True))
        ss.pop(COMPOSER_PREVIEW_WAV_KEY)
        self.assertFalse(_chord_row_lives_in_player(ss, "chords:s1:a", has_melody=False))


class TestSuggestionCardAppTest(unittest.TestCase):
    """Headless Streamlit AppTest (not a real browser)."""

    @staticmethod
    def _run(click_index: int | None):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(_HARNESS, default_timeout=120)
        at.run()
        assert not at.exception, at.exception
        if click_index is not None:
            btns = [b for b in at.button if "Preview" in (b.label or "")]
            btns[click_index].click().run()
            assert not at.exception, at.exception
        return at

    @staticmethod
    def _rows(at) -> int:
        return len([m for m in at.markdown if "composer-suggestion-chords" in m.value])

    def test_initial_cards_each_show_one_chord_row_and_correct_romans(self) -> None:
        at = self._run(None)
        self.assertEqual(self._rows(at), 3)
        text = " ".join(m.value for m in at.markdown)
        self.assertIn("V7/V", text)
        self.assertIsNone(re.search(r"(?<![♭ivx])II7", text))  # D7 is V7/V, never a bare II7
        self.assertEqual(at.session_state["_html_calls"], [])

    def test_preview_replaces_static_row_with_player_chips(self) -> None:
        at = self._run(0)
        calls = at.session_state["_html_calls"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["html"].count('class="cplay-chord-chip"'), 4)
        self.assertEqual(self._rows(at), 2)  # previewed card dropped its static row
        self.assertLessEqual(calls[0]["height"], 160)
        self.assertNotIn(" controls ", calls[0]["html"])

    def test_switching_candidate_moves_the_player(self) -> None:
        at = self._run(1)
        slot = at.session_state["composer_preview_slot"]
        calls = at.session_state["_html_calls"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(self._rows(at), 2)
        card_ids = at.session_state["_sugs"]
        self.assertTrue(slot.endswith(card_ids[1]))
        # card 0 still shows its own static chord row
        first_card = [m.value for m in at.markdown if "composer-suggestion-card" in m.value][0]
        self.assertIn("composer-suggestion-chords", first_card)

    def test_refinement_proposal_shares_the_single_chord_row(self) -> None:
        from composition_chord_suggestions import symbols_to_entries
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(_HARNESS, default_timeout=120)
        at.run()
        sec_id = at.session_state["sec_id"]
        at.session_state["_show_refine"] = True
        at.session_state[f"composer_refine_proposal_{sec_id}"] = {
            "id": "refine_x",
            "name": "More tension",
            "why": "test",
            "chords": symbols_to_entries(["Cmaj7", "Em7", "D7", "G7"]),
        }
        at.run()
        assert not at.exception, at.exception
        before = "".join(m.value for m in at.markdown if "proposed progression" in m.value)
        self.assertEqual(before, "")
        self.assertEqual(at.session_state["_html_calls"], [])
        btn = next(b for b in at.button if b.key == f"composer_refine_preview_{sec_id}")
        btn.click().run()
        assert not at.exception, at.exception
        calls = at.session_state["_html_calls"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["html"].count('class="cplay-chord-chip"'), 4)
        self.assertNotIn('<div class="cplay-chords"', calls[0]["html"])
        refine_md = " ".join(m.value for m in at.markdown if "proposed progression" in m.value)
        # the card no longer prints the proposed chords a second time
        self.assertIn("see the player below", refine_md)
        self.assertNotIn("<strong>| Cmaj7", refine_md)


if __name__ == "__main__":
    unittest.main()
