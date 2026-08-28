"""Composition playback — UI-to-audio path, not WAV generation alone."""

from __future__ import annotations

import inspect
import unittest

from composition_document import (
    apply_melody_events,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
from composition_preview import (
    COMPOSER_PREVIEW_AUTOPLAY_KEY,
    COMPOSER_PREVIEW_NONCE_KEY,
    build_composer_playback_html,
    inspect_preview_wav,
    play_composer_preview,
    render_composer_playback,
    render_local_composer_playback,
)
from composition_session_state import COMPOSER_PREVIEW_WAV_KEY
from composition_studio_page import (
    _play_chord_idea,
    _render_hum_sing_panel,
    _render_phase_chords,
    _render_section_transport,
    _render_suggestion_card,
    render_composition_studio_page,
)


def _song_with_chords():
    doc = bootstrap_from_vision(genre="Pop", song_idea="Play path", key="C major", bpm=100, meter="4/4")
    apply_structure_template(doc, "simple")
    verse = ordered_sections(doc)[0]
    apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C Am F G"))
    return doc, verse


class FakeStreamlit:
    def __init__(self) -> None:
        self.markdowns: list[str] = []
        self.audio_calls: list[tuple] = []
        self.buttons: list[str] = []

    def markdown(self, text: str, **_kwargs) -> None:
        self.markdowns.append(str(text))

    def caption(self, text: str, **_kwargs) -> None:
        self.markdowns.append(str(text))

    def columns(self, _spec):
        return (self, self)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def button(self, label: str, **_kwargs) -> bool:
        self.buttons.append(str(label))
        return False

    def audio(self, data, **kwargs) -> None:
        self.audio_calls.append((data, kwargs))

    def rerun(self) -> None:
        return None


class TestPlayablePayloadSeam(unittest.TestCase):
    def test_play_chords_button_path_arms_nonempty_autoplay_html(self) -> None:
        doc, verse = _song_with_chords()
        ss: dict = {}
        result = play_composer_preview(
            ss,
            doc,
            section_id=str(verse["id"]),
            include_melody=False,
            loops=1,
        )
        self.assertTrue(result["ok"], result.get("reason"))
        self.assertTrue(result["playable"])
        self.assertGreater(result["byte_len"], 44)
        self.assertGreater(result["peak"], 0.02)
        self.assertGreater(result["duration_seconds"], 0.2)
        self.assertEqual(result["bpm"], 100)
        self.assertEqual(result["meter"], "4/4")
        self.assertTrue(result["chords"])
        self.assertIn("C", result["chords"])
        html = result["html"]
        self.assertIn("composer-playback-audio", html)
        self.assertIn("autoplay", html)
        self.assertIn("data:audio/wav;base64,", html)
        self.assertGreater(len(html.split("base64,", 1)[1]), 80)
        self.assertEqual(ss.get(COMPOSER_PREVIEW_NONCE_KEY), result["nonce"])
        self.assertTrue(ss.get(COMPOSER_PREVIEW_AUTOPLAY_KEY))
        self.assertTrue(ss.get(COMPOSER_PREVIEW_WAV_KEY))
        stats = inspect_preview_wav(ss[COMPOSER_PREVIEW_WAV_KEY])
        self.assertTrue(stats["playable"])

    def test_play_melody_uses_accepted_events_and_tempo(self) -> None:
        doc, verse = _song_with_chords()
        apply_melody_events(
            doc,
            str(verse["id"]),
            [
                {"pitch": "E4", "midi": 64, "duration_beats": 2.0, "beat": 0.0, "measure": 1},
                {"pitch": "G4", "midi": 67, "duration_beats": 2.0, "beat": 2.0, "measure": 1},
            ],
            replace=True,
        )
        ss: dict = {}
        chords_only = play_composer_preview(
            ss, doc, section_id=str(verse["id"]), include_melody=False, loops=1
        )
        with_mel = play_composer_preview(
            ss, doc, section_id=str(verse["id"]), include_melody=True, loops=1
        )
        self.assertTrue(chords_only["ok"] and with_mel["ok"])
        self.assertTrue(with_mel["include_melody"])
        self.assertNotEqual(chords_only["signature"], with_mel["signature"])
        self.assertGreater(with_mel["nonce"], chords_only["nonce"])

    def test_arrangement_preview_is_its_own_payload(self) -> None:
        doc, verse = _song_with_chords()
        ss: dict = {}
        original = play_composer_preview(
            ss, doc, scope="song", include_melody=True, loops=1
        )
        funk = play_composer_preview(
            ss,
            doc,
            scope="song",
            include_melody=True,
            loops=1,
            arrangement_style="Funk",
        )
        self.assertTrue(original["ok"] and funk["ok"])
        self.assertNotEqual(original["signature"], funk["signature"])
        self.assertIn("autoplay", funk["html"])

    def test_replay_remounts_new_nonce(self) -> None:
        doc, verse = _song_with_chords()
        ss: dict = {}
        first = play_composer_preview(ss, doc, section_id=str(verse["id"]), loops=1)
        second = play_composer_preview(ss, doc, section_id=str(verse["id"]), loops=1)
        self.assertTrue(first["ok"] and second["ok"])
        self.assertNotEqual(first["nonce"], second["nonce"])
        self.assertIn(f'data-nonce="{second["nonce"]}"', second["html"])
        self.assertNotIn(f'data-nonce="{first["nonce"]}"', second["html"])

    def test_empty_chords_do_not_arm_player(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Empty", key="C major")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        ss: dict = {}
        result = play_composer_preview(ss, doc, section_id=str(verse["id"]), loops=1)
        self.assertFalse(result["ok"])
        self.assertFalse(result["playable"])
        self.assertFalse(ss.get(COMPOSER_PREVIEW_WAV_KEY))

    def test_html_builder_marks_autoplay_and_restart(self) -> None:
        doc, verse = _song_with_chords()
        result = play_composer_preview({}, doc, section_id=str(verse["id"]), loops=1)
        html = build_composer_playback_html(result["wav"], nonce=9, autoplay=True)
        self.assertIn('id="composer-playback-9"', html)
        self.assertIn("current.play()", html)
        self.assertIn(".pause()", html)
        self.assertIn("currentTime = 0", html)

    def test_render_harness_mounts_playable_payload(self) -> None:
        doc, verse = _song_with_chords()
        ss: dict = {}
        result = play_composer_preview(ss, doc, section_id=str(verse["id"]), loops=1)
        self.assertTrue(result["ok"])
        fake = FakeStreamlit()
        mounted = render_composer_playback(fake, ss, stop_key="t_stop")
        self.assertTrue(mounted)
        self.assertTrue(any("Now playing" in m for m in fake.markdowns))
        self.assertTrue(fake.audio_calls, "Playable path must mount native st.audio")
        data, kwargs = fake.audio_calls[0]
        self.assertTrue(data)
        self.assertGreater(len(data), 44)
        self.assertTrue(kwargs.get("autoplay"), kwargs)
        self.assertIn("composer_preview_audio_", str(kwargs.get("key") or ""))

    def test_chord_idea_button_uses_same_seam(self) -> None:
        doc, verse = _song_with_chords()
        ss: dict = {}
        self.assertTrue(_play_chord_idea(ss, doc, str(verse["id"]), ["Am", "F", "C", "G"], loops=1))
        self.assertTrue(inspect_preview_wav(ss.get(COMPOSER_PREVIEW_WAV_KEY)).get("playable"))


class TestClickRunRemount(unittest.TestCase):
    def test_click_run_mounts_audio_element_without_extra_rerun(self) -> None:
        """Click-run: arm → local player in the same script run (keeps the gesture)."""
        doc, verse = _song_with_chords()
        ss: dict = {}
        result = play_composer_preview(
            ss,
            doc,
            section_id=str(verse["id"]),
            loops=1,
            slot="chords:local",
            label="Playing chords",
        )
        self.assertTrue(result["ok"], result.get("reason"))
        fake = FakeStreamlit()
        self.assertFalse(render_local_composer_playback(fake, ss, slot="other"))
        self.assertFalse(fake.audio_calls)
        mounted = render_local_composer_playback(fake, ss, slot="chords:local")
        self.assertTrue(mounted)
        self.assertTrue(fake.audio_calls, "Same-run local mount must use native st.audio")
        data, kwargs = fake.audio_calls[0]
        self.assertTrue(data)
        self.assertTrue(kwargs.get("autoplay"), kwargs)
        self.assertIn("composer_preview_audio_", str(kwargs.get("key") or ""))
        self.assertTrue(any('data-preview-slot="chords:local"' in m for m in fake.markdowns))
        self.assertTrue(any("Playing chords" in m for m in fake.markdowns))
        transport = inspect.getsource(_render_section_transport)
        self.assertNotIn("st.rerun()", transport)
        page = inspect.getsource(render_composition_studio_page)
        self.assertNotIn("flush_composer_preview_dock", page)
        self.assertIn("_attach_local_preview", transport)

    def test_streamlit_click_harness_arms_playable_wav(self) -> None:
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("streamlit.testing.v1.AppTest unavailable")
        from pathlib import Path

        harness = str(Path(__file__).resolve().parent / "composer_preview_click_app.py")
        at = AppTest.from_file(harness, default_timeout=45)
        at.run()
        self.assertFalse(at.exception)
        preview = [b for b in at.button if "Preview" in str(b.label)]
        play_chords = [b for b in at.button if "Play chords" in str(b.label)]
        self.assertTrue(preview, "Preview button missing from harness")
        self.assertTrue(play_chords, "Play chords button missing from harness")
        play_chords[0].click().run()
        self.assertFalse(at.exception)
        self.assertIn(COMPOSER_PREVIEW_WAV_KEY, at.session_state)
        wav = at.session_state[COMPOSER_PREVIEW_WAV_KEY]
        stats = inspect_preview_wav(wav if isinstance(wav, (bytes, bytearray)) else None)
        self.assertTrue(stats.get("playable"), stats)
        self.assertGreater(int(at.session_state[COMPOSER_PREVIEW_NONCE_KEY] or 0), 0)
        self.assertTrue(bool(at.session_state[COMPOSER_PREVIEW_AUTOPLAY_KEY]))
        preview[0].click().run()
        self.assertFalse(at.exception)
        self.assertGreater(int(at.session_state[COMPOSER_PREVIEW_NONCE_KEY] or 0), 1)


class TestButtonPathWiring(unittest.TestCase):
    def test_transport_and_preview_call_playable_seam(self) -> None:
        transport = inspect.getsource(_render_section_transport)
        self.assertIn("play_composer_preview", transport)
        self.assertNotIn("st.audio(", transport)
        self.assertIn("_attach_local_preview", transport)
        self.assertIn("slot=transport_slot", transport)
        page = inspect.getsource(render_composition_studio_page)
        self.assertNotIn("flush_composer_preview_dock", page)
        self.assertIn("_attach_local_preview", inspect.getsource(_render_section_transport))
        card = inspect.getsource(_render_suggestion_card)
        self.assertIn("_attach_local_preview", card)
        self.assertIn("slot=card_slot", card)
        chords = inspect.getsource(_render_phase_chords)
        self.assertIn("_render_section_transport", chords)
        self.assertIn('button_label="▶ Play chords"', chords)
        self.assertIn("include_melody=False", chords)
        render = inspect.getsource(render_composer_playback)
        self.assertIn("st_mod.audio", render)
        self.assertIn("autoplay", render)
        self.assertIn("composer_preview_audio_", render)
        self.assertNotIn("components.v1", render)
        self.assertNotIn("st_mod.components", render)
        hum = inspect.getsource(_render_hum_sing_panel)
        self.assertIn("play_composer_preview", hum)
        self.assertIn("Record your melody over these chords.", hum)
        self.assertIn("prepare_armed_record_transport", hum)
        self.assertIn("mic_lead_beats", hum)
        self.assertIn("backing_origin_in_capture_beats", hum)
        self.assertIn("▶ Hear the chords", hum)
        self.assertIn("include_melody=False", hum)
        self.assertIn("progression_line", hum)
        self.assertIn("span_events_across_section_timeline", hum)
        self.assertIn("over the chords", hum)
        self.assertIn("build_live_chord_follow_html", hum)
        self.assertNotIn("**1. Arm the microphone**", hum)
        self.assertNotIn("**2. Start count-in + backing**", hum)


class TestCompositionStudioQaSmoke(unittest.TestCase):
    def test_studio_page_exposes_qa_controls(self) -> None:
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("streamlit.testing.v1.AppTest unavailable")
        from pathlib import Path

        from composition_preview import composition_surface_label

        harness = str(Path(__file__).resolve().parent / "composer_studio_qa_smoke_app.py")
        at = AppTest.from_file(harness, default_timeout=90)
        at.run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        labels = [str(b.label) for b in at.button]
        self.assertTrue(any("Shape accepted melody" in lab for lab in labels), labels)
        self.assertTrue(any("Refine accepted melody" in lab for lab in labels), labels)
        self.assertTrue(any("Hear the chords" in lab for lab in labels), labels)
        section_like = [lab for lab in labels if "Verse" in lab or "Chorus" in lab]
        self.assertGreaterEqual(len(section_like), 2, labels)
        play_like = [lab for lab in labels if "Play" in lab or "Preview" in lab]
        self.assertTrue(play_like, labels)
        joined = "\n".join(str(m.value) for m in at.markdown) + "\n".join(str(c.value) for c in at.caption)
        self.assertIn("Composition surface", joined)
        self.assertTrue(
            "progression" in joined.lower() or "C (1 bar)" in joined or "chord" in joined.lower(),
            joined[:800],
        )
        stamp = composition_surface_label()
        self.assertIn("Composition surface", stamp)


if __name__ == "__main__":
    unittest.main()
