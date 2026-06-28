"""Music AMI context — intent, finalize, active song, practice payload."""

from __future__ import annotations

import unittest

from global_active_song_state import get_active_pick_key, prepare_global_active_song, sync_active_song_to_canonical
from music_ami_context import (
    attach_question_song_to_context,
    build_music_applied_math_context,
    cache_music_ami_context,
    detect_music_send_intent,
    extract_section_from_question,
    extract_song_title_from_question,
    finalize_music_context_for_send,
    gather_practice_ami_snapshot,
)
from music_ami_pages import promote_music_ami_context_at_send


class TestMusicSendIntent(unittest.TestCase):
    def test_practice_plan_intent(self) -> None:
        self.assertEqual(
            detect_music_send_intent("What should I practice next?", "practice"),
            "practice_plan",
        )

    def test_section_focus_intent(self) -> None:
        self.assertEqual(
            detect_music_send_intent("How should I practice this chorus?", "practice"),
            "section_focus",
        )

    def test_tempo_key_intent(self) -> None:
        self.assertEqual(
            detect_music_send_intent("What key should I play this in?", "practice"),
            "tempo_key",
        )

    def test_practice_history_analysis_intent(self) -> None:
        self.assertEqual(
            detect_music_send_intent("Analyze my practice history and tell me what to focus on", "log"),
            "practice_history_analysis",
        )

    def test_difficulty_intent(self) -> None:
        self.assertEqual(
            detect_music_send_intent("Is this song too difficult for my level?", "practice"),
            "difficulty",
        )


class TestSongExtraction(unittest.TestCase):
    def test_quoted_title(self) -> None:
        self.assertEqual(extract_song_title_from_question('Should I learn "Wonderwall"?'), "Wonderwall")

    def test_chorus_section(self) -> None:
        self.assertEqual(extract_section_from_question("How should I practice the chorus slowly?"), "Chorus")


class TestGlobalActiveSong(unittest.TestCase):
    def test_sync_propagates_pick_key(self) -> None:
        session = {
            "selected_song": {"title": "Test Song", "pick_key": "pop:test"},
            "active_catalog_pick_key": "pop:test",
        }
        sync_active_song_to_canonical(session)
        self.assertEqual(get_active_pick_key(session), "pop:test")
        self.assertEqual(session["_master_song_pick_key"], "pop:test")

    def test_prepare_reads_canonical(self) -> None:
        session = {
            "selected_song": {"title": "Blue Bossa", "pick_key": "jazz:blue"},
            "active_catalog_pick_key": "jazz:blue",
            "matching_song_dropdown": "stale:other",
        }
        prepare_global_active_song(session)
        self.assertEqual(session["matching_song_dropdown"], "jazz:blue")


class TestPracticeSnapshot(unittest.TestCase):
    def test_gather_practice_payload(self) -> None:
        session = {
            "studio_page": "practice",
            "instrument": "Guitar",
            "level": "Intermediate",
            "display_key": "G",
            "practice_focus_section": "Chorus",
            "practice_groove_style": "Rock",
            "last_practice_mode": "Section drill",
            "selected_song": {
                "title": "Test Song",
                "artist": "Artist",
                "genre": "Rock",
                "pick_key": "rock:test",
                "bpm": 120,
                "sections": ["Verse", "Chorus"],
            },
            "active_catalog_pick_key": "rock:test",
        }
        snap = gather_practice_ami_snapshot(session)
        self.assertEqual(snap["title"], "Test Song")
        self.assertEqual(snap["instrument"], "Guitar")
        self.assertEqual(snap["practice_focus_section"], "Chorus")
        self.assertEqual(snap["genre"], "Rock")
        self.assertEqual(snap["bpm"], 120)


class TestPracticeLogAmiSnapshot(unittest.TestCase):
    def test_recent_practice_history_from_persistence_fixture(self) -> None:
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from practice_log_state import migrate_practice_log_entry

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "practice_history.json"
            entry = migrate_practice_log_entry(
                {
                    "session_id": "fixture-1",
                    "date": "2026-06-26",
                    "active_song": "Autumn Leaves",
                    "duration_minutes": 30,
                    "updated_at": "2026-06-26T12:00:00+00:00",
                }
            )
            path.write_text(json.dumps([entry]), encoding="utf-8")
            session = {
                "selected_song": {"title": "Autumn Leaves", "pick_key": "jazz:autumn"},
                "active_catalog_pick_key": "jazz:autumn",
            }
            with patch("practice_log_persistence._local_path", lambda *, st=None: path):
                with patch("practice_log_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("practice_log_persistence._load_cloud_logs", lambda *, st=None: []):
                        snap = gather_practice_ami_snapshot(session)
            history = snap.get("recent_practice_history") or []
            self.assertTrue(history)
            self.assertEqual(history[0].get("active_song"), "Autumn Leaves")
            payload = snap.get("practice_log_ami_payload") or {}
            self.assertIn("practice_log_summary", payload)

    def test_analyze_practice_context_includes_payload(self) -> None:
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from practice_log_state import migrate_practice_log_entry

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "practice_history.json"
            entry = migrate_practice_log_entry(
                {
                    "session_id": "fixture-2",
                    "date": "2026-06-26",
                    "active_song": "Blue Bossa",
                    "duration_minutes": 20,
                    "updated_at": "2026-06-26T12:00:00+00:00",
                }
            )
            path.write_text(json.dumps([entry]), encoding="utf-8")
            session = {
                "selected_song": {"title": "Blue Bossa", "pick_key": "jazz:blue"},
                "active_catalog_pick_key": "jazz:blue",
            }
            with patch("practice_log_persistence._local_path", lambda *, st=None: path):
                with patch("practice_log_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("practice_log_persistence._load_cloud_logs", lambda *, st=None: []):
                        ctx = build_music_applied_math_context(
                            "log",
                            session,
                            question="Analyze my practice history",
                        )
            self.assertTrue(ctx.get("recent_practice_history"))
            self.assertIn("practice_log_ami_payload", ctx)
            self.assertEqual(ctx.get("routing_hint"), "practice_history_analysis")


class TestFinalizeMusicContext(unittest.TestCase):
    def test_finalize_anchors_active_song(self) -> None:
        session = {
            "instrument": "Piano",
            "selected_song": {"title": "Autumn Leaves", "pick_key": "jazz:autumn"},
            "active_catalog_pick_key": "jazz:autumn",
            "practice_focus_section": "Head",
        }
        cache_music_ami_context(session, coach_page="practice")
        ctx: dict = {}
        finalize_music_context_for_send(
            ctx,
            session,
            question="What should I practice next?",
            coach_page="practice",
        )
        self.assertEqual(ctx.get("routing_hint"), "practice_plan")
        self.assertEqual((ctx.get("active_song") or {}).get("title"), "Autumn Leaves")
        self.assertEqual(ctx.get("practice_focus_section"), "Head")

    def test_stale_context_cleared_for_new_named_song(self) -> None:
        ctx = {
            "question_song": "Old Song",
            "song_focus": {"title": "Old Song"},
        }
        attach_question_song_to_context(ctx, 'How do I practice "Wonderwall"?', {})
        self.assertEqual(ctx.get("question_song"), "Wonderwall")

    def test_promote_at_send(self) -> None:
        session = {
            "selected_song": {"title": "Test Song", "pick_key": "pop:test"},
            "active_catalog_pick_key": "pop:test",
            "instrument": "Voice",
            "practice_focus_section": "Verse",
        }
        ctx: dict = {"instrument": "Voice"}
        diag = promote_music_ami_context_at_send(
            ctx,
            session,
            source_page="practice",
            question="Is this song too difficult for my level?",
        )
        self.assertEqual(diag.get("music_send_intent"), "difficulty")
        self.assertEqual(ctx.get("routing_hint"), "difficulty")
        self.assertIn("practice_snapshot", ctx)

    def test_build_applied_math_context(self) -> None:
        session = {
            "selected_song": {"title": "Song A", "artist": "Band", "pick_key": "pop:a"},
            "active_catalog_pick_key": "pop:a",
            "instrument": "Guitar",
            "level": "Beginner",
            "display_key": "C",
            "practice_focus_section": "Chorus",
        }
        ctx = build_music_applied_math_context("practice", session, question="How should I practice this chorus?")
        self.assertEqual(ctx.get("coach_page"), "practice")
        self.assertIn("Song A", str(ctx.get("song") or ""))
        self.assertEqual(ctx.get("routing_hint"), "section_focus")
        self.assertEqual(ctx.get("practice_focus_section"), "Chorus")


class TestCacheSignature(unittest.TestCase):
    def test_cache_skips_unchanged(self) -> None:
        session = {
            "selected_song": {"title": "Cached", "pick_key": "pop:cached"},
            "active_catalog_pick_key": "pop:cached",
            "instrument": "Piano",
        }
        first = cache_music_ami_context(session, coach_page="practice")
        second = cache_music_ami_context(session, coach_page="practice")
        self.assertEqual(first.get("cache_action"), "built")
        self.assertEqual(second.get("cache_action"), "skipped_unchanged")


if __name__ == "__main__":
    unittest.main()
