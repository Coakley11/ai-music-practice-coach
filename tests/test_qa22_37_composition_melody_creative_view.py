"""Issue 30: the Creative Lab 'Composed Melody' view draws real sheet music (abcjs), never raw ABC / the app emblem.

Root cause: the view imported the whole app module and called render_abc(..., key=...) (no such parameter);
the TypeError fell through to st.code(<raw ABC>) and the import re-ran the app, drawing its emblem.
"""
import re
import sys
import unittest
from unittest import mock

import improvisation_intelligence_ui as ui
from composition_document import bootstrap_from_vision
from composition_session_state import COMPOSER_ACTIVE_KEY

E_MAJOR_MELODY = [("E4", 0), ("F#4", 1), ("G#4", 2), ("A4", 3), ("B4", 4), ("C#5", 5), ("D#5", 6), ("E5", 7)]


def _doc(key="E major"):
    doc = bootstrap_from_vision(genre="Pop", song_idea="t", title="Melody Song", key=key, bpm=100)
    sec = {
        "id": "s1", "label": "Verse", "label_variant": 1,
        "chords": [{"chord": "E", "bars": 1}, {"chord": "A", "bars": 1}],
        "melody": {
            "events": [{"pitch": p, "beat": float(b), "duration_beats": 1.0} for p, b in E_MAJOR_MELODY],
            "phrases": [],
        },
        "lyrics": {"raw_text": "", "lines": [], "intent": {"communicate": "", "emotion": "", "role": "", "remember": ""}},
    }
    form = doc.setdefault("form", {})
    form.setdefault("sections", {})["s1"] = sec
    form["section_order"] = ["s1"]
    return doc, "Verse"


class _FakeSt:
    def __init__(self):
        self.calls = []

    def expander(self, *a, **k):
        import contextlib
        return contextlib.nullcontext()

    def markdown(self, *a, **k):
        self.calls.append(("markdown", a))

    def caption(self, *a, **k):
        self.calls.append(("caption", a))

    def code(self, *a, **k):
        self.calls.append(("code", a))


def _run(practice_key, original="E major"):
    doc, _label = _doc(original)
    ss = {COMPOSER_ACTIVE_KEY: doc, "instrument": "Piano"}
    fake = _FakeSt()
    html_calls = []
    import streamlit.components.v1 as comp

    with mock.patch.object(comp, "html", side_effect=lambda h, **k: html_calls.append(h)):
        ui._render_composition_melody_in_creative(fake, ss, practice_key)
    return fake, html_calls


class TestCreativeComposedMelody(unittest.TestCase):
    def test_no_raw_abc_and_app_module_not_imported(self):
        before = "streamlit_music_practice_app" in sys.modules
        fake, html_calls = _run("E")
        self.assertFalse([c for c in fake.calls if c[0] == "code"])
        self.assertEqual(len(html_calls), 1)
        self.assertEqual("streamlit_music_practice_app" in sys.modules, before)

    def test_score_has_chords_and_four_sharps_in_original_key(self):
        _fake, html = _run("E")
        abc = html[0]
        self.assertRegex(abc, r"K:E\b")
        self.assertIn('"E"', abc)
        self.assertIn('"A"', abc)

    def test_practice_key_d_gives_two_sharps_and_transposed_chords_and_e_restores(self):
        _f, d_html = _run("D")
        self.assertRegex(d_html[0], r"K:D\b")
        self.assertIn('"D"', d_html[0])
        self.assertIn('"G"', d_html[0])
        self.assertNotIn("K:E", d_html[0])
        _f, e_html = _run("E")
        self.assertRegex(e_html[0], r"K:E\b")

    def test_saved_melody_is_not_modified(self):
        doc, _ = _doc("E major")
        import copy

        snapshot = copy.deepcopy(doc)
        ss = {COMPOSER_ACTIVE_KEY: doc, "instrument": "Piano"}
        import streamlit.components.v1 as comp

        with mock.patch.object(comp, "html"):
            ui._render_composition_melody_in_creative(_FakeSt(), ss, "D")
        # (Reading the doc adds empty default fields such as melody.intent; musical content is untouched.)
        a, b = doc["form"]["sections"]["s1"], snapshot["form"]["sections"]["s1"]
        self.assertEqual(a["melody"]["events"], b["melody"]["events"])
        self.assertEqual(a["chords"], b["chords"])
        self.assertEqual(doc["global"].get("original_key_center"), snapshot["global"].get("original_key_center"))


if __name__ == "__main__":
    unittest.main()
