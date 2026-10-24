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


class DestinationShownOnClickTests(unittest.TestCase):
    """The outgoing song must not stay on screen while the Skip run works."""

    def test_marker_names_the_neighbouring_entry(self) -> None:
        import html as _html

        from karaoke_ui import karaoke_transition_dest_marker

        entry = {"entry_id": "e2", "title": 'Blues "in" F minor', "artist": "Your progression",
                 "practice_key": "Fm", "bpm": 120, "source": "custom_progression"}
        marker = karaoke_transition_dest_marker("next", entry)
        self.assertIn('class="ui-karaoke-transition-dest" hidden', marker)
        for attr in ('data-dir="next"', 'data-entry="e2"', 'data-key="Fm"', 'data-bpm="120"',
                     'data-source="Custom progression"', f'data-title="{_html.escape(entry["title"], quote=True)}"'):
            self.assertIn(attr, marker)
        catalog = karaoke_transition_dest_marker("previous", {"entry_id": "e1", "title": "Shallow", "source": "catalog_song"})
        self.assertIn('data-source="Catalog song"', catalog)
        self.assertIn('data-bpm=""', catalog)

    def test_skip_controls_render_both_neighbours(self) -> None:
        import inspect

        from karaoke_ui import render_karaoke_skip_controls

        src = inspect.getsource(render_karaoke_skip_controls)
        self.assertIn('(("next", _idx + 1), ("previous", _idx - 1))', src)
        self.assertIn("st.markdown(_dest_markers, unsafe_allow_html=True)", src)

    def test_card_transport_knows_which_entry_it_renders(self) -> None:
        self.assertIn("now_singing=_now_singing,", APP)
        js = (Path(__file__).resolve().parents[1] / "backing_transport_component" / "index.html").read_text(encoding="utf-8")
        # Shown on the Next / Previous click, lifted only by the destination's own render.
        self.assertIn('showTransitionDest(dir === "previous" ? "previous" : "next");', js)
        self.assertIn("if (dest && args.now_singing && args.now_singing === dest.entry) clearDest();", js)
        # Drawn on the parent body, never inside Streamlit's React tree.
        self.assertIn("pdoc.body.appendChild(o);", js)


if __name__ == "__main__":
    unittest.main()
