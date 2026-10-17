"""MC4 — the Mission take → Upload Analysis handoff keeps the context the take was recorded with.

Found while preparing the real (Supabase-backed) handoff acceptance: the pending envelope stores the
sealed Mission context (``recording_seal``) but restoring it in Upload Analysis re-sealed the Mission *as
it is now* (``prepare_mission_upload_from_missions``). In the session that recorded the take the two
agree; in any other session (refresh, reconnect, another device, a Mission changed since) a one-chord take
was coached against the current tempo / chord. The envelope was written at record time, so its seal wins.
Two- and three-chord takes were already protected by their sealed span.
"""

from __future__ import annotations

import copy
import json
import unittest

import mission_pending_upload_persistence as mpp
from mission_pending_upload_analysis import PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY, build_pending_upload_envelope
from mission_practice_context import (
    MISSION_RECORDING_SEAL_KEY,
    ensure_mission_practice_context,
    seal_recording_context,
    set_mission_tempo,
)
from recording_analysis_context import build_analysis_context_snapshot
from tests.test_mc4_span_recording import GOLDEN_SESSION, _World, _block, record_span_take

ASSET = {"recording_id": "t1", "fingerprint": "fpx", "storage_ref": "music-media/u/ws/t1.wav", "local_path": None}


def _recording_session(tempo=134, **extra) -> dict:
    s = dict(GOLDEN_SESSION, analysis_recording_type="Mission Recording",
             analysis_mission_parameters={"chord": "A", "mission_type": "Target tone drill"}, **extra)
    set_mission_tempo(s, tempo)
    seal_recording_context(s, association="live_record_take")
    return s


def _fresh_session(env, live_tempo=None, **extra) -> dict:
    """Another session: same workspace defaults, no seal, the envelope as read back from storage."""
    s = dict(GOLDEN_SESSION, analysis_recording_type="Mission Recording",
             analysis_mission_parameters={"chord": "A", "mission_type": "Target tone drill"}, **extra)
    s[PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY] = json.loads(json.dumps(env))          # JSON, as any storage sink returns it
    if live_tempo:
        set_mission_tempo(s, live_tempo)
    return s


class _Loaded:
    """Makes the restore find the take's audio (storage itself is not under test here)."""

    def __enter__(self):
        self._orig = mpp._load_asset_bytes
        mpp._load_asset_bytes = lambda asset, st=None: (b"RIFF" + b"\0" * 64, "")
        return self

    def __exit__(self, *a):
        mpp._load_asset_bytes = self._orig


class TestSingleChordSealSurvivesRestore(unittest.TestCase):
    def test_a_fresh_session_keeps_the_tempo_the_take_was_recorded_at(self) -> None:
        env = build_pending_upload_envelope(_recording_session(134), dry_asset=ASSET)
        self.assertEqual(env["recording_seal"]["tempo_bpm"], 134)
        fresh = _fresh_session(env)
        self.assertNotEqual(ensure_mission_practice_context(fresh).tempo_bpm, 134)      # the premise: live state differs
        with _Loaded():
            diag = mpp.apply_pending_upload_envelope_to_session(fresh, force=True)
        self.assertEqual(diag["hydrate"], "ok")
        snap = build_analysis_context_snapshot(fresh, association="t")
        self.assertEqual(snap["mission_tempo_bpm"], 134)
        self.assertEqual(fresh[MISSION_RECORDING_SEAL_KEY]["tempo_bpm"], 134)
        self.assertEqual(fresh["analysis_mission_parameters"]["tempo_bpm"], 134)

    def test_changing_the_mission_afterwards_does_not_change_the_saved_take(self) -> None:
        env = build_pending_upload_envelope(_recording_session(134), dry_asset=ASSET)
        fresh = _fresh_session(env, live_tempo=82)
        with _Loaded():
            mpp.apply_pending_upload_envelope_to_session(fresh, force=True)
        set_mission_tempo(fresh, 100)
        self.assertEqual(build_analysis_context_snapshot(fresh, association="t")["mission_tempo_bpm"], 134)

    def test_the_sealed_chord_is_restored_too(self) -> None:
        recorded = _recording_session(134)
        sealed_chord = recorded[MISSION_RECORDING_SEAL_KEY]["chord"]["symbol"]
        env = build_pending_upload_envelope(recorded, dry_asset=ASSET)
        fresh = _fresh_session(env)
        fresh["ii_selected_chord"] = "G"                                              # the live selection moved on
        with _Loaded():
            mpp.apply_pending_upload_envelope_to_session(fresh, force=True)
        self.assertEqual(fresh["analysis_mission_parameters"]["chord"], sealed_chord)
        self.assertEqual(fresh[MISSION_RECORDING_SEAL_KEY]["chord"]["symbol"], sealed_chord)

    def test_envelopes_without_a_usable_seal_still_restore(self) -> None:
        for broken in (None, {}, {"chord": {"symbol": "A"}}, "garbage"):
            env = build_pending_upload_envelope(_recording_session(134), dry_asset=ASSET)
            env["recording_seal"] = broken
            if broken is None:
                env.pop("recording_seal")
            fresh = _fresh_session(env, live_tempo=82)
            with _Loaded():
                diag = mpp.apply_pending_upload_envelope_to_session(fresh, force=True)
            self.assertEqual(diag["hydrate"], "ok", broken)                           # degrades to the freshly prepared seal
            self.assertEqual(build_analysis_context_snapshot(fresh, association="t")["mission_tempo_bpm"], 82)

    def test_restore_helper_reports_what_it_did(self) -> None:
        env = build_pending_upload_envelope(_recording_session(134), dry_asset=ASSET)
        self.assertTrue(mpp.restore_sealed_context_from_envelope({}, env))
        self.assertFalse(mpp.restore_sealed_context_from_envelope({}, {"recording_seal": {}}))
        self.assertFalse(mpp.restore_sealed_context_from_envelope({}, {}))


class TestRestoredTakeIsJudgedOnItsOwnContext(unittest.TestCase):
    """Restoring the sealed context must not turn into "your Mission changed — record again"."""

    def _restored(self, live_tempo=82):
        env = build_pending_upload_envelope(_recording_session(134), dry_asset=ASSET)
        fresh = _fresh_session(env, live_tempo=live_tempo)
        with _Loaded():
            mpp.apply_pending_upload_envelope_to_session(fresh, force=True)
        return fresh

    def test_a_restored_take_is_not_stale_because_the_mission_moved_on(self) -> None:
        from mission_practice_context import recording_context_stale_warning

        fresh = self._restored(live_tempo=82)
        self.assertNotEqual(ensure_mission_practice_context(fresh).tempo_bpm, 134)
        self.assertEqual(recording_context_stale_warning(fresh), "")

    def test_analysis_context_comes_from_the_sealed_take(self) -> None:
        from mission_practice_context import enrich_analysis_context

        recorded = _recording_session(134)
        sealed_chord = recorded[MISSION_RECORDING_SEAL_KEY]["chord"]["symbol"]
        fresh = self._restored(live_tempo=82)
        out = enrich_analysis_context(fresh, {})
        self.assertEqual(out["mission_practice_context"]["tempo_bpm"], 134)
        self.assertEqual(out["mission_chord"], sealed_chord)
        self.assertNotIn("mission_context_stale_warning", out)

    def test_without_a_restored_take_the_old_staleness_rule_is_unchanged(self) -> None:
        from mission_practice_context import recording_context_stale_warning

        session = _recording_session(134)
        self.assertEqual(recording_context_stale_warning(session), "")
        set_mission_tempo(session, 100)                                                  # the Mission moved on after recording
        self.assertIn("tempo changed from 134 to 100 BPM", recording_context_stale_warning(session))

    def test_recording_a_new_take_ends_the_restored_authority(self) -> None:
        from mission_practice_context import MISSION_SEALED_BY_ENVELOPE_KEY, recording_context_stale_warning

        fresh = self._restored(live_tempo=82)
        self.assertTrue(fresh.get(MISSION_SEALED_BY_ENVELOPE_KEY))
        seal_recording_context(fresh, association="live_record_take")                    # a new take seals the live Mission
        self.assertNotIn(MISSION_SEALED_BY_ENVELOPE_KEY, fresh)
        self.assertEqual(fresh[MISSION_RECORDING_SEAL_KEY]["tempo_bpm"], 82)
        set_mission_tempo(fresh, 100)
        self.assertIn("tempo changed from 82 to 100 BPM", recording_context_stale_warning(fresh))

    def test_clearing_the_prepared_take_ends_it_too(self) -> None:
        from mission_practice_context import MISSION_SEALED_BY_ENVELOPE_KEY

        fresh = self._restored()
        mpp.clear_prepared_mission_upload(fresh, st=None)
        self.assertNotIn(MISSION_SEALED_BY_ENVELOPE_KEY, fresh)


class TestSpanEnvelopeCarriesTheTakeContext(unittest.TestCase):
    def _env(self):
        block = _block(["Bm7b5", "E7", "Am"], key="Am", bpm=134, instrument="Flute", level="Intermediate")
        session = dict(GOLDEN_SESSION, analysis_recording_type="Mission Recording", instrument="Flute")
        with _World(key="Am"):
            take = record_span_take(session, audio_bytes=b"take-x", source="live", span=block)
            session["_mission_live_take"] = {
                "take_id": "t", "dry_fp": "d", "audio_fp": take["audio_fp"],
                "timing": {"backing_offset_sec": 0.308, "backing_fp": "fp9"},
                "backing": {"fp": "fp9", "bpm": 134, "loops": 4, "count_in_bars": 1}}
            env = build_pending_upload_envelope(session, dry_asset=dict(ASSET, fingerprint=take["audio_fp"]))
        return json.loads(json.dumps(env)), block

    def test_everything_a_fresh_session_needs_is_in_the_envelope(self) -> None:
        env, block = self._env()
        self.assertEqual(env["schema_version"], 2)
        span = env["span_take"]["span"]
        self.assertEqual([t["chord"] for t in span["timeline"]], ["Bm7b5", "E7", "Am"])         # exact, ordered
        for key in ("song_title", "song_session", "span_id", "span_fingerprint", "timeline_fingerprint", "practice_key",
                    "chart_key", "pick_key", "instrument", "level", "style", "bpm", "meter", "loops", "count_in_bars",
                    "mission_id", "mission_label", "evaluation_focus", "section"):
            self.assertIn(key, span, key)
        self.assertEqual((span["bpm"], span["practice_key"], span["instrument"]), (134, "Am", "Flute"))
        self.assertEqual(env["live_take"]["timing"]["backing_offset_sec"], 0.308)               # stored offset
        self.assertEqual(env["live_take"]["backing"]["fp"], "fp9")                              # exact backing identity
        for key in ("recording_seal", "metrics", "evaluation_criteria", "mission"):
            self.assertIn(key, env, key)

    def test_a_fresh_session_restores_the_sealed_span_and_ignores_the_current_mission(self) -> None:
        env, block = self._env()
        fresh = _fresh_session(env, live_tempo=100)
        with _World(key="Am"), _Loaded():
            mpp.apply_pending_upload_envelope_to_session(fresh, force=True)
            snap = build_analysis_context_snapshot(fresh, association="t")
        self.assertEqual(snap["mission_tempo_bpm"], 134)
        self.assertEqual(snap["mission_span"]["bpm"], 134)
        self.assertEqual([t["chord"] for t in snap["mission_span"]["timeline"]], ["Bm7b5", "E7", "Am"])
        self.assertEqual(fresh["_mission_live_take"]["timing"]["backing_offset_sec"], 0.308)

    def test_v1_envelopes_load_without_span_fields(self) -> None:
        env = build_pending_upload_envelope(_recording_session(134), dry_asset=ASSET)
        self.assertEqual(env["schema_version"], 1)
        self.assertNotIn("span_take", env)
        self.assertNotIn("live_take", env)
        fresh = _fresh_session(env)
        with _Loaded():
            self.assertEqual(mpp.apply_pending_upload_envelope_to_session(fresh, force=True)["hydrate"], "ok")


class TestFailureBehaviour(unittest.TestCase):
    def test_a_write_that_is_not_confirmed_is_not_a_save(self) -> None:
        from mission_upload_handoff import handoff_mission_take_to_upload_analysis

        session = _recording_session(134)
        session["_mission_live_mic_pending"] = b"RIFF" + b"\0" * 64
        fake_mps = type("M", (), {"force_save_music_state": staticmethod(lambda st, reason="": True)})

        class St:                                                                       # no cloud confirmation recorded
            session_state: dict = {}

        import sys
        from unittest import mock

        with mock.patch.dict(sys.modules, {"music_persistent_state": fake_mps}), \
                mock.patch.object(mpp, "_persist_audio_asset", lambda *a, **k: dict(ASSET)):
            ok, err = handoff_mission_take_to_upload_analysis(session, audio_bytes=b"RIFF" + b"\0" * 64, filename="t.wav",
                                                              source="live", st=St())
        self.assertFalse(ok)
        self.assertIn("cloud=False", err)
        self.assertNotIn("_navigate_to_studio_page", session)                           # no navigation on an unconfirmed write
        self.assertEqual(session["_mission_live_mic_pending"][:4], b"RIFF")             # the local take is kept


if __name__ == "__main__":
    unittest.main()
