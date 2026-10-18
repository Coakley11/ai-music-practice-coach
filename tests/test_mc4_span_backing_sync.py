"""MC4 — the "Backing is not playing <span>" gate reads the backing that is actually sounding.

Reproduced bug: Play the recorder backing on a 3-chord span, switch to the 2-chord span and
play it through Mission Backing Jam, return → Run AI coach analysis said "Backing is not
playing C♯m7♭5 → F♯7" although that span was the one audibly playing. Cause: the recorder's
sounding-span identity outlived its WAV (scope/span invalidation removed the WAV, not the
identity), Mission Backing was not consulted, and the identity was a string (span id + chord
spelling) rather than the harmony.
"""

from __future__ import annotations

import io
import unittest
import wave
from contextlib import ExitStack
from types import SimpleNamespace
from unittest import mock

import mission_span_recording_context as src
from mission_exact_chord_backing import generate_exact_chord_backing_wav, invalidate_exact_chord_backing_cache
from mission_practice_context import (
    MISSION_BACKING_SOUNDING_CHORD_KEY,
    MISSION_BACKING_SOUNDING_SPAN_KEY,
    ensure_mission_practice_context,
    mission_capture_allowed,
    ui_backing_chord_mismatch,
)
from tests.test_mc4_span_recording import GOLDEN_SESSION, SCOPE_KEY, _stage

IIVI = ["Gm7", "C7", "Fmaj7"]
TWO = ["Gm7", "C7"]


def _tiny_wav(*_a, **_k) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * 2205)
    return out.getvalue()


class _Env:
    """Live song / Practice Key resolvers + fast backing render + optional Mission Backing owner."""

    def __init__(self, *, key="F", jam_source=None):
        self.key, self.jam_source = key, jam_source

    def __enter__(self):
        self._s = ExitStack()
        self._s.enter_context(mock.patch.object(src, "_song_session", lambda s: "song-A"))
        self._s.enter_context(mock.patch.object(src, "_live_practice_key", lambda s: self.key))
        self._s.enter_context(mock.patch.object(src, "_live_chart_key", lambda s: self.key))
        self._s.enter_context(mock.patch("mission_span_backing._song_session", lambda s: "song-A"))
        self._s.enter_context(mock.patch("backing_audio.generate_backing_track", _tiny_wav))
        src_ns = SimpleNamespace(source=self.jam_source) if self.jam_source else None
        self._s.enter_context(mock.patch("backing_context.get_backing_context", lambda s: src_ns))
        return self

    def __exit__(self, *exc):
        self._s.close()


def _session(chords=IIVI, **kw):
    s = dict(GOLDEN_SESSION)
    _stage(s, chords, **kw)
    ensure_mission_practice_context(s, force=True)
    return s


def _switch(session, chords, **kw):
    """Pick another span / scope on Missions (what render_span_missions does on rerun)."""
    _stage(session, chords, **kw)
    ensure_mission_practice_context(session)


def _play(session):
    wav, _label = generate_exact_chord_backing_wav(session)
    assert wav
    return wav


def _stop(session):
    """The recorder's ■ Stop handler (span scope)."""
    session.pop("mission_exact_backing_wav", None)
    session["mission_exact_backing_play_nonce"] = 0
    session.pop(MISSION_BACKING_SOUNDING_SPAN_KEY, None)


def _stage_jam(session, chords, key="F"):
    session["_mission_span_backing"] = {
        "active": True, "song_session": "song-A", "practice_key": key,
        "timeline": [{"chord": c, "bars": 1} for c in chords],
    }


class TestCanonicalIdentity(unittest.TestCase):
    def test_enharmonic_spellings_are_one_chord(self) -> None:
        cc = src.canonical_chord
        self.assertEqual(cc("C#m7b5"), cc("Dbm7b5"))
        self.assertEqual(cc("F#7"), cc("Gb7"))
        self.assertEqual(cc("Bbmaj7"), cc("A#maj7"))
        self.assertNotEqual(cc("C7"), cc("Cmaj7"))
        self.assertNotEqual(cc("Am7"), cc("C6"))  # same notes, different root

    def test_harmony_ignores_spelling_but_not_bars(self) -> None:
        self.assertEqual(src.harmonic_timeline([("C#m7b5", 1), ("F#7", 1)]),
                         src.harmonic_timeline([("Dbm7b5", 1), ("Gb7", 1)]))
        self.assertNotEqual(src.harmonic_timeline([("Gm7", 1), ("C7", 1)]),
                            src.harmonic_timeline([("Gm7", 2), ("C7", 1)]))


class TestSpanBackingSync(unittest.TestCase):
    def test_three_chord_play_is_in_sync(self) -> None:
        with _Env():
            s = _session(IIVI)
            _play(s)
            self.assertEqual(ui_backing_chord_mismatch(s), (False, ""))
            self.assertEqual(mission_capture_allowed(s, require_mission_workflow=True, capture_path="analysis")[0], True)

    def test_two_chord_play_is_in_sync(self) -> None:
        with _Env():
            s = _session(TWO)
            _play(s)
            self.assertEqual(ui_backing_chord_mismatch(s), (False, ""))

    def test_reproduced_bug_3chord_play_then_2chord_mission_backing(self) -> None:
        with _Env(jam_source="mission"):
            s = _session(IIVI)
            _play(s)
            _switch(s, TWO)  # scope/span change invalidates the recorder backing
            self.assertNotIn("mission_exact_backing_wav", s)
            self.assertNotIn(MISSION_BACKING_SOUNDING_SPAN_KEY, s)  # the claim went with its WAV
            _stage_jam(s, TWO)  # Mission Backing Jam audibly plays the 2-chord span
            self.assertEqual(ui_backing_chord_mismatch(s), (False, ""))
            ok, msg = mission_capture_allowed(s, require_mission_workflow=True, capture_path="live")
            self.assertTrue(ok, msg)

    def test_mission_backing_playing_a_different_span_still_warns(self) -> None:
        with _Env(jam_source="mission"):
            s = _session(TWO)
            _stage_jam(s, IIVI)
            bad, msg = ui_backing_chord_mismatch(s)
            self.assertTrue(bad)
            self.assertIn("The generated backing is not", msg)

    def test_mission_backing_not_the_owner_is_ignored(self) -> None:
        with _Env(jam_source="regular_song"):
            s = _session(TWO)
            _stage_jam(s, IIVI)
            self.assertEqual(ui_backing_chord_mismatch(s), (False, ""))

    def test_recorder_playing_a_different_span_still_warns(self) -> None:
        with _Env():
            s = _session(IIVI)
            _play(s)
            claim = dict(s[MISSION_BACKING_SOUNDING_SPAN_KEY])
            _switch(s, TWO)
            # Force the stale situation the old code allowed: a claim + WAV for the 3-chord span.
            s[MISSION_BACKING_SOUNDING_SPAN_KEY] = claim
            s["mission_exact_backing_wav"] = b"wav"
            bad, msg = ui_backing_chord_mismatch(s)
            self.assertTrue(bad)
            self.assertIn("The generated backing is not **Gm7 → C7", msg)

    def test_practice_key_change_then_play(self) -> None:
        with _Env(key="F") as env:
            s = _session(IIVI)
            _play(s)
            env.key = "G"
            ensure_mission_practice_context(s)
            self.assertNotIn(MISSION_BACKING_SOUNDING_SPAN_KEY, s)  # old-key backing removed
            self.assertEqual(ui_backing_chord_mismatch(s), (False, ""))
            _play(s)
            self.assertEqual(ui_backing_chord_mismatch(s), (False, ""))
            self.assertEqual(s[MISSION_BACKING_SOUNDING_SPAN_KEY]["harmony"],
                             src.harmonic_timeline([("Am7", 1), ("D7", 1), ("Gmaj7", 1)]))

    def test_mission_backing_return_after_key_change_compares_in_concert(self) -> None:
        with _Env(key="G", jam_source="mission"):
            s = _session(["Am7", "D7", "Gmaj7"], key="G")
            _stage_jam(s, IIVI, key="F")  # staged at F, re-keyed to the live G by Mission Backing
            self.assertEqual(ui_backing_chord_mismatch(s), (False, ""))

    def test_stop_and_restart(self) -> None:
        with _Env():
            s = _session(IIVI)
            _play(s)
            _stop(s)
            self.assertEqual(ui_backing_chord_mismatch(s), (False, ""))
            _play(s)
            self.assertEqual(ui_backing_chord_mismatch(s), (False, ""))

    def test_invalidation_clears_claim(self) -> None:
        with _Env():
            s = _session(IIVI)
            _play(s)
            invalidate_exact_chord_backing_cache(s)
            self.assertNotIn(MISSION_BACKING_SOUNDING_SPAN_KEY, s)

    def test_switch_span_and_play_new_backing(self) -> None:
        with _Env():
            s = _session(TWO)
            _play(s)
            _switch(s, IIVI)
            self.assertEqual(ui_backing_chord_mismatch(s), (False, ""))
            _play(s)
            self.assertEqual(ui_backing_chord_mismatch(s), (False, ""))
            self.assertEqual(len(s[MISSION_BACKING_SOUNDING_SPAN_KEY]["harmony"]), 3)

    def test_same_chords_at_another_place_in_the_song_are_in_sync(self) -> None:
        with _Env():
            s = _session(TWO)
            _play(s)
            claim, wav = dict(s[MISSION_BACKING_SOUNDING_SPAN_KEY]), s["mission_exact_backing_wav"]
            s["_mission_span_recording_context"]["span_id"] = "other-occurrence"
            ensure_mission_practice_context(s, force=True)
            s[MISSION_BACKING_SOUNDING_SPAN_KEY], s["mission_exact_backing_wav"] = claim, wav
            self.assertEqual(ui_backing_chord_mismatch(s), (False, ""))

    def test_enharmonic_backing_is_in_sync(self) -> None:
        with _Env(key="Bm"):
            s = _session(["C#m7b5", "F#7"], key="Bm")
            _play(s)
            claim = s[MISSION_BACKING_SOUNDING_SPAN_KEY]
            claim["harmony"] = src.harmonic_timeline([("Dbm7b5", 1), ("Gb7", 1)])
            self.assertEqual(ui_backing_chord_mismatch(s), (False, ""))

    def test_same_harmony_other_tempo_names_the_tempo(self) -> None:
        with _Env():
            s = _session(TWO)
            _play(s)
            live_bpm = ensure_mission_practice_context(s).span["bpm"]
            s[MISSION_BACKING_SOUNDING_SPAN_KEY]["bpm"] = live_bpm + 8
            bad, msg = ui_backing_chord_mismatch(s)
            self.assertTrue(bad)
            self.assertIn(f"at {live_bpm + 8} BPM", msg)
            self.assertIn(f"set to {live_bpm} BPM", msg)

    def test_single_chord_gate_unchanged(self) -> None:
        s = {
            "ii_selected_chord": "Am7",
            "ii_selected_chord_index": 0,
            "improv_mission_chord_options": ["Am7"],
            MISSION_BACKING_SOUNDING_CHORD_KEY: "Dm7",
        }
        bad, msg = ui_backing_chord_mismatch(s)
        self.assertTrue(bad)
        self.assertEqual(msg, "UI chord **Am7** does not match the generated backing **Dm7**. Generate Backing to sync.")
        s[SCOPE_KEY] = "single"
        s[MISSION_BACKING_SOUNDING_CHORD_KEY] = "Am7"
        self.assertEqual(ui_backing_chord_mismatch(s), (False, ""))


if __name__ == "__main__":
    unittest.main()
