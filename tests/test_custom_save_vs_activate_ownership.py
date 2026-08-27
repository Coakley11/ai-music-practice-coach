"""Catalog vs saved Custom vs Global Active — four blocking Human QA invariants.

Saved Custom library selection, Custom page editor/view state, and globally
active song are separate. Only explicit Set as Active may claim Global Active.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from custom_progression_lab import (
    CPL_ACTIVE_KEY,
    CPL_SAVED_KEY,
    cpl_workspace_practice_key,
    prepare_custom_workspace_sidebar_display_key,
    save_progression,
)
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY,
    LAST_CUSTOM_STATE_KEY,
    SONG_PICKER_ACTIVE_SOURCE_KEY,
    SONG_PICKER_PRESENTED_SOURCE_KEY,
    SONG_PICKER_SOURCE_CATALOG,
    SONG_PICKER_SOURCE_CUSTOM,
    SONG_PICKER_USER_TAB_AT_KEY,
    SONG_PICKER_USER_TAB_KEY,
    SOURCE_CATALOG,
    SOURCE_CUSTOM,
    USER_CATALOG_SOURCE_CHOICE_KEY,
    commit_custom_active_song,
    custom_pick_key_for,
    custom_progression_is_active,
    music_picker_shows_custom_hub,
    on_song_picker_source_change,
    prepare_songs_picker_entry,
    promote_last_custom_for_picker_entry,
    reconcile_music_picker_source_widget,
    reconcile_picker_music_source,
    snapshot_last_custom_state,
    switch_to_catalog_from_custom,
)
from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY, get_practice_concert_key
from studio_nav_history import navigate_studio_page
from tests.test_custom_to_catalog_owner_switch import (
    CATALOG,
    PK_SHAPE,
    _shape_catalog_session,
    _trial_active,
)


def _st(session: dict) -> SimpleNamespace:
    return SimpleNamespace(session_state=session, rerun=lambda: None)


def _refresh(session: dict) -> None:
    """Rerun/refresh hydrate used by Songs + Custom page."""
    reconcile_picker_music_source(session)
    reconcile_music_picker_source_widget(session)


def _assert_shape_catalog_owner(test: unittest.TestCase, session: dict, *, practice_key: str) -> None:
    test.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
    test.assertFalse(custom_progression_is_active(session))
    test.assertEqual(session.get("song"), "Shape of You")
    test.assertEqual(session.get("active_catalog_pick_key"), PK_SHAPE)
    test.assertEqual(str(session.get("display_key") or ""), practice_key)
    selected = session.get("selected_song") or {}
    test.assertEqual(str(selected.get("title") or session.get("song") or ""), "Shape of You")


def _assert_trial_custom_owner(test: unittest.TestCase, session: dict) -> None:
    test.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
    test.assertTrue(custom_progression_is_active(session))
    test.assertIn("Trial Song", str(session.get("song") or ""))
    test.assertEqual(str(session.get("display_key") or ""), "D")
    test.assertEqual(
        get_practice_concert_key(session, custom_pick_key_for(_trial_active())),
        "D",
    )


def _persist_reboot_hydrate(session: dict) -> dict:
    """Hard-reboot-shaped restore: persist envelope + Songs hydrate only."""
    restored = {
        ACTIVE_MUSIC_SOURCE_KEY: session.get(ACTIVE_MUSIC_SOURCE_KEY),
        "song": session.get("song"),
        "active_song_title": session.get("active_song_title"),
        "active_catalog_pick_key": session.get("active_catalog_pick_key"),
        "selected_song": dict(session.get("selected_song") or {}),
        "display_key": session.get("display_key"),
        "concert_key": session.get("concert_key"),
        SONG_PICKER_ACTIVE_SOURCE_KEY: session.get(SONG_PICKER_ACTIVE_SOURCE_KEY),
        SONG_PICKER_PRESENTED_SOURCE_KEY: session.get(SONG_PICKER_PRESENTED_SOURCE_KEY),
        SONG_PICKER_USER_TAB_KEY: session.get(SONG_PICKER_USER_TAB_KEY),
        LAST_CUSTOM_STATE_KEY: dict(session.get(LAST_CUSTOM_STATE_KEY) or {}),
        CPL_ACTIVE_KEY: dict(session.get(CPL_ACTIVE_KEY) or {}),
        CPL_SAVED_KEY: dict(session.get(CPL_SAVED_KEY) or {}),
        PRACTICE_KEY_BY_SOURCE_KEY: dict(session.get(PRACTICE_KEY_BY_SOURCE_KEY) or {}),
        "studio_page": "picker",
        "_reconcile_song_picker_catalog": CATALOG,
        "active_song_state": dict(session.get("active_song_state") or {}),
    }
    epoch = session.get(EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY)
    if epoch is not None:
        restored[EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY] = epoch
    tab_at = session.get(SONG_PICKER_USER_TAB_AT_KEY)
    if tab_at is not None:
        restored[SONG_PICKER_USER_TAB_AT_KEY] = tab_at
    _refresh(restored)
    return restored


def _save_trial_without_activating(session: dict) -> dict:
    active = _trial_active()
    session[CPL_ACTIVE_KEY] = active
    session.setdefault(CPL_SAVED_KEY, {})
    save_progression(session[CPL_SAVED_KEY], "Trial Song", active)
    snapshot_last_custom_state(session)
    return active


class TestCustomSaveVsActivateOwnership(unittest.TestCase):
    def test_save_custom_without_set_as_active_keeps_catalog_owner(self) -> None:
        session = _shape_catalog_session(practice_key="Bm")
        session["studio_page"] = "custom"
        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        _save_trial_without_activating(session)
        self.assertIn("Trial Song", session.get(CPL_SAVED_KEY) or {})
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
        self.assertFalse(custom_progression_is_active(session))
        self.assertEqual(session.get("song"), "Shape of You")
        self.assertEqual(session.get("active_catalog_pick_key"), PK_SHAPE)

        navigate_studio_page(session, "picker")
        _refresh(session)
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
        self.assertFalse(custom_progression_is_active(session))
        self.assertEqual(session.get("song"), "Shape of You")
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CATALOG)
        self.assertIsNone(session.get("_pending_custom_active_song_activation"))
        last = session.get(LAST_CUSTOM_STATE_KEY) or {}
        self.assertEqual(str((last.get("active") or {}).get("name") or ""), "Trial Song")

    def test_custom_page_return_uses_original_d_without_seizing_ga(self) -> None:
        session = _shape_catalog_session(practice_key="G")
        session["studio_page"] = "custom"
        session["display_key"] = "G"
        session["concert_key"] = "G"
        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        active = _save_trial_without_activating(session)
        snapshot_last_custom_state(session)
        navigate_studio_page(session, "picker")
        _refresh(session)
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)

        session["studio_page"] = "custom"
        session["display_key"] = "G"
        session["concert_key"] = "G"
        session["custom_workspace_practice_key"] = "G"
        prepare_custom_workspace_sidebar_display_key(_st(session), session)
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
        self.assertFalse(custom_progression_is_active(session))
        self.assertEqual(cpl_workspace_practice_key(session, active), "D")
        self.assertEqual(session.get("custom_workspace_practice_key"), "D")
        self.assertEqual(session.get("song"), "Shape of You")
        self.assertEqual(session.get("display_key"), "G")

    def test_first_render_after_each_nav_keeps_shape_bm_and_trial_local_d(self) -> None:
        """Human QA: no transient Trial D on Shape, and Custom first render is local D.

        Capture state immediately after each navigation/hydrate — before refresh.
        """
        session = _shape_catalog_session(practice_key="Bm")
        session["studio_page"] = "custom"
        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        active = _save_trial_without_activating(session)

        prepare_custom_workspace_sidebar_display_key(_st(session), session)
        _assert_shape_catalog_owner(self, session, practice_key="Bm")
        self.assertEqual(cpl_workspace_practice_key(session, active), "D")
        self.assertEqual(session.get("custom_workspace_practice_key"), "D")
        self.assertEqual(get_practice_concert_key(session, PK_SHAPE), "Bm")

        navigate_studio_page(session, "picker")
        _assert_shape_catalog_owner(self, session, practice_key="Bm")
        self.assertEqual(get_practice_concert_key(session, PK_SHAPE), "Bm")
        self.assertNotEqual(str(session.get("display_key") or ""), "D")

        _refresh(session)
        _assert_shape_catalog_owner(self, session, practice_key="Bm")

        restored = _persist_reboot_hydrate(session)
        _assert_shape_catalog_owner(self, restored, practice_key="Bm")

        session["studio_page"] = "custom"
        session["custom_workspace_practice_key"] = "Bm"
        prepare_custom_workspace_sidebar_display_key(_st(session), session)
        _assert_shape_catalog_owner(self, session, practice_key="Bm")
        self.assertEqual(cpl_workspace_practice_key(session, active), "D")
        self.assertEqual(session.get("custom_workspace_practice_key"), "D")
        self.assertFalse(custom_progression_is_active(session))

        prepare_custom_workspace_sidebar_display_key(_st(session), session)
        _assert_shape_catalog_owner(self, session, practice_key="Bm")
        self.assertEqual(session.get("custom_workspace_practice_key"), "D")

    def test_leaked_trial_d_restored_on_first_songs_nav_before_refresh(self) -> None:
        """Even if Custom overlay already wrote D, Custom→Songs restores Shape Bm now."""
        session = _shape_catalog_session(practice_key="Bm")
        session["studio_page"] = "custom"
        _save_trial_without_activating(session)
        session["display_key"] = "D"
        session["concert_key"] = "D"
        navigate_studio_page(session, "picker")
        _assert_shape_catalog_owner(self, session, practice_key="Bm")
        self.assertEqual(get_practice_concert_key(session, PK_SHAPE), "Bm")

    def test_explicit_set_as_active_from_catalog_uses_trial_original_d(self) -> None:
        session = _shape_catalog_session(practice_key="G")
        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        _save_trial_without_activating(session)
        navigate_studio_page(session, "picker")
        self.assertEqual(session.get("display_key"), "G")
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)

        with patch("songs.state.persist_music_local_state"):
            commit_custom_active_song(
                _st(session),
                _trial_active(),
                invalidate_backing=lambda *_a, **_k: None,
            )
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        self.assertTrue(custom_progression_is_active(session))
        self.assertIn("Trial Song", str(session.get("song") or ""))
        self.assertEqual(str(session.get("display_key") or ""), "D")
        self.assertEqual(
            get_practice_concert_key(session, custom_pick_key_for(_trial_active())),
            "D",
        )
        session["studio_page"] = "custom"
        navigate_studio_page(session, "picker")
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)

    def test_trial_active_songs_tabs_stay_navigable(self) -> None:
        session = _shape_catalog_session(practice_key="Bm")
        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        with patch("songs.state.persist_music_local_state"):
            commit_custom_active_song(
                _st(session),
                _trial_active(),
                invalidate_backing=lambda *_a, **_k: None,
            )
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)
        session[SONG_PICKER_PRESENTED_SOURCE_KEY] = SONG_PICKER_SOURCE_CUSTOM
        session["_last_reconciled_song_picker_source"] = SONG_PICKER_SOURCE_CUSTOM
        session["studio_page"] = "picker"

        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        on_song_picker_source_change(
            _st(session),
            song_picker_catalog=CATALOG,
            invalidate_backing=lambda *_a, **_k: None,
        )
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        self.assertTrue(custom_progression_is_active(session))
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CATALOG)
        self.assertFalse(music_picker_shows_custom_hub(session))

        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CUSTOM
        on_song_picker_source_change(
            _st(session),
            song_picker_catalog=CATALOG,
            invalidate_backing=lambda *_a, **_k: None,
        )
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)
        self.assertTrue(music_picker_shows_custom_hub(session))

        session["_catalog_owns_until_custom_click"] = True
        reconcile_picker_music_source(session)
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)

    def test_refresh_after_each_transition_preserves_owner_and_tab(self) -> None:
        session = _shape_catalog_session(practice_key="Bm")
        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        _save_trial_without_activating(session)
        navigate_studio_page(session, "picker")
        _refresh(session)
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CATALOG)
        self.assertEqual(session.get("song"), "Shape of You")

        with patch("songs.state.persist_music_local_state"):
            commit_custom_active_song(
                _st(session),
                _trial_active(),
                invalidate_backing=lambda *_a, **_k: None,
            )
        session[SONG_PICKER_PRESENTED_SOURCE_KEY] = SONG_PICKER_SOURCE_CUSTOM
        _refresh(session)
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)
        self.assertEqual(str(session.get("display_key") or ""), "D")
        self.assertIn("Trial Song", str(session.get("song") or ""))

        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        on_song_picker_source_change(
            _st(session),
            song_picker_catalog=CATALOG,
            invalidate_backing=lambda *_a, **_k: None,
        )
        _refresh(session)
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CATALOG)
        self.assertIn("Trial Song", str(session.get("song") or ""))

    def test_creative_to_songs_remounts_custom_tab_without_catalog_default(self) -> None:
        """Creative → Songs after Set as Active must remount Custom, not Catalog default."""
        session = _shape_catalog_session(practice_key="G")
        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        with patch("songs.state.persist_music_local_state"):
            commit_custom_active_song(
                _st(session),
                _trial_active(),
                invalidate_backing=lambda *_a, **_k: None,
            )
        self.assertEqual(session.get(SONG_PICKER_USER_TAB_KEY), SONG_PICKER_SOURCE_CUSTOM)
        # Persist / Streamlit remount restores Catalog radio + presented Catalog.
        session["studio_page"] = "creative"
        session["_script_run_seq"] = 20
        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        session[SONG_PICKER_PRESENTED_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        navigate_studio_page(session, "picker")
        _refresh(session)
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)
        self.assertTrue(music_picker_shows_custom_hub(session))
        self.assertIn("Trial Song", str(session.get("song") or ""))

        # Widget remount on_change must not keep the Catalog default.
        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        on_song_picker_source_change(
            _st(session),
            song_picker_catalog=CATALOG,
            invalidate_backing=lambda *_a, **_k: None,
        )
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)

        # After Custom actually presented, a later Catalog click stays on Catalog.
        session["_script_run_seq"] = 25
        session.pop("_songs_expect_custom_radio", None)
        session[SONG_PICKER_PRESENTED_SOURCE_KEY] = SONG_PICKER_SOURCE_CUSTOM
        session["_last_reconciled_song_picker_source"] = SONG_PICKER_SOURCE_CUSTOM
        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        on_song_picker_source_change(
            _st(session),
            song_picker_catalog=CATALOG,
            invalidate_backing=lambda *_a, **_k: None,
        )
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CATALOG)
        self.assertFalse(music_picker_shows_custom_hub(session))

        session["studio_page"] = "creative"
        session["_script_run_seq"] = 30
        navigate_studio_page(session, "picker")
        _refresh(session)
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CATALOG)

    def test_persist_catalog_radio_after_set_as_active_heals_without_user_tab(self) -> None:
        session = _shape_catalog_session(practice_key="G")
        with patch("songs.state.persist_music_local_state"):
            commit_custom_active_song(
                _st(session),
                _trial_active(),
                invalidate_backing=lambda *_a, **_k: None,
            )
        session["studio_page"] = "picker"
        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        session[SONG_PICKER_PRESENTED_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        prepare_songs_picker_entry(session)
        _refresh(session)
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)

    def test_hard_reboot_does_not_activate_merely_saved_custom(self) -> None:
        session = _shape_catalog_session(practice_key="Bm")
        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        _save_trial_without_activating(session)
        snapshot_last_custom_state(session)
        promote_last_custom_for_picker_entry(session)

        restored = {
            ACTIVE_MUSIC_SOURCE_KEY: session.get(ACTIVE_MUSIC_SOURCE_KEY),
            "song": session.get("song"),
            "active_song_title": session.get("active_song_title"),
            "active_catalog_pick_key": session.get("active_catalog_pick_key"),
            "selected_song": dict(session.get("selected_song") or {}),
            "display_key": session.get("display_key"),
            SONG_PICKER_ACTIVE_SOURCE_KEY: session.get(SONG_PICKER_ACTIVE_SOURCE_KEY),
            LAST_CUSTOM_STATE_KEY: dict(session.get(LAST_CUSTOM_STATE_KEY) or {}),
            CPL_ACTIVE_KEY: dict(session.get(CPL_ACTIVE_KEY) or {}),
            CPL_SAVED_KEY: dict(session.get(CPL_SAVED_KEY) or {}),
            PRACTICE_KEY_BY_SOURCE_KEY: dict(session.get(PRACTICE_KEY_BY_SOURCE_KEY) or {}),
            "studio_page": "picker",
            "_reconcile_song_picker_catalog": CATALOG,
        }
        self.assertNotIn(EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY, restored)
        self.assertFalse(restored.get(USER_CATALOG_SOURCE_CHOICE_KEY))
        _refresh(restored)
        self.assertEqual(restored.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
        self.assertFalse(custom_progression_is_active(restored))
        self.assertEqual(restored.get("song"), "Shape of You")
        self.assertEqual(restored.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CATALOG)
        self.assertIn("Trial Song", restored.get(CPL_SAVED_KEY) or {})

    def test_save_only_lifecycle_keeps_shape_after_rerun_refresh_reboot(self) -> None:
        session = _shape_catalog_session(practice_key="Bm")
        session["studio_page"] = "custom"
        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        _save_trial_without_activating(session)
        navigate_studio_page(session, "picker")
        for _ in range(3):
            _refresh(session)
        _assert_shape_catalog_owner(self, session, practice_key="Bm")
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CATALOG)
        self.assertFalse(music_picker_shows_custom_hub(session))

        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CUSTOM
        on_song_picker_source_change(
            _st(session),
            song_picker_catalog=CATALOG,
            invalidate_backing=lambda *_a, **_k: None,
        )
        _refresh(session)
        _assert_shape_catalog_owner(self, session, practice_key="Bm")
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)
        self.assertTrue(music_picker_shows_custom_hub(session))

        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        on_song_picker_source_change(
            _st(session),
            song_picker_catalog=CATALOG,
            invalidate_backing=lambda *_a, **_k: None,
        )
        _refresh(session)
        _assert_shape_catalog_owner(self, session, practice_key="Bm")
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CATALOG)

        restored = _persist_reboot_hydrate(session)
        _assert_shape_catalog_owner(self, restored, practice_key="Bm")
        self.assertEqual(restored.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CATALOG)
        self.assertIn("Trial Song", restored.get(CPL_SAVED_KEY) or {})
        self.assertIsNone(restored.get(EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY))

    def test_set_as_active_lifecycle_keeps_trial_d_after_rerun_refresh_reboot(self) -> None:
        session = _shape_catalog_session(practice_key="G")
        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        _save_trial_without_activating(session)
        with patch("songs.state.persist_music_local_state"):
            commit_custom_active_song(
                _st(session),
                _trial_active(),
                invalidate_backing=lambda *_a, **_k: None,
            )
        session["studio_page"] = "custom"
        navigate_studio_page(session, "picker")
        for _ in range(3):
            _refresh(session)
        _assert_trial_custom_owner(self, session)
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)
        self.assertTrue(music_picker_shows_custom_hub(session))

        restored = _persist_reboot_hydrate(session)
        _assert_trial_custom_owner(self, restored)
        self.assertEqual(restored.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)
        self.assertTrue(music_picker_shows_custom_hub(restored))

    def test_explicit_shape_after_trial_restores_own_state_without_trial_leak(self) -> None:
        session = _shape_catalog_session(practice_key="G")
        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        with patch("songs.state.persist_music_local_state"):
            commit_custom_active_song(
                _st(session),
                _trial_active(),
                invalidate_backing=lambda *_a, **_k: None,
            )
        _assert_trial_custom_owner(self, session)
        with patch("songs.state.persist_music_local_state"):
            ok = switch_to_catalog_from_custom(
                _st(session),
                song_picker_catalog=CATALOG,
                invalidate_backing=lambda *_a, **_k: None,
            )
        self.assertTrue(ok)
        _refresh(session)
        _assert_shape_catalog_owner(self, session, practice_key="Bm")
        self.assertNotEqual(str(session.get("display_key") or ""), "D")
        self.assertNotIn("Trial Song", str(session.get("song") or ""))
        last = session.get(LAST_CUSTOM_STATE_KEY) or {}
        self.assertEqual(str((last.get("active") or {}).get("name") or ""), "Trial Song")

    def test_widget_safe_false_landing_does_not_oscillate_catalog_custom(self) -> None:
        session = _shape_catalog_session(practice_key="Bm")
        session["_streamlit_widgets_locked_this_run"] = True
        session["_script_run_seq"] = 8
        with patch("songs.state.persist_music_local_state"):
            commit_custom_active_song(
                _st(session),
                _trial_active(),
                invalidate_backing=lambda *_a, **_k: None,
            )
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)
        seen = []
        for seq in (9, 10, 11):
            session["_script_run_seq"] = seq
            session["_streamlit_widgets_locked_this_run"] = True
            _refresh(session)
            seen.append(
                (
                    session.get(ACTIVE_MUSIC_SOURCE_KEY),
                    session.get(SONG_PICKER_ACTIVE_SOURCE_KEY),
                )
            )
        self.assertEqual(
            seen,
            [
                (SOURCE_CUSTOM, SONG_PICKER_SOURCE_CUSTOM),
                (SOURCE_CUSTOM, SONG_PICKER_SOURCE_CUSTOM),
                (SOURCE_CUSTOM, SONG_PICKER_SOURCE_CUSTOM),
            ],
        )
        self.assertNotIn("_pending_song_picker_active_source", session)


if __name__ == "__main__":
    unittest.main()
