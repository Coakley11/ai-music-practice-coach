"""User rule 2026-11-21: in Voice the singing panel is ALWAYS there - with or without lyrics - and it is the
automatic-follow destination while the Lead Sheet is closed.

Cloud Dev f1e8941a (the user's check): a song without entered lyrics showed no singing panel and the Lead Sheet
took the automatic scrolling. Three causes, all for "no lyrics":
* the panel was built only when some section had lyrics, or when Show Chords was off;
* ``CHART_ALWAYS_SHOWN`` held the chart open whatever the Lead Sheet switch said;
* the follow target was the chart's current chord.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import streamlit_music_practice_app as app

SRC = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")

NO_LYRICS = {"Intro": {"lyrics": [], "chords": ["C", "G"]}, "Verse": {"lyrics": [], "chords": ["Am", "F"]}}
NO_LYRICS_NO_CHORDS = {"Intro": {"lyrics": [], "chords": []}, "Verse": {"lyrics": [], "chords": []}}
WITH_LYRICS = {"Verse": {"lyrics": ["first line", "second line"], "chords": ["C", "G"]}}
TIMELINE = [
    {"t": 0.0, "time": 0.0, "chord": "C", "section": "Intro", "bar_in_section": 0, "event_index": 0},
    {"t": 2.0, "time": 2.0, "chord": "Am", "section": "Verse", "bar_in_section": 0, "event_index": 1},
]


def _surface(panel):
    return app.live_follow_along_component_html(
        b"", TIMELINE, "<div class='lead-grid'><div class='live-chart-cell current-chord'>C</div></div>",
        audio_url="/app/static/x.wav", karaoke_hold_from_shared_controller=True,
        karaoke_lyrics_panel=panel, karaoke_hide_chart=True,
    )


class ThePanelIsBuiltWithoutLyrics(unittest.TestCase):
    def test_voice_always_builds_the_panel(self) -> None:
        i = SRC.index("        if _karaoke_voice:\n            _user_section_text = section_lyrics or {}")
        block = SRC[i:SRC.index("        _karaoke_song_title = ", i)]
        self.assertIn('_karaoke_lyric_panel = _panel_map or {"Performance": {"lyrics": [], "chords": []}}', block)
        self.assertNotIn('if any(entry.get("lyrics") for entry in _panel_map.values()):', block)

    def test_the_panel_html_is_there_for_a_song_without_lyrics(self) -> None:
        html_ = _surface(NO_LYRICS)
        self.assertIn('id="karaoke-lyric-panel"', html_)
        self.assertIn("const CHART_ALWAYS_SHOWN = false;", html_)

    def test_without_a_panel_the_chart_is_still_the_display(self) -> None:
        self.assertIn("const CHART_ALWAYS_SHOWN = true;", _surface(None))


def _browser(test: unittest.TestCase, panel, *, ls_open: bool):
    try:
        from playwright import sync_api
    except ImportError:
        test.skipTest("playwright not installed")
    marker = f'<span class="ks-ls-state" data-ls-open="{"1" if ls_open else "0"}" hidden></span>'
    page_html = "<!doctype html><html><body>" + marker + _surface(panel) + "</body></html>"
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(page_html, wait_until="load")
            page.wait_for_function("() => typeof window.__karaokeUpdateLyricPanel === 'function'", timeout=10000)
            before = page.evaluate("() => (document.getElementById('karaoke-lyric-panel') || {}).innerText || ''")
            page.evaluate(f"() => window.__karaokeUpdateLyricPanel({json.dumps(TIMELINE[0])}, {{timeline: window.__karaokeTimeline}})")
            out = page.evaluate("""() => {
              const p = document.getElementById('karaoke-lyric-panel');
              const t = window.__karaokeFollowTarget ? window.__karaokeFollowTarget() : null;
              return {text: (p.innerText || '').replace(/\\s+/g, ' '),
                      chips: document.querySelectorAll('#karaoke-lp-chord-strip .karaoke-lp-chord').length,
                      section: (document.getElementById('karaoke-lp-section') || {}).textContent || '',
                      next: (document.getElementById('karaoke-lp-next') || {}).textContent || '',
                      target: t ? (t.closest && t.closest('#karaoke-lyric-panel') ? 'panel' : 'chart') : ''};
            }""")
            out["before"] = before
            return out
        finally:
            browser.close()


class AVoiceSongWithoutLyricsInTheBrowser(unittest.TestCase):
    def test_the_panel_shows_the_section_the_chords_and_next(self) -> None:
        out = _browser(self, NO_LYRICS, ls_open=False)
        self.assertIn("This song has no lyrics", out["before"])
        self.assertIn("No lyrics for this song - follow the chords.", out["text"])
        self.assertEqual(out["section"], "Intro")
        self.assertIn("Verse", out["next"])
        self.assertGreater(out["chips"], 0)
        self.assertNotIn("Instrumental", out["text"])

    def test_show_chords_off_keeps_the_panel_without_chords(self) -> None:
        out = _browser(self, NO_LYRICS_NO_CHORDS, ls_open=False)
        self.assertIn("No lyrics for this song - follow the music.", out["text"])
        self.assertEqual(out["chips"], 0)

    def test_the_lead_sheet_closed_follows_the_panel_not_the_chart(self) -> None:
        self.assertEqual(_browser(self, NO_LYRICS, ls_open=False)["target"], "panel")

    def test_the_lead_sheet_open_still_follows_the_chart(self) -> None:
        self.assertEqual(_browser(self, NO_LYRICS, ls_open=True)["target"], "chart")

    def test_a_song_with_lyrics_is_unchanged(self) -> None:
        out = _browser(self, WITH_LYRICS, ls_open=False)
        self.assertNotIn("No lyrics for this song", out["text"])


if __name__ == "__main__":
    unittest.main()
