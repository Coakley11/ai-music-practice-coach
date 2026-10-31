"""Regression: Custom / slash chord builder must keep the chosen quality.

Hosted-app bug: root F + quality m6 previewed as ``F`` ("Use F") because the
page-start purge treated the ``cpl_custom_qual_*`` widget key as ephemeral and
wiped it on every rerun. The earlier fix only unit-tested the string assembly.
"""

from __future__ import annotations

import unittest

from streamlit.testing.v1 import AppTest

from cpl_page_ui import assemble_custom_chord
from custom_progression_lab import (
    is_cpl_ephemeral_widget_key,
    purge_cpl_ephemeral_widget_keys,
    should_purge_cpl_widget_key_on_page_start,
)


class TestAssembleCustomChord(unittest.TestCase):
    def test_f_m6(self) -> None:
        self.assertEqual(assemble_custom_chord("F", "m6"), "Fm6")

    def test_major_has_no_suffix(self) -> None:
        self.assertEqual(assemble_custom_chord("F", ""), "F")

    def test_slash_bass_keeps_quality(self) -> None:
        self.assertEqual(assemble_custom_chord("F", "m6", "Ab"), "Fm6/Ab")

    def test_extensions_and_alterations(self) -> None:
        for quality in ("m", "7", "maj7", "m7", "m7b5", "dim7", "6/9", "13", "7#9", "7b13", "sus4", "add9"):
            with self.subTest(quality=quality):
                self.assertEqual(assemble_custom_chord("Bb", quality), f"Bb{quality}")
                self.assertEqual(assemble_custom_chord("Bb", quality, "D"), f"Bb{quality}/D")


class TestQualityKeySurvivesPurge(unittest.TestCase):
    KEYS = (
        "cpl_slash_root_C_Verse",
        "cpl_custom_qual_C_Verse",
        "cpl_custom_qual_C_Verse__last",
        "cpl_slash_bass_C_Verse",
        "cpl_custom_text_C_Verse",
    )

    def test_builder_inputs_are_not_ephemeral(self) -> None:
        for key in self.KEYS:
            with self.subTest(key=key):
                self.assertFalse(is_cpl_ephemeral_widget_key(key))
                self.assertFalse(should_purge_cpl_widget_key_on_page_start(key))

    def test_purge_keeps_builder_inputs(self) -> None:
        session = {key: "x" for key in self.KEYS}
        purge_cpl_ephemeral_widget_keys(session)
        self.assertEqual(set(session), set(self.KEYS))

    def test_other_cpl_custom_widget_keys_stay_ephemeral(self) -> None:
        self.assertTrue(is_cpl_ephemeral_widget_key("cpl_custom_Verse"))


def _quality_page() -> None:
    """Mirrors the builder: page-start purge, then root + quality pickers."""
    import streamlit as st

    from cpl_page_ui import _quality_pill_label, _tap_pick, assemble_custom_chord
    from custom_progression_lab import CHORD_EDIT_QUALITIES, purge_cpl_ephemeral_widget_keys

    purge_cpl_ephemeral_widget_keys(st.session_state)
    roots = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
    root = _tap_pick("Root note", roots, key="cpl_slash_root_C_Verse", default="C")
    tokens = [_quality_pill_label(q) for q in CHORD_EDIT_QUALITIES]
    token = _tap_pick("Quality", tokens, key="cpl_custom_qual_C_Verse", default="major")
    st.session_state["_built"] = assemble_custom_chord(root, "" if token == "major" else token)


class TestBuilderRerunCycle(unittest.TestCase):
    def _pills(self, at: AppTest):
        by_label = {p.label: p for p in at.pills}
        return by_label["Root note"], by_label["Quality"]

    def test_f_then_m6_builds_fm6_and_survives_reruns(self) -> None:
        at = AppTest.from_function(_quality_page, default_timeout=30).run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state["_built"], "C")

        root, _ = self._pills(at)
        root.set_value("F").run()
        self.assertEqual(at.session_state["_built"], "F")

        _, quality = self._pills(at)
        quality.set_value("m6").run()
        self.assertEqual(at.session_state["_built"], "Fm6")

        for _ in range(3):
            at.run()
            self.assertEqual(at.session_state["_built"], "Fm6")

        root, _ = self._pills(at)
        root.set_value("Bb").run()
        self.assertEqual(at.session_state["_built"], "Bbm6")

        _, quality = self._pills(at)
        quality.set_value("7").run()
        self.assertEqual(at.session_state["_built"], "Bb7")


if __name__ == "__main__":
    unittest.main()
