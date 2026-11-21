"""The Backing card reports a Karaoke song's own end -- never a Key Cycling take, never after a Stop.

Browser run 2026-11-21 (Karaoke Set, 390 px): the Key Cycling Stop turned cycling off, the card's
end report came back on with that render, the stopped take read as "ended" and the set moved on to
its next song (Blackbird, Original Key G major) -- the card's Original Key "changed" from C minor.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.test_key_cycle_pause_reports_sounding_key import _silent_wav

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "backing_transport_component" / "index.html").read_text(encoding="utf-8")

_PARENT = """<html><body><audio id="AUDIO_ID" src="http://card.test/take.wav" preload="auto"></audio>
<iframe id="card"></iframe>
<script>window.__sent = []; window.addEventListener('message', function (e) {
  if (e.data && e.data.type === 'streamlit:setComponentValue') window.__sent.push(e.data.value); });</script>
</body></html>"""

_RENDER = """(args) => { const f = document.getElementById('card');
  f.contentWindow.postMessage({ type: 'streamlit:render', args: args }, '*'); }"""

_ACTIONS = """() => (window.__sent || []).map(v => (v && (v.action || v)) || '').map(String)"""


def _run(test, audio_id: str, playing_args: dict, after_args: dict, stop_audio_js: str) -> list:
    try:
        from playwright import sync_api
    except Exception:  # pragma: no cover
        test.skipTest("playwright not installed")
    wav = _silent_wav(seconds=2.0)

    def handle(route):
        if route.request.url.endswith(".wav"):
            route.fulfill(status=200, body=wav, headers={"Content-Type": "audio/wav", "Content-Length": str(len(wav))})
        else:
            route.fulfill(status=200, content_type="text/html", body=_PARENT.replace("AUDIO_ID", audio_id))

    errors: list = []
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        try:
            page = browser.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.route("http://card.test/**", handle)
            page.goto("http://card.test/app/")
            page.evaluate("(html) => { document.getElementById('card').srcdoc = html; }", CARD)
            page.wait_for_timeout(800)
            page.evaluate(_RENDER, playing_args)
            page.evaluate("() => document.getElementById('" + audio_id + "').play()")
            page.wait_for_timeout(900)                       # the card has seen it playing
            page.evaluate(stop_audio_js)
            page.evaluate(_RENDER, after_args)
            page.wait_for_timeout(3200)                      # past the take's end and the 0.7 s debounce
            test.assertTrue(page.evaluate("() => document.querySelector('audio').ended"), "the take did not end")
            sent = page.evaluate(_ACTIONS)
        finally:
            browser.close()
    test.assertEqual(errors, [], errors)
    return sent


_BASE = {"enabled": True, "server_playing": True, "render_id": "r1", "restart_on_resume": False, "count_in": None}
_RUN_TO_END = "() => {}"  # the 2 s take plays on to its own end


class TheCardReportsOnlyTheSongsOwnEnd(unittest.TestCase):
    def test_a_karaoke_take_that_plays_to_its_end_is_reported(self) -> None:
        sent = _run(self, "backing-audio",
                    dict(_BASE, report_ended=True, transport="playing", cycle_active=False),
                    dict(_BASE, report_ended=True, transport="playing", cycle_active=False), _RUN_TO_END)
        self.assertIn("ended", sent)

    def test_after_the_key_cycling_stop_nothing_is_reported(self) -> None:
        # cycling on (no end report) -> its Stop: cycling off, report back on, transport stopped
        sent = _run(self, "kc-buf-0",
                    dict(_BASE, report_ended=False, transport="playing", cycle_active=True),
                    dict(_BASE, report_ended=True, transport="stopped", cycle_active=False, server_playing=False),
                    _RUN_TO_END)
        self.assertNotIn("ended", sent)

    def test_a_stopped_song_is_not_reported_as_ended(self) -> None:
        sent = _run(self, "backing-audio",
                    dict(_BASE, report_ended=True, transport="playing", cycle_active=False),
                    dict(_BASE, report_ended=True, transport="stopped", cycle_active=False, server_playing=False),
                    _RUN_TO_END)
        self.assertNotIn("ended", sent)

    def test_a_key_cycling_take_is_never_the_songs_end(self) -> None:
        sent = _run(self, "kc-buf-1",
                    dict(_BASE, report_ended=True, transport="playing", cycle_active=False),
                    dict(_BASE, report_ended=True, transport="playing", cycle_active=False), _RUN_TO_END)
        self.assertNotIn("ended", sent)


def _hook(test, args: dict) -> list:
    """The singing panel's player calls __backingReportKaraokeEnded from its own ended event."""
    try:
        from playwright import sync_api
    except Exception:  # pragma: no cover
        test.skipTest("playwright not installed")
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.route("http://card.test/**", lambda r: r.fulfill(status=200, content_type="text/html",
                                                                   body=_PARENT.replace("AUDIO_ID", "x")))
            page.goto("http://card.test/app/")
            page.evaluate("(html) => { document.getElementById('card').srcdoc = html; }", CARD)
            page.wait_for_timeout(800)
            page.evaluate(_RENDER, args)
            page.wait_for_timeout(300)
            page.evaluate("() => window.__backingReportKaraokeEnded()")
            page.wait_for_timeout(400)
            return page.evaluate(_ACTIONS)
        finally:
            browser.close()


class TheSingingPanelsEndHook(unittest.TestCase):
    """Browser run 2026-11-21 on 4e803012 (Karaoke Set, 390 px): after the Key Cycling Stop the set still
    moved on -- the singing panel's own player reported its end through this hook, which sent "ended"
    whatever the transport said."""

    def test_while_playing_it_reports_the_end(self) -> None:
        self.assertIn("ended", _hook(self, dict(_BASE, report_ended=False, transport="playing")))

    def test_while_key_cycling_is_on_it_reports_nothing(self) -> None:
        # acceptance run 2026-11-21 on 0cc15d8c: the Key Cycling Stop's click produced this end while the
        # card still said playing (the server had not applied the Stop yet)
        self.assertNotIn("ended", _hook(self, dict(_BASE, report_ended=False, transport="playing", cycle_active=True)))

    def test_after_a_stop_it_reports_nothing(self) -> None:
        self.assertNotIn("ended", _hook(self, dict(_BASE, report_ended=False, transport="stopped", server_playing=False)))


def test_the_server_advances_a_set_only_for_a_playing_song() -> None:
    src = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
    i = src.index('elif _card_action == "ended":')
    block = src[i:i + 4200]
    assert 'and transport_intent(st.session_state) == "playing"' in block
    assert block.index('transport_intent(st.session_state) == "playing"') < block.index("transition_karaoke_performance(")
    assert "and not _kc_owns_song_end(st.session_state)" in block
    assert block.index("_kc_owns_song_end") < block.index("transition_karaoke_performance(")


def test_key_cycling_owns_the_song_end_while_it_is_on() -> None:
    from unittest import mock

    import backing_key_cycle as kc
    import streamlit_music_practice_app as app

    with mock.patch("monetization_entitlements.can_use", return_value=True),             mock.patch.object(kc, "persist_key_cycle_position", return_value=True):
        ss: dict = {"display_key": "A", "concert_key": "A"}
        assert app._kc_owns_song_end(ss) is False
        kc.start_key_cycle(ss, start_key="Am", interval=5, direction="up")
        assert app._kc_owns_song_end(ss) is True


if __name__ == "__main__":
    unittest.main()
