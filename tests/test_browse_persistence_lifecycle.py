"""Regression tests: Browse filters (Search, Genres, Favorites, Clear Filters)
must all participate in the same page-scoped snapshot/restore lifecycle, so a
reload/reconnect can never silently resurrect stale Browse state or lose a
just-applied Clear Filters / Favorites-toggle change.

Also covers the deeper root cause found while verifying that lifecycle live:
``should_suppress_music_workspace_save`` treats ``startup_fingerprint_matches``
(a one-time "does the just-hydrated state equal what we built at startup"
signal) as grounds to skip every later ``autosave``-reasoned save for the rest
of the session, even once the live content fingerprint has already proven
something genuinely changed. This silently dropped Browse filter changes
(Search/Genre/Favorites/Clear Filters all save with reason="autosave") before
they ever reached disk, regardless of the page-snapshot fix above.

And a third root cause, found verifying the same-session page-revisit path
(PAGE-REVISIT-1): Streamlit drops a widget-bound session_state key once its
widget is no longer rendered on a run (e.g. navigating from Songs to another
page). ``handle_studio_page_transition`` snapshots the departing page right
then, so ``capture_page_snapshot`` saw the key already gone and silently
overwrote an already-correct earlier snapshot (the search commit's own save)
with one missing the value entirely. On return, the touch guard then refused
to restore it, reading "user touched this, trust the live value" when the
live value no longer existed at all.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from songs.picker_session import (
    CATALOG_FAVORITES_KEY,
    FAVORITES_ONLY_USER_TOUCHED_KEY,
    SONG_PICKER_FAVORITES_ONLY_KEY,
    SONG_SEARCH_TEXT_KEY,
    SONG_SEARCH_USER_TOUCHED_KEY,
    WORKSPACE_GENRE_FILTERS_KEY,
    apply_picker_session_resets,
    request_clear_browse_filters,
    toggle_catalog_favorite,
    toggle_favorites_filter,
    toggle_genre_filter,
)
from songs.state import ACTIVE_CATALOG_PICK_KEY
from studio_page_persistence import (
    _PAGE_LOCAL_KEYS,
    _PAGE_SNAPSHOT_USER_TOUCH_GUARDS,
    _PAGE_SNAPSHOTS_KEY,
    restore_page_snapshot,
    save_page_snapshot,
)


def _picker_snapshot(state: dict) -> dict:
    return (state.get(_PAGE_SNAPSHOTS_KEY) or {}).get("picker") or {}


def test_favorites_only_is_page_local_and_guarded():
    assert SONG_PICKER_FAVORITES_ONLY_KEY in _PAGE_LOCAL_KEYS["picker"]
    assert (
        _PAGE_SNAPSHOT_USER_TOUCH_GUARDS.get(SONG_PICKER_FAVORITES_ONLY_KEY)
        == FAVORITES_ONLY_USER_TOUCHED_KEY
    )


def test_toggle_favorites_filter_writes_picker_page_snapshot():
    state: dict = {}
    toggle_favorites_filter(state)
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is True
    assert _picker_snapshot(state).get(SONG_PICKER_FAVORITES_ONLY_KEY) is True

    toggle_favorites_filter(state)
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is False
    assert _picker_snapshot(state).get(SONG_PICKER_FAVORITES_ONLY_KEY) is False


def test_request_clear_browse_filters_writes_picker_page_snapshot():
    state: dict = {
        SONG_SEARCH_TEXT_KEY: "Sheeran",
        WORKSPACE_GENRE_FILTERS_KEY: ["Jazz"],
        SONG_PICKER_FAVORITES_ONLY_KEY: True,
    }
    request_clear_browse_filters(state)
    snap = _picker_snapshot(state)
    assert snap.get(WORKSPACE_GENRE_FILTERS_KEY) == []
    assert snap.get(SONG_PICKER_FAVORITES_ONLY_KEY) is False
    # Search text is only actually blanked one rerun later (apply_picker_session_resets,
    # mirroring the widget-apply ordering in the real app) — closing that gap is what
    # apply_picker_session_resets' own save_page_snapshot call is for.
    apply_picker_session_resets(state)
    snap = _picker_snapshot(state)
    assert state[SONG_SEARCH_TEXT_KEY] == ""
    assert snap.get(SONG_SEARCH_TEXT_KEY) == ""


def test_stale_favorites_only_cannot_resurrect_after_turned_off():
    """A reload/reconnect must not bring back a stale Favorites-ON value once the
    user has explicitly turned it off this session (same touch-guard pattern as
    Search and Genre filters)."""
    state: dict = {SONG_PICKER_FAVORITES_ONLY_KEY: True}
    # Simulate a stale on-disk snapshot saved before the merge (Favorites stuck ON).
    save_page_snapshot(state, "picker")

    toggle_favorites_filter(state)  # user turns it OFF
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is False

    # Simulate any later page-snapshot restore attempt (e.g. a subsequent hydration).
    restore_page_snapshot(state, "picker")
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is False


def test_stale_favorites_only_true_round_trips_without_contradictory_state():
    """STALE-1: a persisted snapshot that already has Favorites ON hydrates cleanly
    (no leftover contradictory global/page-local split)."""
    state: dict = {}
    save_page_snapshot({SONG_PICKER_FAVORITES_ONLY_KEY: True, **state}, "picker")
    seeded_snapshot = {SONG_PICKER_FAVORITES_ONLY_KEY: True}
    state[_PAGE_SNAPSHOTS_KEY] = {"picker": seeded_snapshot}

    restore_page_snapshot(state, "picker")
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is True
    # Page-local, not a bare untouched global: a later explicit OFF still wins.
    toggle_favorites_filter(state)
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is False


def test_clear_filters_then_reset_leaves_no_stale_state_after_restore():
    """STALE-4 core assertion: after Clear Filters + the next rerun's reset-apply,
    the stored snapshot itself (what a reload would read back) is already fully
    cleared — no race window where an old snapshot could still resurrect it."""
    state: dict = {
        SONG_SEARCH_TEXT_KEY: "Sheeran",
        WORKSPACE_GENRE_FILTERS_KEY: ["Jazz"],
        SONG_PICKER_FAVORITES_ONLY_KEY: True,
    }
    request_clear_browse_filters(state)
    apply_picker_session_resets(state)

    snap = _picker_snapshot(state)
    assert snap.get(SONG_SEARCH_TEXT_KEY) == ""
    assert snap.get(WORKSPACE_GENRE_FILTERS_KEY) == []
    assert snap.get(SONG_PICKER_FAVORITES_ONLY_KEY) is False

    # A subsequent restore (simulating a reload reading this now-current snapshot)
    # must not reintroduce the pre-clear values.
    restore_page_snapshot(state, "picker")
    assert state[SONG_SEARCH_TEXT_KEY] == ""
    assert state[WORKSPACE_GENRE_FILTERS_KEY] == []
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is False


def test_clear_filters_preserves_canonical_favorite_records():
    """Clear Filters resets the Favorites *Browse filter*, never the canonical
    Favorite song data."""
    state: dict = {CATALOG_FAVORITES_KEY: []}
    toggle_catalog_favorite(state, "Pop|Shallow — Lady Gaga")
    toggle_favorites_filter(state)
    assert state[CATALOG_FAVORITES_KEY] == ["Pop|Shallow — Lady Gaga"]
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is True

    request_clear_browse_filters(state)

    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is False
    assert state[CATALOG_FAVORITES_KEY] == ["Pop|Shallow — Lady Gaga"]

    # Turning the Browse filter back on still surfaces the still-starred song.
    toggle_favorites_filter(state)
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is True
    assert "Pop|Shallow — Lady Gaga" in state[CATALOG_FAVORITES_KEY]


def test_browse_filter_changes_never_touch_active_song():
    """Active Song selection stays global/unrestricted — Browse filter writers
    must never write ACTIVE_CATALOG_PICK_KEY."""
    state: dict = {ACTIVE_CATALOG_PICK_KEY: "Pop|Say — John Mayer"}
    toggle_favorites_filter(state)
    toggle_genre_filter(state, "Jazz")
    request_clear_browse_filters(state)
    apply_picker_session_resets(state)
    assert state[ACTIVE_CATALOG_PICK_KEY] == "Pop|Say — John Mayer"


class AutosaveStaleStartupFingerprintTests(unittest.TestCase):
    """A genuine content change must not be silently dropped by a stale
    startup-alignment flag (the actual reason Browse filter saves never
    reached disk live, independent of the page-snapshot fix above)."""

    def test_startup_fingerprint_matches_blocks_autosave_precondition(self):
        # Documents the defect in isolation: should_suppress_music_workspace_save
        # treats this startup-only flag as valid for the whole session.
        from music_startup_save_suppression import (
            STARTUP_FINGERPRINT_MATCHES_KEY,
            should_suppress_music_workspace_save,
        )

        hydrated = {STARTUP_FINGERPRINT_MATCHES_KEY: True}
        assert should_suppress_music_workspace_save(dict(hydrated), "autosave")[0]

    def test_autosave_if_changed_clears_stale_flag_once_content_diverges(self):
        from music_startup_save_suppression import STARTUP_FINGERPRINT_MATCHES_KEY
        from music_workspace_cloud_save import music_autosave_if_changed

        ss = {
            "_music_workspace_blob_hydrated": True,
            STARTUP_FINGERPRINT_MATCHES_KEY: True,
        }
        st = MagicMock()
        st.session_state = ss

        with patch("music_workspace_cloud_save.force_music_workspace_save") as force_save:
            force_save.return_value = True
            result = music_autosave_if_changed(
                st, build_state=lambda _s: {"core": {}, "session": {"song_search_text": "Sheeran"}}
            )

        force_save.assert_called_once()
        self.assertFalse(result["skipped"])
        self.assertFalse(ss.get(STARTUP_FINGERPRINT_MATCHES_KEY))

    def test_autosave_if_changed_leaves_flag_alone_when_nothing_changed(self):
        """No-op reruns (content fingerprint unchanged) must not touch the flag —
        only a genuine divergence invalidates it."""
        from music_startup_save_suppression import STARTUP_FINGERPRINT_MATCHES_KEY
        from music_workspace_cloud_save import APP_ID, music_autosave_if_changed

        state = {"core": {}, "session": {"song_search_text": "Sheeran"}}
        import hashlib
        import json

        fp = hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]
        ss = {
            "_music_workspace_blob_hydrated": True,
            STARTUP_FINGERPRINT_MATCHES_KEY: True,
            f"_suite_autosave_fp::{APP_ID}": fp,
        }
        st = MagicMock()
        st.session_state = ss

        with patch("music_workspace_cloud_save.force_music_workspace_save") as force_save:
            result = music_autosave_if_changed(st, build_state=lambda _s: dict(state))

        force_save.assert_not_called()
        self.assertTrue(result["skipped"])
        self.assertTrue(ss.get(STARTUP_FINGERPRINT_MATCHES_KEY))


class PickerSnapshotSurvivesWidgetPurgeTests(unittest.TestCase):
    """PAGE-REVISIT-1: a widget-bound key Streamlit has dropped from live
    session_state (its widget wasn't rendered on an intervening page) must not
    be lost from the page snapshot, and must still restore on return."""

    def test_capture_carries_forward_a_purged_key_from_the_existing_snapshot(self):
        from studio_page_persistence import _PAGE_SNAPSHOTS_KEY, capture_page_snapshot

        state = {
            _PAGE_SNAPSHOTS_KEY: {"picker": {SONG_SEARCH_TEXT_KEY: "Sheeran"}},
            # song_search_text itself is absent -- Streamlit dropped it.
        }
        snap = capture_page_snapshot(state, "picker")
        self.assertEqual(snap.get(SONG_SEARCH_TEXT_KEY), "Sheeran")

    def test_capture_prefers_live_value_over_existing_snapshot(self):
        from studio_page_persistence import _PAGE_SNAPSHOTS_KEY, capture_page_snapshot

        state = {
            SONG_SEARCH_TEXT_KEY: "Mayer",
            _PAGE_SNAPSHOTS_KEY: {"picker": {SONG_SEARCH_TEXT_KEY: "Sheeran"}},
        }
        snap = capture_page_snapshot(state, "picker")
        self.assertEqual(snap.get(SONG_SEARCH_TEXT_KEY), "Mayer")

    def test_restore_applies_a_touched_key_once_live_value_is_purged(self):
        from studio_page_persistence import apply_page_snapshot

        state = {SONG_SEARCH_USER_TOUCHED_KEY: True}
        apply_page_snapshot(state, {SONG_SEARCH_TEXT_KEY: "Sheeran"})
        self.assertEqual(state.get(SONG_SEARCH_TEXT_KEY), "Sheeran")

    def test_restore_still_guards_a_genuinely_live_touched_value(self):
        """The original purpose of the touch guard is unaffected: a live,
        in-session edit still wins over a stale stored snapshot."""
        from studio_page_persistence import apply_page_snapshot

        state = {
            SONG_SEARCH_TEXT_KEY: "live value",
            SONG_SEARCH_USER_TOUCHED_KEY: True,
        }
        apply_page_snapshot(state, {SONG_SEARCH_TEXT_KEY: "stale snapshot value"})
        self.assertEqual(state.get(SONG_SEARCH_TEXT_KEY), "live value")
