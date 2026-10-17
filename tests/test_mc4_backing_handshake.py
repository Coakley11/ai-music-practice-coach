"""MC4 — Generate Backing → recorder handshake (Python side).

Human review: after Generate Backing the UI said "Backing generated … Record plays it with your take"
while the browser recorder stayed on "Loading the generated backing…" with Record disabled forever.
Python's "generated" and the browser's "not ready" had diverged and nothing reconciled them.

The contract now: "ready" is only the browser's acknowledgement of the exact fingerprint *and* load
request (nonce); a failed load is an explicit state; anything older cannot arm a newer backing.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import mission_exact_chord_backing_ui as ui
import mission_generated_backing as mgb
import mission_recorder as mr

ROOT = Path(__file__).resolve().parents[1]


def _session(fp: str = "aaaa", *, nonce: int = 1, duration: float = 28.6, signature: str = "sig") -> dict:
    return {
        mgb.GENERATED_KEY: {"fp": fp, "signature": signature, "label": "C♯m7♭5 → F♯7 → Bm", "bpm": 148, "loops": 4,
                            "duration_sec": duration},
        mgb.ASSETS_KEY: {fp: b"RIFFwav"},
        "mission_exact_backing_wav": b"x",
        mgb.NONCE_KEY: nonce,
    }


def _ack(fp="aaaa", state="ready", nonce=1, **kw) -> dict:
    return dict({"fp": fp, "state": state, "nonce": nonce, "attempts": 1, "error": "", "duration_sec": 28.57,
                 "instance": "inst1", "trace": [{"step": "armed"}]}, **kw)


class _St:
    """Records the Streamlit calls the status renderer makes."""

    def __init__(self, button=False):
        self.calls, self._button = [], button

    def container(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def info(self, t):
        self.calls.append(("info", t))

    def success(self, t):
        self.calls.append(("success", t))

    def error(self, t):
        self.calls.append(("error", t))

    def caption(self, t):
        self.calls.append(("caption", t))

    def button(self, label, key=None):
        self.calls.append(("button", label))
        return self._button

    def rerun(self):
        self.calls.append(("rerun", ""))


class TestLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        p = mock.patch.object(mgb, "_signature_text", lambda s: "sig")
        p.start()
        self.addCleanup(p.stop)

    def test_states_follow_the_browsers_acknowledgement(self) -> None:
        s = {}
        self.assertEqual(mgb.backing_lifecycle(s)["state"], "not_generated")
        s = _session()
        self.assertEqual(mgb.backing_lifecycle(s)["state"], "preparing")   # generated is NOT ready
        self.assertTrue(mgb.record_backing_ack(s, _ack(state="loading")))
        self.assertEqual(mgb.backing_lifecycle(s)["state"], "preparing")
        self.assertTrue(mgb.record_backing_ack(s, _ack()))
        life = mgb.backing_lifecycle(s)
        self.assertEqual((life["state"], life["duration_sec"]), ("ready", 28.6))
        self.assertTrue(mgb.record_backing_ack(s, _ack(state="failed", error="HTTP 404")))
        self.assertEqual(mgb.backing_lifecycle(s)["state"], "failed")
        self.assertEqual(mgb.backing_lifecycle(s)["error"], "HTTP 404")

    def test_an_old_acknowledgement_cannot_arm_a_newer_backing(self) -> None:
        s = _session("aaaa", nonce=1)
        mgb.record_backing_ack(s, _ack("aaaa", nonce=1))
        self.assertEqual(mgb.backing_lifecycle(s)["state"], "ready")
        # a new backing is generated (new fingerprint): the earlier ack no longer counts …
        s.update(_session("bbbb", nonce=2))
        self.assertEqual(mgb.backing_lifecycle(s)["state"], "preparing")
        # … and a late ack for the old fingerprint, or for the old request, is refused
        self.assertFalse(mgb.record_backing_ack(s, _ack("aaaa", nonce=2)))
        self.assertFalse(mgb.record_backing_ack(s, _ack("bbbb", nonce=1)))
        self.assertEqual(mgb.backing_lifecycle(s)["state"], "preparing")
        self.assertTrue(mgb.record_backing_ack(s, _ack("bbbb", nonce=2)))
        self.assertEqual(mgb.backing_lifecycle(s)["state"], "ready")

    def test_same_asset_regenerated_needs_a_fresh_acknowledgement(self) -> None:
        s = _session("aaaa", nonce=1)
        mgb.record_backing_ack(s, _ack("aaaa", nonce=1))
        mgb.request_backing_reload(s)                                       # Retry / Generate again: nonce moves
        self.assertEqual(s[mgb.NONCE_KEY], 2)
        self.assertEqual(mgb.backing_lifecycle(s)["state"], "preparing")
        self.assertFalse(mgb.record_backing_ack(s, _ack("aaaa", nonce=1)))  # the earlier load's ack is stale
        self.assertTrue(mgb.record_backing_ack(s, _ack("aaaa", nonce=2)))
        self.assertEqual(mgb.backing_lifecycle(s)["state"], "ready")

    def test_changing_a_setting_invalidates_ready(self) -> None:
        s = _session()
        mgb.record_backing_ack(s, _ack())
        with mock.patch.object(mgb, "_signature_text", lambda _s: "other settings"):
            life = mgb.backing_lifecycle(s)
        self.assertEqual((life["state"], life["reason"]), ("stale", "settings changed"))
        s2 = _session(); mgb.record_backing_ack(s2, _ack()); s2.pop("mission_exact_backing_wav")
        self.assertEqual(mgb.backing_lifecycle(s2)["state"], "stale")

    def test_malformed_acknowledgements_are_ignored(self) -> None:
        s = _session()
        for bad in (None, "ready", {}, _ack(state="armed"), _ack(fp="")):
            self.assertFalse(mgb.record_backing_ack(s, bad))
        self.assertNotIn(mgb.ACK_KEY, s)
        self.assertFalse(mgb.record_backing_ack({}, _ack()))                # nothing generated

    def test_failure_is_logged_once_with_the_browser_trace(self) -> None:
        s = _session()
        with mock.patch.object(mgb, "_LOG") as log:       # independent of global logging configuration
            mgb.record_backing_ack(s, _ack(state="failed", error="HTTP 404"))
            mgb.record_backing_ack(s, _ack(state="failed", error="HTTP 404"))   # same outcome re-delivered by a rerun
        self.assertEqual(log.warning.call_count, 1)
        args = log.warning.call_args.args
        text = args[0] % args[1:]
        self.assertIn("HTTP 404", text)
        self.assertIn("armed", text)

    def test_generate_starts_a_new_request(self) -> None:
        s = _session("aaaa", nonce=3)
        mgb.record_backing_ack(s, _ack("aaaa", nonce=3))
        wav = b"RIFF" + b"\0" * 64
        fake_engine = SimpleNamespace(generate_exact_chord_backing_wav=lambda sess: (wav, "label"),
                                      invalidate_exact_chord_backing_cache=lambda sess: None)
        ctx = SimpleNamespace(span=None, tempo_bpm=100, meter="4/4", count_in_bars=0, loops=1, loop=False,
                              display_key="C", chord=SimpleNamespace(symbol="C"))
        with mock.patch.dict("sys.modules", {"mission_exact_chord_backing": fake_engine}), \
                mock.patch("mission_live_recording_mix.wav_duration_sec", lambda w: 1.0), \
                mock.patch("mission_practice_context.ensure_mission_practice_context", lambda s_: ctx):
            rec = mgb.generate_mission_backing(s)
        self.assertEqual(s[mgb.NONCE_KEY], 4)
        self.assertNotIn(mgb.ACK_KEY, s)
        self.assertEqual(mgb.backing_lifecycle(s)["state"], "preparing")
        self.assertEqual(rec["fp"], s[mgb.GENERATED_KEY]["fp"])


class TestRecorderArgs(unittest.TestCase):
    def setUp(self) -> None:
        p = mock.patch.object(mgb, "_signature_text", lambda s: "sig")
        p.start()
        self.addCleanup(p.stop)

    def test_recorder_gets_the_exact_request_and_records_the_ack(self) -> None:
        s = _session("aaaa", nonce=2)
        seen = {}

        def fake_component(key=None, default=None, **args):
            seen.update(args)
            return {"ack": _ack("aaaa", nonce=2, instance="instX")}

        with mock.patch.object(mr, "_COMPONENT", fake_component), \
                mock.patch.object(mr, "backing_media_url", lambda wav, coords: "/media/x.wav"):
            take = mr.render_mission_recorder(None, s, key="k", backing=s[mgb.GENERATED_KEY], backing_wav=b"RIFFwav")
        self.assertIsNone(take)                                              # an ack is not a take
        self.assertEqual((seen["backing_fp"], seen["backing_url"], seen["load_nonce"]), ("aaaa", "/media/x.wav", 2))
        self.assertEqual(seen["backing_duration_sec"], 28.6)
        self.assertEqual(mgb.backing_lifecycle(s)["state"], "ready")
        # the next run tells a remounted recorder which instance Python believes was ready
        with mock.patch.object(mr, "_COMPONENT", fake_component), \
                mock.patch.object(mr, "backing_media_url", lambda wav, coords: "/media/x.wav"):
            mr.render_mission_recorder(None, s, key="k", backing=s[mgb.GENERATED_KEY], backing_wav=b"RIFFwav")
        self.assertEqual(seen["acked_instance"], "instX")

    def test_without_a_ready_backing_nothing_is_offered(self) -> None:
        seen = {}

        def fake_component(key=None, default=None, **args):
            seen.update(args)
            return None

        with mock.patch.object(mr, "_COMPONENT", fake_component):
            mr.render_mission_recorder(None, {}, key="k", backing=None, backing_wav=None)
        self.assertEqual((seen["backing_fp"], seen["backing_url"]), ("", ""))

    def test_a_take_still_comes_back_alongside_its_ack(self) -> None:
        import base64
        s = _session()
        value = {"take_id": "t1", "wav_b64": base64.b64encode(b"RIFFx").decode(), "timing": {"backing_fp": "aaaa"},
                 "ack": _ack()}
        with mock.patch.object(mr, "_COMPONENT", lambda **kw: value), \
                mock.patch.object(mr, "backing_media_url", lambda wav, coords: "/media/x.wav"):
            take = mr.render_mission_recorder(None, s, key="k", backing=s[mgb.GENERATED_KEY], backing_wav=b"RIFFwav")
        self.assertEqual((take["take_id"], take["timing"]["backing_fp"]), ("t1", "aaaa"))
        self.assertEqual(mgb.backing_lifecycle(s)["state"], "ready")


class TestStatusWording(unittest.TestCase):
    def setUp(self) -> None:
        p = mock.patch.object(mgb, "_signature_text", lambda s: "sig")
        p.start()
        self.addCleanup(p.stop)

    def test_preparing_ready_failed(self) -> None:
        s = _session()
        st = _St(); ui.render_backing_lifecycle_status(st, s, key_prefix="p")
        self.assertEqual(st.calls, [("info", "Preparing recorder…")])
        mgb.record_backing_ack(s, _ack())
        st = _St(); ui.render_backing_lifecycle_status(st, s, key_prefix="p")
        self.assertEqual(st.calls[0][0], "success")
        self.assertTrue(st.calls[0][1].startswith("Backing ready · 28.6 s"))
        self.assertNotIn("generated", st.calls[0][1].lower())
        mgb.record_backing_ack(s, _ack(state="failed", error="HTTP 404"))
        st = _St(); ui.render_backing_lifecycle_status(st, s, key_prefix="p")
        self.assertEqual(st.calls[0], ("error", "Backing was generated but could not be loaded into the recorder. "
                                                 "Generate it again."))
        self.assertIn(("button", "Retry loading the backing"), st.calls)

    def test_retry_button_requests_a_new_load(self) -> None:
        s = _session(); mgb.record_backing_ack(s, _ack(state="failed", error="HTTP 404"))
        st = _St(button=True); ui.render_backing_lifecycle_status(st, s, key_prefix="p")
        self.assertEqual(s[mgb.NONCE_KEY], 2)
        self.assertIn(("rerun", ""), st.calls)
        self.assertEqual(mgb.backing_lifecycle(s)["state"], "preparing")

    def test_nothing_is_claimed_when_there_is_no_current_backing(self) -> None:
        st = _St(); ui.render_backing_lifecycle_status(st, {}, key_prefix="p")
        self.assertEqual(st.calls, [])
        s = _session()
        with mock.patch.object(mgb, "_signature_text", lambda _s: "changed"):
            st = _St(); ui.render_backing_lifecycle_status(st, s, key_prefix="p")
        self.assertEqual(st.calls, [])                                      # the panel shows the stale warning

    def test_generate_panel_no_longer_announces_success(self) -> None:
        src = (ROOT / "mission_exact_chord_backing_ui.py").read_text(encoding="utf-8")
        self.assertNotIn("Backing generated:", src)
        self.assertNotIn("Record plays it with your take", src)
        self.assertIn("Generating backing…", src)


class TestComponentContract(unittest.TestCase):
    """Static guards on the recorder page (the behaviour is exercised in a browser — see the sibling test)."""

    def setUp(self) -> None:
        self.html = (ROOT / "mission_recorder_component" / "index.html").read_text(encoding="utf-8")

    def test_errors_are_not_overwritten_by_a_later_render(self) -> None:
        self.assertNotIn("Loading the generated backing", self.html)
        self.assertIn("could not be loaded into the recorder", self.html)
        self.assertNotIn("loadingFp", self.html)                             # the in-flight guard that could wedge

    def test_every_load_is_token_guarded_and_bounded(self) -> None:
        self.assertIn("token !== loadToken", self.html)
        self.assertRegex(self.html, r"MAX_ATTEMPTS\s*=\s*3")
        self.assertIn("AbortController", self.html)                          # no fetch can hang forever
        self.assertTrue(re.search(r"sendAck\(\)", self.html))


if __name__ == "__main__":
    unittest.main()
