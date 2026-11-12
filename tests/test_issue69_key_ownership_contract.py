"""Issue 69 Part D: the ownership map's load-bearing claims, as checks.

``docs/issue69-key-ownership-map.md`` documents how a Practice Key reaches the music. A
document drifts from the code silently; these are the claims it would be dangerous to be
wrong about, so they fail here instead.

Each test names the claim it defends. Several are source-level, because the paths they
describe live inline in a 28k-line Streamlit script and cannot be called without a script
run - the alternative was to assert nothing.
"""

from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8",
                                                           errors="replace")


class TheEngineIsNotImplicated(unittest.TestCase):
    """Claim: every chord in the report transposes correctly already."""

    CASES = (
        ("B♭", 4, "D"), ("E♭", 4, "G"), ("Bb", 4, "D"), ("Eb", 4, "G"),
        ("Gm", 4, "Bm"), ("F", 4, "A"),
        ("Csus4/D", 2, "Dsus4/E"), ("Csus4", 2, "Dsus4"),
        ("D/F#", 2, "E/G#"), ("D/F♯", 2, "E/G#"), ("A/C#", 2, "B/D#"),
    )

    def test_every_reported_chord(self):
        from music_theory import transpose_chord

        for symbol, steps, want in self.CASES:
            with self.subTest(symbol=symbol, steps=steps):
                self.assertEqual(transpose_chord(symbol, steps), want)


class ThePhrasingGuideIsARendererNotATransposer(unittest.TestCase):
    """Claim: it takes no key, so wrong chords there came from upstream."""

    def test_it_accepts_no_key_argument(self):
        import inspect

        from lyrics_presentation import phrasing_guide_html

        params = set(inspect.signature(phrasing_guide_html).parameters)
        for key_name in ("key", "practice_key", "concert_key", "catalog_key",
                         "chart_key", "target_key"):
            with self.subTest(param=key_name):
                self.assertNotIn(key_name, params)

    def test_it_renders_the_cue_it_is_handed_verbatim(self):
        from lyrics_presentation import phrasing_guide_html

        cue = "Instrumental — D · G · Bm · A"
        html_out = phrasing_guide_html({"Intro": ""}, {"Intro": [cue]},
                                       section_names=["Intro"])
        self.assertIn("D", html_out)
        self.assertIn("Bm", html_out)


class TheCueTextPathIsOnePass(unittest.TestCase):
    """Claim: key names and chords are rewritten together, never in two passes."""

    def test_no_bare_substring_replacement_of_the_catalog_key_remains(self):
        import inspect

        from musician_coaching import adapt_text_to_practice_key

        source = inspect.getsource(adapt_text_to_practice_key)
        self.assertNotIn("out.replace(old, new)", source)

    def test_the_chord_pattern_accepts_typographic_accidentals(self):
        from musician_coaching import _CHORD_IN_PROSE

        for symbol in ("B♭", "E♭", "C♯", "F♯m", "Bb", "C#"):
            with self.subTest(symbol=symbol):
                match = _CHORD_IN_PROSE.match(symbol)
                self.assertIsNotNone(match, f"{symbol!r} did not match at all")
                self.assertEqual(match.group("chord"), symbol)

    def test_no_result_ever_carries_two_accidentals(self):
        from musician_coaching import transpose_lyric_cue

        doubled = re.compile("[A-G](?:#|b|♯|♭)(?:#|b|♯|♭)")
        cue = "X — B♭ · E♭ · Gm · F · A/C#"
        for catalog, practice in (("Bb", "D"), ("D", "F#"), ("G", "Bb"), ("C", "Eb")):
            with self.subTest(pair=f"{catalog}->{practice}"):
                out = transpose_lyric_cue(cue, catalog_key=catalog,
                                          practice_key=practice)
                self.assertIsNone(doubled.search(out), out)


class TheKaraokeChartReassertionIsLoadBearing(unittest.TestCase):
    """Claim: the karaoke chart is re-asserted on purpose, immediately before the build.

    It exists because the sealed BackingContext lags a karaoke transition. If it is ever
    removed, the Part C reasoning changes and this map is wrong.
    """

    def test_the_reassertion_is_still_there(self):
        self.assertIn("sections_for_backing = sections", APP)
        self.assertIn("Karaoke isolation: sections_for_backing starts as the karaoke", APP)

    def test_it_runs_after_the_other_writers_and_before_the_arrangement(self):
        reassert = APP.index("Karaoke isolation: sections_for_backing starts as the karaoke")
        humanize = APP.index("performed_sections, _hri_annotations = _humanized_backing_sections")
        self.assertLess(reassert, humanize,
                        "the re-assertion must be the last writer before the build")

    def test_the_signature_key_follows_the_karaoke_entry(self):
        self.assertIn("_kr_audio_key = km.current_session_practice_key(st.session_state)",
                      APP)
        self.assertIn("_audio_signature_key = _kr_audio_key", APP)


class OnlyTheExplicitGestureRekeysThePerformance(unittest.TestCase):
    """Claim: reruns, hydration, navigation and backing updates cannot re-key."""

    def test_the_retune_is_called_from_exactly_one_place(self):
        callers = []
        for path in sorted(ROOT.glob("*.py")):
            if path.name == "karaoke_mode.py":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for n, line in enumerate(text.splitlines(), 1):
                if re.search(r"\bretune_now_singing_entry\s*\(", line):
                    callers.append(f"{path.name}:{n}")
        self.assertEqual(len(callers), 1, f"callers: {callers}")
        self.assertTrue(callers[0].startswith("streamlit_music_practice_app.py"))

    def test_that_place_is_the_shared_explicit_gesture_helper(self):
        call = APP.index("km.retune_now_singing_entry(")
        helper = APP.index("def _karaoke_retune_after_explicit_key_change")
        following = APP.index(chr(10) + "def ", helper + 1)
        self.assertLess(helper, call, "the retune must sit inside the helper")
        self.assertLess(call, following)

    def test_the_helper_is_reached_only_from_the_three_on_change_callbacks(self):
        """Part E measured why this matters.

        The wiring first sat inside one sidebar branch, so a performance started from
        Songs - where the sidebar widget is plain ``display_key`` - never re-keyed. The
        app has three Practice Key controls a musician can touch; each must reach the
        helper, and nothing that is not an ``on_change`` may.
        """
        import ast

        tree = ast.parse(APP)
        enclosing: dict[str, int] = {}

        class Walk(ast.NodeVisitor):
            def __init__(self):
                self.stack: list[str] = []

            def visit_FunctionDef(self, node):
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            def visit_Call(self, node):
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name == "_karaoke_retune_after_explicit_key_change":
                    owner = self.stack[-1] if self.stack else "<module>"
                    enclosing[owner] = enclosing.get(owner, 0) + 1
                self.generic_visit(node)

        Walk().visit(tree)
        self.assertEqual(
            set(enclosing),
            {
                "_on_mission_or_global_pk_change",
                "_apply_card_practice_key_change",
                "_on_custom_workspace_practice_key_change",
            },
            f"call sites: {enclosing}",
        )
        for callback in enclosing:
            with self.subTest(callback=callback):
                self.assertIn(f"on_change={callback}", APP,
                              "every caller must be a widget's on_change")

    def test_the_sidebar_call_is_outside_the_per_widget_branches(self):
        """``display_key`` is a real widget identity, not a fallback."""
        callback = APP.index("def _on_mission_or_global_pk_change")
        guard = APP.index('if _pk_widget_key != "display_key":', callback)
        call = APP.index("_karaoke_retune_after_explicit_key_change(", guard)
        router = APP.index("on_sidebar_practice_concert_key_change()", guard)
        self.assertLess(call, router,
                        "the retune must run before the owner-aware commit")
        def indent_of(pos: int) -> int:
            line_start = APP.rfind(chr(10), 0, pos) + 1
            return pos - line_start

        self.assertEqual(
            indent_of(call), indent_of(guard),
            "the call must sit at the guard's own level, not nested inside it",
        )

    def test_the_practice_key_store_has_no_route_into_the_queue(self):
        """Hydration and page code go through the store; the store must not reach here."""
        from songs.practice_key_state import set_practice_concert_key

        import karaoke_mode as km

        state = {"instrument": "Voice"}
        state[km.KARAOKE_QUEUE_KEY] = [{
            "entry_id": "e1", "pick_key": "Pop\u001fSay — John Mayer",
            "title": "Say", "artist": "John Mayer", "practice_key": "C",
            "play_count": 1,
        }]
        state[km.KARAOKE_SESSION_ACTIVE_KEY] = True
        state[km.KARAOKE_SESSION_INDEX_KEY] = 0
        state["active_catalog_pick_key"] = "Pop\u001fSay — John Mayer"

        set_practice_concert_key(state, "D",
                                 pick_key="Pop\u001fSay — John Mayer",
                                 commit_catalog_practice_key=True)
        self.assertEqual(km.current_session_practice_key(state), "C")


class TheMusicianIsToldTheKeyMoved(unittest.TestCase):
    """A re-key silences the take that was playing; unexplained silence is a defect.

    Part E caught the renderer existing and never being called - the notice was set
    on every re-key and read by nobody.
    """

    def test_the_notice_renderer_is_called_by_the_app(self):
        self.assertIn("render_karaoke_retune_notice", APP)
        call = APP.index("_render_kr_notice(st)")
        self.assertGreater(call, 0)

    def test_it_renders_where_the_control_is(self):
        """The karaoke panel is inside a collapsed expander; the sidebar is not."""
        imp = APP.index("from karaoke_ui import render_karaoke_retune_notice")
        window = APP[imp:imp + 400]
        self.assertIn("with _working_sidebar:", window)

    def test_the_notice_text_names_both_keys(self):
        import karaoke_ui

        class Fake:
            def __init__(self):
                self.session_state = {
                    "instrument": "Voice",
                    karaoke_ui.KARAOKE_RETUNE_NOTICE_KEY: {"from": "Bb", "to": "D"},
                }
                self.said: list[str] = []

            def info(self, text):
                self.said.append(("info", text))

            def error(self, text):
                self.said.append(("error", text))

        fake = Fake()
        self.assertTrue(karaoke_ui.render_karaoke_retune_notice(fake))
        kind, text = fake.said[0]
        self.assertEqual(kind, "info")
        self.assertIn("Bb", text)
        self.assertIn("D", text)
        self.assertNotIn(karaoke_ui.KARAOKE_RETUNE_NOTICE_KEY, fake.session_state,
                         "the notice is one shot")


class ARetuneDropsTheOldKeysChordsAndAudioTogether(unittest.TestCase):
    """Claim: the chords on screen cannot outlive the audio they described."""

    def test_the_stale_set_covers_both_the_take_and_the_timeline(self):
        import karaoke_mode as km

        stale = set(km._RETUNE_STALE_AUDIO_KEYS)
        for audio in ("_last_backing_wav", "_last_backing_signature",
                      "_backing_wav_building_signature"):
            with self.subTest(key=audio):
                self.assertIn(audio, stale)
        for chords in ("_last_backing_timeline", "_kc_audible_follow_timeline",
                       "_kc_audible_chart_html", "_kc_audible_signature"):
            with self.subTest(key=chords):
                self.assertIn(chords, stale)

    def test_the_arrangement_facts_are_not_in_it(self):
        """Tempo, feel, meter and sections survive a key change by design."""
        import karaoke_mode as km

        stale = set(km._RETUNE_STALE_AUDIO_KEYS)
        for keep in ("_kc_audible_bpm", "_kc_audible_groove", "_kc_audible_meter",
                     "_kc_audible_section_names", "backing_track_bpm",
                     "_pending_backing_scope"):
            with self.subTest(key=keep):
                self.assertNotIn(keep, stale)

    def test_the_stash_that_writes_them_still_writes_them(self):
        """If the stash stops recording these, the stale set needs revisiting."""
        source = (ROOT / "backing_key_cycle.py").read_text(encoding="utf-8",
                                                           errors="replace")
        stash = source.index("def stash_audible_arrangement_after_generate")
        body = source[stash:stash + 2500]
        for key in ("_kc_audible_follow_timeline", "_kc_audible_chart_html",
                    "_kc_audible_signature", "_last_backing_timeline"):
            with self.subTest(key=key):
                self.assertIn(key, body)


class TheMapItselfIsPresent(unittest.TestCase):
    def test_the_document_exists_and_names_both_authorities(self):
        doc = (ROOT / "docs" / "issue69-key-ownership-map.md").read_text(
            encoding="utf-8", errors="replace")
        for needed in ("Practice Concert Key", "entry", "current_session_practice_key",
                       "retune_now_singing_entry", "stash_audible_arrangement_after_generate"):
            with self.subTest(term=needed):
                self.assertIn(needed, doc)


if __name__ == "__main__":
    unittest.main()
