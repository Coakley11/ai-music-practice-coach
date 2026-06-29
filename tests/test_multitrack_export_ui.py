"""Multitrack Step 4 Save Export UI — readiness state and render wiring."""

from __future__ import annotations

import base64
import io
import unittest
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

from multitrack_export_ui import (
    MT_EXPORT_SAVE_NAME_KEY,
    MT_MIXED_EXPORT_SIG_KEY,
    ensure_mixed_export_save_name,
    render_step4_save_export_panel,
)
from multitrack_session_persistence import (
    mixed_export_is_ready,
    resolve_mixed_export_wav_bytes,
)
from studio_page_persistence import _B64_MARKER, _encode_snapshot_value


def _sample_wav_bytes(*, duration_sec: float = 0.05, rate: int = 44100) -> bytes:
    buf = io.BytesIO()
    nframes = max(1, int(rate * duration_sec))
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * nframes)
    return buf.getvalue()


class TestMixedExportReadiness(unittest.TestCase):
    def test_resolve_bytes_from_live_session(self) -> None:
        audio = _sample_wav_bytes()
        session = {"mixed_track_wav": audio}
        self.assertEqual(resolve_mixed_export_wav_bytes(session), audio)

    def test_resolve_bytes_from_persist_encoding(self) -> None:
        audio = _sample_wav_bytes()
        encoded = _encode_snapshot_value(audio)
        session = {"mixed_track_wav": encoded}
        resolved = resolve_mixed_export_wav_bytes(session)
        self.assertEqual(resolved, audio)
        self.assertEqual(session["mixed_track_wav"], audio)

    def test_mixed_export_is_ready_matches_download_gate(self) -> None:
        audio = _sample_wav_bytes()
        session = {"mixed_track_wav": audio}
        self.assertTrue(mixed_export_is_ready(session))
        session["mixed_track_wav"] = None
        self.assertFalse(mixed_export_is_ready(session))

    def test_save_name_initialized_for_ready_mix(self) -> None:
        audio = _sample_wav_bytes()
        session: dict = {"mixed_track_wav": audio}
        name = ensure_mixed_export_save_name(session, song_title="Say", mixed=audio)
        self.assertIn("Say mix", name)
        self.assertEqual(session[MT_EXPORT_SAVE_NAME_KEY], name)
        self.assertIn(MT_MIXED_EXPORT_SIG_KEY, session)

    def test_save_name_refreshes_when_new_mix_created(self) -> None:
        audio_a = _sample_wav_bytes(duration_sec=0.05)
        audio_b = _sample_wav_bytes(duration_sec=0.08)
        session: dict = {"mixed_track_wav": audio_a, MT_EXPORT_SAVE_NAME_KEY: "Old name"}
        ensure_mixed_export_save_name(session, song_title="Say", mixed=audio_a)
        old_sig = session[MT_MIXED_EXPORT_SIG_KEY]
        ensure_mixed_export_save_name(session, song_title="Say", mixed=audio_b)
        self.assertNotEqual(session[MT_MIXED_EXPORT_SIG_KEY], old_sig)
        self.assertIn("Say mix", session[MT_EXPORT_SAVE_NAME_KEY])
        self.assertNotEqual(session[MT_EXPORT_SAVE_NAME_KEY], "Old name")

    def test_save_name_persists_across_rerun_simulation(self) -> None:
        audio = _sample_wav_bytes()
        session: dict = {"mixed_track_wav": audio}
        ensure_mixed_export_save_name(session, song_title="Say", mixed=audio)
        first = session[MT_EXPORT_SAVE_NAME_KEY]
        ensure_mixed_export_save_name(session, song_title="Say", mixed=audio)
        self.assertEqual(session[MT_EXPORT_SAVE_NAME_KEY], first)


class TestStep4SaveExportRender(unittest.TestCase):
    def test_save_export_ui_renders_when_mixed_ready(self) -> None:
        audio = _sample_wav_bytes()
        session: dict = {"mixed_track_wav": audio}
        st = MagicMock()
        st.markdown = MagicMock()
        st.text_input = MagicMock(return_value="Say mix test")
        st.button = MagicMock(return_value=False)

        render_step4_save_export_panel(
            st,
            session,
            song_title="Say",
            track_items_for_mix=[{"slot": "Layer 1", "name": "Sax", "volume": 1.0}],
            include_backing=False,
            backing_volume=0.75,
            mixed_wav=audio,
        )

        st.markdown.assert_any_call("##### Save Export")
        st.text_input.assert_called_once()
        self.assertEqual(st.text_input.call_args.kwargs.get("key"), MT_EXPORT_SAVE_NAME_KEY)
        self.assertNotIn("value", st.text_input.call_args.kwargs)
        st.button.assert_called_once()
        self.assertEqual(st.button.call_args.args[0], "Save Export")

    def test_save_export_skipped_without_mixed_wav(self) -> None:
        st = MagicMock()
        render_step4_save_export_panel(
            st,
            {},
            song_title="Say",
            track_items_for_mix=[],
            include_backing=False,
            backing_volume=0.75,
        )
        st.text_input.assert_not_called()
        st.button.assert_not_called()

    def test_step4_download_and_save_share_ready_helper(self) -> None:
        app_source = (
            Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"
        ).read_text(encoding="utf-8")
        ui_source = (
            Path(__file__).resolve().parents[1] / "multitrack_export_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn("resolve_mixed_export_wav_bytes", app_source)
        self.assertIn("mixed_export_wav = resolve_mixed_export_wav_bytes", app_source)
        self.assertIn("render_step4_save_export_panel", app_source)
        self.assertIn("mixed_wav=mixed_export_wav", app_source)
        self.assertIn("resolve_mixed_export_wav_bytes", ui_source)
        self.assertNotIn('value=default_name', ui_source)

    def test_encoded_mixed_enables_save_export_after_resolve(self) -> None:
        audio = _sample_wav_bytes()
        encoded = { _B64_MARKER: base64.b64encode(audio).decode("ascii") }
        session: dict = {"mixed_track_wav": encoded}
        self.assertTrue(mixed_export_is_ready(session))
        st = MagicMock()
        st.markdown = MagicMock()
        st.text_input = MagicMock(return_value="Say mix")
        st.button = MagicMock(return_value=False)
        render_step4_save_export_panel(
            st,
            session,
            song_title="Say",
            track_items_for_mix=[{"slot": "Layer 1", "name": "Sax", "volume": 1.0}],
            include_backing=False,
            backing_volume=0.75,
        )
        st.text_input.assert_called_once()
        st.button.assert_called_once()


if __name__ == "__main__":
    unittest.main()
