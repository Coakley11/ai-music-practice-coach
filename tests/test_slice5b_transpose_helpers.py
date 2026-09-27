"""Slice 5B — unified Practice ↔️ Transpose helpers (display-only facts)."""

from __future__ import annotations

import unittest
from pathlib import Path

from instrument_transposition import (
    CHART_IN_INSTRUMENT_KEY_KEY,
    SELECTED_TRANSPOSING_INSTRUMENT_KEY,
    WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
    transpose_helpers_facts,
)


def _labels(facts: list[tuple[str, str]]) -> list[str]:
    return [label for label, _ in facts]


def _value(facts: list[tuple[str, str]], label: str) -> str:
    for lab, val in facts:
        if lab == label:
            return val
    raise AssertionError(f"missing fact {label!r} in {facts}")


class TestSlice5BTransposeHelpersFacts(unittest.TestCase):
    def test_clarinet_fields_and_written_on(self) -> None:
        session = {
            CHART_IN_INSTRUMENT_KEY_KEY: True,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Clarinet",
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Bb Clarinet",
            "display_key": "F",
        }
        facts = transpose_helpers_facts(
            session,
            original_key="D",
            concert_key="F",
            instrument="Clarinet",
        )
        labels = _labels(facts)
        self.assertEqual(labels[0], "Original Key")
        self.assertEqual(labels[1], "Practice / Concert Key")
        self.assertIn("Instrument", labels)
        self.assertIn("Written Key", labels)
        self.assertIn("Written-chart mode", labels)
        self.assertIn("Chart key", labels)
        self.assertNotIn("Shape Key", labels)
        self.assertEqual(_value(facts, "Original Key"), "D")
        self.assertEqual(_value(facts, "Practice / Concert Key"), "F")
        self.assertEqual(_value(facts, "Written Key"), "G")
        self.assertEqual(_value(facts, "Written-chart mode"), "ON")
        self.assertEqual(_value(facts, "Chart key"), "G")
        self.assertEqual(session["display_key"], "F")

    def test_tenor_sax_written_off_concert_chart(self) -> None:
        session = {
            CHART_IN_INSTRUMENT_KEY_KEY: False,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)",
        }
        facts = transpose_helpers_facts(
            session,
            original_key="C",
            concert_key="C",
            instrument="Saxophone",
        )
        self.assertEqual(_value(facts, "Written-chart mode"), "OFF")
        self.assertEqual(_value(facts, "Chart key"), "C")
        self.assertEqual(_value(facts, "Written Key"), "D")
        self.assertIn("Tenor", _value(facts, "Instrument"))

    def test_guitar_includes_shape_and_capo_not_written(self) -> None:
        session = {
            "guitar_capo_enabled": True,
            "guitar_capo_shape_key": "G",
            "display_key": "C",
        }
        facts = transpose_helpers_facts(
            session,
            original_key="C",
            concert_key="C",
            instrument="Guitar",
        )
        labels = _labels(facts)
        self.assertIn("Capo", labels)
        self.assertIn("Shape Key", labels)
        self.assertIn("Chart / shapes key", labels)
        self.assertNotIn("Written Key", labels)
        self.assertNotIn("Written-chart mode", labels)
        self.assertEqual(_value(facts, "Capo"), "ON")
        self.assertEqual(_value(facts, "Shape Key"), "G")
        self.assertEqual(session["display_key"], "C")

    def test_piano_minimal_facts_no_duplicates(self) -> None:
        facts = transpose_helpers_facts(
            {},
            original_key="G",
            concert_key="A",
            instrument="Piano",
        )
        labels = _labels(facts)
        self.assertEqual(labels.count("Original Key"), 1)
        self.assertEqual(labels.count("Practice / Concert Key"), 1)
        self.assertEqual(labels.count("Chart key"), 1)
        self.assertEqual(_value(facts, "Chart key"), "A")

    def test_facts_do_not_mutate_session(self) -> None:
        session = {
            CHART_IN_INSTRUMENT_KEY_KEY: True,
            "display_key": "F",
            "instrument": "Clarinet",
            "backing_owner_kind": "catalog",
        }
        before = dict(session)
        transpose_helpers_facts(
            session,
            original_key="D",
            concert_key="F",
            instrument="Clarinet",
        )
        self.assertEqual(session[CHART_IN_INSTRUMENT_KEY_KEY], before[CHART_IN_INSTRUMENT_KEY_KEY])
        self.assertEqual(session["display_key"], before["display_key"])
        self.assertEqual(session["backing_owner_kind"], before["backing_owner_kind"])

    def test_practice_page_uses_single_unified_helper(self) -> None:
        src = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        marker = 'elif _practice_active_tool == "transpose":'
        start = src.index(marker)
        end = src.index("elif _practice_active_tool ==", start + len(marker))
        block = src[start:end]
        self.assertIn("render_unified_transpose_helpers", block)
        self.assertNotIn("Transpose / capo helpers", block)
        self.assertNotIn("render_general_transpose_helper", block)
        self.assertNotIn("render_practice_transposing_controls", block)
        self.assertEqual(block.count("st.expander"), 0)


if __name__ == "__main__":
    unittest.main()
