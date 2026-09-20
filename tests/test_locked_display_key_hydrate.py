"""Locked display_key widget: hydrate must not late-write after mount."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from song_catalog.catalog import format_pick_key
from songs.practice_key_state import (
    get_practice_concert_key,
    set_practice_concert_key,
)

from music_workflow_song_practice import (
    OWNER_PK_HYDRATE_RERUN_FLAG,
    apply_or_queue_practice_key_hydrate,
    discard_stale_pending_display_key,
    ensure_missions_parent_practice_key_hydrated,
    maybe_rerun_owner_practice_key_hydrate,
)


SLOW = format_pick_key("Pop", "Slow Dancing in a Burning Room — John Mayer")
PERFECT = format_pick_key("Pop", "Perfect — Ed Sheeran")


class _LockedSession(dict):
    """Raise like Streamlit when a mounted widget key is assigned."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.locked = False
        self.illegal_writes: list[tuple[str, object]] = []

    def __setitem__(self, key, value):  # type: ignore[override]
        if self.locked and key == "display_key":
            self.illegal_writes.append((str(key), value))
            raise RuntimeError(
                "st.session_state.display_key cannot be modified after the widget "
                "with key display_key is instantiated"
            )
        return super().__setitem__(key, value)


def _slow_session(**extra) -> _LockedSession:
    session = _LockedSession(
        {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "creative_improv_intelligence_tab": "Missions",
            "improv_entry_mode": "Song-Based Improvisation",
            "active_catalog_pick_key": SLOW,
            "active_music_source": "catalog",
            "selected_song": {
                "title": "Slow Dancing in a Burning Room",
                "artist": "John Mayer",
                "key": "C#m",
                "pick_key": SLOW,
            },
            "original_key": "C#m",
            "display_key": "C#m",
            "concert_key": "C#m",
        }
    )
    session.update(extra)
    return session


class LockedDisplayKeyHydrateTests(unittest.TestCase):
    def test_hydrate_saved_mismatch_does_not_write_mounted_display_key(self) -> None:
        session = _slow_session()
        set_practice_concert_key(
            session,
            "D#m",
            pick_key=SLOW,
            allow_restore_original=True,
            commit_catalog_practice_key=True,
        )
        session["display_key"] = "C#m"
        session["concert_key"] = "C#m"
        session["_streamlit_widgets_locked_this_run"] = True
        session.locked = True
        try:
            token = ensure_missions_parent_practice_key_hydrated(session)
        except RuntimeError as exc:
            self.fail(f"late display_key write: {exc}")
        self.assertEqual(session.illegal_writes, [])
        self.assertEqual(session.get("display_key"), "C#m")
        self.assertEqual(str(session.get("_pending_display_key") or ""), "D#m")
        self.assertEqual(str(session.get("_pending_display_key_pick") or ""), SLOW)
        self.assertEqual(token, "D#m")
        self.assertTrue(session.get(OWNER_PK_HYDRATE_RERUN_FLAG))

    def test_resolver_is_read_only_after_widget_lock(self) -> None:
        from workflow_key_identity import resolve_practice_key_identity_for_ui

        session = _slow_session()
        set_practice_concert_key(
            session,
            "Em",
            pick_key=SLOW,
            allow_restore_original=True,
            commit_catalog_practice_key=True,
        )
        session["_streamlit_widgets_locked_this_run"] = True
        session.locked = True
        try:
            ident = resolve_practice_key_identity_for_ui(session)
        except RuntimeError as exc:
            self.fail(f"late display_key write: {exc}")
        self.assertEqual(session.illegal_writes, [])
        self.assertEqual(session.get("display_key"), "C#m")
        self.assertIsNotNone(ident)

    def test_user_commit_outranks_pending_automatic_restore(self) -> None:
        session = _slow_session(_pending_display_key="C#m")
        session["_pending_display_key_pick"] = SLOW
        session["_pending_display_key_source"] = "missions_parent_hydrate"
        session["_pk_user_commit_token"] = "Em"
        session["_pk_user_commit_pick"] = SLOW
        dropped = discard_stale_pending_display_key(session)
        self.assertTrue(dropped)
        self.assertFalse(str(session.get("_pending_display_key") or ""))

    def test_stale_pending_discarded_when_owner_pick_changes(self) -> None:
        session = _slow_session(_pending_display_key="D#m")
        session["_pending_display_key_pick"] = SLOW
        session["_pending_display_key_source"] = "missions_parent_hydrate"
        session["active_catalog_pick_key"] = PERFECT
        dropped = discard_stale_pending_display_key(session)
        self.assertTrue(dropped)
        self.assertFalse(str(session.get("_pending_display_key") or ""))

    def test_pending_consumed_before_widget_mount(self) -> None:
        from session_widget_safe import apply_pending_widget_hydrates

        session = _slow_session()
        session["_pending_display_key"] = "D#m"
        session["_pending_display_key_pick"] = SLOW
        session["_pending_display_key_source"] = "missions_parent_hydrate"
        apply_pending_widget_hydrates(session)
        self.assertEqual(session.get("display_key"), "D#m")
        self.assertFalse(str(session.get("_pending_display_key") or ""))

    def test_at_most_one_controlled_rerun(self) -> None:
        session = _slow_session()
        session["_streamlit_widgets_locked_this_run"] = True
        session.locked = True
        apply_or_queue_practice_key_hydrate(session, "D#m")
        reruns = []

        class _St:
            def rerun(self) -> None:
                reruns.append(1)

        st_like = _St()
        first = maybe_rerun_owner_practice_key_hydrate(st_like, session)
        session[OWNER_PK_HYDRATE_RERUN_FLAG] = True
        second = maybe_rerun_owner_practice_key_hydrate(st_like, session)
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(len(reruns), 1)
        self.assertEqual(session.illegal_writes, [])

    def test_hydrate_release_path_with_picker_does_not_write_mounted_key(self) -> None:
        from backing_source_navigation import hydrate_picker_source_for_page
        from music_source_ownership import maybe_reset_practice_key_on_source_activation

        session = _slow_session()
        set_practice_concert_key(
            session,
            "D#m",
            pick_key=SLOW,
            allow_restore_original=True,
            commit_catalog_practice_key=True,
        )
        session["_streamlit_widgets_locked_this_run"] = True
        session.locked = True
        st_like = SimpleNamespace(session_state=session)
        try:
            hydrate_picker_source_for_page(session, st_like=st_like)
            maybe_reset_practice_key_on_source_activation(session, st_like=st_like, surface="picker")
            ensure_missions_parent_practice_key_hydrated(session)
        except RuntimeError as exc:
            self.fail(f"late display_key write: {exc}")
        self.assertEqual(session.illegal_writes, [])
        self.assertEqual(session.get("display_key"), "C#m")
        self.assertEqual(get_practice_concert_key(session, SLOW), "D#m")


if __name__ == "__main__":
    unittest.main()
