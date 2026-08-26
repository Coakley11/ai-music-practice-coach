"""Custom Progression active-source persistence across rerun/refresh/navigation."""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from unittest import mock


def _trial_active() -> dict:
    return {
        "id": "trial-rev-1",
        "name": "Trial Song",
        "original_key_center": "D",
        "original_sections": {
            "Verse": [{"chord": "D", "bars": 1}, {"chord": "A", "bars": 1}],
            "Chorus": [],
            "Bridge": [],
            "Intro": [],
            "Outro": [],
        },
        "bpm": 96,
    }


class TestCustomActiveSourcePersistence(unittest.TestCase):
    def _custom_session(self) -> dict:
        from songs.music_source import (
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_CUSTOM,
            custom_pick_key_for,
            custom_selected_song_record,
            set_custom_source,
        )

        active = _trial_active()
        pick = custom_pick_key_for(active)
        selected = custom_selected_song_record(active)
        session = {
            "studio_page": "picker",
            "active_music_source": SOURCE_CUSTOM,
            "active_catalog_pick_key": pick,
            "selected_song": selected,
            "song": "Trial Song",
            "display_key": "D",
            "concert_key": "D",
            "cpl_active_progression": active,
            "song_picker_active_source": SONG_PICKER_SOURCE_CUSTOM,
            "active_song_state": {
                "pick_key": pick,
                "music_source": SOURCE_CUSTOM,
                "custom_progression_name": "Trial Song",
                "custom_home_key": "D",
                "selected_song": selected,
                "display_key": "D",
            },
            "sbi_preview_source": "Custom progression",
            "improv_song_source": "Custom progression",
        }
        set_custom_source(session)
        return session

    def test_01_songs_catalog_to_custom_rerun_stays_custom(self) -> None:
        from songs.music_source import (
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_CUSTOM,
            custom_progression_is_active,
            reconcile_music_picker_source_widget,
            reconcile_picker_music_source,
        )

        session = self._custom_session()
        # Simulate ordinary Streamlit rerun hydrate.
        reconcile_picker_music_source(session)
        reconcile_music_picker_source_widget(session)
        self.assertTrue(custom_progression_is_active(session))
        self.assertEqual(session["active_music_source"], SOURCE_CUSTOM)
        self.assertEqual(session["song_picker_active_source"], SONG_PICKER_SOURCE_CUSTOM)
        self.assertTrue(str(session.get("active_catalog_pick_key") or "").startswith("custom::"))

    def test_02_songs_custom_refresh_restore_stays_custom(self) -> None:
        from songs.music_source import (
            SONG_PICKER_SOURCE_CATALOG,
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_CUSTOM,
            ensure_active_music_source_from_canonical,
            reconcile_music_picker_source_widget,
        )

        session = self._custom_session()
        # Refresh often leaves/defaults the radio to catalog while blob says custom.
        session["song_picker_active_source"] = SONG_PICKER_SOURCE_CATALOG
        ensure_active_music_source_from_canonical(session)
        reconcile_music_picker_source_widget(session)
        self.assertEqual(session["active_music_source"], SOURCE_CUSTOM)
        self.assertEqual(session["song_picker_active_source"], SONG_PICKER_SOURCE_CUSTOM)
        self.assertEqual(session["cpl_active_progression"]["name"], "Trial Song")

    def test_03_creative_sbi_custom_rerun_stays_custom(self) -> None:
        from studio_page_state import flush_pending_improv_song_source, resolve_improv_song_source

        session = self._custom_session()
        session["studio_page"] = "creative"
        # Widget flaked to Active song while persisted preview is Custom.
        session["improv_song_source"] = "Active song"
        flush_pending_improv_song_source(session)
        self.assertEqual(resolve_improv_song_source(session), "Custom progression")
        self.assertEqual(session.get("improv_song_source"), "Custom progression")

    def test_04_creative_custom_refresh_keeps_same_progression(self) -> None:
        from studio_page_state import init_improvisation_state, resolve_improv_song_source

        session = self._custom_session()
        session.pop("improv_song_source", None)
        session["sbi_preview_source"] = "Custom progression"
        init_improvisation_state(session, is_custom_active=False)
        self.assertEqual(resolve_improv_song_source(session), "Custom progression")
        self.assertEqual(session["cpl_active_progression"]["name"], "Trial Song")

    def test_05_songs_custom_to_creative_opens_same_custom(self) -> None:
        from source_session_state import resolve_sbi_preview

        session = self._custom_session()
        session["studio_page"] = "creative"
        preview = resolve_sbi_preview(session)
        self.assertEqual(preview["source"], "Custom progression")
        self.assertEqual(preview["title"], "Trial Song")

    def test_06_custom_backing_nav_does_not_restore_old_catalog(self) -> None:
        from backing_source_navigation import (
            invalidate_backing_restore_for_active_source_change,
            last_valid_backing_session_survives_ordinary_nav,
        )
        from songs.music_source import SOURCE_CUSTOM, custom_progression_is_active

        love = "Country\u001fLove Story — Taylor Swift"
        session = self._custom_session()
        session["studio_page"] = "backing"
        session["_backing_context"] = {
            "source": "regular_song",
            "bound_pick_key": love,
            "active_song_id": love,
            "song_title": "Love Story",
            "key": "C",
            "display_key": "C",
            "concert_key": "C",
        }
        invalidate_backing_restore_for_active_source_change(
            session,
            previous_identity=f"pk::{love}",
            new_identity="cpl::trial-rev-1",
            reason="test_custom_source",
        )
        self.assertTrue(custom_progression_is_active(session))
        self.assertEqual(session["active_music_source"], SOURCE_CUSTOM)
        self.assertFalse(last_valid_backing_session_survives_ordinary_nav(session))

    def test_07_deliberate_custom_to_catalog_still_works(self) -> None:
        """Deliberate catalog switch uses USER_CATALOG / PENDING — not radio lag inference."""
        from songs.music_source import (
            PENDING_CATALOG_FROM_PICKER_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            reconcile_music_picker_source_widget,
        )

        session = self._custom_session()
        session[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        session[PENDING_CATALOG_FROM_PICKER_KEY] = True
        session["song_picker_active_source"] = SONG_PICKER_SOURCE_CATALOG
        reconcile_music_picker_source_widget(session)
        self.assertTrue(session.get(PENDING_CATALOG_FROM_PICKER_KEY))
        self.assertEqual(session["song_picker_active_source"], SONG_PICKER_SOURCE_CATALOG)
        # Same-run second reconcile must not heal Catalog → Custom.
        reconcile_music_picker_source_widget(session)
        self.assertTrue(session.get(PENDING_CATALOG_FROM_PICKER_KEY))
        self.assertEqual(session["song_picker_active_source"], SONG_PICKER_SOURCE_CATALOG)

    def test_07b_lagging_catalog_radio_after_custom_activate_heals(self) -> None:
        """After Set-as-Active, lagging Catalog radio must heal — not reclaim Roads (E5)."""
        from songs.music_source import (
            LAST_RECONCILED_SONG_PICKER_SOURCE_KEY,
            PENDING_CATALOG_FROM_PICKER_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_CUSTOM,
            reconcile_music_picker_source_widget,
        )

        session = self._custom_session()
        session[LAST_RECONCILED_SONG_PICKER_SOURCE_KEY] = SONG_PICKER_SOURCE_CUSTOM
        session["song_picker_active_source"] = SONG_PICKER_SOURCE_CATALOG
        reconcile_music_picker_source_widget(session)
        self.assertFalse(session.get(PENDING_CATALOG_FROM_PICKER_KEY))
        self.assertEqual(session["song_picker_active_source"], SONG_PICKER_SOURCE_CUSTOM)
        self.assertEqual(session["active_music_source"], SOURCE_CUSTOM)

    def test_08_partial_user_catalog_flag_still_queues_restore(self) -> None:
        """USER_CATALOG set while pick is still custom:: must queue catalog restore."""
        from songs.music_source import (
            EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY,
            PENDING_CATALOG_FROM_PICKER_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            reconcile_music_picker_source_widget,
        )

        session = self._custom_session()
        # Partial Catalog switch (identity still custom::) — not a Set-as-Active epoch.
        session.pop(EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY, None)
        session[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        session["song_picker_active_source"] = SONG_PICKER_SOURCE_CATALOG
        with mock.patch(
            "music_restore_phase.music_restore_phase_complete",
            return_value=True,
        ):
            reconcile_music_picker_source_widget(session)
        self.assertTrue(session.get(PENDING_CATALOG_FROM_PICKER_KEY))

    def test_09_custom_activation_clears_stale_catalog_pending(self) -> None:
        """Set-as-Active must clear PENDING catalog so disk cannot stay on Roads (E5)."""
        from songs.music_source import (
            PENDING_CATALOG_FROM_PICKER_KEY,
            PENDING_CUSTOM_ACTIVE_SONG_KEY,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            queue_custom_active_song_activation,
        )

        session = self._custom_session()
        session[PENDING_CATALOG_FROM_PICKER_KEY] = True
        session[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        st = SimpleNamespace(session_state=session)
        queue_custom_active_song_activation(st, _trial_active())
        self.assertFalse(session.get(PENDING_CATALOG_FROM_PICKER_KEY))
        self.assertFalse(session.get(USER_CATALOG_SOURCE_CHOICE_KEY))
        self.assertIsInstance(session.get(PENDING_CUSTOM_ACTIVE_SONG_KEY), dict)

    def test_12_queue_set_as_active_outranks_prior_catalog_epoch(self) -> None:
        """Country Roads pick epoch must not discard a later Set-as-Active queue (E5)."""
        import time
        from songs.music_source import (
            EXPLICIT_CATALOG_SELECTION_EPOCH_KEY,
            EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY,
            PENDING_CUSTOM_ACTIVE_SONG_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            SOURCE_CATALOG,
            SOURCE_CUSTOM,
            apply_pending_custom_active_song_activation_before_widgets,
            explicit_catalog_selection_is_authoritative,
            queue_custom_active_song_activation,
        )

        roads_pk = "Country\x1fTake Me Home, Country Roads — John Denver"
        session = {
            "studio_page": "picker",
            "active_music_source": SOURCE_CATALOG,
            "active_catalog_pick_key": roads_pk,
            "selected_song": {
                "title": "Take Me Home, Country Roads",
                "artist": "John Denver",
                "key": "A",
                "pick_key": roads_pk,
            },
            "song": "Take Me Home, Country Roads",
            "display_key": "A",
            "concert_key": "A",
            "song_picker_active_source": SONG_PICKER_SOURCE_CATALOG,
            "cpl_active_progression": _trial_active(),
            EXPLICIT_CATALOG_SELECTION_EPOCH_KEY: float(time.time()),
        }
        self.assertTrue(explicit_catalog_selection_is_authoritative(session))
        st = SimpleNamespace(session_state=session)
        queue_custom_active_song_activation(st, _trial_active())
        self.assertIsInstance(session.get(PENDING_CUSTOM_ACTIVE_SONG_KEY), dict)
        self.assertIsNotNone(session.get(EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY))
        self.assertIsNone(session.get(EXPLICIT_CATALOG_SELECTION_EPOCH_KEY))
        self.assertFalse(explicit_catalog_selection_is_authoritative(session))

        def _inv(*_a, **_k):
            return None

        with mock.patch(
            "music_state_writes.may_write_contested",
            return_value=True,
        ):
            applied = apply_pending_custom_active_song_activation_before_widgets(
                st, invalidate_backing=_inv
            )
        self.assertTrue(applied)
        self.assertEqual(session.get("active_music_source"), SOURCE_CUSTOM)
        self.assertIn("Trial Song", str(session.get("selected_song", {}).get("title") or ""))

    def test_11_stale_catalog_radio_callback_ignored_until_custom_presented(self) -> None:
        """Catalog on_change is ignored until Songs radio has presented Custom (E5)."""
        from songs.music_source import (
            EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY,
            SONG_PICKER_PRESENTED_SOURCE_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_CUSTOM,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            on_song_picker_source_change,
        )

        session = self._custom_session()
        session[EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY] = 1000.0
        session.pop(SONG_PICKER_PRESENTED_SOURCE_KEY, None)
        session["song_picker_active_source"] = SONG_PICKER_SOURCE_CATALOG
        st = SimpleNamespace(session_state=session, rerun=lambda: None)
        switched = {"n": 0}

        def _inv(*_a, **_k):
            return None

        with mock.patch(
            "songs.music_source.switch_to_catalog_from_custom",
            side_effect=lambda *_a, **_k: switched.__setitem__("n", switched["n"] + 1) or True,
        ):
            on_song_picker_source_change(
                st,
                song_picker_catalog={},
                invalidate_backing=_inv,
            )
        self.assertEqual(switched["n"], 0)
        self.assertEqual(session["active_music_source"], SOURCE_CUSTOM)
        self.assertFalse(session.get(USER_CATALOG_SOURCE_CHOICE_KEY))

        # After Custom was presented, Catalog radio is a genuine user flip.
        session[SONG_PICKER_PRESENTED_SOURCE_KEY] = SONG_PICKER_SOURCE_CUSTOM
        session["song_picker_active_source"] = SONG_PICKER_SOURCE_CATALOG
        with mock.patch(
            "songs.music_source.switch_to_catalog_from_custom",
            side_effect=lambda *_a, **_k: switched.__setitem__("n", switched["n"] + 1) or True,
        ):
            on_song_picker_source_change(
                st,
                song_picker_catalog={},
                invalidate_backing=_inv,
            )
        self.assertEqual(switched["n"], 1)

    def test_10_delayed_catalog_reclaim_after_custom_activate_blocked(self) -> None:
        """Trial green then delayed Country Roads reclaim must not win (E5 flake).

        Models: Catalog active → explicit Custom commit → persist → ordinary
        hydrate/reconcile → second reconcile → restore/recovery catalog pick.
        Explicit Catalog selection afterward must still win.
        """
        import time
        from types import SimpleNamespace

        from songs.music_source import (
            EXPLICIT_CATALOG_SELECTION_EPOCH_KEY,
            EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY,
            PENDING_CATALOG_FROM_PICKER_KEY,
            PENDING_CUSTOM_ACTIVE_SONG_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_CATALOG,
            SOURCE_CUSTOM,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            apply_pending_catalog_from_picker_before_widgets,
            apply_pending_custom_active_song_activation_before_widgets,
            commit_custom_active_song,
            custom_progression_is_active,
            explicit_catalog_selection_is_authoritative,
            explicit_custom_activation_is_authoritative,
            reconcile_music_picker_source_widget,
            reconcile_picker_music_source,
            set_catalog_source,
        )
        from songs.state import apply_pick_key, apply_saved_music_context, format_pick_key

        roads_pk = format_pick_key(
            "Country", "Take Me Home, Country Roads — John Denver"
        )
        clocks_pk = format_pick_key("Pop", "Clocks — Coldplay")
        catalog = {
            "Country": {
                "Take Me Home, Country Roads — John Denver": {
                    "title": "Take Me Home, Country Roads",
                    "artist": "John Denver",
                    "key": "A",
                }
            },
            "Pop": {
                "Clocks — Coldplay": {
                    "title": "Clocks",
                    "artist": "Coldplay",
                    "key": "Eb",
                }
            },
        }

        # Start as Catalog Country Roads.
        session = {
            "studio_page": "picker",
            "active_music_source": SOURCE_CATALOG,
            "active_catalog_pick_key": roads_pk,
            "selected_song": {
                "pick_key": roads_pk,
                "title": "Take Me Home, Country Roads",
                "artist": "John Denver",
                "key": "A",
            },
            "song_picker_active_source": SONG_PICKER_SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "_suite_last_cloud_fetch_payload": {
                "core": {"pick_key": roads_pk, "song": "Take Me Home, Country Roads"},
            },
        }
        st = SimpleNamespace(session_state=session)

        def _inv(_s=None, *_a, **_k):
            return None

        # Explicit Custom activation (Trial Song) — stamps custom epoch.
        with mock.patch("songs.state.persist_music_local_state", return_value=None), mock.patch(
            "songs.music_source.on_active_song_identity_changed", return_value=None
        ), mock.patch(
            "songs.music_source.note_active_source_change", return_value=None
        ), mock.patch(
            "active_song_state.write_canonical_active_song_state", return_value=None
        ), mock.patch(
            "global_active_song_state.sync_active_song_to_canonical", return_value=None
        ), mock.patch(
            "custom_progression_lab.prepare_cpl_backing_handoff", return_value=None
        ):
            commit_custom_active_song(st, _trial_active(), invalidate_backing=_inv)

        self.assertTrue(explicit_custom_activation_is_authoritative(session))
        self.assertTrue(custom_progression_is_active(session))
        self.assertEqual(session["active_music_source"], SOURCE_CUSTOM)
        self.assertTrue(str(session.get("active_catalog_pick_key") or "").startswith("custom::"))

        # Delayed stale reclaim attempts (1–2s window / ordinary reruns).
        session[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        session[PENDING_CATALOG_FROM_PICKER_KEY] = True
        session["song_picker_active_source"] = SONG_PICKER_SOURCE_CATALOG
        with mock.patch(
            "music_restore_phase.music_restore_phase_complete",
            return_value=True,
        ):
            reconcile_picker_music_source(session)
            reconcile_music_picker_source_widget(session)
        self.assertFalse(session.get(USER_CATALOG_SOURCE_CHOICE_KEY))
        self.assertFalse(session.get(PENDING_CATALOG_FROM_PICKER_KEY))
        self.assertEqual(session["active_music_source"], SOURCE_CUSTOM)

        session[PENDING_CATALOG_FROM_PICKER_KEY] = True
        apply_pending_catalog_from_picker_before_widgets(
            st,
            song_picker_catalog=catalog,
            invalidate_backing=_inv,
        )
        self.assertEqual(session["active_music_source"], SOURCE_CUSTOM)
        self.assertFalse(session.get(PENDING_CATALOG_FROM_PICKER_KEY))

        apply_saved_music_context(
            st,
            {"pick_key": roads_pk, "song": "Take Me Home, Country Roads"},
            song_picker_catalog=catalog,
        )
        self.assertEqual(session["active_music_source"], SOURCE_CUSTOM)
        self.assertTrue(str(session.get("active_catalog_pick_key") or "").startswith("custom::"))

        apply_pick_key(
            st,
            roads_pk,
            catalog,
            origin="restore",
            persist=False,
            skip_activity_log=True,
        )
        self.assertEqual(session["active_music_source"], SOURCE_CUSTOM)
        self.assertTrue(str(session.get("active_catalog_pick_key") or "").startswith("custom::"))

        set_catalog_source(session)
        self.assertEqual(session["active_music_source"], SOURCE_CUSTOM)

        # Second ordinary hydrate still Custom.
        reconcile_picker_music_source(session)
        reconcile_music_picker_source_widget(session)
        self.assertTrue(custom_progression_is_active(session))
        self.assertEqual(session.get("song_picker_active_source"), SONG_PICKER_SOURCE_CUSTOM)

        # Explicit Catalog selection afterward legitimately wins.
        session[EXPLICIT_CATALOG_SELECTION_EPOCH_KEY] = float(time.time()) + 1.0
        session[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        self.assertFalse(explicit_custom_activation_is_authoritative(session))
        self.assertTrue(explicit_catalog_selection_is_authoritative(session))
        # Queued Custom pending must not reclaim Trial after Catalog epoch wins.
        session[PENDING_CUSTOM_ACTIVE_SONG_KEY] = {"cpl_active_key": "cpl_active_progression"}
        apply_pending_custom_active_song_activation_before_widgets(st, invalidate_backing=_inv)
        self.assertFalse(session.get(PENDING_CUSTOM_ACTIVE_SONG_KEY))
        with mock.patch(
            "music_state_writes.may_write_contested",
            return_value=True,
        ):
            apply_pick_key(st, clocks_pk, catalog, origin="user", persist=False)
        self.assertEqual(session["active_music_source"], SOURCE_CATALOG)
        self.assertIn("Clocks", str(session.get("selected_song", {}).get("title") or ""))
        self.assertTrue(explicit_catalog_selection_is_authoritative(session))
        self.assertFalse(explicit_custom_activation_is_authoritative(session))


if __name__ == "__main__":
    unittest.main()
