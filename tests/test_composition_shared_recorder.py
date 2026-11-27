"""The shared recorder route exists, is off, and cannot disturb an accepted melody.

Unit tests over the wiring only. The component is injected as a stub, so these prove the
take lifecycle and the boundaries - not that a browser records anything. Real microphone
and playback acceptance is still outstanding.
"""

from __future__ import annotations

import base64
import os
import unittest

from composition_recording_timing import SOURCE_BASIC_RECORDER, SOURCE_SHARED_CLOCK
from composition_shared_recorder import (
    FLAG_ENV,
    FLAG_SESSION_KEY,
    accompaniment_fingerprint,
    backing_key,
    prepare_accompaniment,
    build_recorder_args,
    discard_recording,
    ingest_take,
    recorder_load_nonce,
    recording_scope,
    recording_status,
    render_shared_recorder,
    shared_recorder_enabled,
    take_audio,
    take_source,
)

SR = 48000
WAV = b"RIFF....stand-in-for-audio"


def _timing(music_start_frame: int = SR * 2) -> dict:
    return {
        "source": SOURCE_SHARED_CLOCK,
        "sample_rate": SR,
        "capture_first_frame": 0,
        "music_start_frame": music_start_frame,
        "music_offset_sec": music_start_frame / SR,
    }


class _Component:
    """Stands in for RECORDER_COMPONENT: records its args, returns what it is told to."""

    def __init__(self, value=None) -> None:
        self.value = value
        self.calls: list[dict] = []

    def __call__(self, *, key=None, default=None, **args):
        self.calls.append({"key": key, **args})
        return self.value


class TestTheFlagDefaultsOff(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.pop(FLAG_ENV, None)

    def tearDown(self) -> None:
        os.environ.pop(FLAG_ENV, None)
        if self._env is not None:
            os.environ[FLAG_ENV] = self._env

    def test_off_with_no_session_and_no_env(self) -> None:
        self.assertFalse(shared_recorder_enabled())
        self.assertFalse(shared_recorder_enabled({}))

    def test_a_session_can_turn_it_on(self) -> None:
        self.assertTrue(shared_recorder_enabled({FLAG_SESSION_KEY: True}))

    def test_a_session_off_wins_over_the_environment(self) -> None:
        os.environ[FLAG_ENV] = "1"
        self.assertFalse(shared_recorder_enabled({FLAG_SESSION_KEY: False}))

    def test_the_environment_can_turn_it_on_for_a_test_run(self) -> None:
        os.environ[FLAG_ENV] = "yes"
        self.assertTrue(shared_recorder_enabled({}))


class TestScopeIsSongAndSection(unittest.TestCase):
    def test_two_sections_of_one_song_differ(self) -> None:
        self.assertNotEqual(recording_scope("doc1", "verse"), recording_scope("doc1", "chorus"))

    def test_the_same_section_name_in_two_songs_differs(self) -> None:
        """Section ids are unique per document, not globally."""
        self.assertNotEqual(recording_scope("doc1", "verse"), recording_scope("doc2", "verse"))

    def test_an_unsaved_document_still_gets_a_scope(self) -> None:
        self.assertTrue(recording_scope("", "verse"))
        self.assertNotEqual(recording_scope("", "verse"), recording_scope("", "chorus"))

    def test_takes_do_not_cross_sections(self) -> None:
        ss: dict = {}
        a = recording_scope("doc1", "verse")
        b = recording_scope("doc1", "chorus")
        ingest_take(ss, a, {"take_id": "t1", "wav": WAV, "timing": _timing()})
        self.assertEqual(take_audio(ss, a), WAV)
        self.assertEqual(take_audio(ss, b), b"")


class TestARerunDoesNotDisturbARecording(unittest.TestCase):
    """Requirement 9: an ordinary rerun must not restart or discard the recording."""

    def test_the_load_nonce_is_stable_across_reruns(self) -> None:
        ss: dict = {}
        scope = recording_scope("doc1", "verse")
        first = recorder_load_nonce(ss, scope)
        for _ in range(5):
            self.assertEqual(recorder_load_nonce(ss, scope), first)

    def test_rendering_repeatedly_keeps_the_same_nonce(self) -> None:
        ss: dict = {}
        scope = recording_scope("doc1", "verse")
        comp = _Component(None)
        for _ in range(3):
            render_shared_recorder(None, ss, scope=scope, component=comp, bpm=120)
        self.assertEqual({c["load_nonce"] for c in comp.calls}, {1})

    def test_a_rerun_does_not_re_ingest_the_same_take(self) -> None:
        ss: dict = {}
        scope = recording_scope("doc1", "verse")
        comp = _Component(
            {
                "take_id": "t1",
                "wav_b64": base64.b64encode(WAV).decode("ascii"),
                "timing": _timing(),
            }
        )
        self.assertIsNotNone(render_shared_recorder(None, ss, scope=scope, component=comp))
        for _ in range(3):
            self.assertIsNone(render_shared_recorder(None, ss, scope=scope, component=comp))
        self.assertEqual(take_audio(ss, scope), WAV)

    def test_a_rerun_does_not_drop_the_audio(self) -> None:
        ss: dict = {}
        scope = recording_scope("doc1", "verse")
        ingest_take(ss, scope, {"take_id": "t1", "wav": WAV, "timing": _timing()})
        comp = _Component(None)
        for _ in range(3):
            render_shared_recorder(None, ss, scope=scope, component=comp)
        self.assertEqual(take_audio(ss, scope), WAV)

    def test_only_a_discard_changes_the_nonce(self) -> None:
        ss: dict = {}
        scope = recording_scope("doc1", "verse")
        before = recorder_load_nonce(ss, scope)
        discard_recording(ss, scope)
        self.assertGreater(recorder_load_nonce(ss, scope), before)
        self.assertEqual(take_audio(ss, scope), b"")


class TestARecordingIsNotADecision(unittest.TestCase):
    """Requirement 10: a new take must not activate or replace an accepted melody."""

    def test_ingesting_a_take_leaves_an_accepted_melody_alone(self) -> None:
        accepted = [{"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 0.0}]
        ss: dict = {
            "composer_melody_accepted_verse": list(accepted),
            "composer_melody_active_source_verse": "ai_suggestion",
        }
        scope = recording_scope("doc1", "verse")
        ingest_take(ss, scope, {"take_id": "t1", "wav": WAV, "timing": _timing()})
        self.assertEqual(ss["composer_melody_accepted_verse"], accepted)
        self.assertEqual(ss["composer_melody_active_source_verse"], "ai_suggestion")

    def test_ingesting_a_take_writes_no_proposal_and_no_events(self) -> None:
        ss: dict = {}
        scope = recording_scope("doc1", "verse")
        ingest_take(ss, scope, {"take_id": "t1", "wav": WAV, "timing": _timing()})
        for key in ss:
            self.assertNotIn("proposal", str(key))
            self.assertNotIn("melody", str(key))

    def test_only_composition_owned_keys_are_written(self) -> None:
        ss: dict = {}
        scope = recording_scope("doc1", "verse")
        ingest_take(ss, scope, {"take_id": "t1", "wav": WAV, "timing": _timing()})
        for key in ss:
            self.assertTrue(str(key).startswith("_composer_"), f"{key!r} is not Composition's")
        self.assertFalse([k for k in ss if str(k).startswith(("mt_", "_mt_"))])

    def test_audio_and_timing_are_separate_objects(self) -> None:
        """Requirement 6: the recording and its transcription are not one blob."""
        ss: dict = {}
        scope = recording_scope("doc1", "verse")
        ingest_take(ss, scope, {"take_id": "t1", "wav": WAV, "timing": _timing()})
        self.assertEqual(take_audio(ss, scope), WAV)
        status = recording_status(ss, scope)
        self.assertTrue(status["synchronized"])
        self.assertNotIn("wav", str(status))


class TestUnknownTimingIsReportedNotGuessed(unittest.TestCase):
    """Requirement 8, and the fallback route's honesty."""

    def test_a_take_with_no_timing_is_unsynchronized(self) -> None:
        ss: dict = {}
        scope = recording_scope("doc1", "verse")
        ingest_take(ss, scope, {"take_id": "t1", "wav": WAV, "timing": {}})
        status = recording_status(ss, scope)
        self.assertFalse(status["synchronized"])
        self.assertTrue(str(status["reason"]).strip())
        self.assertIn("not aligned", status["caption"])

    def test_the_old_route_audio_is_labelled_basic_recorder(self) -> None:
        """Audio parked by st.audio_input has no timing at all."""
        ss: dict = {}
        scope = recording_scope("doc1", "verse")
        ss[f"_composer_take_audio_{scope}"] = WAV
        self.assertEqual(take_source(ss, scope), SOURCE_BASIC_RECORDER)
        status = recording_status(ss, scope)
        self.assertFalse(status["synchronized"])
        self.assertTrue(status["has_audio"])

    def test_a_measured_take_is_labelled_shared_clock(self) -> None:
        ss: dict = {}
        scope = recording_scope("doc1", "verse")
        ingest_take(ss, scope, {"take_id": "t1", "wav": WAV, "timing": _timing()})
        self.assertEqual(take_source(ss, scope), SOURCE_SHARED_CLOCK)

    def test_no_audio_at_all_reports_nothing_measured(self) -> None:
        status = recording_status({}, recording_scope("doc1", "verse"))
        self.assertFalse(status["synchronized"])
        self.assertFalse(status["has_audio"])


class TestTheComponentGetsCompositionsSettings(unittest.TestCase):
    """Requirement 4: chords, BPM, meter and the optional count-in."""

    def test_count_in_beats_follow_bars_and_meter(self) -> None:
        self.assertEqual(build_recorder_args(count_in_bars=1, beats_per_bar=4)["count_in_beats"], 4)
        self.assertEqual(build_recorder_args(count_in_bars=2, beats_per_bar=3)["count_in_beats"], 6)
        self.assertEqual(build_recorder_args(count_in_bars=0, beats_per_bar=4)["count_in_beats"], 0)

    def test_compound_meter_counts_its_own_pulse(self) -> None:
        """6/8 counts six eighth-note pulses, matching Composition's _beats_per_bar."""
        args = build_recorder_args(count_in_bars=1, beats_per_bar=6, bpm=150)
        self.assertEqual(args["count_in_beats"], 6)
        self.assertEqual(args["count_in_beats_per_bar"], 6)
        self.assertEqual(args["count_in_bpm"], 150.0)

    def test_a_section_with_no_chords_can_still_record(self) -> None:
        self.assertFalse(build_recorder_args()["require_backing"])

    def test_composition_monitors_nothing(self) -> None:
        """No overdubbing: the chords are the only thing to play along with."""
        self.assertEqual(build_recorder_args()["monitors"], [])

    def test_music_capture_constraints_are_requested(self) -> None:
        """Not the browser's speech pipeline, which the old route gets by default."""
        constraints = build_recorder_args()["constraints"]
        if constraints:
            self.assertFalse(constraints.get("noiseSuppression", True))
            self.assertFalse(constraints.get("autoGainControl", True))
            self.assertFalse(constraints.get("echoCancellation", True))

    def test_a_disabled_reason_disables_the_control(self) -> None:
        args = build_recorder_args(disabled_reason="librosa is unavailable")
        self.assertTrue(args["disabled"])
        self.assertEqual(args["disabled_reason"], "librosa is unavailable")

    def test_garbage_settings_do_not_raise(self) -> None:
        args = build_recorder_args(bpm="fast", beats_per_bar=None, count_in_bars="two")
        self.assertEqual(args["count_in_bpm"], 0.0)
        self.assertEqual(args["count_in_beats_per_bar"], 4)


class TestMalformedTakesAreIgnored(unittest.TestCase):
    def test_no_value_from_the_component(self) -> None:
        ss: dict = {}
        self.assertIsNone(
            render_shared_recorder(
                None, ss, scope=recording_scope("d", "s"), component=_Component(None)
            )
        )
        self.assertEqual(ss, {})

    def test_a_take_with_no_audio(self) -> None:
        ss: dict = {}
        comp = _Component({"take_id": "t1", "timing": _timing()})
        self.assertIsNone(
            render_shared_recorder(None, ss, scope=recording_scope("d", "s"), component=comp)
        )

    def test_undecodable_audio(self) -> None:
        ss: dict = {}
        comp = _Component({"take_id": "t1", "wav_b64": "!!!not base64!!!", "timing": _timing()})
        render_shared_recorder(None, ss, scope=recording_scope("d", "s"), component=comp)
        self.assertEqual(take_audio(ss, recording_scope("d", "s")), b"")

    def test_a_component_that_raises_does_not_break_the_page(self) -> None:
        class Boom:
            def __call__(self, **_kwargs):
                raise RuntimeError("component failed")

        self.assertIsNone(
            render_shared_recorder(None, {}, scope=recording_scope("d", "s"), component=Boom())
        )


def _silent_wav(seconds: float = 0.5, rate: int = 44100) -> bytes:
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(2 * int(rate * seconds)))
    return buf.getvalue()


class _Gen:
    """A stand-in accompaniment renderer that counts how often it was asked to work."""

    def __init__(self, wav: bytes | None = None, raises: bool = False) -> None:
        self.wav = wav
        self.raises = raises
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.raises:
            raise RuntimeError("render failed")
        return self.wav


SETTINGS = dict(chords=["D", "Bm", "G", "A"], bpm=120, meter="4/4", key="D", count_in_bars=1)


class TestColdStartAccompaniment(unittest.TestCase):
    """The musician must not have to press Play chords before recording."""

    def test_a_cold_start_generates_the_accompaniment(self) -> None:
        ss: dict = {}
        gen = _Gen(_silent_wav())
        got = prepare_accompaniment(
            ss, recording_scope("doc1", "verse"), generate=gen, **SETTINGS
        )
        self.assertEqual(gen.calls, 1)
        self.assertTrue(got["wav"])
        self.assertFalse(got["reused"])
        self.assertEqual(got["error"], "")
        self.assertTrue(got["has_chords"])

    def test_the_duration_comes_from_the_wav_header(self) -> None:
        got = prepare_accompaniment(
            {},
            recording_scope("doc1", "verse"),
            generate=_Gen(_silent_wav(seconds=2.0)),
            **SETTINGS,
        )
        self.assertAlmostEqual(got["duration_sec"], 2.0, places=2)

    def test_a_section_with_no_chords_is_not_an_error(self) -> None:
        """Humming to the count-in alone is a legitimate way to capture an idea."""
        ss: dict = {}
        gen = _Gen(_silent_wav())
        got = prepare_accompaniment(
            ss,
            recording_scope("doc1", "verse"),
            generate=gen,
            chords=[],
            bpm=120,
            meter="4/4",
            key="D",
            count_in_bars=1,
        )
        self.assertEqual(gen.calls, 0)
        self.assertFalse(got["has_chords"])
        self.assertEqual(got["error"], "")
        self.assertEqual(got["wav"], b"")


class TestCacheReuse(unittest.TestCase):
    def test_an_exact_match_is_reused_without_regenerating(self) -> None:
        ss: dict = {}
        gen = _Gen(_silent_wav())
        scope = recording_scope("doc1", "verse")
        first = prepare_accompaniment(ss, scope, generate=gen, **SETTINGS)
        second = prepare_accompaniment(ss, scope, generate=gen, **SETTINGS)
        self.assertEqual(gen.calls, 1, "the accompaniment was rendered twice")
        self.assertTrue(second["reused"])
        self.assertEqual(second["wav"], first["wav"])

    def test_repeated_reads_keep_reusing(self) -> None:
        ss: dict = {}
        gen = _Gen(_silent_wav())
        scope = recording_scope("doc1", "verse")
        for _ in range(4):
            prepare_accompaniment(ss, scope, generate=gen, **SETTINGS)
        self.assertEqual(gen.calls, 1)


class TestStaleAndForeignCachesAreRejected(unittest.TestCase):
    """Recording against chords you cannot hear is worse than a short wait."""

    def _changed(self, **overrides):
        ss: dict = {}
        scope = recording_scope("doc1", "verse")
        old = _silent_wav(seconds=1.0)
        prepare_accompaniment(ss, scope, generate=_Gen(old), **SETTINGS)
        gen = _Gen(_silent_wav(seconds=3.0))
        settings = dict(SETTINGS)
        settings.update(overrides)
        return prepare_accompaniment(ss, scope, generate=gen, **settings), gen, old

    def test_edited_chords_regenerate(self) -> None:
        got, gen, old = self._changed(chords=["D", "Bm", "G", "Em"])
        self.assertEqual(gen.calls, 1)
        self.assertFalse(got["reused"])
        self.assertNotEqual(got["wav"], old)

    def test_a_different_tempo_regenerates(self) -> None:
        got, gen, _old = self._changed(bpm=90)
        self.assertEqual(gen.calls, 1)
        self.assertFalse(got["reused"])

    def test_a_different_meter_regenerates(self) -> None:
        got, gen, _old = self._changed(meter="3/4")
        self.assertEqual(gen.calls, 1)
        self.assertFalse(got["reused"])

    def test_a_different_key_regenerates(self) -> None:
        got, gen, _old = self._changed(key="Eb")
        self.assertEqual(gen.calls, 1)
        self.assertFalse(got["reused"])

    def test_a_different_count_in_regenerates(self) -> None:
        """The count-in is part of the rendered audio, so it is part of the identity."""
        got, gen, _old = self._changed(count_in_bars=0)
        self.assertEqual(gen.calls, 1)
        self.assertFalse(got["reused"])

    def test_another_section_does_not_inherit_the_render(self) -> None:
        ss: dict = {}
        gen = _Gen(_silent_wav())
        prepare_accompaniment(ss, recording_scope("doc1", "verse"), generate=gen, **SETTINGS)
        prepare_accompaniment(ss, recording_scope("doc1", "chorus"), generate=gen, **SETTINGS)
        self.assertEqual(gen.calls, 2)

    def test_another_song_does_not_inherit_the_render(self) -> None:
        ss: dict = {}
        gen = _Gen(_silent_wav())
        prepare_accompaniment(ss, recording_scope("doc1", "verse"), generate=gen, **SETTINGS)
        prepare_accompaniment(ss, recording_scope("doc2", "verse"), generate=gen, **SETTINGS)
        self.assertEqual(gen.calls, 2, "another song's accompaniment was served")

    def test_the_fingerprint_itself_separates_songs(self) -> None:
        a = accompaniment_fingerprint(scope=recording_scope("doc1", "verse"), **SETTINGS)
        b = accompaniment_fingerprint(scope=recording_scope("doc2", "verse"), **SETTINGS)
        self.assertNotEqual(a, b)


class TestFailedGeneration(unittest.TestCase):
    def test_a_renderer_returning_nothing_reports_an_error(self) -> None:
        got = prepare_accompaniment(
            {}, recording_scope("doc1", "verse"), generate=_Gen(None), **SETTINGS
        )
        self.assertTrue(got["error"])
        self.assertEqual(got["wav"], b"")

    def test_a_renderer_that_raises_reports_an_error(self) -> None:
        got = prepare_accompaniment(
            {}, recording_scope("doc1", "verse"), generate=_Gen(raises=True), **SETTINGS
        )
        self.assertTrue(got["error"])
        self.assertEqual(got["wav"], b"")

    def test_a_failure_caches_nothing(self) -> None:
        """A later attempt must try again, not serve a failure."""
        ss: dict = {}
        scope = recording_scope("doc1", "verse")
        prepare_accompaniment(ss, scope, generate=_Gen(None), **SETTINGS)
        gen = _Gen(_silent_wav())
        got = prepare_accompaniment(ss, scope, generate=gen, **SETTINGS)
        self.assertEqual(gen.calls, 1)
        self.assertTrue(got["wav"])

    def test_no_renderer_at_all_reports_an_error(self) -> None:
        got = prepare_accompaniment(
            {}, recording_scope("doc1", "verse"), generate=None, **SETTINGS
        )
        self.assertTrue(got["error"])

    def test_the_recorder_is_not_drawn_when_generation_fails(self) -> None:
        """Better no recorder than a recorder running against missing chords."""

        class _St:
            def __init__(self) -> None:
                self.warnings: list[str] = []

            def warning(self, text) -> None:
                self.warnings.append(str(text))

        st = _St()
        comp = _Component({"take_id": "t1", "wav": WAV, "timing": _timing()})
        got = render_shared_recorder(
            st,
            {},
            scope=recording_scope("doc1", "verse"),
            component=comp,
            chords=["D", "Bm"],
            bpm=120,
            meter="4/4",
            section_key="D",
            count_in_bars=1,
            generate_backing=_Gen(None),
        )
        self.assertIsNone(got)
        self.assertEqual(comp.calls, [], "the recorder was drawn without its chords")
        self.assertTrue(st.warnings)


class TestCountInIsNotAnAlignmentOffset(unittest.TestCase):
    """Two different quantities that must never be conflated."""

    def test_preparing_the_accompaniment_reports_no_offset(self) -> None:
        got = prepare_accompaniment(
            {}, recording_scope("doc1", "verse"), generate=_Gen(_silent_wav()), **SETTINGS
        )
        for forbidden in ("music_offset_sec", "count_in_sec", "timing", "music_start_frame"):
            self.assertNotIn(forbidden, got)

    def test_the_offset_still_comes_only_from_measured_timing(self) -> None:
        ss: dict = {}
        scope = recording_scope("doc1", "verse")
        prepare_accompaniment(ss, scope, generate=_Gen(_silent_wav()), **SETTINGS)
        self.assertFalse(recording_status(ss, scope)["synchronized"])


class TestCacheIdentityIsStableAcrossReruns(unittest.TestCase):
    """A rerun must not re-render the accompaniment or move the asset under the recorder.

    Streamlit reruns the whole script on every interaction, so the fingerprint is recomputed
    from scratch each time. If any part of it were unstable - a dict iteration order, a
    float repr, a timestamp - every rerun would look like a cache miss, regenerate the
    chords, hand the component a new asset fingerprint and make Record briefly unavailable
    while it reloaded. That is the failure these pin.
    """

    def _render(self, ss, gen, comp, *, scope):
        return render_shared_recorder(
            None,
            ss,
            scope=scope,
            component=comp,
            chords=["D", "Bm", "G", "A"],
            bpm=120,
            meter="4/4",
            section_key="D",
            count_in_bars=1,
            generate_backing=gen,
        )

    def test_six_reruns_render_the_accompaniment_once(self) -> None:
        ss: dict = {}
        gen = _Gen(_silent_wav())
        comp = _Component(None)
        scope = recording_scope("doc1", "verse")
        for _ in range(6):
            self._render(ss, gen, comp, scope=scope)
        self.assertEqual(gen.calls, 1, "a rerun re-rendered the chords")

    def test_the_fingerprint_does_not_drift(self) -> None:
        ss: dict = {}
        gen = _Gen(_silent_wav())
        comp = _Component(None)
        scope = recording_scope("doc1", "verse")
        seen = set()
        for _ in range(6):
            self._render(ss, gen, comp, scope=scope)
            seen.add(str(ss[backing_key(scope)]["fingerprint"]))
        self.assertEqual(len(seen), 1, f"the cache identity drifted: {seen}")

    def test_the_component_is_handed_the_same_asset_every_rerun(self) -> None:
        """A changing backing_fp would restart the browser-side load each rerun."""
        ss: dict = {}
        gen = _Gen(_silent_wav())
        comp = _Component(None)
        scope = recording_scope("doc1", "verse")
        for _ in range(4):
            self._render(ss, gen, comp, scope=scope)
        self.assertEqual(len({c["backing_fp"] for c in comp.calls}), 1)
        self.assertEqual(len({c["backing_duration_sec"] for c in comp.calls}), 1)
        self.assertEqual(len({c["load_nonce"] for c in comp.calls}), 1)

    def test_the_fingerprint_function_is_deterministic(self) -> None:
        kwargs = dict(
            scope=recording_scope("doc1", "verse"),
            chords=["D", "Bm", "G", "A"],
            bpm=120,
            meter="4/4",
            key="D",
            count_in_bars=1,
        )
        self.assertEqual(
            len({accompaniment_fingerprint(**kwargs) for _ in range(5)}),
            1,
        )

    def test_an_arriving_take_does_not_invalidate_the_accompaniment(self) -> None:
        """Recording does not change the chords, so the cache must survive a take."""
        ss: dict = {}
        gen = _Gen(_silent_wav())
        scope = recording_scope("doc1", "verse")
        comp = _Component(None)
        self._render(ss, gen, comp, scope=scope)
        before = str(ss[backing_key(scope)]["fingerprint"])
        ingest_take(ss, scope, {"take_id": "t1", "wav": WAV, "timing": _timing()})
        taken = _Component(
            {"take_id": "t2", "wav": WAV, "timing": _timing()}
        )
        self._render(ss, gen, taken, scope=scope)
        self.assertEqual(gen.calls, 1)
        self.assertEqual(str(ss[backing_key(scope)]["fingerprint"]), before)

    def test_a_discard_keeps_the_accompaniment_but_frees_the_recorder(self) -> None:
        """Discarding a take is not a reason to re-render chords that did not change."""
        ss: dict = {}
        gen = _Gen(_silent_wav())
        scope = recording_scope("doc1", "verse")
        comp = _Component(None)
        self._render(ss, gen, comp, scope=scope)
        nonce_before = recorder_load_nonce(ss, scope)
        discard_recording(ss, scope)
        self._render(ss, gen, comp, scope=scope)
        self.assertEqual(gen.calls, 1, "a discard re-rendered the chords")
        self.assertGreater(recorder_load_nonce(ss, scope), nonce_before)


class TestTheIdleReadoutSaysWhatRecordWillDo(unittest.TestCase):
    """"Ready." does not tell the player whether the chords arrive with their first note."""

    def _text(self, **over):
        ss: dict = {}
        comp = _Component(None)
        kwargs = dict(
            scope=recording_scope("doc1", "verse"),
            component=comp,
            chords=["D", "Bm", "G", "A"],
            bpm=120,
            meter="4/4",
            section_key="D",
            count_in_bars=1,
            generate_backing=_Gen(_silent_wav()),
        )
        kwargs.update(over)
        render_shared_recorder(None, ss, **kwargs)
        self.assertTrue(comp.calls, "the recorder was not drawn")
        return str(comp.calls[-1].get("ready_text") or "")

    def test_an_armed_accompaniment_is_announced(self) -> None:
        said = self._text()
        self.assertIn("chords", said.lower())
        self.assertIn("together", said.lower())

    def test_a_section_with_no_chords_says_count_in_only(self) -> None:
        said = self._text(chords=[], generate_backing=None)
        self.assertIn("count-in only", said.lower())
        self.assertIn("no chords yet", said.lower())

    def test_the_readout_is_never_empty(self) -> None:
        """An empty string makes the component fall back to "Ready." again."""
        self.assertTrue(self._text().strip())
        self.assertTrue(self._text(chords=[], generate_backing=None).strip())


if __name__ == "__main__":
    unittest.main()
