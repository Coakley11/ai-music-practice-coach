"""Issue 78B - one Record arms the mic, counts in, and starts every monitored part on one clock.

These are the deterministic half of the slice: which layers a player hears while overdubbing, where
each of them is placed (the shared Align contract, not a second opinion), what the recorder is told
about the count-in, and what timing is kept with the take. The measured timing itself needs a real
AudioContext and is proved in the browser harness, not here.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from multitrack_live_recorder import (  # noqa: E402
    TAKE_TIMING_KEY,
    build_monitors,
    count_in_beats,
    forget_take_timing,
    monitor_fingerprint,
    monitor_slots,
    normalize_timing,
    ready_text,
    record_take_timing,
    take_filename,
    take_timing,
    timing_caption,
)

COMPONENT = (ROOT / "mission_recorder_component" / "index.html").read_text(encoding="utf-8")
SLOTS = ["Layer 1", "Layer 2", "Layer 3"]


def session(**tracks: bytes) -> dict:
    """A session with the given slots already holding audio."""
    return {"mt_tracks": dict(tracks), "mt_track_controls": {}}


def url_for(data: bytes, coordinates: str) -> str:
    return "/media/" + coordinates


class WhatThePlayerHearsWhileOverdubbing(unittest.TestCase):
    def test_the_layer_being_recorded_is_never_played_back_into_the_room(self) -> None:
        st = session(**{"Layer 1": b"a", "Layer 2": b"b"})
        self.assertEqual(monitor_slots(st, recording_slot="Layer 1", slots=SLOTS), ["Layer 2"])

    def test_empty_slots_are_not_monitors(self) -> None:
        st = session(**{"Layer 2": b"b"})
        self.assertEqual(monitor_slots(st, recording_slot="Layer 3", slots=SLOTS), ["Layer 2"])

    def test_a_muted_layer_is_not_played(self) -> None:
        st = session(**{"Layer 1": b"a", "Layer 2": b"b"})
        st["mt_track_controls"] = {"Layer 2": {"volume": 1.0, "delay": 0.0, "mute": True, "solo": False}}
        self.assertEqual(monitor_slots(st, recording_slot="Layer 1", slots=SLOTS), [])

    def test_solo_narrows_to_the_soloed_layers(self) -> None:
        st = session(**{"Layer 1": b"a", "Layer 2": b"b", "Layer 3": b"c"})
        st["mt_track_controls"] = {
            "Layer 2": {"volume": 1.0, "delay": 0.0, "mute": False, "solo": False},
            "Layer 3": {"volume": 1.0, "delay": 0.0, "mute": False, "solo": True},
        }
        self.assertEqual(monitor_slots(st, recording_slot="Layer 1", slots=SLOTS), ["Layer 3"])

    def test_a_soloed_layer_is_heard_even_while_recording_a_third(self) -> None:
        st = session(**{"Layer 1": b"a", "Layer 2": b"b", "Layer 3": b"c"})
        st["mt_track_controls"] = {"Layer 1": {"volume": 1.0, "delay": 0.0, "mute": False, "solo": True}}
        self.assertEqual(monitor_slots(st, recording_slot="Layer 2", slots=SLOTS), ["Layer 1"])


class TheMonitorsUseTheOneAlignContract(unittest.TestCase):
    def build(self, delay: float) -> dict:
        st = session(**{"Layer 1": b"a", "Layer 2": b"bb"})
        st["mt_track_controls"] = {"Layer 2": {"volume": 1.0, "delay": delay, "mute": False, "solo": False}}
        made = build_monitors(st, recording_slot="Layer 1", slots=SLOTS, media_url=url_for)
        self.assertEqual(len(made), 1)
        return made[0]

    def test_zero_align_places_the_layer_at_musical_zero(self) -> None:
        m = self.build(0.0)
        self.assertEqual((m["start_delay_sec"], m["buffer_offset_sec"]), (0.0, 0.0))

    def test_a_positive_align_delays_the_layer(self) -> None:
        m = self.build(0.5)
        self.assertEqual((m["start_delay_sec"], m["buffer_offset_sec"]), (0.5, 0.0))

    def test_a_negative_align_skips_into_the_layer_rather_than_moving_nothing(self) -> None:
        m = self.build(-0.5)
        self.assertEqual((m["start_delay_sec"], m["buffer_offset_sec"]), (0.0, 0.5))

    def test_the_schedule_is_the_contracts_own_answer_not_a_second_opinion(self) -> None:
        from multitrack_align_contract import transport_payload

        for delay in (-1.25, -0.01, 0.0, 0.33, 2.0):
            m = self.build(delay)
            want = transport_payload(delay)
            self.assertEqual(
                (m["start_delay_sec"], m["buffer_offset_sec"]),
                (want["startDelaySec"], want["bufferOffsetSec"]),
                f"delay {delay}",
            )

    def test_a_silent_monitor_volume_is_lifted_to_something_audible(self) -> None:
        # A monitor nobody can hear is heard as a fault in the recorder, not as a mixer setting.
        st = session(**{"Layer 1": b"a", "Layer 2": b"bb"})
        st["mt_track_controls"] = {"Layer 2": {"volume": 0.0, "delay": 0.0, "mute": False, "solo": False}}
        made = build_monitors(st, recording_slot="Layer 1", slots=SLOTS, media_url=url_for)
        self.assertGreater(made[0]["volume"], 0.0)

    def test_each_monitor_is_identified_by_its_own_bytes(self) -> None:
        st = session(**{"Layer 1": b"a", "Layer 2": b"bb", "Layer 3": b"ccc"})
        made = build_monitors(st, recording_slot="Layer 1", slots=SLOTS, media_url=url_for)
        self.assertEqual(len(made), 2)
        self.assertNotEqual(made[0]["fp"], made[1]["fp"])
        self.assertEqual(made[0]["fp"], monitor_fingerprint(b"bb"))

    def test_the_same_audio_keeps_the_same_fingerprint_across_runs(self) -> None:
        self.assertEqual(monitor_fingerprint(b"take"), monitor_fingerprint(b"take"))
        self.assertNotEqual(monitor_fingerprint(b"take"), monitor_fingerprint(b"takes"))

    def test_an_asset_that_cannot_be_registered_is_left_out_rather_than_half_armed(self) -> None:
        def refuse(data: bytes, coordinates: str) -> str:
            raise RuntimeError("no media manager")

        st = session(**{"Layer 1": b"a", "Layer 2": b"bb"})
        self.assertEqual(build_monitors(st, recording_slot="Layer 1", slots=SLOTS, media_url=refuse), [])


class TheCountInIsTheOneTheSetupPanelShows(unittest.TestCase):
    def test_none_is_no_beats(self) -> None:
        self.assertEqual(count_in_beats(bars=0, beats_per_bar=4), 0)

    def test_one_bar_of_four_four(self) -> None:
        self.assertEqual(count_in_beats(bars=1, beats_per_bar=4), 4)

    def test_two_bars_of_four_four(self) -> None:
        self.assertEqual(count_in_beats(bars=2, beats_per_bar=4), 8)

    def test_a_three_four_bar_counts_three(self) -> None:
        self.assertEqual(count_in_beats(bars=1, beats_per_bar=3), 3)

    def test_nonsense_is_no_count_in_rather_than_an_error(self) -> None:
        self.assertEqual(count_in_beats(bars=None, beats_per_bar=4), 0)
        self.assertEqual(count_in_beats(bars=-2, beats_per_bar=4), 0)


class TheRecorderSaysWhatItIsAboutToDo(unittest.TestCase):
    def test_a_first_layer_alone_says_so(self) -> None:
        text = ready_text(beats=0, monitors=0, has_backing=False)
        self.assertIn("on its own", text)
        self.assertIn("Nothing else is playing", text)

    def test_the_count_in_is_named(self) -> None:
        self.assertIn("4-beat count-in", ready_text(beats=4, monitors=0, has_backing=False))

    def test_the_backing_and_the_layers_are_both_named(self) -> None:
        text = ready_text(beats=8, monitors=2, has_backing=True)
        self.assertIn("count-in", text)
        self.assertIn("the backing", text)
        self.assertIn("2 other layers", text)

    def test_one_other_layer_is_singular(self) -> None:
        self.assertIn("your other layer", ready_text(beats=0, monitors=1, has_backing=False))

    def test_it_claims_one_clock_because_that_is_what_happens(self) -> None:
        self.assertIn("one clock", ready_text(beats=4, monitors=1, has_backing=True))


class TheTakeFilenameIsSafeToStore(unittest.TestCase):
    """It reaches durable storage through persist_track_audio, so it must not carry a path."""

    def test_a_slot_with_a_slash_does_not_produce_a_path(self) -> None:
        name = take_filename("sax / winds")
        self.assertNotIn("/", name)
        self.assertNotIn("\\", name)
        self.assertEqual(name, "sax-winds-take.wav")

    def test_it_is_still_recognisable_as_the_layer(self) -> None:
        self.assertEqual(take_filename("guitar"), "guitar-take.wav")
        self.assertEqual(take_filename("extra layer"), "extra-layer-take.wav")

    def test_it_keeps_the_wav_suffix_the_decoder_reads(self) -> None:
        for slot in ("guitar", "sax / winds", "  ", "Keys/Pads!!", "..", "x" * 200):
            self.assertTrue(take_filename(slot).endswith(".wav"), slot)

    def test_a_nameless_slot_still_gets_a_name(self) -> None:
        self.assertEqual(take_filename("   "), "layer-take.wav")
        self.assertEqual(take_filename("!!!"), "layer-take.wav")

    def test_no_traversal_survives(self) -> None:
        for slot in ("../../etc/passwd", r"..\..\win", "./x"):
            name = take_filename(slot)
            self.assertNotIn("..", name)
            self.assertNotIn("/", name)


class TheTakeKeepsWhatWasMeasured(unittest.TestCase):
    def raw(self, **kw) -> dict:
        base = {
            "sample_rate": 48000,
            "count_in_sec": 2.0,
            "music_offset_sec": 2.03,
            "scheduled_music_offset_sec": 2.0,
            "backing_offset_sec": 2.03,
            "capture_first_frame": 1024,
            "music_start_frame": 97024,
            "monitor_count": 2,
            "backing_fp": "abc123",
            "device": "Mic",
            "settings": {"noiseSuppression": False},
        }
        base.update(kw)
        return base

    def test_the_fields_survive(self) -> None:
        out = normalize_timing(self.raw())
        self.assertEqual(out["sample_rate"], 48000.0)
        self.assertEqual(out["music_start_frame"], 97024)
        self.assertEqual(out["monitor_count"], 2)
        self.assertEqual(out["backing_fp"], "abc123")
        self.assertEqual(out["settings"], {"noiseSuppression": False})

    def test_frames_are_whole_numbers(self) -> None:
        out = normalize_timing(self.raw(capture_first_frame=1024.0))
        self.assertIsInstance(out["capture_first_frame"], int)

    def test_a_missing_measurement_is_absent_rather_than_zero(self) -> None:
        out = normalize_timing({"sample_rate": 48000, "music_offset_sec": None})
        self.assertNotIn("music_offset_sec", out)

    def test_nonsense_numbers_are_refused(self) -> None:
        out = normalize_timing(self.raw(music_offset_sec=float("nan"), count_in_sec=float("inf")))
        self.assertNotIn("music_offset_sec", out)
        self.assertNotIn("count_in_sec", out)

    def test_nothing_measured_is_an_empty_record_not_a_fabricated_one(self) -> None:
        self.assertEqual(normalize_timing(None), {})
        self.assertEqual(normalize_timing({}), {})

    def test_the_timing_is_kept_against_its_own_slot(self) -> None:
        st: dict = {}
        record_take_timing(st, "Layer 1", self.raw())
        record_take_timing(st, "Layer 2", self.raw(monitor_count=1))
        self.assertEqual(take_timing(st, "Layer 1")["monitor_count"], 2)
        self.assertEqual(take_timing(st, "Layer 2")["monitor_count"], 1)
        self.assertEqual(take_timing(st, "Layer 3"), {})

    def test_discarding_a_take_discards_its_timing(self) -> None:
        st: dict = {}
        record_take_timing(st, "Layer 1", self.raw())
        forget_take_timing(st, "Layer 1")
        self.assertEqual(take_timing(st, "Layer 1"), {})

    def test_forgetting_an_absent_slot_is_harmless(self) -> None:
        st: dict = {}
        forget_take_timing(st, "Layer 1")
        self.assertEqual(st.get(TAKE_TIMING_KEY, {}), {})

    def test_the_caption_reports_the_measurement_and_nothing_else(self) -> None:
        line = timing_caption(normalize_timing(self.raw()))
        self.assertIn("48.0 kHz", line)
        self.assertIn("2.0 s count-in", line)
        self.assertIn("2.030 s", line)

    def test_an_uploaded_take_says_nothing_rather_than_implying_a_measurement(self) -> None:
        self.assertEqual(timing_caption({}), "")
        self.assertEqual(timing_caption(None), "")


class TheComponentSchedulesInTheRightOrder(unittest.TestCase):
    """The ordering guarantees, read off the component itself.

    The browser harness measures the result; these pin the structure, so a later edit that moves
    the start decision back in front of the capture cannot pass unnoticed.
    """

    def test_capture_is_connected_before_anything_audible_is_scheduled(self) -> None:
        connect = COMPONENT.index("src.connect(node); node.connect(mute)")
        schedule = COMPONENT.index("const countInStart = c.currentTime + lead")
        self.assertLess(connect, schedule)

    def test_musical_zero_is_the_count_in_start_plus_the_count_in(self) -> None:
        self.assertIn("const musicStart = countInStart + countInSec;", COMPONENT)

    def test_the_monitors_start_at_musical_zero_plus_their_own_align(self) -> None:
        self.assertIn("s.start(musicStart + entry.asset.startDelay, offset);", COMPONENT)

    def test_nothing_is_scheduled_at_the_clocks_present_value(self) -> None:
        self.assertIn("const lead = 0.25;", COMPONENT)
        self.assertNotIn("s.start(c.currentTime)", COMPONENT)

    def test_the_negative_align_skip_cannot_swallow_the_whole_layer(self) -> None:
        self.assertIn("entry.buf.duration - offset < 0.05", COMPONENT)

    def test_every_scheduled_source_is_stopped_not_only_the_backing(self) -> None:
        stop_block = COMPONENT[COMPONENT.index("async function stop()"):]
        self.assertIn("r.sources", stop_block)
        self.assertIn("for (const osc of r.clicks", stop_block)

    def test_the_request_is_ready_only_once_every_asset_has_decoded(self) -> None:
        body = COMPONENT[COMPONENT.index("async function loadAssets"):COMPONENT.index("function syncBacking")]
        # The ready state is set after the loop over assets, not inside it.
        loop = body.index("for (const asset of assets)")
        ready = body.index('bk.state = "ready"')
        self.assertLess(loop, ready)
        self.assertIn("armed = got;", body)

    def test_one_asset_keeps_its_own_fingerprint_as_the_requests(self) -> None:
        # Mission passes exactly one asset, so its handshake must be untouched by the generalisation.
        self.assertIn('return (assets || requestAssets()).map((a) => a.fp).join("+");', COMPONENT)

    def test_the_count_in_is_synthesised_so_it_never_waits_on_an_asset(self) -> None:
        block = COMPONENT[COMPONENT.index("function scheduleCountIn"):COMPONENT.index("async function start()")]
        self.assertIn("createOscillator", block)
        self.assertNotIn("fetch", block)

    def test_the_scheduling_clock_and_the_latency_compensated_sets_are_kept_apart(self) -> None:
        # Mixing them silently adds the output+input latency to any difference, which is exactly
        # how a 2.000 s count-in first measured as 2.052 s.
        block = COMPONENT[COMPONENT.index("count_in_sec: r.countInSec"):COMPONENT.index("monitor_count:")]
        self.assertIn("scheduled_count_in_offset_sec: frameOffset(r.countInFrame),", block)
        self.assertIn("count_in_offset_sec: frameOffset(r.countInFrame) === null ? null : frameOffset(r.countInFrame) + outLat + inLat,", block)
        self.assertIn("scheduled_music_offset_sec: musicOffset,", block)
        self.assertIn("music_offset_sec: musicOffset === null ? null : musicOffset + outLat + inLat,", block)

    def test_both_offset_sets_are_kept_with_the_take(self) -> None:
        kept = normalize_timing({
            "scheduled_count_in_offset_sec": 0.25, "count_in_offset_sec": 0.301,
            "scheduled_music_offset_sec": 2.25, "music_offset_sec": 2.301,
            "output_latency_sec": 0.04, "input_latency_sec": 0.011,
        })
        self.assertAlmostEqual(kept["music_offset_sec"] - kept["count_in_offset_sec"], 2.0, places=6)
        self.assertAlmostEqual(
            kept["scheduled_music_offset_sec"] - kept["scheduled_count_in_offset_sec"], 2.0, places=6
        )
        self.assertAlmostEqual(
            kept["music_offset_sec"] - kept["scheduled_music_offset_sec"],
            kept["output_latency_sec"] + kept["input_latency_sec"], places=9,
        )

    def test_the_timing_reports_musical_zero_as_well_as_the_backing(self) -> None:
        for field in ("music_start_frame", "music_offset_sec", "count_in_sec", "monitor_count"):
            self.assertIn(field + ":", COMPONENT)

    def test_mission_still_gets_a_null_backing_offset_when_it_has_no_backing(self) -> None:
        self.assertIn("backing_offset_sec: scheduledOffset === null ? null :", COMPONENT)
        self.assertIn("const scheduledOffset = frameOffset(r.backingFrame);", COMPONENT)

    def test_the_count_in_args_default_to_no_count_in(self) -> None:
        block = COMPONENT[COMPONENT.index("function countInSeconds"):COMPONENT.index("function note(")]
        self.assertIn("if (beats <= 0 || bpm <= 0) return 0;", block)

    def test_the_accent_marks_the_bar(self) -> None:
        self.assertIn("const accent = i % perBar === 0;", COMPONENT)

    def test_the_recording_status_does_not_call_a_layer_the_backing(self) -> None:
        # With one monitored layer and no backing, "the generated backing" would be a lie, and a
        # player told the wrong thing stops trusting the rest of the readout.
        block = COMPONENT[COMPONENT.index("const layers = rec.monitors"):COMPONENT.index("status(what")]
        self.assertIn('rec.backingFrame !== null && layers > 0', block)
        self.assertIn('else if (layers > 0) what = "Recording with " + plural(layers, "layer") + " of your own";', block)

    def test_the_component_is_one_recorder_not_two(self) -> None:
        self.assertEqual(len(re.findall(r"new AudioContext\(", COMPONENT)), 1)
        self.assertEqual(len(re.findall(r'registerProcessor\("mission-capture"', COMPONENT)), 1)


class TheSharedRecorderIsReusedNotReimplemented(unittest.TestCase):
    def test_the_multitrack_surface_renders_the_mission_component(self) -> None:
        src = (ROOT / "multitrack_live_recorder.py").read_text(encoding="utf-8")
        self.assertIn("from mission_recorder import RECORDER_COMPONENT", src)
        self.assertNotIn("declare_component", src)

    def test_mission_exports_the_component_it_already_declared(self) -> None:
        import mission_recorder

        self.assertIs(mission_recorder.RECORDER_COMPONENT, mission_recorder._COMPONENT)

    def test_music_capture_constraints_are_the_shared_ones(self) -> None:
        from mission_music_capture import MUSIC_CAPTURE_CONSTRAINTS

        self.assertEqual(
            MUSIC_CAPTURE_CONSTRAINTS,
            {"echoCancellation": False, "noiseSuppression": False, "autoGainControl": False},
        )


if __name__ == "__main__":
    unittest.main()
