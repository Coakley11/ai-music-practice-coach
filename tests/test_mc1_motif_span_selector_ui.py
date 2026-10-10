"""MC1 — Phrase / Motif target-scope control and span selection persistence."""

from __future__ import annotations

import logging
import unittest
from unittest.mock import patch

from improvisation_intelligence import ImprovSessionContext
from improvisation_intelligence_ui import (
    MOTIF_SPAN_SELECTION_STATE_KEY,
    MOTIF_TARGET_SCOPE_STATE_KEY,
    MOTIF_TARGET_SCOPE_WIDGET_KEY,
    _render_motif_span_selector,
    _render_motif_target_scope,
)
from improvisation_motif import section_harmony_rows
from music_theory import transpose_chord

logging.disable(logging.CRITICAL)


class _FakeSt:
    """Widgets return the session value when one exists (a prior run / user pick), else the index."""

    def __init__(self, session_state: dict) -> None:
        self.session_state = session_state
        self.options: dict[str, list[str]] = {}
        self.text: list[str] = []

    def _widget(self, options, index, format_func, key):
        fmt = format_func or str
        self.options[key] = [fmt(o) for o in options]
        value = self.session_state.get(key)
        if value not in options:
            value = options[index]
        self.session_state[key] = value
        return value

    def radio(self, _label, options, index=0, format_func=None, horizontal=False, key=None):
        return self._widget(list(options), index, format_func, key)

    def selectbox(self, _label, options, index=0, format_func=None, key=None):
        return self._widget(list(options), index, format_func, key)

    def markdown(self, body, **_kw):
        self.text.append(str(body))

    info = caption = warning = markdown


SECTIONS = {"Verse": ["Cmaj7", "Am7", "Dm7", "G7"], "Chorus": ["Fmaj7", "Em7", "A7", "Dm7", "G7", "Cmaj7"]}


def _ctx(key: str) -> ImprovSessionContext:
    return ImprovSessionContext(
        song_title="Span Song", artist="", key_center=key, display_key=key, instrument="Piano",
        level="Intermediate", focus="Improvisation", sections={},
    )


def _rows(steps: int = 0, key: str = "C", sections=SECTIONS):
    moved = {name: [transpose_chord(c, steps, reference_key=key) for c in chords] for name, chords in sections.items()}
    return section_harmony_rows(moved, section_names=list(moved))


def _session(**extra) -> dict:
    ss = {"active_catalog_pick_key": "span-song-pick"}
    ss.update(extra)
    return ss


class TestTargetScope(unittest.TestCase):
    def test_single_chord_is_the_default(self) -> None:
        ss = _session()
        st = _FakeSt(ss)
        self.assertEqual(_render_motif_target_scope(st, ss), "single")
        self.assertEqual(st.options[MOTIF_TARGET_SCOPE_WIDGET_KEY], ["Single chord", "2 chords", "3 chords"])

    def test_scope_survives_the_widget_being_dropped(self) -> None:
        ss = _session()
        ss[MOTIF_TARGET_SCOPE_WIDGET_KEY] = "span3"
        self.assertEqual(_render_motif_target_scope(_FakeSt(ss), ss), "span3")
        ss.pop(MOTIF_TARGET_SCOPE_WIDGET_KEY)  # Streamlit drops widget state off-page
        self.assertEqual(_render_motif_target_scope(_FakeSt(ss), ss), "span3")
        self.assertEqual(ss[MOTIF_TARGET_SCOPE_STATE_KEY], "span3")

    def test_garbage_scope_value_falls_back_to_single(self) -> None:
        ss = _session(**{MOTIF_TARGET_SCOPE_WIDGET_KEY: "bogus", MOTIF_TARGET_SCOPE_STATE_KEY: "bogus"})
        self.assertEqual(_render_motif_target_scope(_FakeSt(ss), ss), "single")


class TestSpanSelection(unittest.TestCase):
    def _render(self, ss: dict, rows, key: str, scope: str = "span3", *, pin_key: bool = True) -> _FakeSt:
        """``pin_key`` stands in for the app's Practice Key ownership (out of MC1 scope),
        which a bare session dict cannot reproduce: the selector only consumes that key."""
        st = _FakeSt(ss)
        kwargs = dict(session_state=ss, improv_ctx=_ctx(key), section_rows=rows, scope=scope)
        if pin_key:
            with patch("improvisation_intelligence_ui._coherent_improv_key_pair", return_value=(key, key)):
                _render_motif_span_selector(st, **kwargs)
        else:
            _render_motif_span_selector(st, **kwargs)
        return st

    def test_top_ranked_span_is_selected_by_default(self) -> None:
        ss = _session()
        st = self._render(ss, _rows(), "C")
        labels = st.options["improv_motif_span_pick_3"]
        self.assertEqual(labels[0], "Dm7 → G7 → Cmaj7 · ii–V–I · Chorus")
        self.assertTrue(all("|" not in label and "#" not in label for label in labels))
        selected = ss[MOTIF_SPAN_SELECTION_STATE_KEY]["span3"]
        self.assertEqual(ss["improv_motif_span_pick_3"], selected)
        self.assertTrue(any("Multi-chord motif generation is coming" in t for t in st.text))

    def test_user_pick_is_kept_and_survives_a_practice_key_change(self) -> None:
        from harmonic_span_analyzer import analyze_harmonic_spans
        from improvisation_intelligence_ui import _improv_source_id

        ss = _session()
        st_c = self._render(ss, _rows(), "C", scope="span2")
        source = _improv_source_id(ss, _ctx("C"))
        ids = [s.span_id for s in analyze_harmonic_spans(_rows(), key_center="C", length=2, source_id=source)]
        ss["improv_motif_span_pick_2"] = ids[2]  # the user picks the third-ranked span
        self._render(ss, _rows(), "C", scope="span2")
        self.assertEqual(ss[MOTIF_SPAN_SELECTION_STATE_KEY]["span2"], ids[2])
        # Practice Key C -> D: the same logical span stays selected (even if the widget
        # remounts) while every displayed label transposes.
        ss.pop("improv_motif_span_pick_2")
        st_d = self._render(ss, _rows(2, "D"), "D", scope="span2")
        self.assertEqual(ss["improv_motif_span_pick_2"], ids[2])
        labels_c = st_c.options["improv_motif_span_pick_2"]
        labels_d = st_d.options["improv_motif_span_pick_2"]
        self.assertEqual(labels_c[0], "Dm7 → G7 · ii–V · Verse")
        self.assertEqual(labels_d[0], "Em7 → A7 · ii–V · Verse")
        self.assertEqual(len(labels_c), len(labels_d))

    def test_switching_song_does_not_leak_the_old_selection(self) -> None:
        ss = _session()
        self._render(ss, _rows(), "C")
        old = ss[MOTIF_SPAN_SELECTION_STATE_KEY]["span3"]
        ss["active_catalog_pick_key"] = "another-song"
        other = {"A": ["Am7", "D7", "Gmaj7", "Em7"], "B": ["Cmaj7", "D7", "Gmaj7"]}
        st = self._render(ss, _rows(sections=other, key="G"), "G")
        new = ss[MOTIF_SPAN_SELECTION_STATE_KEY]["span3"]
        self.assertNotEqual(new, old)
        self.assertEqual(ss["improv_motif_span_pick_3"], new)
        self.assertTrue(st.options["improv_motif_span_pick_3"][0].startswith("Am7 → D7 → Gmaj7 · ii–V–I"))

    def test_written_chart_projects_display_labels(self) -> None:
        ss = _session(
            instrument="Saxophone",
            selected_transposing_instrument="Alto saxophone (Eb)",
            show_chart_in_instrument_key=True,
            concert_key="C",
            display_key="C",
        )
        st = self._render(ss, _rows(), "C", pin_key=False)
        # Alto (Eb) written chart: concert Dm7–G7–Cmaj7 reads Bm7–E7–Amaj7; the span itself
        # (and its key-relative label) is the concert one.
        self.assertEqual(st.options["improv_motif_span_pick_3"][0], "Bm7 → E7 → Amaj7 · ii–V–I · Chorus")
        self.assertTrue(any("Bm7 → E7 → Amaj7" in t for t in st.text))

    def test_labels_follow_the_chart_while_practice_key_is_mid_flight(self) -> None:
        """Browser-observed state: authoritative key already G, chart still in F."""
        ss = _session()
        st = _FakeSt(ss)
        ipanema = {"Intro": ["Gm7", "C7", "Gm7", "C7"], "A": ["Fmaj7", "G7", "Gm7", "Gb7", "Fmaj7", "Gb7"],
                   "Outro": ["Gm7", "C7", "Fmaj7", "Fmaj7"]}
        rows = section_harmony_rows(ipanema, section_names=list(ipanema))
        with patch("improvisation_intelligence_ui._coherent_improv_key_pair", return_value=("G", "G")):
            _render_motif_span_selector(st, session_state=ss, improv_ctx=_ctx("F"), section_rows=rows, scope="span3")
        labels = st.options["improv_motif_span_pick_3"]
        self.assertEqual(labels[0], "Gm7 → C7 → Fmaj7 · ii–V–I · Outro")
        self.assertIn("Gm7 → Gb7 → Fmaj7 · ii–subV–I · A", labels)
        self.assertFalse(any("bVII" in label for label in labels))

    def test_no_span_message(self) -> None:
        ss = _session()
        st = self._render(ss, section_harmony_rows({"A": ["C", "G"]}, section_names=["A"]), "C", scope="span3")
        self.assertTrue(any("No 3-chord span" in t for t in st.text))


if __name__ == "__main__":
    unittest.main()
