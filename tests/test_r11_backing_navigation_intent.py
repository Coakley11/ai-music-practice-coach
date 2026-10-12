"""R11 BACKNAV / BKKEY: navigation intent decides Backing ownership.

Plain Backing navigation opens regular Backing for the global source. Only an
explicit "Open in Backing Studio" (SBI / Style Jam / Generator / Mission) makes
a specialized session, and that session is not a standing preference.

Live first writers pinned here:

* ``prepare_global_backing_navigation`` stamped a page navigation from Creative
  with the SBI Custom preview showing as a specialized handoff.
* "Restore last" on ordinary navigation reopened SBI / jam / Mission sessions,
  and the Backing page snapshot re-applied a specialized context.
* ``hydrate_backing_context_after_restore`` rebuilt Custom SBI from leftover
  stamps (nested Custom SBI, preview source) on a plain visit.
* ``release_generated_jam_key_for_catalog_surface`` cleared the song's own
  Practice Key (Perfect C#) whenever it differed from Original.
* Explicit Composition SBI Backing was an empty stub without a key.
"""

from __future__ import annotations

import unittest

from tests.test_r11_empty_and_composition_sbi import PERFECT, _Base


def _sbi_ctx(**over):
    from backing_context import BackingContext

    base = dict(
        source="song_improv", source_label="Song-Based Improvisation", active_song_id="",
        song_title="My Progression", key="C", display_key="C", concert_key="C",
        bpm=100, style="", groove="", entry_mode="Song-Based Improvisation",
        sbi_source_owner="Custom progression", sbi_material_kind="custom",
    )
    base.update(over)
    return BackingContext(**base)


class TestPlainNavigationIsNotAHandoff(_Base):
    def _perfect_on_custom_sbi(self) -> dict:
        from source_session_state import SBI_PREVIEW_SOURCE_KEY
        from songs.practice_key_state import set_practice_concert_key

        session = self.new_session()
        pick = self.activate_catalog(session, *PERFECT)
        set_practice_concert_key(session, "C#", pick_key=pick, allow_restore_original=True)
        session["studio_page"] = "creative"
        session["improv_intelligence_tab"] = "Entry & Jam"
        session["improv_entry_mode"] = "Song-Based Improvisation"
        session["improv_song_source"] = "Custom progression"
        session[SBI_PREVIEW_SOURCE_KEY] = "Custom progression"
        session["_sbi_custom_sidebar_overlay"] = True
        self.perfect = pick
        return session

    def test_backnav2_page_nav_from_custom_sbi_is_not_specialized(self) -> None:
        from backing_source_navigation import (
            BACKING_ENTRY_CLASS_KEY,
            BACKING_ENTRY_SPECIALIZED_HANDOFF,
            prepare_global_backing_navigation,
        )

        session = self._perfect_on_custom_sbi()
        prepare_global_backing_navigation(session, from_page="creative")
        self.assertNotEqual(session.get(BACKING_ENTRY_CLASS_KEY), BACKING_ENTRY_SPECIALIZED_HANDOFF)
        self.assertNotEqual(session.get("_backing_explicit_handoff_source"), "song_improv")

    def test_backnav6_specialized_sessions_do_not_survive_ordinary_navigation(self) -> None:
        from backing_context import set_backing_context
        from backing_source_navigation import last_valid_backing_session_survives_ordinary_nav

        session = self._perfect_on_custom_sbi()
        for ctx in (
            _sbi_ctx(),
            _sbi_ctx(sbi_source_owner="Active song", sbi_material_kind="catalog", song_title="Perfect"),
            _sbi_ctx(source="entry_jam", entry_mode="Style Jam Mode", song_title="Entry Style Jam"),
            _sbi_ctx(source="custom_progression"),     # Custom is not the global owner here
        ):
            set_backing_context(session, ctx)
            self.assertFalse(last_valid_backing_session_survives_ordinary_nav(session), ctx.source)

    def test_plain_navigation_releases_live_and_snapshot_specialized_contexts(self) -> None:
        from backing_context import get_backing_context, set_backing_context
        from backing_source_navigation import (
            plain_backing_navigation_in_flight,
            release_stale_specialized_backing_for_plain_navigation,
        )

        session = self._perfect_on_custom_sbi()
        set_backing_context(session, _sbi_ctx())
        session["_nested_custom_sbi_backing"] = True
        session["_backing_explicit_handoff_source"] = "song_improv"
        session["_studio_page_snapshots"] = {"backing": {"backing_context": _sbi_ctx().to_dict()}}

        release_stale_specialized_backing_for_plain_navigation(session)

        ctx = get_backing_context(session)
        self.assertTrue(ctx is None or ctx.source != "song_improv")
        snaps = session.get("_studio_page_snapshots") or {}
        self.assertNotIn("backing_context", snaps.get("backing") or {})
        self.assertNotIn("_nested_custom_sbi_backing", session)
        self.assertNotIn("_backing_explicit_handoff_source", session)
        self.assertTrue(plain_backing_navigation_in_flight(session))

    def test_page_restore_does_not_rebuild_custom_sbi_on_plain_navigation(self) -> None:
        from backing_context import _persisted_backing_is_custom_sbi
        from backing_source_navigation import PLAIN_BACKING_NAVIGATION_KEY

        session = self._perfect_on_custom_sbi()
        session["studio_page"] = "backing"
        session["_nested_custom_sbi_backing"] = True
        self.assertTrue(_persisted_backing_is_custom_sbi(session), "precondition: leftover stamps")
        session[PLAIN_BACKING_NAVIGATION_KEY] = True
        self.assertFalse(_persisted_backing_is_custom_sbi(session))

    def test_explicit_cta_still_marks_a_specialized_entry(self) -> None:
        from backing_source_navigation import (
            explicit_specialized_backing_handoff_pending,
            mark_specialized_backing_handoff_entry,
        )

        session = self._perfect_on_custom_sbi()
        self.assertFalse(explicit_specialized_backing_handoff_pending(session))
        mark_specialized_backing_handoff_entry(session)
        self.assertTrue(explicit_specialized_backing_handoff_pending(session))


class TestSongKeySurvivesJamRelease(_Base):
    def test_bkkey1_perfects_c_sharp_survives_releasing_a_jam_on_practice(self) -> None:
        from generated_jam_key_context import release_generated_jam_key_for_catalog_surface
        from songs.practice_key_state import get_practice_concert_key, set_practice_concert_key

        session = self.new_session()
        pick = self.activate_catalog(session, *PERFECT)
        set_practice_concert_key(session, "C#", pick_key=pick, allow_restore_original=True)
        session["studio_page"] = "practice"
        session["_generated_jam_key_owner_active"] = True
        session["improv_jam_key"] = "G"           # the Generator's default, Perfect's Original
        session["display_key"] = "G"              # left on display by the jam (live state)
        session["concert_key"] = "G"
        session["_backing_explicit_handoff_source"] = "entry_jam"
        release_generated_jam_key_for_catalog_surface(session)
        self.assertEqual(get_practice_concert_key(session, pick, default=""), "C#",
                         "Perfect's own Practice Key was cleared back to Original")


class TestExplicitCompositionBackingCarriesItsKey(_Base):
    def test_bkkey4_composition_backing_uses_the_compositions_key_and_chords(self) -> None:
        from backing_context import build_song_improv_context
        from sbi_lane_practice_key import commit_composition_lane_practice_key
        from songs.practice_key_state import set_practice_concert_key
        from source_session_state import SBI_PREVIEW_SOURCE_KEY

        session = self.new_session()
        self.activate_composition(session)
        pick = self.activate_catalog(session, *PERFECT)
        set_practice_concert_key(session, "C#", pick_key=pick, allow_restore_original=True)
        self.enter_creative(session)
        session["improv_intelligence_tab"] = "Entry & Jam"
        session["improv_entry_mode"] = "Song-Based Improvisation"
        from songs.music_source import set_catalog_source, set_custom_source
        from studio_page_state import apply_improv_song_source, flush_pending_improv_song_source

        apply_improv_song_source(session, "Composition", set_catalog_source=set_catalog_source,
                                 set_custom_source=set_custom_source, widget_safe=True)
        flush_pending_improv_song_source(session)
        session["improv_song_source"] = "Composition"
        self.assertEqual(session.get(SBI_PREVIEW_SOURCE_KEY), "Composition")

        ctx = build_song_improv_context(session)
        self.assertEqual(ctx.sbi_source_owner, "Composition")
        self.assertEqual((ctx.key, ctx.concert_key), ("C", "C"), "not Perfect's C#")
        self.assertEqual(set(ctx.progression), {"C", "Am", "F", "G"})

        commit_composition_lane_practice_key(session, "Eb")
        ctx = build_song_improv_context(session)
        self.assertEqual(ctx.concert_key, "Eb")
        self.assertEqual(set(ctx.progression), {"Eb", "Cm", "Ab", "Bb"})


if __name__ == "__main__":
    unittest.main()
