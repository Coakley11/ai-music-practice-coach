"""Lead Sheet open/close hand-off (K7) and Key Cycling + capo Lead Sheet projection.

K7: closing the Lead Sheet went silent. The card transport paused the outgoing
player at the Close click, before the page player existed (a full rerun plus
buffering later), and the per-run transport reset flipped st.audio's autoplay
prop, which re-created the sounding page player paused.

KC + capo: the cycle Lead Sheet treated the fixed guitar shape key as the
reading key ("Key: Dm" over F#m audio, shape chords as cells, no capo number),
and the in-app sheet kept the saved Practice Key's capo while other keys sounded.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_APP = (_ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
_KC = (_ROOT / "backing_key_cycle.py").read_text(encoding="utf-8")
_TRANSPORT = (_ROOT / "backing_transport_component" / "index.html").read_text(encoding="utf-8")


def _js_body(src: str, name: str) -> str:
    i = src.index(f"function {name}(")
    j = src.index("\n      function ", i + 10)
    return src[i:j]


def _capo_session(**extra):
    session = {
        "instrument": "Guitar",
        "guitar_capo_enabled": True,
        "guitar_capo_shape_key": "Dm",
    }
    session.update(extra)
    return session


def _cells(html: str) -> list[str]:
    body = html[html.index('<div class="lead-sheet'):]
    return re.findall(r"<div class='chord-symbol'>(.*?)</div>", body)


def _hints(html: str) -> list[str]:
    return re.findall(r"class='chord-shape-hint'[^>]*>(.*?)<", html)


BLUES = {
    "Fm": ["Fm6", "Fm6", "Db7", "C7"],
    "F#m": ["F#m6", "F#m6", "D7", "C#7"],  # cells follow the Key Spelling prefs: C#7 -> Db7
    "Gm": ["Gm6", "Gm6", "Eb7", "D7"],
}


class CycleShapeProjectionTests(unittest.TestCase):
    def test_shape_stays_fixed_and_the_capo_moves_with_the_sounding_key(self) -> None:
        from backing_key_cycle import cycle_shape_projection

        session = _capo_session()
        got = {k: cycle_shape_projection(session, k) for k in ("Fm", "F#m", "Gm", "Dm")}
        self.assertEqual({k: v["capo_fret"] for k, v in got.items()}, {"Fm": 3, "F#m": 4, "Gm": 5, "Dm": 0})
        self.assertEqual({v["shape_key"] for v in got.values()}, {"Dm"})
        self.assertEqual({v["shape_tonic"] for v in got.values()}, {"D"})

    def test_no_projection_outside_shape_mode(self) -> None:
        from backing_key_cycle import cycle_shape_projection

        self.assertIsNone(cycle_shape_projection({"instrument": "Piano"}, "Fm"))
        self.assertIsNone(cycle_shape_projection(_capo_session(guitar_capo_enabled=False), "Fm"))


class CycleLeadSheetShapeModeTests(unittest.TestCase):
    def _sheet(self, key: str) -> str:
        from backing_key_cycle import project_cycle_display_key
        from backing_key_cycle_handoff import build_cycle_lead_sheet_html

        session = _capo_session()
        return build_cycle_lead_sheet_html(
            sounding_key=key,
            sections={"Verse": list(BLUES[key])},
            song_name="Blues in F minor",
            song_data={"key": "Fm"},
            session=session,
            chart_display_key=project_cycle_display_key(session, key),
        )

    def test_each_cycling_key_shows_its_concert_cells_shape_hints_and_capo(self) -> None:
        for key, fret in (("Fm", 3), ("F#m", 4), ("Gm", 5)):
            with self.subTest(key=key):
                html = self._sheet(key)
                self.assertIn(f"Key: {key}", html)
                self.assertIn(f"Charts in D minor · capo {fret}", html)
                spelled = BLUES[key][3].replace("C#7", "Db7")
                self.assertEqual(_cells(html)[:4], [BLUES[key][0], "%", BLUES[key][2], spelled])
                self.assertEqual(_hints(html)[:3], ["Dm6 shape", "Bb7 shape", "A7 shape"])
                # Not the Written-mode layout: no shape key presented as the reading key.
                self.assertNotIn("Key: Dm", html)
                self.assertNotIn("Reading Dm", html)

    def test_written_mode_cycle_sheet_keeps_reading_and_sounding_pills(self) -> None:
        from backing_key_cycle_handoff import build_cycle_lead_sheet_html
        from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY

        session = {
            "instrument": "Saxophone",
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)",
            "show_chart_in_instrument_key": True,
        }
        html = build_cycle_lead_sheet_html(
            sounding_key="Cm",
            chart_display_key="Am",
            sections={"Verse": ["Cm", "Fm", "G7", "Cm"]},
            song_name="Minor Blues",
            session=session,
        )
        self.assertIn("Reading Am", html)
        self.assertIn("Sounding Cm", html)
        self.assertEqual(_cells(html)[:2], ["Am", "Dm"])
        self.assertNotIn("capo", html)


class CycleCurrentNextProjectionTests(unittest.TestCase):
    def test_shape_mode_current_next_stay_concert_like_the_cells(self) -> None:
        from backing_key_cycle import display_projection_bundle

        bundle = display_projection_bundle(_capo_session(), sounding_key="F#m", include_timelines=False)
        self.assertEqual(bundle["chartMode"], "shape")
        self.assertEqual(bundle["readingKey"], "Dm")  # playbar still names the shape key
        self.assertEqual(bundle["displaySemitones"], 0)

    def test_written_mode_current_next_still_move_to_the_written_key(self) -> None:
        from backing_key_cycle import display_projection_bundle
        from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY

        session = {
            "instrument": "Saxophone",
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)",
            "show_chart_in_instrument_key": True,
        }
        bundle = display_projection_bundle(session, sounding_key="Cm", include_timelines=False)
        self.assertEqual(bundle["readingKey"], "Am")
        self.assertNotEqual(bundle["displaySemitones"], 0)


class SharedProjectionContractTests(unittest.TestCase):
    def test_playbar_capo_line_reads_the_shared_projection(self) -> None:
        i = _KC.index('capo_line = ""\n    shape_tonic_attr = ""')
        block = _KC[i : _KC.index("# The audible buffer is stale", i)]
        self.assertIn("cycle_shape_projection(", block)
        self.assertNotIn("capo_fret_for_shape(", block)

    def test_in_app_sheet_uses_the_cycling_key_capo_while_cycling(self) -> None:
        self.assertIn("_sheet_cycle_capo = cycle_shape_projection(", _APP)
        self.assertIn("tuple(sorted(_sheet_cycle_capo.items())) if _sheet_cycle_capo else ()", _APP)
        self.assertIn("capo_fret=_sheet_capo_fret,", _APP)
        self.assertIn("capo_shape_key=_sheet_capo_shape,", _APP)


class PagePlayerAutoplayTests(unittest.TestCase):
    def test_same_take_keeps_its_autoplay_prop_across_the_per_run_reset(self) -> None:
        from backing_track_state import page_player_autoplay

        session = {"_backing_autoplay": True}
        self.assertTrue(page_player_autoplay(session, "/tmp/take.wav"))
        session["_backing_autoplay"] = False  # prepare_backing_transport_for_session on the next rerun
        self.assertTrue(page_player_autoplay(session, "/tmp/take.wav"))
        self.assertTrue(page_player_autoplay(session, "/tmp/take.wav"))

    def test_stop_and_a_new_take_still_change_the_prop(self) -> None:
        from backing_track_state import page_player_autoplay

        session = {"_backing_autoplay": True}
        page_player_autoplay(session, "/tmp/take.wav")
        session["_backing_autoplay"] = False
        self.assertFalse(page_player_autoplay(session, "/tmp/other.wav"))
        session = {"_backing_autoplay": True}
        page_player_autoplay(session, "/tmp/take.wav")
        session.update({"_backing_autoplay": False, "_backing_transport_user_stopped": True})
        self.assertFalse(page_player_autoplay(session, "/tmp/take.wav"))

    def test_a_take_without_a_path_follows_the_flag(self) -> None:
        from backing_track_state import page_player_autoplay

        session = {"_backing_autoplay": True}
        page_player_autoplay(session, "")
        session["_backing_autoplay"] = False
        self.assertFalse(page_player_autoplay(session, ""))

    def test_page_player_mount_uses_the_stable_prop(self) -> None:
        self.assertIn("_page_autoplay = page_player_autoplay(st.session_state, _wav_path)", _APP)
        self.assertEqual(_APP.count("autoplay=_page_autoplay,"), 2)
        self.assertIn("(not _leadsheet_open or _sheet_taking_over)", _APP)


class TransportHandoffContractTests(unittest.TestCase):
    def test_the_click_records_the_live_player_without_pausing_it(self) -> None:
        body = _js_body(_TRANSPORT, "recordHandoff")
        self.assertNotIn(".pause()", body)
        self.assertIn("el: src", body)
        self.assertIn("playing: !!a", body)

    def test_the_destination_takes_over_at_the_live_position_and_retires_the_source(self) -> None:
        body = _js_body(_TRANSPORT, "takeOver")
        self.assertIn("handoffPosition(h)", body)
        self.assertIn("h.el.pause()", body)
        self.assertLess(body.index("h.el.pause()"), body.index("target.play()"))
        self.assertIn("takeOver(target, h)", _js_body(_TRANSPORT, "applyHandoff"))
        for ev in ("loadedmetadata", "canplay", "play"):
            self.assertIn(f'hdoc.addEventListener("{ev}", window.parent.__backingHandoffMediaHook, true)', _TRANSPORT)

    def test_key_cycling_audio_is_never_a_handoff_party(self) -> None:
        self.assertIn("if (cycleOwnsAudio()) return;", _js_body(_TRANSPORT, "recordHandoff"))
        self.assertIn("cycleOwnsAudio()", _js_body(_TRANSPORT, "currentHandoff"))
        self.assertIn("isPagePlayer(a)", _js_body(_TRANSPORT, "isHandoffTarget"))

    def test_the_sheet_player_retires_the_page_player_when_it_takes_over(self) -> None:
        i = _APP.index("function consumeBackingPlayheadHandoff()")
        body = _APP[i : _APP.index("const p = audio.play();", i)]
        self.assertIn("h.playing === false", body)
        # The outgoing player is retired only once this one is really playing.
        retire = body[body.index("const retire = () =>"):]
        self.assertIn("if (h.el) h.el.pause();", retire[: retire.index("};")])
        self.assertIn('audio.addEventListener("playing", retire, {{ once: true }})', body)
        # Silent until it takes over, so the two players are never heard together.
        self.assertLess(body.index("audio.muted = true;"), body.index('audio.addEventListener("playing", retire'))
        self.assertIn("audio.muted = wasMuted;", retire[: retire.index("};")])

    def test_a_slow_mount_still_takes_over_a_sounding_player(self) -> None:
        i = _APP.index("function consumeBackingPlayheadHandoff()")
        body = _APP[i : _APP.index("const livePos", i)]
        self.assertIn("&& !stillSounding) h = null;", body)
        self.assertIn("&& !stillSounding) || cycleOwnsAudio()", _js_body(_TRANSPORT, "currentHandoff"))


if __name__ == "__main__":
    unittest.main()
