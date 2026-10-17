"""The lead-sheet player's static WAV URL must resolve under the app's base path.

The follow-along player is a components.html srcdoc frame, so its URLs resolve
against the app page. Streamlit Community Cloud serves the app under /~/+/; a
root "/app/static/…" URL reached the Cloud wrapper (303 to the login page)
instead of the app, and the lead sheet opened with no audio.
"""

from __future__ import annotations

import re
import unittest

import streamlit_music_practice_app as app


def _live_audio_src(html: str) -> str:
    m = re.search(r'<audio id="live-audio"[^>]*\ssrc="([^"]*)"', html)
    assert m, "live-audio element missing"
    return m.group(1)


class LeadSheetAudioUrlBasePathTests(unittest.TestCase):
    def _render(self, url: str) -> str:
        return app.live_follow_along_component_html(b"", [], "", audio_url=url, autoplay=True)

    def test_static_url_is_page_relative(self) -> None:
        src = _live_audio_src(self._render("/app/static/kc/0cf8372514fb90eaa6d7.wav"))
        self.assertEqual(src, "app/static/kc/0cf8372514fb90eaa6d7.wav")

    def test_never_embeds_inline_wav_when_url_given(self) -> None:
        html = self._render("/app/static/kc/0cf8372514fb90eaa6d7.wav")
        self.assertNotIn("data:audio/wav;base64,", html)

    def test_page_relative_resolves_under_cloud_base_path(self) -> None:
        from urllib.parse import urljoin

        src = _live_audio_src(self._render("/app/static/kc/abc.wav"))
        for page in ("https://x.streamlit.app/~/+/", "https://x.streamlit.app/~/+/backing", "http://localhost:8501/"):
            with self.subTest(page=page):
                base = page.rsplit("/", 1)[0] + "/"
                self.assertEqual(urljoin(page, src), base + "app/static/kc/abc.wav")


if __name__ == "__main__":
    unittest.main()
