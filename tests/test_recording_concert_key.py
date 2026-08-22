"""Upload recording Concert Key + written-key projection regressions."""

from __future__ import annotations

import unittest

from custom_progression_lab import CPL_SAVED_KEY
from recording_analysis_context import (
    ANALYSIS_EVAL_INSTRUMENTS_KEY,
    ANALYSIS_RECORDING_CONCERT_KEY_KEY,
    ANALYSIS_SONG_SOURCE_ID_KEY,
    ANALYSIS_SONG_SOURCE_NAME_KEY,
    ANALYSIS_SONG_SOURCE_TYPE_KEY,
    ANALYSIS_TARGET_LAYER_KEY,
    RECORDING_CONCERT_KEY_UNSPECIFIED,
    RECORDING_TYPE_MT_LAYER,
    RECORDING_TYPE_MT_MIX,
    RECORDING_TYPE_PRACTICE,
    SONG_SOURCE_CUSTOM,
    SONG_SOURCE_OTHER,
    apply_snapshot_to_analysis_ctx,
    attach_selected_song_harmony_to_snapshot,
    build_analysis_context_snapshot,
    build_instrument_written_key_map,
    concert_key_choice_from_token,
    concert_key_token_from_choice,
    persist_snapshot_on_result,
    transpose_song_harmony_to_recording_key,
)


def _custom_song_session(*, concert_choice: str | None = None, **extra: object) -> dict:
    session = {
        "analysis_recording_type": RECORDING_TYPE_PRACTICE,
        "song": "Song A",
        "chart_key": "G",
        "display_key": "G",
        ANALYSIS_SONG_SOURCE_TYPE_KEY: SONG_SOURCE_CUSTOM,
        ANALYSIS_SONG_SOURCE_ID_KEY: "custom::Song C",
        ANALYSIS_SONG_SOURCE_NAME_KEY: "Song C",
        ANALYSIS_EVAL_INSTRUMENTS_KEY: ["Alto Saxophone"],
        CPL_SAVED_KEY: {
            "Song C": {
                "name": "Song C",
                "original_key_center": "C",
                "bpm": 100,
                "time_signature": "4/4",
                "original_sections": {
                    "A": [
                        {"chord": "C"},
                        {"chord": "Am"},
                        {"chord": "F"},
                        {"chord": "G"},
                    ],
                },
            }
        },
    }
    if concert_choice is not None:
        session[ANALYSIS_RECORDING_CONCERT_KEY_KEY] = concert_choice
    session.update(extra)
    return session


class ConcertKeyChoiceHelpersTests(unittest.TestCase):
    def test_token_label_roundtrip_preserves_mode(self) -> None:
        self.assertEqual(concert_key_token_from_choice("C major"), "C")
        self.assertEqual(concert_key_token_from_choice("F# minor"), "F#m")
        self.assertEqual(concert_key_token_from_choice("Eb major"), "Eb")
        self.assertEqual(concert_key_choice_from_token("Ebm"), "Eb minor")
        self.assertEqual(
            concert_key_token_from_choice(RECORDING_CONCERT_KEY_UNSPECIFIED),
            "",
        )


class WrittenKeyProjectionTests(unittest.TestCase):
    def test_alto_and_tenor_from_concert_c_major(self) -> None:
        mapping = build_instrument_written_key_map(
            "C",
            ["Alto Saxophone", "Tenor Saxophone", "Guitar"],
        )
        self.assertEqual(mapping["Alto Saxophone"], "A major")
        self.assertEqual(mapping["Tenor Saxophone"], "D major")
        self.assertEqual(mapping["Guitar"], "C major")

    def test_minor_mode_preserved_for_alto(self) -> None:
        mapping = build_instrument_written_key_map("Fm", ["Alto Saxophone", "Flute"])
        self.assertEqual(mapping["Alto Saxophone"], "D minor")
        self.assertEqual(mapping["Flute"], "F minor")


class RecordingKeyOverrideTests(unittest.TestCase):
    def test_song_key_defaults_when_unset(self) -> None:
        session = _custom_song_session()
        snap = attach_selected_song_harmony_to_snapshot(
            session, build_analysis_context_snapshot(session)
        )
        self.assertEqual(snap.get("song_canonical_key"), "C")
        self.assertEqual(snap.get("recording_concert_key"), "C")
        self.assertEqual(snap.get("display_key"), "C")
        self.assertIn("C", snap.get("target_chords") or [])

    def test_override_transposes_harmony_without_mutating_saved_song(self) -> None:
        session = _custom_song_session(concert_choice="Eb major")
        snap = attach_selected_song_harmony_to_snapshot(
            session, build_analysis_context_snapshot(session)
        )
        song_ctx = snap.get("selected_song_analysis_context") or {}
        self.assertEqual(song_ctx.get("key"), "C")
        self.assertIn("C", song_ctx.get("chord_progression") or [])
        self.assertEqual(snap.get("recording_concert_key"), "Eb")
        self.assertEqual(snap.get("display_key"), "Eb")
        chords = snap.get("target_chords") or []
        self.assertIn("Eb", chords)
        self.assertIn("Cm", chords)
        self.assertNotIn("C", chords)
        # Saved CPL song untouched.
        saved = session[CPL_SAVED_KEY]["Song C"]
        self.assertEqual(saved.get("original_key_center"), "C")

    def test_transpose_helper_c_to_eb(self) -> None:
        sections, chords = transpose_song_harmony_to_recording_key(
            canonical_key="C",
            recording_key="Eb",
            sections={"A": ["C", "Am", "F", "G"]},
            chords=["C", "Am", "F", "G"],
        )
        self.assertEqual(sections["A"][0], "Eb")
        self.assertEqual(chords[0], "Eb")
        self.assertEqual(chords[1], "Cm")

    def test_alto_written_key_on_override(self) -> None:
        session = _custom_song_session(concert_choice="C major")
        snap = attach_selected_song_harmony_to_snapshot(
            session, build_analysis_context_snapshot(session)
        )
        self.assertEqual(snap.get("written_key"), "A major")
        self.assertEqual(
            (snap.get("instrument_written_keys") or {}).get("Alto Saxophone"),
            "A major",
        )

    def test_mix_multiple_written_projections(self) -> None:
        session = _custom_song_session(
            concert_choice="C major",
            analysis_recording_type=RECORDING_TYPE_MT_MIX,
            **{
                ANALYSIS_EVAL_INSTRUMENTS_KEY: [
                    "Alto Saxophone",
                    "Tenor Saxophone",
                    "Guitar",
                ],
            },
        )
        snap = attach_selected_song_harmony_to_snapshot(
            session, build_analysis_context_snapshot(session)
        )
        written = snap.get("instrument_written_keys") or {}
        self.assertEqual(written.get("Alto Saxophone"), "A major")
        self.assertEqual(written.get("Tenor Saxophone"), "D major")
        self.assertEqual(written.get("Guitar"), "C major")
        self.assertEqual(snap.get("recording_concert_key"), "C")

    def test_layer_target_written_key(self) -> None:
        session = _custom_song_session(
            concert_choice="C major",
            analysis_recording_type=RECORDING_TYPE_MT_LAYER,
            **{
                ANALYSIS_EVAL_INSTRUMENTS_KEY: ["Alto Saxophone", "Guitar"],
                ANALYSIS_TARGET_LAYER_KEY: "Alto Saxophone",
            },
        )
        snap = attach_selected_song_harmony_to_snapshot(
            session, build_analysis_context_snapshot(session)
        )
        self.assertEqual(snap.get("written_key"), "A major")
        self.assertEqual(snap.get("target_layer"), "Alto Saxophone")

    def test_other_unspecified_has_no_key(self) -> None:
        session = _custom_song_session(
            concert_choice=RECORDING_CONCERT_KEY_UNSPECIFIED,
            **{
                ANALYSIS_SONG_SOURCE_TYPE_KEY: SONG_SOURCE_OTHER,
                ANALYSIS_SONG_SOURCE_ID_KEY: "",
                ANALYSIS_SONG_SOURCE_NAME_KEY: "Long tones",
            },
        )
        snap = attach_selected_song_harmony_to_snapshot(
            session, build_analysis_context_snapshot(session)
        )
        self.assertEqual(snap.get("recording_concert_key"), "")
        self.assertEqual(snap.get("display_key"), "")
        self.assertEqual(snap.get("target_chords"), [])

    def test_history_preserves_recording_key_against_ambient(self) -> None:
        session = _custom_song_session(concert_choice="Eb major")
        snap = attach_selected_song_harmony_to_snapshot(
            session, build_analysis_context_snapshot(session)
        )
        result = persist_snapshot_on_result({"ok": True}, snap)
        self.assertEqual(result.get("recording_concert_key"), "Eb")
        self.assertEqual(result.get("written_key"), "C major")  # Alto: Eb concert → C written
        later = apply_snapshot_to_analysis_ctx(
            {"display_key": "G", "target_chords": ["Gmaj7"]},
            result["analysis_context_snapshot"],
        )
        self.assertEqual(later.get("display_key"), "Eb")
        self.assertEqual(later.get("recording_concert_key"), "Eb")
        self.assertIn("Eb", later.get("target_chords") or [])
        self.assertNotIn("Gmaj7", later.get("target_chords") or [])


class _RecordingSt:
    """Minimal Streamlit stand-in that records widget labels from the live Upload path."""

    def __init__(self, session: dict) -> None:
        self.session_state = session
        self.selectbox_labels: list[str] = []
        self.multiselect_labels: list[str] = []
        self.radio_labels: list[str] = []
        self.captions: list[str] = []
        self.errors: list[str] = []
        self.markdowns: list[str] = []

    def markdown(self, text: str = "", **_k: object) -> None:
        self.markdowns.append(str(text))

    def caption(self, text: str = "", **_k: object) -> None:
        self.captions.append(str(text))

    def info(self, text: str = "", **_k: object) -> None:
        self.captions.append(str(text))

    def error(self, text: str = "", **_k: object) -> None:
        self.errors.append(str(text))

    def columns(self, *_a: object, **_k: object) -> list:
        class _Col:
            def __enter__(self_inner):
                return self

            def __exit__(self_inner, *_exc):
                return False

        return [_Col(), _Col()]

    def radio(self, label: str, options, **kwargs):
        self.radio_labels.append(str(label))
        key = kwargs.get("key")
        opts = list(options)
        if key and key not in self.session_state:
            self.session_state[key] = opts[0]
        return self.session_state.get(key, opts[0])

    def selectbox(self, label: str, options, **kwargs):
        self.selectbox_labels.append(str(label))
        key = kwargs.get("key")
        opts = list(options)
        cur = self.session_state.get(key) if key else None
        if key is not None and (cur is None or cur not in opts):
            idx = int(kwargs.get("index") or 0)
            self.session_state[key] = opts[idx] if opts else None
        if key is not None and self.session_state.get(key) not in opts:
            raise AssertionError(
                f"Streamlit would abort: {label!r} value "
                f"{self.session_state.get(key)!r} not in options"
            )
        return self.session_state.get(key)

    def multiselect(self, label: str, options, **kwargs):
        self.multiselect_labels.append(str(label))
        key = kwargs.get("key")
        if key and key not in self.session_state:
            self.session_state[key] = []
        return list(self.session_state.get(key) or [])

    def text_input(self, label: str, **kwargs):
        self.selectbox_labels.append(str(label))
        key = kwargs.get("key")
        return self.session_state.get(key, "") if key else ""


class UploadSetupLivePathConcertKeyTests(unittest.TestCase):
    """Inspect the real ``render_upload_analysis_setup`` path (not helpers alone)."""

    def _render(
        self,
        *,
        workflow: str,
        recording_type: str,
        instruments: list[str],
        song_key: str = "Eb",
        concert_choice: str | None = None,
    ) -> tuple[_RecordingSt, dict]:
        from custom_progression_lab import CPL_SAVED_KEY
        from recording_analysis_context import (
            ANALYSIS_EVAL_INSTRUMENT_KEY,
            ANALYSIS_EVAL_INSTRUMENTS_KEY,
            ANALYSIS_RECORDING_CONCERT_KEY_KEY,
            ANALYSIS_SONG_SOURCE_ID_KEY,
            ANALYSIS_SONG_SOURCE_NAME_KEY,
            ANALYSIS_SONG_SOURCE_TYPE_KEY,
            ANALYSIS_TARGET_LAYER_KEY,
            RECORDING_TYPE_MT_LAYER,
            SONG_SOURCE_CUSTOM,
        )
        from upload_analysis_modes import MULTITRACK_RECORDING, SINGLE_RECORDING
        from upload_analysis_setup_ui import render_upload_analysis_setup

        session: dict = {
            "analysis_mode": workflow,
            "analysis_recording_type": recording_type,
            ANALYSIS_SONG_SOURCE_TYPE_KEY: SONG_SOURCE_CUSTOM,
            ANALYSIS_SONG_SOURCE_ID_KEY: "custom::Song Eb",
            ANALYSIS_SONG_SOURCE_NAME_KEY: "Song Eb",
            ANALYSIS_EVAL_INSTRUMENTS_KEY: list(instruments),
            ANALYSIS_EVAL_INSTRUMENT_KEY: instruments[0],
            CPL_SAVED_KEY: {
                "Song Eb": {
                    "name": "Song Eb",
                    "original_key_center": song_key,
                    "bpm": 100,
                    "time_signature": "4/4",
                    "original_sections": {
                        "A": [{"chord": song_key}, {"chord": "Cm"}],
                    },
                }
            },
        }
        if recording_type == RECORDING_TYPE_MT_LAYER:
            session[ANALYSIS_TARGET_LAYER_KEY] = instruments[0]
        if concert_choice is not None:
            session[ANALYSIS_RECORDING_CONCERT_KEY_KEY] = concert_choice
        st = _RecordingSt(session)
        out = render_upload_analysis_setup(
            st,
            session,
            instrument_options=list(instruments),
            default_instrument=instruments[0],
            custom_song_choices=[{"id": "custom::Song Eb", "label": "Song Eb"}],
        )
        # Sanity: workflow constants used for branch coverage.
        self.assertIn(workflow, {SINGLE_RECORDING, MULTITRACK_RECORDING})
        return st, out

    def test_single_recording_renders_concert_key_prompt(self) -> None:
        from recording_analysis_context import RECORDING_TYPE_PRACTICE
        from upload_analysis_modes import SINGLE_RECORDING

        st, out = self._render(
            workflow=SINGLE_RECORDING,
            recording_type=RECORDING_TYPE_PRACTICE,
            instruments=["Guitar"],
        )
        self.assertIn("Concert Key of this recording", st.selectbox_labels)
        self.assertFalse(st.errors)
        self.assertEqual(out.get("recording_concert_key_label"), "Eb major")

    def test_multitrack_layer_renders_concert_key_prompt(self) -> None:
        from recording_analysis_context import RECORDING_TYPE_MT_LAYER
        from upload_analysis_modes import MULTITRACK_RECORDING

        st, out = self._render(
            workflow=MULTITRACK_RECORDING,
            recording_type=RECORDING_TYPE_MT_LAYER,
            instruments=["Alto Saxophone", "Guitar"],
        )
        self.assertIn("Concert Key of this recording", st.selectbox_labels)
        self.assertTrue(
            any("Written Key for Alto Saxophone" in c for c in st.captions),
            st.captions,
        )
        self.assertEqual(out.get("recording_concert_key"), "Eb")

    def test_multitrack_mix_renders_concert_key_prompt(self) -> None:
        from recording_analysis_context import RECORDING_TYPE_MT_MIX
        from upload_analysis_modes import MULTITRACK_RECORDING

        st, _out = self._render(
            workflow=MULTITRACK_RECORDING,
            recording_type=RECORDING_TYPE_MT_MIX,
            instruments=["Tenor Saxophone", "Guitar"],
        )
        self.assertIn("Concert Key of this recording", st.selectbox_labels)
        self.assertTrue(
            any("Written Key for Tenor Saxophone" in c for c in st.captions),
            st.captions,
        )

    def test_options_include_major_minor_and_distinct_enharmonics(self) -> None:
        from recording_analysis_context import recording_concert_key_choice_labels

        labels = recording_concert_key_choice_labels()
        self.assertIn("C major", labels)
        self.assertIn("C minor", labels)
        self.assertIn("C# minor", labels)
        self.assertIn("Db minor", labels)
        self.assertNotEqual(
            labels.index("C# minor"),
            labels.index("Db minor"),
        )

    def test_song_default_preserves_eb_spelling_not_d_sharp(self) -> None:
        from recording_analysis_context import (
            ANALYSIS_RECORDING_CONCERT_KEY_KEY,
            RECORDING_TYPE_PRACTICE,
        )
        from upload_analysis_modes import SINGLE_RECORDING

        st, out = self._render(
            workflow=SINGLE_RECORDING,
            recording_type=RECORDING_TYPE_PRACTICE,
            instruments=["Piano"],
            song_key="Eb",
        )
        self.assertEqual(st.session_state[ANALYSIS_RECORDING_CONCERT_KEY_KEY], "Eb major")
        self.assertEqual(out.get("recording_concert_key_label"), "Eb major")
        self.assertNotEqual(out.get("recording_concert_key_label"), "D# major")

    def test_db_minor_override_preserved_in_snapshot(self) -> None:
        from recording_analysis_context import (
            ANALYSIS_RECORDING_CONCERT_KEY_KEY,
            RECORDING_TYPE_PRACTICE,
            attach_selected_song_harmony_to_snapshot,
            build_analysis_context_snapshot,
        )
        from upload_analysis_modes import SINGLE_RECORDING

        st, _out = self._render(
            workflow=SINGLE_RECORDING,
            recording_type=RECORDING_TYPE_PRACTICE,
            instruments=["Guitar"],
            song_key="C",
            concert_choice="Db minor",
        )
        self.assertEqual(st.session_state[ANALYSIS_RECORDING_CONCERT_KEY_KEY], "Db minor")
        snap = attach_selected_song_harmony_to_snapshot(
            st.session_state, build_analysis_context_snapshot(st.session_state)
        )
        self.assertEqual(snap.get("recording_concert_key_label"), "Db minor")
        self.assertEqual(snap.get("recording_concert_key"), "Dbm")
        self.assertNotEqual(snap.get("recording_concert_key_label"), "C# minor")

    def test_override_does_not_mutate_saved_song_key(self) -> None:
        from custom_progression_lab import CPL_SAVED_KEY
        from recording_analysis_context import RECORDING_TYPE_PRACTICE
        from upload_analysis_modes import SINGLE_RECORDING

        st, out = self._render(
            workflow=SINGLE_RECORDING,
            recording_type=RECORDING_TYPE_PRACTICE,
            instruments=["Guitar"],
            song_key="C",
            concert_choice="Eb major",
        )
        self.assertEqual(out.get("recording_concert_key"), "Eb")
        saved = st.session_state[CPL_SAVED_KEY]["Song Eb"]
        self.assertEqual(saved.get("original_key_center"), "C")

    def test_alto_written_key_updates_from_concert_key(self) -> None:
        from recording_analysis_context import RECORDING_TYPE_PRACTICE
        from upload_analysis_modes import SINGLE_RECORDING

        st, out = self._render(
            workflow=SINGLE_RECORDING,
            recording_type=RECORDING_TYPE_PRACTICE,
            instruments=["Alto Saxophone"],
            song_key="C",
            concert_choice="C major",
        )
        self.assertTrue(
            any("Written Key for Alto Saxophone: **A major**" in c for c in st.captions),
            st.captions,
        )
        self.assertEqual(
            (out.get("instrument_written_keys") or {}).get("Alto Saxophone"),
            "A major",
        )

    def test_tenor_written_key_updates_from_concert_key(self) -> None:
        from recording_analysis_context import RECORDING_TYPE_PRACTICE
        from upload_analysis_modes import SINGLE_RECORDING

        st, out = self._render(
            workflow=SINGLE_RECORDING,
            recording_type=RECORDING_TYPE_PRACTICE,
            instruments=["Tenor Saxophone"],
            song_key="C",
            concert_choice="C major",
        )
        self.assertTrue(
            any("Written Key for Tenor Saxophone: **D major**" in c for c in st.captions),
            st.captions,
        )
        self.assertEqual(
            (out.get("instrument_written_keys") or {}).get("Tenor Saxophone"),
            "D major",
        )

    def test_non_transposing_instrument_omits_written_key_caption(self) -> None:
        from recording_analysis_context import RECORDING_TYPE_PRACTICE
        from upload_analysis_modes import SINGLE_RECORDING

        st, _out = self._render(
            workflow=SINGLE_RECORDING,
            recording_type=RECORDING_TYPE_PRACTICE,
            instruments=["Guitar"],
            song_key="C",
            concert_choice="C major",
        )
        self.assertFalse(any("Written Key for Guitar" in c for c in st.captions), st.captions)

    def test_restored_concert_key_survives_first_paint(self) -> None:
        """History/pre-seeded take key must not be wiped on first widget paint."""
        from recording_analysis_context import (
            ANALYSIS_RECORDING_CONCERT_KEY_KEY,
            RECORDING_TYPE_PRACTICE,
        )
        from upload_analysis_modes import SINGLE_RECORDING

        st, out = self._render(
            workflow=SINGLE_RECORDING,
            recording_type=RECORDING_TYPE_PRACTICE,
            instruments=["Guitar"],
            song_key="C",
            concert_choice="Db minor",
        )
        self.assertEqual(st.session_state[ANALYSIS_RECORDING_CONCERT_KEY_KEY], "Db minor")
        self.assertEqual(out.get("recording_concert_key_label"), "Db minor")
        self.assertNotEqual(out.get("recording_concert_key_label"), "C major")
        self.assertNotEqual(out.get("recording_concert_key_label"), "C# minor")

    def test_song_change_resets_concert_key_to_new_song_default(self) -> None:
        """Changing the selected song resets Concert Key to that song's spelling."""
        from custom_progression_lab import CPL_SAVED_KEY
        from recording_analysis_context import (
            ANALYSIS_RECORDING_CONCERT_KEY_KEY,
            ANALYSIS_SONG_SOURCE_ID_KEY,
            ANALYSIS_SONG_SOURCE_NAME_KEY,
            RECORDING_TYPE_PRACTICE,
        )
        from upload_analysis_modes import SINGLE_RECORDING
        from upload_analysis_setup_ui import render_upload_analysis_setup

        st, _out = self._render(
            workflow=SINGLE_RECORDING,
            recording_type=RECORDING_TYPE_PRACTICE,
            instruments=["Guitar"],
            song_key="C",
            concert_choice="Eb major",
        )
        self.assertEqual(st.session_state[ANALYSIS_RECORDING_CONCERT_KEY_KEY], "Eb major")

        # Switch Custom song (including the library picker widget key Streamlit owns).
        st.session_state[ANALYSIS_SONG_SOURCE_ID_KEY] = "custom::Song F"
        st.session_state[ANALYSIS_SONG_SOURCE_NAME_KEY] = "Song F"
        st.session_state["_analysis_song_pick_custom"] = "Song F"
        st.session_state[CPL_SAVED_KEY]["Song F"] = {
            "name": "Song F",
            "original_key_center": "F",
            "bpm": 100,
            "time_signature": "4/4",
            "original_sections": {"A": [{"chord": "F"}, {"chord": "Bb"}]},
        }
        st.selectbox_labels.clear()
        out2 = render_upload_analysis_setup(
            st,
            st.session_state,
            instrument_options=["Guitar"],
            default_instrument="Guitar",
            custom_song_choices=[
                {"id": "custom::Song Eb", "label": "Song Eb"},
                {"id": "custom::Song F", "label": "Song F"},
            ],
        )
        self.assertIn("Concert Key of this recording", st.selectbox_labels)
        self.assertEqual(st.session_state[ANALYSIS_RECORDING_CONCERT_KEY_KEY], "F major")
        self.assertEqual(out2.get("recording_concert_key_label"), "F major")
        self.assertNotEqual(out2.get("recording_concert_key_label"), "Eb major")


if __name__ == "__main__":
    unittest.main()
