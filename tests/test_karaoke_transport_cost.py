"""Karaoke Play / Skip reach audio in one Backing run, without full-WAV work.

Measured Cloud-like (Streamlit 1.61, base path, 20 Mbit/s): a Skip took three
full Backing runs, the outgoing song stayed on screen 10-17 s and first audio
came 17-27 s after the click. Each run also paid for copying the whole session
state dozens of times (``session_state or {}`` in the Karaoke helpers calls
SessionStateProxy.__len__), and the Lead Sheet re-read and base64-encoded the
take every rerun before handing the player a URL anyway.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import karaoke_mode as km

APP = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")


class _ProxyLike:
    """Mapping with st.session_state's cost profile: any size / truth test fails."""

    def __init__(self, data: dict) -> None:
        self._d = dict(data)

    def get(self, key, default=None):
        return self._d.get(key, default)

    def __getitem__(self, key):
        return self._d[key]

    def __setitem__(self, key, value):
        self._d[key] = value

    def __contains__(self, key):
        return key in self._d

    def pop(self, key, default=None):
        return self._d.pop(key, default)

    def setdefault(self, key, default=None):
        return self._d.setdefault(key, default)

    def __len__(self):
        raise AssertionError("session truth test copies the whole session state")

    def __bool__(self):
        raise AssertionError("session truth test copies the whole session state")


class KaraokeHelpersDoNotCopySessionTests(unittest.TestCase):
    def _session(self) -> _ProxyLike:
        plain: dict = {"instrument": "Voice"}
        km.add_to_queue(plain, "Pop\x1fShallow", title="Shallow", practice_key="G", bpm=96)
        km.add_to_queue(plain, "Jazz\x1fAutumn Leaves", title="Autumn Leaves", practice_key="Bm", bpm=120)
        km.start_session(plain)
        return _ProxyLike(plain)

    def test_now_singing_helpers_never_take_the_session_truth_value(self) -> None:
        ss = self._session()
        self.assertTrue(km.is_voice_mode(ss))
        self.assertTrue(km.is_karaoke_session_active(ss))
        self.assertEqual(len(km.get_queue(ss)), 2)
        self.assertEqual(km.current_session_pick_key(ss), "Pop\x1fShallow")
        self.assertEqual((km.current_session_entry(ss) or {}).get("title"), "Shallow")
        km.reconcile_karaoke_session_after_restore(ss)
        km.countdown_enabled(ss)
        km.effective_catalog_pick_key(ss)

    def test_none_and_empty_sessions_still_answer(self) -> None:
        self.assertFalse(km.is_voice_mode(None))
        self.assertFalse(km.is_karaoke_session_active(None))
        self.assertEqual(km.get_queue(None), [])
        km.reconcile_karaoke_session_after_restore({})
        km.reconcile_karaoke_session_after_restore(None)


def _between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


class LongTakeDeliveryTests(unittest.TestCase):
    def test_generation_does_not_base64_the_take(self) -> None:
        generation = APP.split("_wav_pending = False", 1)[1].split("if _play_clicked:", 1)[0]
        self.assertNotIn("prepare_wav_b64(", generation)

    def test_sheet_resolves_the_url_before_touching_bytes(self) -> None:
        block = _between(APP, "_ls_wav = b\"\"\n        _ls_b64 = \"\"\n        _ls_url = \"\"", "_karaoke_identity_trace(\n                st.session_state,\n                \"player_mount\"")
        fallback = block.index("if not _ls_url:\n                _ls_wav = load_backing_wav_bytes")
        self.assertLess(block.index("_ls_publish(_ls_path"), fallback)
        self.assertLess(block.index('_ls_url = _kr_static'), fallback)
        self.assertNotIn("prepare_wav_b64(", block[:fallback])
        # The base64 string is never parked in session for the next rerun.
        self.assertNotIn('st.session_state["_last_backing_wav_b64"] =', APP)


class KaraokeDestinationMountsInItsOwnRunTests(unittest.TestCase):
    def test_auto_generate_falls_through_to_the_player(self) -> None:
        block = _between(APP, "if _play_needs_generate or _karaoke_auto_gen or _cycle_continue_play:\n                    st.session_state[BACKING_AUTOPLAY] = True", "if _play_clicked:")
        karaoke = _between(block, "if _karaoke_auto_gen and not (_play_needs_generate or _cycle_continue_play):", "else:")
        self.assertNotIn("st.rerun()", karaoke)
        # The one-shot play request is consumed here, not by a later rerun after Stop.
        self.assertIn('st.session_state.pop("_backing_play_request", None)', karaoke)
        self.assertIn("st.rerun()", block[block.index("else:"):])


if __name__ == "__main__":
    unittest.main()
