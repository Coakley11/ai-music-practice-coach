"""Notation/TAB metronome integration.

Mounts the existing ``practice_metronome`` widget underneath a generated
Notation/TAB exercise via ``streamlit_music_practice_app.render_notation_metronome``
rather than building a second metronome engine. These tests cover the six
areas called out for this slice: visibility, BPM/meter defaults, no
duplication, isolation from canonical song/Backing state, instrument
coverage, and that mounting the metronome can never trigger a notation
regeneration.
"""

from __future__ import annotations

import inspect
import re
import unittest
import unittest.mock as mock

import streamlit_music_practice_app as app
from practice_notation import generate_practice_notation
from practice_setup_controls import DEFAULT_INSTRUMENT_OPTIONS

_SECTIONS = {
    "Verse 1": ["Am7", "Dm7", "G7", "Cmaj7"],
    "Chorus": ["F", "C", "G", "Am"],
}


class TestMetronomeVisibility(unittest.TestCase):
    """Shown only when a generated exercise is available."""

    def test_no_notation_renders_nothing(self) -> None:
        with mock.patch("practice_metronome.render_metronome_widget") as fake:
            app.render_notation_metronome(
                app, notation=None, default_bpm=100, default_signature="4/4"
            )
        fake.assert_not_called()

    def test_generated_notation_renders_the_metronome(self) -> None:
        notation = generate_practice_notation(
            song_title="Song", artist="", display_key="C", original_key="C",
            bpm=100, groove_style="Pop", instrument="Piano", focus="general",
            section_focus="Verse 1", sections=_SECTIONS, guitar_tabs={},
        )
        with mock.patch("practice_metronome.render_metronome_widget") as fake:
            app.render_notation_metronome(
                app, notation=notation, default_bpm=100, default_signature="4/4"
            )
        fake.assert_called_once()


class TestMetronomeDefaults(unittest.TestCase):
    """Seeded from the exercise's own effective BPM/meter, never from
    canonical song/Backing/Key-Cycling state (the caller passes those in;
    this function only forwards them)."""

    def test_bpm_and_meter_forwarded_to_the_widget(self) -> None:
        notation = object()  # truthy stand-in; only visibility matters here
        with mock.patch("practice_metronome.render_metronome_widget") as fake:
            app.render_notation_metronome(
                app, notation=notation, default_bpm=133, default_signature="6/8"
            )
        fake.assert_called_once()
        _, kwargs = fake.call_args
        self.assertEqual(kwargs["default_bpm"], 133)
        self.assertEqual(kwargs["default_signature"], "6/8")
        self.assertTrue(kwargs["compact"])

    def test_non_numeric_or_missing_inputs_fall_back_safely(self) -> None:
        notation = object()
        with mock.patch("practice_metronome.render_metronome_widget") as fake:
            app.render_notation_metronome(
                app, notation=notation, default_bpm=0, default_signature=""
            )
        _, kwargs = fake.call_args
        self.assertEqual(kwargs["default_bpm"], 100)
        self.assertEqual(kwargs["default_signature"], "4/4")

    def test_float_bpm_is_coerced_to_int(self) -> None:
        notation = object()
        with mock.patch("practice_metronome.render_metronome_widget") as fake:
            app.render_notation_metronome(
                app, notation=notation, default_bpm=128.0, default_signature="3/4"
            )
        _, kwargs = fake.call_args
        self.assertEqual(kwargs["default_bpm"], 128)
        self.assertIsInstance(kwargs["default_bpm"], int)

    def test_call_site_seeds_meter_from_notation_meter_not_song_time_sig(self) -> None:
        """generate_practice_notation() has no meter parameter and always
        lays its content out in 4/4 (practice_notation.NOTATION_METER) --
        seeding the metronome from the song's own ``_time_sig`` instead
        would mismatch a 6/8 song's metronome against this panel's actual
        (always 4/4) rhythmic content."""
        src = inspect.getsource(app)
        call_start = src.index("render_notation_metronome(\n")
        # The call's own closing ")" is the first one at the same
        # indentation as its opening line (not one inside a comment, like
        # the "generate_practice_notation()" mentioned in the docstring
        # above it).
        call_indent = len(src[:call_start].rsplit("\n", 1)[-1])
        close_marker = "\n" + " " * call_indent + ")"
        call_end = src.index(close_marker, call_start)
        call_text = src[call_start:call_end]
        code_only = "\n".join(
            line for line in call_text.split("\n") if not line.strip().startswith("#")
        )
        self.assertIn("default_signature=NOTATION_METER", code_only)
        self.assertNotIn("_time_sig", code_only)

    def test_notation_meter_constant_matches_the_generators_fixed_meter(self) -> None:
        from practice_notation import NOTATION_METER

        self.assertEqual(NOTATION_METER, "4/4")


class TestNoWidgetDuplication(unittest.TestCase):
    """Full Song renders one notation block per unique section (several
    ``render_abc`` calls for one NotationResult) -- the metronome call site
    must sit after that loop closes, not inside it, so one exercise still
    gets exactly one metronome."""

    def test_exactly_one_call_site_in_the_app(self) -> None:
        src = inspect.getsource(app)
        self.assertEqual(src.count("render_notation_metronome("), 2)  # def + 1 call

    def test_call_site_is_a_sibling_of_the_tab_abc_branch_not_inside_the_loop(self) -> None:
        src = inspect.getsource(app)
        lines = src.split("\n")
        branch_indent = call_indent = loop_indent = None
        for line in lines:
            stripped = line.lstrip(" ")
            indent = len(line) - len(stripped)
            if stripped.startswith('if getattr(_notation, "format", "") == "tab":'):
                branch_indent = indent
            if stripped.startswith("for _sec in _notation_sections:"):
                loop_indent = indent
            if stripped.startswith("render_notation_metronome(") and "def " not in line:
                call_indent = indent
        self.assertIsNotNone(branch_indent)
        self.assertIsNotNone(loop_indent)
        self.assertIsNotNone(call_indent)
        # Same nesting level as the format if/else, not the deeper for-loop body.
        self.assertEqual(call_indent, branch_indent)
        self.assertGreater(loop_indent, call_indent)


class TestIsolationFromCanonicalState(unittest.TestCase):
    """Must never read or write canonical song BPM, Backing tempo, Practice
    groove, Key Cycling, or Practice Melody state -- only forward the
    caller-supplied exercise BPM/meter into the existing widget."""

    def test_function_body_touches_no_session_state(self) -> None:
        src = inspect.getsource(app.render_notation_metronome)
        self.assertNotIn("session_state", src)

    def test_function_body_references_no_canonical_tempo_or_key_names(self) -> None:
        src = inspect.getsource(app.render_notation_metronome)
        for forbidden in (
            "backing_track_bpm", "practice_groove", "key_cycl", "Key Cycl",
            "practice_concert_key", "practice_melody", "PRACTICE_METRONOME_BPM_KEY",
        ):
            self.assertNotIn(forbidden, src)

    def test_delegates_to_the_existing_widget_only(self) -> None:
        src = inspect.getsource(app.render_notation_metronome)
        self.assertIn("render_metronome_widget(", src)
        # No second audio clock / timer / transport is introduced here.
        self.assertNotIn("setInterval", src)
        self.assertNotIn("AudioContext", src)


class TestInstrumentCoverage(unittest.TestCase):
    """Every instrument's generated result (guitar TAB, piano/bass/wind ABC)
    mounts the metronome the same way."""

    def test_every_default_instrument_mounts_exactly_one_metronome(self) -> None:
        for instrument in DEFAULT_INSTRUMENT_OPTIONS:
            with self.subTest(instrument=instrument):
                notation = generate_practice_notation(
                    song_title="Song", artist="", display_key="C", original_key="C",
                    bpm=110, groove_style="Pop", instrument=instrument, focus="general",
                    section_focus="Verse 1", sections=_SECTIONS, guitar_tabs={},
                )
                self.assertTrue(notation)
                with mock.patch("practice_metronome.render_metronome_widget") as fake:
                    app.render_notation_metronome(
                        app, notation=notation, default_bpm=110, default_signature="4/4"
                    )
                fake.assert_called_once()

    def test_guitar_tab_and_abc_instruments_both_reach_the_metronome(self) -> None:
        guitar = generate_practice_notation(
            song_title="Song", artist="", display_key="C", original_key="C",
            bpm=100, groove_style="Pop", instrument="Guitar", focus="general",
            section_focus="Verse 1", sections=_SECTIONS, guitar_tabs={},
        )
        sax = generate_practice_notation(
            song_title="Song", artist="", display_key="C", original_key="C",
            bpm=100, groove_style="Pop", instrument="Saxophone", focus="general",
            section_focus="Verse 1", sections=_SECTIONS, guitar_tabs={},
        )
        self.assertEqual(guitar.format, "tab")
        self.assertEqual(sax.format, "abc")
        for result in (guitar, sax):
            with mock.patch("practice_metronome.render_metronome_widget") as fake:
                app.render_notation_metronome(
                    app, notation=result, default_bpm=100, default_signature="4/4"
                )
            fake.assert_called_once()


class TestNoUnexpectedRegeneration(unittest.TestCase):
    """Mounting/adjusting the metronome must never regenerate the notation
    or trigger a rerun -- it only reads the already-resolved BPM/meter the
    caller passes in."""

    def test_function_body_never_regenerates_notation_or_reruns(self) -> None:
        src = inspect.getsource(app.render_notation_metronome)
        self.assertNotIn("generate_practice_notation", src)
        self.assertNotIn("_NOTATION_KEY", src)
        self.assertNotIn("st.rerun()", src)
        self.assertNotIn("st_module.rerun()", src)


class TestNoTapTempoOrSubdivisionAddedThisSlice(unittest.TestCase):
    """Explicitly out of scope for this slice."""

    def test_widget_html_has_no_tap_tempo_or_subdivision_controls(self) -> None:
        from practice_metronome import build_metronome_widget_html

        html = build_metronome_widget_html(default_bpm=100, default_signature="4/4")
        self.assertNotRegex(html, re.compile("tap.?tempo", re.IGNORECASE))
        self.assertNotIn("subdiv", html.lower())


if __name__ == "__main__":
    unittest.main()
