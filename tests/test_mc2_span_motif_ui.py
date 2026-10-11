"""MC2 — Phrase / Motif span panel: generate, build, change rhythm, transforms, isolation."""

from __future__ import annotations

import logging
import unittest
from unittest.mock import patch

from harmonic_span_analyzer import analyze_harmonic_spans
from improvisation_intelligence import ImprovSessionContext
from improvisation_intelligence_ui import SPAN_MOTIF_ABC_KEY, SPAN_MOTIF_STATE_KEY, _render_span_motif_panel
from improvisation_motif import section_harmony_rows
from tests.abc_pitch_decoder import bar_chord_symbols, decode_abc_midis

logging.disable(logging.CRITICAL)


class _Block:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class _FakeSt:
    def __init__(self, session_state: dict, clicks: set[str] | None = None) -> None:
        self.session_state = session_state
        self.clicks = set(clicks or ())
        self.text: list[str] = []
        self.disabled: set[str] = set()
        self.rendered_abc: list[str] = []

    def container(self, **_kw):
        return _Block()

    def columns(self, spec, **_kw):
        return [_Block() for _ in range(spec if isinstance(spec, int) else len(spec))]

    def button(self, _label, key=None, disabled=False, **_kw):
        if disabled:
            self.disabled.add(key)
            return False
        return key in self.clicks

    def radio(self, _label, options, index=0, format_func=None, horizontal=False, key=None):
        value = self.session_state.get(key)
        return value if value in options else list(options)[index]

    def markdown(self, body, **_kw):
        self.text.append(str(body))

    info = caption = code = markdown


def _span():
    rows = section_harmony_rows({"Outro": ["Gm7", "C7", "Fmaj7", "Fmaj7"]}, section_names=["Outro"])
    return analyze_harmonic_spans(rows, key_center="F", length=3, source_id="ui")[0]


def _render(ss, clicks=(), *, level="Intermediate", instrument="Piano", span=None):
    st = _FakeSt(ss, set(clicks))
    with patch("improvisation_intelligence_ui._render_motif_sheet_music", side_effect=lambda _st, abc, **_k: st.rendered_abc.append(abc)):
        _render_span_motif_panel(
            st, session_state=ss, span=span or _span(), project=lambda c: c, concert_key="F",
            level=level, instrument=instrument, bpm=100,
        )
    return st


class TestSpanPanel(unittest.TestCase):
    def test_prompt_then_generate_connected_motif_with_chord_symbols(self) -> None:
        ss: dict = {"improv_motif": {"notes": ["C"], "chord": "C7"}}
        st = _render(ss)
        self.assertTrue(any("Generate span motif" in t for t in st.text))
        self.assertNotIn(SPAN_MOTIF_STATE_KEY, ss)

        st = _render(ss, {"improv_span_gen"})
        state = ss[SPAN_MOTIF_STATE_KEY]
        motif = state["current"]
        self.assertEqual(motif["span_length"], "seed")
        self.assertEqual(motif["span_chords"], ["Gm7", "C7", "Fmaj7"])
        self.assertEqual(set(motif["note_chord_index"]), {0, 1, 2})  # the phrase crosses every chord
        abc = st.rendered_abc[-1]
        self.assertEqual(abc, ss[SPAN_MOTIF_ABC_KEY])
        self.assertEqual(decode_abc_midis(abc), motif["midi"])
        self.assertEqual(bar_chord_symbols(abc), [["Gm7"], ["C7"], ["Fmaj7"], []])
        self.assertEqual(ss["improv_motif"], {"notes": ["C"], "chord": "C7"})  # single-chord seed untouched

    def test_build_develops_the_seed_and_change_rhythm_keeps_pitches(self) -> None:
        ss: dict = {}
        _render(ss, {"improv_span_gen"})
        seed = ss[SPAN_MOTIF_STATE_KEY]["seed"]
        _render(ss, {"improv_span_build"})
        built = ss[SPAN_MOTIF_STATE_KEY]["current"]
        self.assertEqual(built["span_length"], "standard")
        self.assertEqual(built["span_seed"], seed["span_seed"])
        self.assertGreater(len(built["notes"]), len(seed["notes"]))
        self.assertEqual(ss[SPAN_MOTIF_STATE_KEY]["seed"], seed)  # the seed is kept, not replaced
        st = _render(ss, {"improv_span_rhythm"})
        after = ss[SPAN_MOTIF_STATE_KEY]["current"]
        self.assertEqual(after["midi"], built["midi"])
        self.assertEqual(after["note_chord_index"], built["note_chord_index"])
        self.assertNotEqual(after["rhythm_meta"]["id"], built["rhythm_meta"]["id"])
        self.assertEqual(decode_abc_midis(st.rendered_abc[-1]), after["midi"])
        _render(ss, {"improv_span_back_to_seed"})
        self.assertEqual(ss[SPAN_MOTIF_STATE_KEY]["current"], seed)

    def test_sequence_and_invert_are_disabled_with_a_reason(self) -> None:
        ss: dict = {}
        st = _render(ss, {"improv_span_gen"})
        self.assertEqual(st.disabled, {"improv_span_seq_up", "improv_span_seq_down", "improv_span_invert"})
        self.assertTrue(any("Sequence and Invert are single-chord transforms" in t for t in st.text))

    def test_new_easier_harder_stay_in_level_and_span(self) -> None:
        ss: dict = {}
        _render(ss, {"improv_span_gen"})
        first = ss[SPAN_MOTIF_STATE_KEY]["current"]
        _render(ss, {"improv_span_new"})
        new = ss[SPAN_MOTIF_STATE_KEY]["current"]
        self.assertNotEqual(new["midi"], first["midi"])
        for key, variant in (("improv_span_easier", "easier"), ("improv_span_harder", "harder")):
            _render(ss, {key})
            m = ss[SPAN_MOTIF_STATE_KEY]["current"]
            self.assertEqual((m["variant"], m["level"], m["span_id"]), (variant, "Intermediate", first["span_id"]))

    def test_another_span_or_level_never_shows_a_stale_motif(self) -> None:
        ss: dict = {}
        _render(ss, {"improv_span_gen"})
        other = analyze_harmonic_spans(
            section_harmony_rows({"A": ["Dm7", "G7", "Cmaj7"]}, section_names=["A"]), key_center="C", length=3, source_id="ui"
        )[0]
        st = _render(ss, span=other)
        self.assertEqual(st.rendered_abc, [])
        self.assertTrue(any("Generate span motif" in t for t in st.text))
        st = _render(ss, level="Advanced")  # back on the first span, but a different Level
        self.assertEqual(st.rendered_abc, [])

    def test_guitar_tab_and_bass_clef(self) -> None:
        ss: dict = {}
        st = _render(ss, {"improv_span_gen"}, instrument="Guitar")
        self.assertTrue(any("Guitar TAB" in t for t in st.text))
        self.assertTrue(any("|" in t and "e" in t.splitlines()[0] for t in st.text if "\n" in t))
        ss2: dict = {}
        st = _render(ss2, {"improv_span_gen"}, instrument="Bass")
        self.assertIn("clef=bass", st.rendered_abc[-1])
        self.assertEqual(decode_abc_midis(st.rendered_abc[-1]), ss2[SPAN_MOTIF_STATE_KEY]["current"]["midi"])


if __name__ == "__main__":
    unittest.main()
