"""MC4 — Mission Recording key authority.

Human review (Autumn Leaves, catalog key B minor, Mission deliberately practised and recorded in A minor):
Upload Analysis said "Concert Key of this recording: B minor" and the report said "Concert Key: B minor"; after
the current Mission key moved on, the analysis itself ran in the *live* key (scale adherence "in Dm", ear
training "Dm natural minor", harmonic frame "/ Dm"). Three keys must stay apart:

* original / saved song key (catalog metadata)          -> "Original/Saved song key: B minor"
* Mission Practice / Concert key (sealed with the take) -> what the take is analysed and described in
* written key (instrument projection of the concert key)
"""

from __future__ import annotations

import json
import unittest
from unittest import mock

import recording_analysis_context as rac
import mission_pending_upload_persistence as mpp
from mission_key_authority import (
    capture_key_authority,
    derive_key_authority_from_envelope,
    seed_recording_concert_key,
    sealed_key_authority,
)
from mission_pending_upload_analysis import PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY, build_pending_upload_envelope
from mission_practice_context import seal_recording_context, set_mission_tempo
from songs.key_state import ActiveMusicalKeyContext
from tests.test_mc4_span_recording import GOLDEN_SESSION, _World, _block, record_span_take

ASSET = {"recording_id": "t1", "fingerprint": "fpx", "storage_ref": "music-media/u/ws/t1.wav", "local_path": None}
SONG_CTX = {
    "source_type": "catalog", "source_id": "al", "title": "Autumn Leaves", "artist": "Eric Clapton", "key": "Bm", "bpm": 82,
    "meter": "4/4", "sections": {"Verse 1": ["Bm", "Em7", "A7", "Dmaj7"]}, "chord_progression": ["Bm", "Em7", "A7", "Dmaj7"],
    "section_chords": {"Verse 1": ["Bm", "Em7", "A7", "Dmaj7"]}, "resolved": True, "authority": "catalog",
    "has_song_harmony": True, "has_song_form": True,
}


def _active_keys(practice="Am", original="Bm", chart=None, written=None, instrument="Flute"):
    return ActiveMusicalKeyContext(original_key=original, practice_concert_key=practice, written_key=written or practice,
                                   shape_key="", chart_key=chart or practice, chart_key_mode="concert", instrument=instrument)


class _Catalog:
    """The catalog says Autumn Leaves is in B minor; the live Mission key is whatever the test sets."""

    def __init__(self, live_practice="Am", instrument="Flute"):
        self._p = [
            mock.patch.object(rac, "selected_song_analysis_context", lambda *a, **k: dict(SONG_CTX)),
            mock.patch("songs.key_state.resolve_active_musical_key",
                       lambda session, **k: _active_keys(live_practice, instrument=instrument)),
        ]

    def __enter__(self):
        for p in self._p:
            p.start()
        return self

    def __exit__(self, *a):
        for p in self._p:
            p.stop()


def _recording_session(instrument="Flute", **extra):
    s = dict(GOLDEN_SESSION, analysis_recording_type="Mission Recording", instrument=instrument,
             analysis_mission_parameters={"chord": "Am", "mission_type": "Target tone drill"},
             analysis_song_source_type="catalog", analysis_song_source_name="Autumn Leaves", **extra)
    set_mission_tempo(s, 134)
    seal_recording_context(s, association="live_record_take")
    return s


def _span_session(instrument="Flute"):
    block = _block(["Bm7b5", "E7", "Am"], key="Am", bpm=134, instrument=instrument, level="Intermediate")
    s = dict(GOLDEN_SESSION, analysis_recording_type="Mission Recording", instrument=instrument,
             analysis_song_source_type="catalog", analysis_song_source_name="Autumn Leaves")
    with _World(key="Am"):
        take = record_span_take(s, audio_bytes=b"take-x", source="live", span=block)
        set_mission_tempo(s, 134)
        seal_recording_context(s, association="live_record_take")
    return s, take


class _Loaded:
    def __enter__(self):
        self._orig = mpp._load_asset_bytes
        mpp._load_asset_bytes = lambda asset, st=None: (b"RIFF" + b"\0" * 64, "")
        return self

    def __exit__(self, *a):
        mpp._load_asset_bytes = self._orig


def _fresh(env, live_key_label="D minor", instrument="Flute"):
    """Another session (refresh / other device) whose *current* Mission and Upload key are different."""
    s = dict(GOLDEN_SESSION, analysis_recording_type="Mission Recording", instrument=instrument,
             analysis_song_source_type="catalog", analysis_song_source_name="Autumn Leaves", display_key="Dm", concert_key="Dm")
    s[rac.ANALYSIS_RECORDING_CONCERT_KEY_KEY] = live_key_label
    s[PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY] = json.loads(json.dumps(env))
    return s


def _snapshot(session):
    snap = rac.build_analysis_context_snapshot(session, association="t")
    return rac.attach_selected_song_harmony_to_snapshot(session, snap)


class TestKeyAuthorityCapture(unittest.TestCase):
    def test_single_chord_take_captures_original_and_concert_key_separately(self) -> None:
        with _Catalog("Am"):
            ka = capture_key_authority(_recording_session())
        self.assertEqual((ka["original_key"], ka["concert_key"], ka["source"]), ("Bm", "Am", "mission"))

    def test_span_take_uses_its_sealed_span_key(self) -> None:
        s, _take = _span_session()
        with _Catalog("Dm"), _World(key="Am"):                                         # the live Mission key is something else
            ka = capture_key_authority(s)
        self.assertEqual((ka["concert_key"], ka["source"]), ("Am", "span"))

    def test_the_envelope_carries_it_and_it_survives_json(self) -> None:
        with _Catalog("Am"):
            env = build_pending_upload_envelope(_recording_session(), dry_asset=ASSET)
        ka = json.loads(json.dumps(env))["sealed_analysis_context"]["key_authority"]
        self.assertEqual((ka["original_key"], ka["concert_key"]), ("Bm", "Am"))
        self.assertEqual(env["schema_version"], 1)                                      # additive

    def test_older_envelopes_fall_back_to_what_they_already_carried(self) -> None:
        s, take = _span_session()
        with _World(key="Am"):
            env = build_pending_upload_envelope(s, dry_asset=dict(ASSET, fingerprint=take["audio_fp"]))
        env.pop("sealed_analysis_context")
        self.assertEqual(derive_key_authority_from_envelope(env)["concert_key"], "Am")   # sealed span
        env.pop("span_take")
        env["recording_seal"] = {"tempo_bpm": 134, "display_key": "Am"}
        self.assertEqual(derive_key_authority_from_envelope(env)["concert_key"], "Am")   # sealed Mission context
        self.assertEqual(derive_key_authority_from_envelope({}), {})


class TestFreshSessionKeepsTheSealedKey(unittest.TestCase):
    def _restored(self, instrument="Flute", live="D minor", span=False):
        if span:
            s, take = _span_session(instrument)
            with _Catalog("Am", instrument), _World(key="Am"):
                env = build_pending_upload_envelope(s, dry_asset=dict(ASSET, fingerprint=take["audio_fp"]))
        else:
            with _Catalog("Am", instrument):
                env = build_pending_upload_envelope(_recording_session(instrument), dry_asset=ASSET)
        fresh = _fresh(env, live, instrument)
        with _Catalog("Dm", instrument), _World(key="Dm"), _Loaded():                   # the Mission's key has since changed
            mpp.apply_pending_upload_envelope_to_session(fresh, force=True)
        return fresh

    def test_the_upload_concert_key_control_is_the_missions_key_not_the_catalogs(self) -> None:
        for span in (False, True):
            fresh = self._restored(span=span)
            self.assertEqual(fresh[rac.ANALYSIS_RECORDING_CONCERT_KEY_KEY], "A minor", f"span={span}")
            self.assertEqual(sealed_key_authority(fresh)["concert_key"], "Am")

    def test_the_analysis_snapshot_is_in_the_sealed_key_whatever_the_ui_says_now(self) -> None:
        for span in (False, True):
            fresh = self._restored(span=span)
            fresh[rac.ANALYSIS_RECORDING_CONCERT_KEY_KEY] = "D minor"                    # even a stale widget value cannot win
            with _Catalog("Dm"), _World(key="Dm"):
                snap = _snapshot(fresh)
            self.assertEqual((snap["recording_concert_key"], snap["recording_concert_key_label"], snap["display_key"]),
                             ("Am", "A minor", "Am"), f"span={span}")
            self.assertEqual(snap["song_canonical_key"], "Bm")                           # the original stays metadata
            mka = snap["mission_key_authority"]
            self.assertEqual((mka["original_key"], mka["concert_key"], mka["concert_key_label"], mka["sealed"]),
                             ("Bm", "Am", "A minor", True))

    def test_the_harmony_the_analyzer_gets_is_the_catalog_harmony_moved_to_a_minor(self) -> None:
        fresh = self._restored()
        with _Catalog("Dm"):
            snap = _snapshot(fresh)
        self.assertEqual(snap["target_chords"], ["Am", "Dm7", "G7", "Cmaj7"])            # Bm Em7 A7 Dmaj7 -> down a tone
        self.assertEqual(snap["sections"], {"Verse 1": ["Am", "Dm7", "G7", "Cmaj7"]})

    def test_the_analysis_context_and_coaching_text_use_a_minor(self) -> None:
        from recording_analysis import AudioFeatures, _pitch_analysis, build_practice_plan
        from tests.test_mc4_flute_pitch_evidence import _features

        fresh = self._restored()
        with _Catalog("Dm"):
            snap = _snapshot(fresh)
        ctx = rac.apply_snapshot_to_analysis_ctx({"instrument": "Flute"}, snap)
        self.assertEqual(ctx["display_key"], "Am")
        f = _features(tempo=134.0)
        plan = " ".join(build_practice_plan({"timing": 80, "pitch": 80, "technique": 80, "groove": 80, "musicality": 80,
                                              "confidence": 80, "tone": 80}, dict(ctx, mission_tempo_bpm=134), f))
        self.assertIn("Am natural minor scale", plan)
        self.assertNotIn("Bm natural minor", plan)
        self.assertNotIn("Dm natural minor", plan)
        ear = " ".join(_pitch_analysis(f, "Flute", ctx)["tips"])
        self.assertIn("Am natural minor degrees", ear)

    def test_changing_the_current_mission_key_after_recording_changes_nothing(self) -> None:
        fresh = self._restored()
        for token, label in (("Dm", "D minor"), ("Em", "E minor"), ("Bm", "B minor")):
            fresh["display_key"] = fresh["concert_key"] = token
            fresh[rac.ANALYSIS_RECORDING_CONCERT_KEY_KEY] = label
            with _Catalog(token):
                self.assertEqual(_snapshot(fresh)["recording_concert_key"], "Am", token)

    def test_catalog_b_minor_and_mission_b_minor_is_unchanged(self) -> None:
        with _Catalog("Bm"):
            s = _recording_session()
            ka = capture_key_authority(s)
            env = build_pending_upload_envelope(s, dry_asset=ASSET)
        self.assertEqual((ka["original_key"], ka["concert_key"]), ("Bm", "Bm"))
        fresh = _fresh(env, "D minor")
        with _Catalog("Dm"), _Loaded():
            mpp.apply_pending_upload_envelope_to_session(fresh, force=True)
            snap = _snapshot(fresh)
        self.assertEqual((snap["recording_concert_key"], snap["target_chords"]), ("Bm", ["Bm", "Em7", "A7", "Dmaj7"]))

    def test_restoring_an_envelope_without_key_information_does_not_crash(self) -> None:
        with _Catalog("Am"):
            env = build_pending_upload_envelope(_recording_session(), dry_asset=ASSET)
        env["sealed_analysis_context"].pop("key_authority")
        env["recording_seal"].pop("display_key", None)
        fresh = _fresh(env, "D minor")
        with _Catalog("Dm"), _Loaded():
            mpp.apply_pending_upload_envelope_to_session(fresh, force=True)
            snap = _snapshot(fresh)
        self.assertEqual(snap["recording_concert_key_label"], "D minor")                 # no sealed key -> the live control, as before


class TestTransposingInstrument(unittest.TestCase):
    def test_concert_key_follows_the_mission_written_key_follows_the_instrument(self) -> None:
        with _Catalog("Am", "Tenor Saxophone"):
            env = build_pending_upload_envelope(_recording_session("Tenor Saxophone"), dry_asset=ASSET)
        fresh = _fresh(env, "D minor", "Tenor Saxophone")
        with _Catalog("Dm", "Tenor Saxophone"), _Loaded():
            mpp.apply_pending_upload_envelope_to_session(fresh, force=True)
            snap = _snapshot(fresh)
        self.assertEqual(snap["song_canonical_key"], "Bm")                               # source metadata
        self.assertEqual(snap["recording_concert_key_label"], "A minor")                 # the Mission's sounding key
        self.assertEqual(snap["instrument_written_keys"], {"Tenor Saxophone": "B minor"})  # a Bb instrument reads a tone higher
        self.assertEqual(snap["written_key"], "B minor")
        lines = rac.format_recording_key_authority_lines({rac.ANALYSIS_CONTEXT_SNAPSHOT_KEY: snap})
        self.assertIn("Concert Key: A minor (Mission Practice Key)", lines)
        self.assertTrue(any("Written Key" in l and "B minor" in l for l in lines), lines)
        self.assertEqual([l for l in lines if "Concert Key" in l and "B minor" in l], [])  # B minor is never the concert key

    def test_voice_has_no_written_key_difference(self) -> None:
        with _Catalog("Am", "Voice"):
            env = build_pending_upload_envelope(_recording_session("Voice"), dry_asset=ASSET)
        fresh = _fresh(env, "D minor", "Voice")
        with _Catalog("Dm", "Voice"), _Loaded():
            mpp.apply_pending_upload_envelope_to_session(fresh, force=True)
            snap = _snapshot(fresh)
        self.assertEqual((snap["recording_concert_key_label"], snap["instrument_written_keys"]), ("A minor", {"Voice": "A minor"}))


class TestStepThreeWording(unittest.TestCase):
    MKA = {"original_key": "Bm", "concert_key": "Am", "concert_key_label": "A minor", "sealed": True}

    def test_the_catalog_key_is_labelled_original_and_the_take_key_is_the_mission_key(self) -> None:
        lines = rac.format_selected_song_authority_lines(SONG_CTX, mission_key=self.MKA)
        self.assertIn("Original/Saved song key: B minor", lines)
        self.assertTrue(any(l.startswith("Saved harmony (original key): ") and "Bm → Em7 → A7" in l for l in lines), lines)
        self.assertFalse(any(l.startswith("Harmony:") or l.startswith("Saved song key") for l in lines), lines)
        plain = rac.format_selected_song_authority_lines(SONG_CTX)                       # not a Mission take: unchanged
        self.assertIn("Saved song key: B minor", plain)
        self.assertTrue(any(l.startswith("Harmony: ") for l in plain))
        same = rac.format_selected_song_authority_lines(SONG_CTX, mission_key=dict(self.MKA, concert_key="Bm", concert_key_label="B minor"))
        self.assertTrue(any(l.startswith("Harmony: ") for l in same))                    # nothing to disambiguate

    def test_concert_key_line_names_the_mission_practice_key(self) -> None:
        lines = rac.format_recording_key_authority_lines({"recording_concert_key": "Am", "recording_concert_key_label": "A minor",
                                                          "mission_key_authority": self.MKA})
        self.assertEqual(lines[0], "Concert Key: A minor (Mission Practice Key)")
        plain = rac.format_recording_key_authority_lines({"recording_concert_key": "Bm", "recording_concert_key_label": "B minor"})
        self.assertEqual(plain[0], "Concert Key: B minor")                               # non-Mission wording unchanged

    def test_coach_summary_names_both_keys_without_ambiguity(self) -> None:
        import io
        import wave

        import numpy as np

        import recording_analysis as ra

        sr = 22050
        y = np.zeros(int(6 * sr), np.float32)
        for k in range(int(6 * 134 / 60)):
            i = int(k * 60 / 134 * sr)
            y[i:i + 400] += np.hanning(400).astype(np.float32) * 0.8
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((y * 32767).astype(np.int16).tobytes())
        ctx = {"instrument": "Flute", "song": "Autumn Leaves", "display_key": "Am", "reference_bpm": 82, "practice_bpm": 82,
               "mission_tempo_bpm": 134, "time_signature": "4/4", "recording_type": "Mission Recording", "level": "Intermediate",
               "mission_key_authority": self.MKA,
               "selected_song_analysis_context": {"title": "Autumn Leaves", "key": "Bm", "meter": "4/4", "bpm": 82}}
        result = ra.analyze_recording(buf.getvalue(), "take.wav", ctx)
        summary = result["coach_summary"]
        self.assertIn("Autumn Leaves — Mission Practice/Concert Key A minor (original song key B minor), 4/4", summary)
        self.assertNotIn("Autumn Leaves — Bm", summary)
        same = dict(ctx, mission_key_authority=dict(self.MKA, concert_key="Bm", concert_key_label="B minor", original_key="Bm"))
        self.assertIn("Mission Practice/Concert Key B minor, 4/4", ra.analyze_recording(buf.getvalue(), "take.wav", same)["coach_summary"])

    def test_the_dashboard_authority_card_uses_the_mission_labels(self) -> None:
        from recording_analysis_ui import render_analysis_dashboard

        snap = {"mission_key_authority": self.MKA, "recording_concert_key": "Am", "recording_concert_key_label": "A minor",
                "selected_song_analysis_context": dict(SONG_CTX)}
        result = {"ok": True, "coach_summary": "x", "biggest_issue": "tone", "next_focus": "Timing", "most_improved": "tone",
                  "instrument": "Flute", "duration": 5.0, "tempo": 134.0, "scores": {"timing": 80, "pitch": 80, "technique": 80,
                  "groove": 80, "musicality": 80, "confidence": 80, "tone": 80}, "categories": {}, "practice_plan": [],
                  "selected_song_analysis_context": dict(SONG_CTX), "analysis_context_snapshot": snap}
        html = render_analysis_dashboard(result)
        self.assertIn("Original/Saved song key: B minor", html)
        self.assertIn("Concert Key: A minor (Mission Practice Key)", html)
        self.assertNotIn("Concert Key: B minor", html)


class TestUploadPageDescribesTheSavedTake(unittest.TestCase):
    """The Upload page must not show the *current* Mission's chord / tempo for a saved take."""

    def _restored_single(self):
        with _Catalog("Am"):
            recorded = _recording_session()
            env = build_pending_upload_envelope(recorded, dry_asset=ASSET)
        sealed_chord = recorded["improv_mission_recording_seal"]["chord"]["symbol"]
        fresh = _fresh(env, "D minor")
        with _Catalog("Dm"), _Loaded():
            mpp.apply_pending_upload_envelope_to_session(fresh, force=True)
        set_mission_tempo(fresh, 100)                                                    # the Mission has moved on
        fresh["ii_selected_chord"] = "Dm"
        return fresh, sealed_chord

    def test_the_locked_mission_parameters_are_the_sealed_ones(self) -> None:
        fresh, sealed_chord = self._restored_single()
        with _Catalog("Dm"):
            rac.apply_mission_recording_defaults(fresh)                                  # Upload Analysis re-prepares itself
        params = fresh["analysis_mission_parameters"]
        self.assertEqual((params["tempo_bpm"], params["chord"]), (134, sealed_chord))
        self.assertNotEqual(params["chord"], "Dm")

    def test_the_compact_mission_line_names_the_sealed_chord(self) -> None:
        from mission_analysis_ui import render_mission_upload_compact_context

        fresh, sealed_chord = self._restored_single()

        class St:
            def __init__(self):
                self.out = []

            def markdown(self, text, **k):
                self.out.append(text)

        st = St()
        render_mission_upload_compact_context(st, fresh)
        self.assertEqual(len(st.out), 1)
        self.assertIn(f"**Chord:** {sealed_chord}", st.out[0])
        self.assertNotIn("Dm", st.out[0] if sealed_chord != "Dm" else "")


class TestChartBadge(unittest.TestCase):
    def test_upload_page_badge_shows_the_saved_takes_key_only_there(self) -> None:
        from app_ui import chart_key_mode_badge_html

        with _Catalog("Am", "Clarinet"):
            env = build_pending_upload_envelope(_recording_session("Clarinet"), dry_asset=ASSET)
        fresh = _fresh(env, "D minor", "Clarinet")
        with _Catalog("Dm", "Clarinet"), _Loaded():
            mpp.apply_pending_upload_envelope_to_session(fresh, force=True)
        fresh["display_key"] = "Dm"
        fresh["studio_page"] = "analysis"
        self.assertIn("Charts in Am", chart_key_mode_badge_html(fresh))
        fresh["studio_page"] = "creative"                                                 # everywhere else: the live Practice Key
        self.assertIn("Charts in Dm", chart_key_mode_badge_html(fresh))


class TestSeeding(unittest.TestCase):
    def test_seed_sets_the_upload_control_from_the_mission_key(self) -> None:
        s = {rac.ANALYSIS_RECORDING_CONCERT_KEY_KEY: "B minor"}
        self.assertEqual(seed_recording_concert_key(s, {"concert_key": "Am"}), "Am")
        self.assertEqual(s[rac.ANALYSIS_RECORDING_CONCERT_KEY_KEY], "A minor")
        s2 = {rac.ANALYSIS_RECORDING_CONCERT_KEY_KEY: "B minor"}
        self.assertEqual(seed_recording_concert_key(s2, {}), "")                         # nothing known: untouched
        self.assertEqual(s2[rac.ANALYSIS_RECORDING_CONCERT_KEY_KEY], "B minor")


if __name__ == "__main__":
    unittest.main()
