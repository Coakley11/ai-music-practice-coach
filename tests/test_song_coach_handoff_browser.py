"""Song-Aware Coaching S7 — Continue in Song-Based Improvisation in a real browser.

Starts the app on an isolated data folder and drives Chromium: a playing coaching loop stops
when the musician continues in Song-Based Improvisation, nothing plays there by itself, Back
returns to the lesson with a brief welcome, and neither the return nor a refresh restarts the
audio. Skipped when Playwright / Chromium is unavailable.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestHandoffInBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        cls._data = tempfile.mkdtemp(prefix="song_coach_handoff_browser_")
        port = _free_port()
        cls.url = f"http://127.0.0.1:{port}"
        env = {**os.environ, "MUSIC_APP_DATA_DIR": cls._data, "PYTHONIOENCODING": "utf-8"}
        cls._server = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "streamlit_music_practice_app.py", "--server.port", str(port),
             "--server.headless", "true", "--browser.gatherUsageStats", "false"],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 180
        while time.time() < deadline:
            try:
                if urllib.request.urlopen(f"{cls.url}/_stcore/health", timeout=2).read().strip() == b"ok":
                    break
            except Exception:
                time.sleep(1)
        else:
            cls._stop_server()
            raise unittest.SkipTest("the app server did not start")
        cls._pw = sync_playwright().start()
        try:
            cls._browser = cls._pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        except Exception as exc:
            cls._pw.stop()
            cls._stop_server()
            raise unittest.SkipTest(f"Chromium unavailable: {exc}")

    @classmethod
    def _stop_server(cls) -> None:
        cls._server.terminate()
        try:
            cls._server.wait(timeout=20)
        except Exception:
            cls._server.kill()
        shutil.rmtree(cls._data, ignore_errors=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._browser.close()
        cls._pw.stop()
        cls._stop_server()

    # ------------------------------------------------------------------ helpers

    def _idle(self, page, ms=1500):
        page.wait_for_timeout(300)
        try:
            page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=90000)
        except Exception:
            pass
        page.wait_for_timeout(ms)

    def _players(self, page):
        out = []
        for f in page.frames:
            try:
                if f.evaluate("() => !!window.__songCoachLoop"):
                    out.append(f)
            except Exception:
                continue
        return out

    def _playing(self, page) -> int:
        n = 0
        for f in self._players(page):
            try:
                n += f.evaluate("() => window.__songCoachLoop.state") == "playing"
            except Exception:
                pass
        return n + page.evaluate("() => [...document.querySelectorAll('audio')].filter(a => !a.paused).length")

    def _open_coaching(self, page):
        tab = page.locator(".st-key-improv_intelligence_tab label").filter(has_text="Song-Aware Coaching")
        for _ in range(3):  # a fresh app may open Creative on another analysis mode
            if tab.count():
                break
            page.wait_for_selector(".st-key-studio_quick_nav_btn_creative button", timeout=60000)
            page.locator(".st-key-studio_quick_nav_btn_creative button").first.click()
            self._idle(page, 3000)
            if tab.count():
                break
            sel = page.locator(".st-key-creative_lab_analysis_mode")
            if sel.count():
                sel.first.click()
                try:
                    page.get_by_role("option").filter(has_text="Improvisation Intelligence").first.click(timeout=5000)
                except Exception:
                    page.keyboard.press("Escape")
                self._idle(page, 3000)
        tab.first.click()
        self._idle(page, 3000)

    # ------------------------------------------------------------------ the journey

    def test_continue_stops_the_loop_and_back_returns_without_audio(self) -> None:
        page = self._browser.new_page(viewport={"width": 1400, "height": 1100})
        page.goto(self.url)
        self._idle(page, 8000)
        songs = page.locator(".st-key-sidebar_goto_song_selection button, .st-key-studio_quick_nav_btn_picker button")
        songs.first.wait_for(state="visible", timeout=60000)
        songs.first.click()
        self._idle(page, 3000)
        page.locator(".st-key-matching_song_dropdown input").first.click()
        page.keyboard.press("Control+A")
        page.keyboard.type("Perfect")
        page.wait_for_timeout(1200)
        page.get_by_role("option").filter(has_text="Perfect").first.click()
        self._idle(page, 3500)
        self._open_coaching(page)
        page.locator(".st-key-song_coach_build button").first.click()
        self._idle(page, 3500)
        player = self._players(page)[0]
        player.locator("#play").click()
        player.wait_for_function("() => window.__songCoachLoop.state === 'playing'", timeout=15000)
        self.assertEqual(self._playing(page), 1)
        self.assertIn("Song-Based Improvisation will open the full song.", page.inner_text("body"))

        page.locator(".st-key-song_coach_continue_sbi button").first.click()
        self._idle(page, 3500)
        self.assertEqual(self._players(page), [], "the coaching loop is gone")
        self.assertEqual(self._playing(page), 0, "nothing plays in Song-Based Improvisation by itself")
        checked = page.locator(".st-key-improv_entry_mode input:checked")
        self.assertTrue(checked.count() and "Song-Based" in page.locator(".st-key-improv_entry_mode").inner_text())
        page.wait_for_timeout(2500)
        self.assertEqual(self._playing(page), 0)

        # Back lives in the fixed floating navigation gutter: click the element itself.
        page.locator(".st-key-studio_nav_back_btn button").first.evaluate("b => b.click()")
        self._idle(page, 3500)
        body = page.inner_text("body")
        self.assertIn("Welcome back", body)
        self.assertIn("Your plan", body)
        players = self._players(page)
        self.assertEqual(len(players), 1)
        self.assertEqual(players[0].evaluate("() => window.__songCoachLoop.state"), "stopped")
        page.wait_for_timeout(3000)
        self.assertEqual(self._playing(page), 0, "returning never restarts the loop")

        page.reload()
        self._idle(page, 9000)
        self.assertEqual(self._playing(page), 0, "a refresh never restarts audio")
        page.close()


if __name__ == "__main__":
    unittest.main()
