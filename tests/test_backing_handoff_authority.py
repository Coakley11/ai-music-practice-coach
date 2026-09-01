"""Regression: Songs→Backing handoff, refresh owner, and Practice Key preservation."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from backing_context import BACKING_CONTEXT_KEY, BackingContext, get_backing_context
from backing_source_navigation import (
    BACKING_INTENT_FROM_SONG_TO_BACKING,
    BACKING_INTENT_RESTORE_LAST,
    hydrate_backing_source_for_page,
    open_backing_for_practice_source,
    prepare_global_backing_navigation,
    restore_practice_backing_if_stale,
    set_backing_open_intent,
)
from custom_progression_lab import CPL_ACTIVE_KEY
from songs.music_source import SOURCE_CUSTOM, custom_pick_key_for, set_custom_source
from songs.practice_key_state import set_practice_concert_key
from studio_nav_history import navigate_studio_page


def _custom_session(*, practice_key: str = "E") -> dict:
    session = {
        "studio_page": "picker",
        "active_music_source": SOURCE_CUSTOM,
        "active_catalog_pick_key": "custom::My Progression",
        "display_key": practice_key,
        "concert_key": practice_key,
        CPL_ACTIVE_KEY: {
            "id": "prog-my",
            "name": "My Progression",
            "original_key_center": "C",
            "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
            "bpm": 90,
        },
    }
    set_custom_source(session)
    canonical_pick = custom_pick_key_for(session[CPL_ACTIVE_KEY])
    session["active_catalog_pick_key"] = canonical_pick
    set_practice_concert_key(session, practice_key, pick_key=canonical_pick)
    return session


class TestBackingHandoffAuthority(unittest.TestCase):
    def test_songs_to_backing_preserves_custom_practice_key(self) -> None:
        session = _custom_session(practice_key="E")
        set_backing_open_intent(session, BACKING_INTENT_FROM_SONG_TO_BACKING)
        hydrate_backing_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "custom_progression")
        self.assertEqual(ctx.concert_key, "E")
        self.assertEqual(session.get("display_key"), "E")

    def test_refresh_restores_custom_not_catalog(self) -> None:
        session = _custom_session(practice_key="E")
        session["studio_page"] = "backing"
        session[BACKING_CONTEXT_KEY] = BackingContext(
            source="regular_song",
            source_label="Catalog song",
            active_song_id="Pop::Say",
            song_title="Say",
            key="G",
            display_key="G",
            concert_key="G",
            bpm=100,
            style="",
            groove="Pop groove",
            bound_pick_key="Pop::Say",
        ).to_dict()
        set_backing_open_intent(session, BACKING_INTENT_RESTORE_LAST)
        hydrate_backing_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "custom_progression")
        self.assertEqual(ctx.song_title, "My Progression")
        self.assertEqual(ctx.concert_key, "E")

    def test_global_nav_stamps_custom_backing_intent(self) -> None:
        session = _custom_session(practice_key="E")
        session["studio_page"] = "picker"
        navigate_studio_page(session, "backing")
        hydrate_backing_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "custom_progression")

    def test_prepare_global_backing_navigation_custom(self) -> None:
        session = _custom_session()
        prepare_global_backing_navigation(session, from_page="picker")
        from backing_source_navigation import BACKING_OPEN_INTENT_KEY

        self.assertEqual(session.get(BACKING_OPEN_INTENT_KEY), BACKING_INTENT_FROM_SONG_TO_BACKING)

    def test_restore_practice_backing_if_stale_composition(self) -> None:
        from composition_songs_bridge import (
            commit_composition_active_song,
            ensure_generic_composition_document,
            set_composition_source,
        )

        session = _custom_session(practice_key="C")
        st = SimpleNamespace(session_state=session)
        set_composition_source(session)
        doc = ensure_generic_composition_document(session)
        commit_composition_active_song(st, doc, invalidate_backing=lambda _s: None)
        session[BACKING_CONTEXT_KEY] = BackingContext(
            source="regular_song",
            source_label="Catalog song",
            active_song_id="Pop::Say",
            song_title="Say",
            key="G",
            display_key="G",
            concert_key="G",
            bpm=100,
            style="",
            groove="Pop groove",
            bound_pick_key="Pop::Say",
        ).to_dict()
        self.assertTrue(restore_practice_backing_if_stale(session, st_like=st))
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "composition_song")

    def test_open_backing_for_practice_source_preserves_saved_key(self) -> None:
        session = _custom_session(practice_key="E")
        session["display_key"] = "C"
        session["concert_key"] = "C"
        ctx = open_backing_for_practice_source(session, st_like=SimpleNamespace(session_state=session))
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.concert_key, "E")

    def test_sidebar_identity_uses_saved_custom_practice_key(self) -> None:
        from sidebar_key_identity import resolve_sidebar_key_identity

        session = _custom_session(practice_key="E")
        ident = resolve_sidebar_key_identity(session)
        self.assertEqual(ident.owner, "custom_progression")
        self.assertEqual(ident.selector_token, "E")

    def test_hydrate_runs_once_per_rerun(self) -> None:
        session = _custom_session(practice_key="E")
        session["studio_page"] = "backing"
        session[BACKING_CONTEXT_KEY] = BackingContext(
            source="regular_song",
            source_label="Catalog song",
            active_song_id="Pop::Say",
            song_title="Say",
            key="G",
            display_key="G",
            concert_key="G",
            bpm=100,
            style="",
            groove="Pop groove",
            bound_pick_key="Pop::Say",
        ).to_dict()
        st_like = SimpleNamespace(session_state=session)
        set_backing_open_intent(session, BACKING_INTENT_RESTORE_LAST)
        hydrate_backing_source_for_page(session, st_like=st_like)
        ctx_after_first = get_backing_context(session)
        hydrate_backing_source_for_page(session, st_like=st_like)
        ctx_after_second = get_backing_context(session)
        self.assertEqual(ctx_after_first.source, "custom_progression")
        self.assertEqual(ctx_after_second.source, "custom_progression")


if __name__ == "__main__":
    unittest.main()
