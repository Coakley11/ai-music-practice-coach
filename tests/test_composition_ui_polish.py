"""Composition UI polish: icon labels on the setup fields, no duplicate Review cover."""

from __future__ import annotations

import unittest

from streamlit.testing.v1 import AppTest

from music_feature_icons import semantic_field_icon


def _welcome_app() -> None:
    from composition_studio_page import _render_welcome_entry, inject_composition_studio_styles
    import streamlit as st

    inject_composition_studio_styles()
    _render_welcome_entry(st.session_state)


def _vision_app() -> None:
    import streamlit as st

    from composition_document import new_composition_document
    from composition_studio_page import _render_phase_vision

    doc = new_composition_document(title="Vision Song")
    _render_phase_vision(st.session_state, doc)


def _review_app() -> None:
    import streamlit as st

    from composition_document import new_composition_document
    from composition_studio_page import _render_phase_review

    doc = new_composition_document(title="Review Song")
    doc["metadata"]["description"] = "A hopeful song."
    _render_phase_review(st.session_state, doc, host_side_panel=False)


def _labels(at: AppTest) -> dict[str, str]:
    out: dict[str, str] = {}
    for w in list(at.selectbox) + list(at.number_input):
        out[str(w.key)] = str(w.label)
    return out


class TestSetupFieldIcons(unittest.TestCase):
    def _check(self, labels: dict[str, str], prefix: str) -> None:
        self.assertEqual(labels[f"composer_{prefix}_genre"], f"{semantic_field_icon('style')} Genre / Style")
        self.assertEqual(labels[f"composer_{prefix}_key"], f"{semantic_field_icon('original_key')} Original Key")
        self.assertEqual(labels[f"composer_{prefix}_bpm"], f"{semantic_field_icon('bpm')} BPM / Tempo")
        self.assertEqual(labels[f"composer_{prefix}_meter"], f"{semantic_field_icon('meter')} Meter")

    def test_welcome_form_labels(self) -> None:
        at = AppTest.from_function(_welcome_app, default_timeout=60).run()
        self.assertFalse(at.exception)
        self._check(_labels(at), "welcome")

    def test_vision_form_labels(self) -> None:
        at = AppTest.from_function(_vision_app, default_timeout=60).run()
        self.assertFalse(at.exception)
        self._check(_labels(at), "vision")

    def test_values_are_unchanged_by_the_relabel(self) -> None:
        at = AppTest.from_function(_welcome_app, default_timeout=60).run()
        self.assertTrue(40 <= int(at.number_input(key="composer_welcome_bpm").value) <= 240)


class TestReviewHeader(unittest.TestCase):
    def test_review_has_no_large_cover_card_but_keeps_idea(self) -> None:
        at = AppTest.from_function(_review_app, default_timeout=60).run()
        self.assertFalse(at.exception)
        html_all = " ".join(str(m.value) for m in at.markdown)
        self.assertNotIn("composer-review-cover", html_all)
        self.assertIn("A hopeful song.", html_all)
        self.assertNotIn("<h2>Review Song</h2>", html_all)


if __name__ == "__main__":
    unittest.main()
