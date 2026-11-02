"""An explicit user meter override survives Load Last Song / restore; a fake one is never written.

Problems fixed on top of ``tests/test_meter_restore.py`` (v2):

P1  Piano Man (3/4) explicitly set to 4/4 on the Backing page was persisted, but
    "Load Last Song" re-activates the song through
    ``songs.music_source.on_active_song_identity_changed`` (force_reset), whose
    song-change reset wiped the override (``(4/4, True)`` -> ``(3/4, False)``).
    The override is now tagged with the song it was chosen for
    (``backing_time_signature_override_song``) and put back after the reset when
    the SAME song is re-activated; another song never inherits it.
P2  ``backing_play_session.capture_backing_play_session_overrides`` compared the
    live meter with the transport default "4/4" and so recorded every 3/4 / 6/8
    catalog song as a user override (``meter_override`` True), which then leaked
    into ``backing_track_state`` / ``backing_filters``. Only the Time signature
    radio flag is evidence of a user choice for a plain catalog song.

Legacy blobs (no song tag) are honoured only when the saved meter differs from
the song's own meter and only for a cold start / same-song re-activation.
Documented residual ambiguity: an old-bug ``(4/4, True)`` on a 3/4 song looks
exactly like a real override and is therefore kept (as in v2) until the
musician resets the radio to the song meter.
"""

from __future__ import annotations

import types
import unittest

from backing_track_state import (
    BACKING_STATE_KEY,
    _apply_filters_to_session_keys,
    _normalize_filters,
    gather_backing_filters,
    prepare_backing_meter_for_widget,
)
from songs.meter_state import (
    BACKING_METER_KEY,
    BACKING_METER_OVERRIDE_KEY,
    BACKING_METER_OVERRIDE_SONG_KEY,
    apply_backing_meter_for_song,
    note_backing_meter_override,
    sync_backing_meter_override_from_widget,
)
from songs.music_source import on_active_song_identity_changed

PM = "cat::piano-man"
PERFECT = "cat::perfect"
PHOTO = "cat::photograph"


def _blob(meter, override, tag="", loops=1) -> dict:
    out = {
        "backing_track_scope": "Full song",
        "backing_track_loops": loops,
        "backing_time_signature_override": override,
        "backing_track_state_version": 1,
    }
    if meter is not None:
        out["backing_time_signature"] = meter
    if tag is not None:
        out[BACKING_METER_OVERRIDE_SONG_KEY] = tag
    return out


def _hydrated(meter, override, tag) -> dict:
    """What the app holds after a hard refresh: blob + keys seeded from it."""
    session = {BACKING_STATE_KEY: _blob(meter, override, tag)}
    _apply_filters_to_session_keys(session, _normalize_filters(session[BACKING_STATE_KEY]))
    return session


def _load_song(session: dict, *, sync_id: str, title: str, meter: str, force: bool = True):
    """Load Last Song / song pick: the real identity-change path, then the page's meter prep."""
    st = types.SimpleNamespace(session_state=session)
    on_active_song_identity_changed(
        st,
        pick_key=f"Pop\x1f{title}",
        title=title,
        artist="X",
        original_key="C",
        is_custom=False,
        sync_id=sync_id,
        default_bpm=90,
        default_groove="Pop groove",
        default_meter=meter,
        invalidate_backing=lambda _st: None,
        force_reset=force,
    )
    prepare_backing_meter_for_widget(session, default_meter=meter)
    return apply_backing_meter_for_song(st, song_id=sync_id, default_time_signature=meter)


class LoadLastSongKeepsExplicitOverride(unittest.TestCase):
    def test_piano_man_explicit_4_4_survives_load_last_song(self) -> None:
        session = _hydrated("4/4", True, PM)
        applied, override, default = _load_song(session, sync_id=PM, title="Piano Man", meter="3/4")
        self.assertEqual((applied, override, default), ("4/4", True, "3/4"))
        blob = session[BACKING_STATE_KEY]
        self.assertEqual(
            (blob["backing_time_signature"], blob["backing_time_signature_override"], blob[BACKING_METER_OVERRIDE_SONG_KEY]),
            ("4/4", True, PM),
        )

    def test_photograph_explicit_3_4_survives_load_last_song(self) -> None:
        session = _hydrated("3/4", True, PHOTO)
        applied, override, _ = _load_song(session, sync_id=PHOTO, title="Photograph", meter="4/4")
        self.assertEqual((applied, override), ("3/4", True))
        self.assertEqual(session[BACKING_STATE_KEY]["backing_time_signature"], "3/4")

    def test_override_of_another_song_is_not_inherited(self) -> None:
        session = _hydrated("4/4", True, PM)
        applied, override, _ = _load_song(session, sync_id=PERFECT, title="Perfect", meter="6/8")
        self.assertEqual((applied, override), ("6/8", False))
        self.assertFalse(session[BACKING_STATE_KEY]["backing_time_signature_override"])
        self.assertEqual(session[BACKING_STATE_KEY][BACKING_METER_OVERRIDE_SONG_KEY], "")

    def test_switch_away_and_back_clears_override(self) -> None:
        session = _hydrated("4/4", True, PM)
        _load_song(session, sync_id=PERFECT, title="Perfect", meter="6/8")
        applied, override, _ = _load_song(session, sync_id=PM, title="Piano Man", meter="3/4")
        self.assertEqual((applied, override), ("3/4", False))

    def test_reset_to_song_meter_clears_override_and_tag(self) -> None:
        session = _hydrated("4/4", True, PM)
        session[BACKING_METER_KEY] = "3/4"  # user picks the song's own meter on the radio
        choice, override = sync_backing_meter_override_from_widget(session, "3/4")
        self.assertEqual((choice, override), ("3/4", False))
        self.assertFalse(session[BACKING_METER_OVERRIDE_KEY])
        self.assertNotIn(BACKING_METER_OVERRIDE_SONG_KEY, session)
        self.assertEqual(gather_backing_filters(session)["backing_time_signature_override"], False)
        self.assertEqual(gather_backing_filters(session)[BACKING_METER_OVERRIDE_SONG_KEY], "")
        # ...and a later Load Last Song finds nothing to preserve.
        session[BACKING_STATE_KEY] = _blob("3/4", False, "")
        applied, override, _ = _load_song(session, sync_id=PM, title="Piano Man", meter="3/4")
        self.assertEqual((applied, override), ("3/4", False))

    def test_radio_choice_tags_override_with_active_song(self) -> None:
        session = {"_canonical_active_backing_song_id": PM, "_last_backing_meter_song": PM}
        st = types.SimpleNamespace(session_state=session)
        note_backing_meter_override(st, "4/4")
        self.assertEqual(session[BACKING_METER_OVERRIDE_SONG_KEY], PM)
        filters = gather_backing_filters(session)
        self.assertEqual(
            (filters["backing_time_signature"], filters["backing_time_signature_override"], filters[BACKING_METER_OVERRIDE_SONG_KEY]),
            ("4/4", True, PM),
        )

    def test_cloud_shaped_blob_round_trip_keeps_override_and_tag(self) -> None:
        from music_resume_payload import _apply_backing_payload

        session: dict = {}
        _apply_backing_payload(
            session,
            {
                "backing_time_signature": "4/4",
                "backing_time_signature_override": True,
                BACKING_METER_OVERRIDE_SONG_KEY: PM,
            },
        )
        self.assertEqual(session[BACKING_METER_KEY], "4/4")
        self.assertTrue(session[BACKING_METER_OVERRIDE_KEY])
        self.assertEqual(session[BACKING_METER_OVERRIDE_SONG_KEY], PM)

    def test_tag_is_dropped_when_there_is_no_override(self) -> None:
        self.assertEqual(_normalize_filters({"backing_time_signature_override": False, BACKING_METER_OVERRIDE_SONG_KEY: PM})[BACKING_METER_OVERRIDE_SONG_KEY], "")
        session = {BACKING_METER_OVERRIDE_SONG_KEY: PM}
        _apply_filters_to_session_keys(session, {"backing_time_signature": "4/4", "backing_time_signature_override": False})
        self.assertNotIn(BACKING_METER_OVERRIDE_SONG_KEY, session)


class LegacyBlobs(unittest.TestCase):
    def test_untagged_true_that_differs_from_song_meter_is_kept_for_same_song(self) -> None:
        # Cannot tell a real v2 override from an old-bug (4/4, True) leftover: kept, as in v2.
        session = _hydrated("4/4", True, None)
        applied, override, _ = _load_song(session, sync_id=PM, title="Piano Man", meter="3/4")
        self.assertEqual((applied, override), ("4/4", True))

    def test_untagged_true_equal_to_song_meter_has_no_effect_and_heals(self) -> None:
        for meter in ("3/4", "6/8", "4/4"):
            with self.subTest(meter=meter):
                session = _hydrated(meter, True, None)
                applied, override, _ = _load_song(session, sync_id=PM, title="Song", meter=meter)
                self.assertEqual((applied, override), (meter, False))
                self.assertFalse(session[BACKING_STATE_KEY]["backing_time_signature_override"])

    def test_untagged_true_is_not_carried_to_another_song_in_a_live_session(self) -> None:
        session = _hydrated("4/4", True, None)
        session["_active_song_identity"] = "pk::Pop\x1fPiano Man"
        from songs.music_source import ACTIVE_SONG_IDENTITY_KEY

        session[ACTIVE_SONG_IDENTITY_KEY] = "pk::Pop\x1fPiano Man"
        applied, override, _ = _load_song(session, sync_id=PERFECT, title="Perfect", meter="6/8")
        self.assertEqual((applied, override), ("6/8", False))

    def test_stale_4_4_false_and_missing_keys_song_meter_wins(self) -> None:
        for blob in (_blob("4/4", False, None), _blob(None, False, None), {}):
            with self.subTest(blob=blob):
                session = {BACKING_STATE_KEY: dict(blob)} if blob else {}
                applied, override, _ = _load_song(session, sync_id=PM, title="Piano Man", meter="3/4")
                self.assertEqual((applied, override), ("3/4", False))

    def test_invalid_saved_meter_does_not_raise(self) -> None:
        # The normaliser maps an unknown meter to 4/4 (pre-existing); it must not crash.
        session = _hydrated("7/4", True, PM)
        applied, _override, _ = _load_song(session, sync_id=PM, title="Piano Man", meter="3/4")
        self.assertIn(applied, ("3/4", "4/4"))


class WriterNeverInventsAnOverride(unittest.TestCase):
    def _play_session_meter(self, meter: str, flag: bool):
        import backing_play_session as bps

        session = {
            "active_catalog_pick_key": "Pop\x1fPiano Man",
            BACKING_METER_KEY: meter,
            BACKING_METER_OVERRIDE_KEY: flag,
            "backing_track_loops": 2,
        }
        bps.capture_backing_play_session_overrides(session, bpm=88)
        return session, bps.get_backing_play_session(session)["overrides"]

    def test_catalog_non_4_4_meter_without_user_choice_is_not_an_override(self) -> None:
        for meter in ("3/4", "6/8", "2/4", "12/8"):
            with self.subTest(meter=meter):
                session, overrides = self._play_session_meter(meter, False)
                self.assertNotIn("meter", overrides)
                self.assertNotIn("meter_override", overrides)
                prepare_backing_meter_for_widget(session, default_meter=meter)
                self.assertFalse(session[BACKING_METER_OVERRIDE_KEY])
                self.assertFalse(gather_backing_filters(session)["backing_time_signature_override"])

    def test_catalog_meter_with_radio_flag_is_an_override(self) -> None:
        session, overrides = self._play_session_meter("4/4", True)
        self.assertEqual((overrides.get("meter"), overrides.get("meter_override")), ("4/4", True))

    def test_reset_to_song_meter_drops_the_play_session_override(self) -> None:
        import backing_play_session as bps

        session, _ = self._play_session_meter("4/4", True)
        session[BACKING_METER_KEY] = "3/4"
        session[BACKING_METER_OVERRIDE_KEY] = False
        bps.capture_backing_play_session_overrides(session, bpm=88)
        overrides = bps.get_backing_play_session(session)["overrides"]
        self.assertNotIn("meter", overrides)
        self.assertNotIn("meter_override", overrides)

    def test_apply_for_song_does_not_persist_true_for_song_meter(self) -> None:
        for meter in ("3/4", "6/8"):
            with self.subTest(meter=meter):
                session: dict = {}
                st = types.SimpleNamespace(session_state=session)
                apply_backing_meter_for_song(st, song_id="cat::x", default_time_signature=meter)
                self.assertFalse(session[BACKING_METER_OVERRIDE_KEY])
                self.assertFalse(gather_backing_filters(session)["backing_time_signature_override"])


if __name__ == "__main__":
    unittest.main()
