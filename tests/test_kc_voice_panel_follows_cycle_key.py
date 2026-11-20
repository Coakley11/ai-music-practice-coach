"""The Voice singing panel's chords follow the key Key Cycling plays (user P1, Android, 2026-11-20).

Blue Bossa, Voice, Key Cycling On (Circle of Fourths): the panel's chord chips read Am7 / Dm7 while
the working key and the Lead Sheet said E-flat minor. The panel's chord map is drawn once by the
server, in the key of that render; Key Cycling then changes key in the browser (the next key's
timeline replaces the current one, no rerun), and the panel only rebuilt its chips on a section
change -- from that fixed map. The chips now take their chord names from the same live timeline,
through the same label projection, as the Lead Sheet's Current / Next.

These tests load the real panel markup and script into Chromium and drive them the way the page
does: ``__karaokeUpdateLyricPanel(event, {timeline, project})`` per chord event, the timeline
swapped for the next key's in place.
"""

from __future__ import annotations

import json
import unittest

import streamlit_music_practice_app as app
from music_theory import transpose_sections_dict

# Blue Bossa's head as the catalog spells it per bar, here in A minor (the user's Practice Key),
# with one subdivided bar (weights + a push) and one hit bar so the bar shapes are exercised too.
HEAD_AM = ["Am7", "Am7", "Dm7", "Dm7", "Bm7b5", "E7#5", "Am7", "Am7",
           "Cm7", "F7", "Bbmaj7", "Bbmaj7", "Bm7b5:3|E7:1p", "Dm7.hit", "Am7", "Am7"]


def _timeline(chords: list[str]) -> list[dict]:
    events = [{"chord": c, "section": "Head", "bar_in_section": i, "section_bars": len(chords)}
              for i, c in enumerate(chords)]
    return app.build_chord_event_timeline(events, 135, 1, "4/4")


class VoicePanelFollowsCycleKey(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except Exception as exc:  # pragma: no cover - environment without Playwright
            raise unittest.SkipTest(f"Playwright is not installed: {exc}") from exc
        head_ebm = transpose_sections_dict({"Head": HEAD_AM}, "Am", "Ebm")["Head"]
        cls.head_ebm = head_ebm
        cls.tl_am = _timeline(HEAD_AM)
        cls.tl_ebm = _timeline(head_ebm)
        panel = {"Head": {"lyrics": ["Intro — Am7 · Dm7"], "chords": list(HEAD_AM),
                          "lyrics_by_key": {"Am": ["Intro — Am7 · Dm7"], "Ebm": ["Intro — Ebm7 · Abm7"]}}}
        cls.html = (
            "<!doctype html><html><head><meta charset='utf-8'></head><body>"
            + app._build_karaoke_lyrics_panel_html(song_title="Blue Bossa", has_panel=True)
            + "<script>var audio = {paused: true};"
            + f"window.__kcTimelineByKey = {{'Am': {json.dumps(cls.tl_am)}, 'Ebm': {json.dumps(cls.tl_ebm)}}};"
            + "</script><script>"
            + app._build_karaoke_lyrics_panel_script(panel)
            + "</script></body></html>"
        )

    def _run(self, js: str):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception as exc:  # pragma: no cover
                raise unittest.SkipTest(f"no Chromium available: {exc}") from exc
            try:
                page = browser.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.set_content(self.html)
                result = page.evaluate(js)
                self.assertEqual(errors, [])
                return result
            finally:
                browser.close()

    CHIPS = """() => [...document.querySelectorAll('#karaoke-lp-chord-strip .karaoke-lp-chord')].map(c => ({
        text: c.textContent.replace(/\\s+/g, ' ').trim(), bar: Number(c.dataset.barInSection),
        hit: c.dataset.hit === '1', push: c.dataset.hasPush === '1', active: c.classList.contains('active')}))"""

    def _drive(self, steps: str) -> dict:
        return self._run(f"""() => {{
            const byKey = window.__kcTimelineByKey, A = byKey['Am'], E = byKey['Ebm'];
            const ctx = (tl) => ({{timeline: tl, project: (c) => c}});
            const chips = {self.CHIPS};
            const lines = () => [...document.querySelectorAll('.karaoke-lp-lyric-line')].map(l => l.textContent);
            const out = {{}};
            {steps}
            return out;
        }}""")

    def test_a_key_change_in_the_same_section_moves_the_chips_to_the_sounding_key(self) -> None:
        r = self._drive("""
            window.__karaokeUpdateLyricPanel(A[0], ctx(A));
            out.before = chips();
            const ev = E.find(e => e.bar_in_section === 3);   // E-flat minor, bar 3, same section
            window.__karaokeUpdateLyricPanel(ev, ctx(E));
            out.after = chips();
        """)
        self.assertEqual([c["text"] for c in r["before"]][:4], ["Am7", "Am7", "Dm7", "Dm7"])
        self.assertEqual([c["text"] for c in r["after"]][:4], self.head_ebm[:4])
        self.assertEqual([c["text"] for c in r["after"]][:2], ["Ebm7", "Ebm7"])
        self.assertEqual([c["bar"] for c in r["after"] if c["active"]], [3])  # highlight on the bar that plays

    def test_every_chip_matches_the_timeline_of_the_key_that_sounds(self) -> None:
        r = self._drive("""
            window.__karaokeUpdateLyricPanel(A[0], ctx(A));
            window.__karaokeUpdateLyricPanel(E[0], ctx(E));
            out.after = chips();
            out.names = E.map(e => [e.bar_in_section, e.chord]);
        """)
        by_bar: dict[int, list[str]] = {}
        for bar, chord in r["names"]:
            by_bar.setdefault(bar, []).append(chord)
        for chip in r["after"]:
            for name in by_bar[chip["bar"]]:
                self.assertIn(name, chip["text"], chip)  # no chip keeps an A-minor chord name
        self.assertNotIn("Am7", " ".join(c["text"] for c in r["after"]))

    def test_the_bar_shapes_are_kept_hit_and_push(self) -> None:
        r = self._drive("""
            window.__karaokeUpdateLyricPanel(A[0], ctx(A));
            window.__karaokeUpdateLyricPanel(E[0], ctx(E));
            out.after = chips();
        """)
        chips = {c["bar"]: c for c in r["after"]}
        self.assertTrue(chips[14]["hit"])          # Dm7.hit -> the E-flat minor chord, still a hit
        self.assertIn("Abm7", chips[14]["text"])
        self.assertTrue(chips[13]["push"])         # Bm7b5:3|E7:1p keeps its push in the new key
        self.assertIn("Fm7b5", chips[13]["text"])
        self.assertIn("Bb7", chips[13]["text"])

    def test_a_chord_run_cue_follows_the_key_and_lyrics_are_untouched_otherwise(self) -> None:
        r = self._drive("""
            window.__karaokeUpdateLyricPanel(A[0], ctx(A));
            out.before = lines();
            window.__karaokeUpdateLyricPanel(E[1], ctx(E));
            out.after = lines();
        """)
        self.assertEqual(r["before"], ["Intro — Am7 · Dm7"])
        self.assertEqual(r["after"], ["Intro — Ebm7 · Abm7"])

    def test_the_same_timeline_does_not_rebuild_on_every_chord(self) -> None:
        r = self._drive("""
            window.__karaokeUpdateLyricPanel(A[0], ctx(A));
            const strip = document.getElementById('karaoke-lp-chord-strip');
            const first = strip.firstElementChild;
            window.__karaokeUpdateLyricPanel(A[1], ctx(A));
            window.__karaokeUpdateLyricPanel(A[2], ctx(A));
            out.same = strip.firstElementChild === first;
        """)
        self.assertTrue(r["same"])

    def test_without_a_timeline_the_map_chords_are_shown_as_before(self) -> None:
        r = self._drive("""
            const ev = Object.assign({}, A[0]);
            window.__karaokeUpdateLyricPanel(ev, null);
            out.after = chips();
        """)
        self.assertEqual([c["text"] for c in r["after"]][:4], ["Am7", "Am7", "Dm7", "Dm7"])

    def test_the_page_passes_its_timeline_and_label_projection_to_the_panel(self) -> None:
        import inspect

        src = inspect.getsource(app)
        self.assertIn("window.__karaokeUpdateLyricPanel(event, {{", src)
        self.assertIn("project: (c, sp) => projectChordLabel(c, sp)", src)


class CueLinesByCycleKey(unittest.TestCase):
    def test_a_chord_run_cue_comes_in_every_cycle_key(self) -> None:
        out = app.cue_lines_by_cycle_key(["Intro — Cm7 · Fm7 · G7"], "Cm", ["Cm", "Fm", "Ebm"])
        self.assertEqual(out["Cm"], ["Intro — Cm7 · Fm7 · G7"])
        self.assertEqual(out["Ebm"], ["Intro — Ebm7 · Abm7 · Bb7"])

    def test_prose_cues_and_lyrics_are_not_repeated_per_key(self) -> None:
        self.assertEqual(app.cue_lines_by_cycle_key(["Bridge — major ii–V–I to Dbmaj7"], "Cm", ["Cm", "Fm"]), {})
        self.assertEqual(app.cue_lines_by_cycle_key(["I see trees of green"], "C", ["C", "F"]), {})
        self.assertEqual(app.cue_lines_by_cycle_key([], "C", ["C", "F"]), {})


if __name__ == "__main__":
    unittest.main()
