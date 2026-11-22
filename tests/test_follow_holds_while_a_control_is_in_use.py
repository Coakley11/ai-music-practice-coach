"""User requirement 2026-11-21: Groove can be changed in Advanced Playback Settings while the music plays.

Measured on 092f6855 (390 px, isolated data, playing): the card's Advanced settings button moved the page to the
settings ('anchor:anchor_backing_playback_settings') and the page follow took it straight back to the singing
panel ('catchup-outside'); the Groove list was opened over a page that was being moved away, and no choice could
be made. Every Groove choice that did register was kept - nothing reset the value; the page moved under the person.

* the controller (v8) holds every follower while a dropdown list is open, and its closing starts the usual 3 s;
* ``C.userNavigated()`` starts the same hold, and a section the person asked for by a button (USER_NAV_ANCHORS)
  is neither dropped by their own tap nor taken back at once.
"""
from __future__ import annotations

import unittest

import lead_sheet_page_follow as lpf
import studio_scroll_anchors as ssa

PAGE = """<!doctype html><html><body>
<div data-testid="stApp"><div data-testid="stMain" style="height:400px;overflow:auto">
<div style="height:3000px"></div></div></div>
<script>{installer}</script></body></html>"""


def _browser(test: unittest.TestCase, steps: str):
    try:
        from playwright import sync_api
    except ImportError:
        test.skipTest("playwright not installed")
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(PAGE.format(installer=lpf.page_follow_controller_js()), wait_until="load")
            page.wait_for_function("() => !!(window.__lsFollow && window.__lsFollow.suspended)", timeout=10000)
            return page.evaluate(steps)
        finally:
            browser.close()


class TheFollowWaitsWhileAControlIsInUse(unittest.TestCase):
    def test_the_version_moves_on_so_open_pages_take_the_new_rules(self) -> None:
        self.assertGreaterEqual(lpf.CONTROLLER_VERSION, 8)

    def test_an_open_dropdown_list_holds_and_its_closing_starts_the_three_seconds(self) -> None:
        out = _browser(self, """async () => {
          const C = window.__lsFollow, wait = (ms) => new Promise(r => setTimeout(r, ms));
          const before = C.suspended();
          const lb = document.createElement('ul'); lb.setAttribute('role', 'listbox');
          lb.innerHTML = '<li role="option">Bossa nova</li>'; document.body.appendChild(lb);
          const open = C.suspended();
          await wait(3300);
          const stillOpen = C.suspended();          // however long it stays open
          lb.remove();
          const justClosed = C.suspended();         // the three seconds start when it closes
          await wait(3300);
          return {before, open, stillOpen, justClosed, after: C.suspended()};
        }""")
        self.assertEqual(out, {"before": False, "open": True, "stillOpen": True, "justClosed": True, "after": False})

    def test_a_hidden_list_does_not_hold(self) -> None:
        out = _browser(self, """() => {
          const lb = document.createElement('ul'); lb.setAttribute('role', 'listbox'); lb.style.display = 'none';
          document.body.appendChild(lb); return window.__lsFollow.suspended();
        }""")
        self.assertFalse(out)

    def test_a_requested_jump_starts_the_hold(self) -> None:
        out = _browser(self, """async () => {
          const C = window.__lsFollow; const a = C.suspended(); C.userNavigated('anchor');
          const b = C.suspended(); await new Promise(r => setTimeout(r, 3300)); return [a, b, C.suspended()];
        }""")
        self.assertEqual(out, [False, True, False])


class TheSettingsButtonIsTheirOwnMove(unittest.TestCase):
    def test_only_the_settings_section_is_a_user_jump(self) -> None:
        self.assertEqual(ssa.USER_NAV_ANCHORS, frozenset({ssa.ANCHOR_BACKING_PLAYBACK_SETTINGS}))
        self.assertNotIn(ssa.ANCHOR_BACKING_FOLLOW_ALONG, ssa.USER_NAV_ANCHORS)

    def test_the_anchor_script_keeps_the_jump_and_starts_the_hold(self) -> None:
        src = open(ssa.__file__, encoding="utf-8").read()
        self.assertIn('user_nav_js = "true" if safe in USER_NAV_ANCHORS else "false"', src)
        self.assertIn("if (!userNav && ctl && ((ctl.suspended && ctl.suspended())", src)
        self.assertIn("if (userNav && ctl && ctl.userNavigated) ctl.userNavigated('anchor');", src)


class TheCardKeyControlOnlyReKeysItsOwnTake(unittest.TestCase):
    """Measured on 092f6855 (390 px, Karaoke Set): ~0.7 s after Blackbird (E) ended and the set moved on, the
    previous take's performance-key control fired its on_change with E and re-keyed Trial Song (saved D) to E -
    chips, chart and the rebuilt audio - and later Jazz tune (C) too."""

    def test_the_callback_compares_the_take_it_was_drawn_for(self) -> None:
        from pathlib import Path

        app = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        i = app.index("def _render_backing_card_performance_key(")
        body = app[i:app.index("with st.container(key=\"backing_card_key_row\"):", i)]
        self.assertIn("_drawn_for = km.render_generation(st.session_state)", body)
        self.assertIn('wkey = f"karaoke_card_perf_key_{_drawn_for}"', body)
        cb = body[body.index("def _on_perf_key_change() -> None:"):]
        self.assertLess(cb.index("if km.render_generation(st.session_state) != _drawn_for:"),
                        cb.index("_karaoke_retune_after_explicit_key_change("))


if __name__ == "__main__":
    unittest.main()
