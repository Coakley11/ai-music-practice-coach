"""Melody preview: one event timeline == audio length; highlight coverage; single score."""

from __future__ import annotations

import io
import unittest
import wave

from composition_document import (
    apply_structure_template,
    bootstrap_from_vision,
    chords_for_playback,
    ordered_sections,
)
from composition_melody_preview import (
    MELODY_AUDIO_TAIL_SEC,
    expanded_section_chords,
    timeline_audio_report,
)
from composition_melody_suggestions import suggest_melody_concepts
from composition_playback_sync import render_synced_score_playback_html
from composition_preview import generate_preview_wav, inspect_preview_wav


def _doc_with_multibar_entries():
    doc = bootstrap_from_vision(genre="Pop", song_idea="x", key="C", bpm=96, meter="4/4")
    apply_structure_template(doc, "simple")
    verse = ordered_sections(doc)[0]
    # multi-bar entries: the raw entry list is SHORTER than the bar count
    verse["chords"] = [
        {"chord": "Cmaj7", "bars": 2},
        {"chord": "Fmaj7", "bars": 1},
        {"chord": "G7", "bars": 1},
    ]
    return doc, verse


def _dur(wav: bytes) -> float:
    with wave.open(io.BytesIO(wav), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


class TestEarlyStopRegression(unittest.TestCase):
    def test_unexpanded_chord_entries_used_to_truncate_the_melody(self) -> None:
        doc, verse = _doc_with_multibar_entries()
        sid = str(verse["id"])
        ev = suggest_melody_concepts(doc, verse, "lyrical", "simple", limit=1)[0]["events"]
        end_sec = max(e["beat"] + e["duration_beats"] for e in ev) * 60.0 / 96
        raw = [str(c["chord"]) for c in verse["chords"]]  # what the card used to pass
        self.assertLess(len(raw), len(expanded_section_chords(doc, sid)))
        wav = generate_preview_wav(doc, section_id=sid, chord_override=raw, include_melody=True, melody_override=ev, loops=1)
        # The mixer now extends the audio instead of cutting notes off.
        self.assertGreaterEqual(_dur(wav), end_sec + MELODY_AUDIO_TAIL_SEC - 1e-3)

    def test_expanded_chords_audio_covers_timeline_plus_tail(self) -> None:
        doc, verse = _doc_with_multibar_entries()
        sid = str(verse["id"])
        chords = expanded_section_chords(doc, sid)
        self.assertEqual(chords, chords_for_playback(doc, scope="section", section_id=sid))
        for feel in ("lyrical", "rhythmic", "bold"):
            for idea in suggest_melody_concepts(doc, verse, feel, "simple", limit=3):
                ev = idea["events"]
                wav = generate_preview_wav(doc, section_id=sid, chord_override=chords, include_melody=True, melody_override=ev, loops=1)
                rep = timeline_audio_report(wav, ev, chords, bpm=96)
                self.assertTrue(rep["audio_covers_timeline"], (idea["id"], rep["audio_sec"], rep["timeline_end_sec"]))
                self.assertGreaterEqual(rep["chord_end_sec"], rep["timeline_end_sec"] - 1e-6)
                self.assertTrue(inspect_preview_wav(wav).get("playable"))

    def test_last_note_is_audible_in_the_audio(self) -> None:
        """Energy in the final note's window must be present (not silence from truncation)."""
        import struct

        doc, verse = _doc_with_multibar_entries()
        sid = str(verse["id"])
        raw = [str(c["chord"]) for c in verse["chords"]]
        ev = suggest_melody_concepts(doc, verse, "lyrical", "simple", limit=1)[0]["events"]
        wav = generate_preview_wav(doc, section_id=sid, chord_override=raw, include_melody=True, melody_override=ev, loops=1, melody_gain=0.9, backing_gain=0.05)
        with wave.open(io.BytesIO(wav), "rb") as wf:
            sr = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
        samples = struct.unpack("<" + "h" * (len(frames) // 2), frames)
        last = [e for e in ev if not e.get("is_rest")][-1]
        a = int(last["beat"] * 60 / 96 * sr) + int(0.1 * sr)
        b = int((last["beat"] + min(1.0, last["duration_beats"])) * 60 / 96 * sr)
        peak = max(abs(s) for s in samples[a:b])
        self.assertGreater(peak, 500)


class TestHighlightTimeline(unittest.TestCase):
    def test_highlight_sequence_covers_every_note_in_order_and_ends_cleanly(self) -> None:
        doc, verse = _doc_with_multibar_entries()
        chords = expanded_section_chords(doc, str(verse["id"]))
        for idea in suggest_melody_concepts(doc, verse, "rhythmic", "simple", limit=3):
            ev = idea["events"]
            rep = timeline_audio_report(None, ev, chords, bpm=96)
            seq = rep["highlight_sequence"]
            n_sounding = sum(1 for e in ev if not e.get("is_rest"))
            self.assertEqual(seq, list(range(n_sounding)))  # every note, once, in order
            spans = [s for s in rep["bundle"]["melody_spans"]]
            for s0, s1 in zip(spans, spans[1:]):  # one timeline: contiguous, no gaps/overlap
                self.assertAlmostEqual(s0["end_sec"], s1["start_sec"], places=6)
            # rests never become highlights
            self.assertTrue(all(not s["highlightable"] for s in spans if s["is_rest"]))

    def test_html_has_transport_and_resets_on_stop_and_end(self) -> None:
        doc, verse = _doc_with_multibar_entries()
        chords = expanded_section_chords(doc, str(verse["id"]))
        ev = suggest_melody_concepts(doc, verse, "lyrical", "simple", limit=1)[0]["events"]
        rep = timeline_audio_report(None, ev, chords, bpm=96)
        html = render_synced_score_playback_html(
            wav_bytes=b"RIFFxxxx", abc_text="X:1\nK:C\nCDEF|", bundle=rep["bundle"], dom_id="t", transport="custom",
        )
        self.assertIn("Play", html)
        self.assertIn("Stop", html)
        self.assertIn("Resume", html)
        self.assertIn("Pause", html)
        self.assertIn('addEventListener("ended", () => {{ resetAll(); }})'.replace("{{", "{").replace("}}", "}"), html)
        self.assertIn("audio.currentTime = 0; resetAll()", html)
        # one compact transport for every preview: the native audio bar is not shown
        default = render_synced_score_playback_html(
            wav_bytes=b"RIFFxxxx", abc_text="X:1\nK:C\nCDEF|", bundle=rep["bundle"], dom_id="t",
        )
        self.assertNotIn(" controls ", default)
        self.assertIn("cplay-btn is-primary", default)


class TestSingleScoreCard(unittest.TestCase):
    def test_card_renders_score_once_with_preview_below(self) -> None:
        import inspect

        import composition_studio_page as page

        src = inspect.getsource(page._render_melody_concept_card)
        # exactly one static-score call site and one synced-score call for the candidate;
        # the synced version replaces the static one (never appended below it).
        self.assertEqual(src.count("_render_melody_staff("), 1)
        self.assertIn("if events and not mounted", src)
        self.assertIn('transport="custom"', src)
        self.assertIn("expanded_section_chords(doc, section_id)", src)
        self.assertLess(src.index("score_box = st.container()"), src.index("Preview with chords"))


if __name__ == "__main__":
    unittest.main()


def _card_script():
    """AppTest body: one candidate card; counts score renders and synced mounts."""
    import streamlit as st
    import streamlit.components.v1 as components

    import composition_studio_page as page
    from composition_document import (
        apply_structure_template,
        bootstrap_from_vision,
        ordered_sections,
    )
    from composition_melody_suggestions import suggest_melody_concepts

    st.session_state.setdefault("n_static", 0)
    st.session_state.setdefault("n_synced", 0)
    st.session_state.setdefault("htmls", [])

    def fake_staff(*a, **k):
        st.session_state["n_static"] += 1

    def fake_html(src, *a, **k):
        st.session_state["htmls"] = list(st.session_state["htmls"]) + [src]
        st.session_state["n_synced"] += 1

    page._render_melody_staff = fake_staff
    components.html = fake_html
    doc = bootstrap_from_vision(genre="Pop", song_idea="x", key="C", bpm=96, meter="4/4")
    apply_structure_template(doc, "simple")
    verse = ordered_sections(doc)[0]
    verse["chords"] = [{"chord": "Cmaj7", "bars": 2}, {"chord": "Fmaj7", "bars": 1}, {"chord": "G7", "bars": 1}]
    idea = suggest_melody_concepts(doc, verse, "lyrical", "simple", limit=1)[0]
    page._render_melody_concept_card(
        st.session_state, doc, str(verse["id"]), idea, prefix="t", is_active=False,
    )


class TestCardAppTest(unittest.TestCase):
    def test_score_once_then_synced_replaces_it_and_covers_every_note(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_function(_card_script, default_timeout=60).run()
        self.assertFalse(at.exception, at.exception)
        self.assertEqual(at.session_state["n_static"], 1)  # before Preview: one static score
        self.assertEqual(at.session_state["n_synced"], 0)
        btn = next(b for b in at.button if "Preview" in str(b.label))
        btn.click().run()
        self.assertFalse(at.exception, at.exception)
        # after Preview: the SAME slot shows the synced score; no extra static copy is added
        self.assertEqual(at.session_state["n_static"], 1)
        self.assertEqual(at.session_state["n_synced"], 1)
        html = at.session_state["htmls"][-1]
        self.assertIn("cplay-btn is-primary", html)  # Play / Pause / Stop transport (compact player)
        self.assertEqual(html.count('class="cplay-paper"'), 1)  # one score in the frame
        # timeline in the frame covers every sounding note of the candidate
        import json
        import re

        m = re.search(r"const cursorSpans = (\[.*?\]);\n", html, re.S)
        spans = json.loads(m.group(1))
        sounding = [s for s in spans if s["highlightable"]]
        self.assertEqual([s["dom_note_index"] for s in sounding], list(range(len(sounding))))
