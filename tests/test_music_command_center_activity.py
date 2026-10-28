from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import music_activity
import suite_activity_client


def _st(**overrides):
    session = {
        "studio_page": "practice",
        "active_catalog_pick_key": "Pop|Shape of You — Ed Sheeran",
        "song": "Shape of You",
        "instrument": "Alto Sax",
        "display_key": "C minor",
        "focus": "Chords",
        "active_music_source": "catalog",
    }
    session.update(overrides)
    return SimpleNamespace(session_state=session)


class MusicCommandCenterActivityTests(unittest.TestCase):
    def test_shared_activity_falls_back_once_when_storage_shim_raises(self) -> None:
        failing_storage = SimpleNamespace(
            record_activity=lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError("Supabase is not configured")
            )
        )
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            suite_activity_client,
            "LOCAL_FALLBACK_DIR",
            Path(tmp),
        ), patch.object(
            suite_activity_client,
            "_record_via_cloud",
            return_value=False,
        ), patch.object(
            suite_activity_client,
            "_load_storage_module",
            return_value=failing_storage,
        ):
            suite_activity_client.record_activity(
                "music",
                "practice_session_started",
                page="Practice",
                metrics={"song": "Shape of You", "workspace_id": "qa"},
            )
            fallback_files = list(Path(tmp).glob("*_activity_fallback.json"))
            self.assertEqual(len(fallback_files), 1)
            rows = json.loads(fallback_files[0].read_text(encoding="utf-8"))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event"], "practice_session_started")
        self.assertEqual(suite_activity_client.last_record_trace()["write_path"], "fallback_json")

    def test_record_uses_existing_shared_activity_pipeline(self) -> None:
        st = _st()
        with patch(
            "music_resume_payload.build_music_resume_payload",
            return_value={"resume_kind": "practice"},
        ), patch("music_resume_payload.continue_card_title", return_value="Continue: Shape of You"), patch(
            "music_resume_payload.continue_card_subtitle", return_value="C minor · Alto Sax"
        ), patch("music_resume_payload.legacy_resume_key_for_payload", return_value="song:shape"), patch(
            "suite_activity_client.record_activity"
        ) as record:
            music_activity._record(
                "practice_session_started",
                st=st,
                page="Practice",
                metrics={"activity_schema_version": 1},
                summary="Practiced Shape of You on Alto Sax in C minor",
            )

        record.assert_called_once()
        args, kwargs = record.call_args
        self.assertEqual(args, ("music", "practice_session_started"))
        self.assertEqual(kwargs["metrics"]["source_type"], "catalog")
        self.assertEqual(kwargs["metrics"]["practice_key"], "C minor")
        self.assertEqual(kwargs["resume_key"], "song:shape")
        self.assertIsInstance(kwargs["local_state"], dict)

    def test_practice_session_started_has_versioned_authoritative_context(self) -> None:
        st = _st()
        context = {
            "song": "Shape of You",
            "artist": "Ed Sheeran",
            "pick_key": "Pop|Shape of You — Ed Sheeran",
            "source_id": "Pop|Shape of You — Ed Sheeran",
            "source_type": "catalog",
            "instrument": "Alto Sax",
            "display_key": "C minor",
            "practice_key": "C minor",
        }
        with patch("music_activity._song_context", return_value=context), patch(
            "music_activity._key_cycling_context",
            return_value={"key_cycling_active": False},
        ), patch("music_activity._record") as record:
            emitted = music_activity.log_practice_session_started(st)

        self.assertTrue(emitted)
        args, kwargs = record.call_args
        self.assertEqual(args[0], "practice_session_started")
        metrics = kwargs["metrics"]
        self.assertEqual(metrics["activity_schema_version"], 2)
        self.assertEqual(metrics["source_type"], "catalog")
        self.assertEqual(metrics["source_id"], context["pick_key"])
        self.assertEqual(metrics["practice_key"], "C minor")
        self.assertEqual(metrics["practice_mode"], "Chords")
        self.assertFalse(metrics["backing_active"])
        self.assertEqual(
            kwargs["summary"],
            "Practiced Shape of You on Alto Sax in C minor",
        )

    def test_identical_streamlit_rerun_does_not_duplicate_session_start(self) -> None:
        st = _st()
        with patch("music_activity._key_cycling_context", return_value={"key_cycling_active": False}), patch(
            "music_activity._record"
        ) as record:
            first = music_activity.log_practice_session_started(st)
            second = music_activity.log_practice_session_started(st)

        self.assertTrue(first)
        self.assertFalse(second)
        record.assert_called_once()

    def test_key_cycling_keeps_practice_and_temporary_keys_separate(self) -> None:
        st = _st(display_key="B minor")
        with patch(
            "music_activity._key_cycling_context",
            return_value={
                "key_cycling_active": True,
                "key_cycling_start_key": "B minor",
                "key_cycling_sounding_key": "D minor",
            },
        ), patch("music_activity._record") as record:
            music_activity.log_practice_session_started(st)

        metrics = record.call_args.kwargs["metrics"]
        self.assertEqual(metrics["practice_key"], "B minor")
        self.assertEqual(metrics["key_cycling_sounding_key"], "D minor")
        self.assertEqual(
            record.call_args.kwargs["summary"],
            "Practiced Shape of You on Alto Sax with Key Cycling, starting in B minor",
        )

    def test_key_cycle_read_does_not_create_runtime_state(self) -> None:
        st = _st()
        st.session_state.pop("_backing_key_cycle_sessions", None)
        context = music_activity._key_cycling_context(st)
        self.assertEqual(context, {"key_cycling_active": False})
        self.assertNotIn("_backing_key_cycle_sessions", st.session_state)

    def test_practice_page_entry_uses_meaningful_session_event(self) -> None:
        st = _st()
        with patch("music_activity.log_practice_session_started") as started, patch(
            "music_activity._record"
        ) as record:
            music_activity.log_studio_page_entered(st, "practice")

        started.assert_called_once_with(st)
        record.assert_not_called()

    def test_source_type_reads_canonical_owner_and_has_pick_prefix_fallback(self) -> None:
        st = _st(active_music_source="composition_song")
        with patch("source_session_state.global_music_source_owner", return_value="composition"):
            self.assertEqual(music_activity._source_type(st), "composition")
        with patch("source_session_state.global_music_source_owner", side_effect=RuntimeError):
            self.assertEqual(music_activity._source_type(st, "custom::trial"), "custom")


if __name__ == "__main__":
    unittest.main()
