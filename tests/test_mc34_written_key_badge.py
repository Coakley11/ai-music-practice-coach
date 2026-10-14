"""MC3.4 — Mission Backing's Written key badge shows the active instrument's icon."""

from __future__ import annotations

import logging
import re
import unittest

from instrument_transposition import CHART_IN_INSTRUMENT_KEY_KEY
from music_feature_icons import CLARINET_ICON_SVG, INSTRUMENT_ICONS
from tests.test_mc32_corrections import _card_html, _staged_session, _visible

logging.disable(logging.CRITICAL)


def _badges(html: str) -> list[str]:
    return re.findall(r'<span class="ui-backing-badge[^"]*">(.*?)</span>', html, flags=re.S)


def _written_badge(html: str) -> str:
    return next((b for b in _badges(html) if "Written key" in b), "")


def _written_session(instrument: str, **extra):
    s, e, sp = _staged_session(instrument=instrument)
    s[CHART_IN_INSTRUMENT_KEY_KEY] = True
    s.update(extra)
    return s


class TestMissionBackingWrittenKeyBadge(unittest.TestCase):
    def test_clarinet_uses_the_rendered_clarinet_icon(self) -> None:
        html = _card_html(_written_session("Clarinet"))
        badge = _written_badge(html)
        self.assertTrue(badge.startswith(CLARINET_ICON_SVG), badge[:120])  # real inline SVG, not escaped
        self.assertNotIn("📝", badge)
        text = _visible(html)
        self.assertIn("Written key · D", text)  # concert C on a B♭ clarinet is written D
        for bad in ("<svg", "<path", "&lt;", "viewBox", "class="):
            self.assertNotIn(bad, text, bad)  # no raw markup printed as text

    def test_saxophone_and_trumpet_use_their_family_icons(self) -> None:
        # The app's instrument is "Saxophone" (Alto/Tenor/… is a sub-type), "Trumpet", "Clarinet".
        for inst, family, written in (("Saxophone", "Saxophone", "A"), ("Trumpet", "Trumpet", "D")):
            with self.subTest(inst=inst):
                badge = _written_badge(_card_html(_written_session(inst)))
                self.assertTrue(badge.startswith(INSTRUMENT_ICONS[family]), (inst, badge[:60]))
                self.assertIn("Written key · ", badge)
                self.assertNotIn("📝", badge)

    def test_written_value_still_comes_from_the_projection(self) -> None:
        from songs.key_state import resolve_active_musical_key

        s = _written_session("Clarinet")
        mk = resolve_active_musical_key(s)
        self.assertEqual(mk.chart_key_mode, "written")
        self.assertIn(f"Written key · {mk.chart_key.split()[0]}", _visible(_card_html(s)))

    def test_concert_instrument_shows_no_written_badge(self) -> None:
        html = _card_html(_written_session("Piano"))
        self.assertEqual(_written_badge(html), "")

    def test_written_mode_off_shows_no_written_badge(self) -> None:
        s, _e, _sp = _staged_session(instrument="Clarinet")
        self.assertEqual(_written_badge(_card_html(s)), "")

    def test_single_chord_mission_card_uses_the_instrument_icon_too(self) -> None:
        from mission_span_backing import clear_span_backing

        s = _written_session("Clarinet")
        clear_span_backing(s)
        html = _card_html(s)
        text = _visible(html)
        self.assertIn("Improvise using only chord tones", text)  # single-chord card unchanged
        self.assertTrue(_written_badge(html).startswith(CLARINET_ICON_SVG))

    def test_span_mission_metadata_unchanged(self) -> None:
        text = _visible(_card_html(_written_session("Clarinet")))
        self.assertIn("The Girl from Ipanema · Enclose the next target · A", text)
        self.assertIn("Written key: D", text)
        self.assertEqual(text.count("Progression:"), 1)  # span progression (written-key chart) once
        self.assertNotIn("Gm7", text)  # no stale one-chord field
        self.assertIn("Instrument · Clarinet", text)

    def test_non_mission_creative_backing_keeps_the_generic_icon(self) -> None:
        from backing_context_ui import _semantic_themed_badge
        from music_feature_icons import semantic_field_icon

        generic = semantic_field_icon("written_key")
        self.assertTrue(_semantic_themed_badge("written_key", "Written key", "D").startswith(
            f'<span class="ui-backing-badge badge-meta">{generic} '))


if __name__ == "__main__":
    unittest.main()
