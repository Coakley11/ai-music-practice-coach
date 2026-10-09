"""The live playbar must always expose the fixed shape and the current capo fret.

In Capo Shape Mode the shape family the player physically holds stays fixed while
Key Cycling moves the sounding key; only the required capo fret moves. The bar
carries the fret in a ``data-kc-capo-fret`` element so the client can refresh it
on a seamless handoff without waiting for a Streamlit remount.
"""
from __future__ import annotations

import re
import unittest

from backing_key_cycle import (
    advance_key_cycle_now,
    previous_key_cycle_now,
    render_backing_key_cycle_playback_bar,
    start_key_cycle,
    temporary_playback_key,
)
from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY, capo_fret_for_shape


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _FakeSt:
    def __init__(self) -> None:
        self.html_calls: list[str] = []

    def html(self, value: str) -> None:
        self.html_calls.append(value)

    def markdown(self, *_a, **_k) -> None:
        return None

    def columns(self, count):
        return [_Ctx() for _ in range(count)]

    def button(self, *_a, **_k) -> bool:
        return False

    def rerun(self) -> None:
        return None


def _session(shape: str = "C", start: str = "Bm") -> dict:
    s = {
        "backing_source_kind": "catalog",
        "practice_key": start,
        "concert_practice_key": start,
        "instrument": "Guitar",
        CAPO_ENABLED_KEY: True,
        CAPO_SHAPE_KEY: shape,
        "_backing_key_cycle_sessions": {},
    }
    start_key_cycle(s, start_key=start, interval=1, direction="up")
    return s


def _bar(session: dict) -> tuple[str | None, int | None, str]:
    fake = _FakeSt()
    render_backing_key_cycle_playback_bar(fake, session)
    html = "\n".join(fake.html_calls)
    shape = re.search(r'ui-key-cycle-shape-tonic">([^<]*)<', html)
    fret = re.search(r'ui-key-cycle-capo-fret"[^>]*>(\d+)<', html)
    return (
        shape.group(1) if shape else None,
        int(fret.group(1)) if fret else None,
        html,
    )


class TestCapoFretDisplay(unittest.TestCase):
    def test_bar_shows_shape_and_fret(self) -> None:
        shape, fret, html = _bar(_session())
        self.assertEqual(shape, "C")
        self.assertIsNotNone(fret)
        self.assertIn("Guitar shape", html)
        self.assertIn("current capo fret", html)

    def test_shape_stays_fixed_while_fret_tracks_the_sounding_key(self) -> None:
        session = _session(shape="C")
        seen: list[tuple[str, str | None, int | None]] = []
        for _ in range(6):
            sounding = temporary_playback_key(session)
            shape, fret, _ = _bar(session)
            seen.append((sounding, shape, fret))
            advance_key_cycle_now(session)

        self.assertTrue(all(s == "C" for _k, s, _f in seen), seen)
        # The fret is whatever the capo model says for that sounding key.
        for sounding, _shape, fret in seen:
            self.assertEqual(fret, int(capo_fret_for_shape(sounding, "C")), sounding)
        # And it genuinely moves as the key cycles.
        self.assertGreater(len({f for _k, _s, f in seen}), 1, seen)

    def test_previous_updates_the_fret_too(self) -> None:
        session = _session(shape="C")
        for _ in range(3):
            advance_key_cycle_now(session)
        forward_key = temporary_playback_key(session)
        _s, forward_fret, _ = _bar(session)
        previous_key_cycle_now(session)
        back_key = temporary_playback_key(session)
        shape, back_fret, _ = _bar(session)
        self.assertEqual(shape, "C")
        self.assertNotEqual(back_key, forward_key)
        self.assertEqual(back_fret, int(capo_fret_for_shape(back_key, "C")))
        self.assertNotEqual(back_fret, forward_fret)

    def test_changing_shape_keeps_the_sounding_key(self) -> None:
        session = _session(shape="C")
        advance_key_cycle_now(session)
        sounding = temporary_playback_key(session)
        session[CAPO_SHAPE_KEY] = "G"
        shape, fret, _ = _bar(session)
        self.assertEqual(shape, "G")
        self.assertEqual(temporary_playback_key(session), sounding)
        self.assertEqual(fret, int(capo_fret_for_shape(sounding, "G")))

    def test_fret_is_client_refreshable(self) -> None:
        """The client syncs the fret on seamless handoff via these hooks."""
        _shape, _fret, html = _bar(_session())
        self.assertIn('data-kc-capo-fret="1"', html)
        self.assertIn("ui-key-cycle-shape-tonic", html)

    def test_no_capo_line_outside_shape_mode(self) -> None:
        session = _session()
        session[CAPO_ENABLED_KEY] = False
        _shape, fret, html = _bar(session)
        self.assertIsNone(fret)
        self.assertNotIn("current capo fret", html)


if __name__ == "__main__":
    unittest.main()
