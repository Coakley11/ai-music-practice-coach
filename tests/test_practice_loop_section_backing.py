"""Practice 'Loop [section] in Backing Track' must open regular Catalog/Custom/Composition."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest import TestCase

from backing_context import BackingContext, get_backing_context, set_backing_context
from backing_source_navigation import (
    BACKING_INTENT_FROM_PRACTICE,
    BACKING_INTENT_RESTORE_LAST,
    BACKING_PROVENANCE_PRACTICE,
    begin_practice_loop_backing_handoff,
    hydrate_backing_source_for_page,
    peek_backing_open_provenance,
    practice_loop_backing_is_active,
    prepare_return_to_backing_source,
    resolve_regular_practice_backing_owner,
    return_to_source_button_label,
    set_backing_open_intent,
    target_page_for_backing_context,
)
from backing_track_state import resolve_selected_section_names
from songs.music_source import SOURCE_CATALOG, SOURCE_COMPOSITION, SOURCE_CUSTOM


SHAPE_PICK = "pop::Shape of You — Ed Sheeran"
VERSE_1 = "Verse 1"
CHORUS = "Chorus"
VERSE_CHORDS = ["Em", "G", "C", "D"]
CHORUS_CHORDS = ["C", "G", "D", "Em"]


def _stale_mission_ctx(**overrides: Any) -> BackingContext:
    payload = dict(
        source="mission",
        source_label="Mission",
        active_song_id="mission-lock",
        song_title="Stale Mission",
        key="Dm",
        display_key="Dm",
        concert_key="Dm",
        bpm=88,
        style="Pop",
        groove="Straight",
        entry_mode="Song-Based Improvisation",
    )
    payload.update(overrides)
    return BackingContext(**payload)


def _stale_jam_ctx(**overrides: Any) -> BackingContext:
    payload = dict(
        source="entry_jam",
        source_label="Entry & Jam",
        active_song_id="jam-lock",
        song_title="Stale Style Jam",
        key="F",
        display_key="F",
        concert_key="F",
        bpm=60,
        style="Bossa Nova",
        groove="Medium",
        entry_mode="Style Jam Mode",
    )
    payload.update(overrides)
    return BackingContext(**payload)


def _catalog_practice_session(*, stale: str = "") -> dict[str, Any]:
    session: dict[str, Any] = {
        "studio_page": "practice",
        "active_music_source": SOURCE_CATALOG,
        "active_catalog_pick_key": SHAPE_PICK,
        "selected_song": {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "pick_key": SHAPE_PICK,
            "key": "C#m",
            "bpm": 96,
            "sections": {
                VERSE_1: list(VERSE_CHORDS),
                CHORUS: list(CHORUS_CHORDS),
            },
        },
        "display_key": "C#m",
        "concert_key": "C#m",
        "backing_track_bpm": 96,
        "practice_focus_section": VERSE_1,
        "instrument": "Guitar",
    }
    if stale == "mission":
        set_backing_context(session, _stale_mission_ctx())
        session["_backing_explicit_handoff_source"] = "mission"
        session["_last_valid_backing_source"] = "mission"
        session["improv_intelligence_tab"] = "Missions"
    elif stale == "jam":
        set_backing_context(session, _stale_jam_ctx())
        session["_backing_explicit_handoff_source"] = "entry_jam"
        session["_last_valid_backing_source"] = "entry_jam"
        session["improv_entry_mode"] = "Style Jam Mode"
        session["improv_intelligence_tab"] = "Entry & Jam"
    return session


def _custom_practice_session(*, stale: str = "") -> dict[str, Any]:
    session: dict[str, Any] = {
        "studio_page": "practice",
        "active_music_source": SOURCE_CUSTOM,
        "active_catalog_pick_key": "custom::trial-rev",
        "cpl_active_progression": {
            "id": "trial-rev",
            "name": "Trial Song",
            "original_key_center": "D",
            "original_sections": {
                VERSE_1: [{"chord": "D", "bars": 2}, {"chord": "G", "bars": 2}],
                CHORUS: [{"chord": "A", "bars": 2}, {"chord": "Bm", "bars": 2}],
            },
            "bpm": 104,
        },
        "display_key": "E",
        "concert_key": "E",
        "original_key": "D",
        "backing_track_bpm": 104,
        "practice_focus_section": VERSE_1,
        "instrument": "Guitar",
    }
    if stale == "mission":
        set_backing_context(session, _stale_mission_ctx())
        session["_backing_explicit_handoff_source"] = "mission"
        session["_last_valid_backing_source"] = "mission"
    elif stale == "jam":
        set_backing_context(session, _stale_jam_ctx())
        session["_backing_explicit_handoff_source"] = "entry_jam"
        session["_last_valid_backing_source"] = "entry_jam"
    return session


def _composition_practice_session(*, stale: str = "") -> dict[str, Any]:
    from composition_songs_bridge import (
        composition_pick_key_for,
        ensure_generic_composition_document,
        set_composition_source,
    )

    session: dict[str, Any] = {
        "studio_page": "practice",
        "instrument": "Piano",
        "composer_saved_compositions": {},
        "display_key": "G",
        "concert_key": "G",
        "backing_track_bpm": 108,
        "practice_focus_section": VERSE_1,
    }
    set_composition_source(session)
    doc = ensure_generic_composition_document(session)
    pick = composition_pick_key_for(doc)
    session["active_catalog_pick_key"] = pick
    session["active_music_source"] = SOURCE_COMPOSITION
    session["display_key"] = "G"
    session["concert_key"] = "G"
    if stale == "mission":
        set_backing_context(session, _stale_mission_ctx())
        session["_backing_explicit_handoff_source"] = "mission"
        session["_last_valid_backing_source"] = "mission"
    elif stale == "jam":
        set_backing_context(session, _stale_jam_ctx())
        session["_backing_explicit_handoff_source"] = "entry_jam"
        session["_last_valid_backing_source"] = "entry_jam"
    return session


def _open_loop(session: dict[str, Any], section: str = VERSE_1) -> None:
    begin_practice_loop_backing_handoff(session, section_key=section, loops=4)
    session["studio_page"] = "backing"
    hydrate_backing_source_for_page(session, st_like=SimpleNamespace(session_state=session))


def _selected_progression(session: dict[str, Any], sections: dict[str, list[str]]) -> list[str]:
    names = list(sections.keys())
    chosen = resolve_selected_section_names(session, names)
    out: list[str] = []
    for name in chosen:
        out.extend(list(sections.get(name) or []))
    return out


class TestPracticeLoopOwnerResolution(TestCase):
    def test_catalog_custom_composition_stay_distinct(self) -> None:
        self.assertEqual(resolve_regular_practice_backing_owner(_catalog_practice_session()), "catalog")
        self.assertEqual(resolve_regular_practice_backing_owner(_custom_practice_session()), "custom")
        self.assertEqual(
            resolve_regular_practice_backing_owner(_composition_practice_session()),
            "composition",
        )


class TestCatalogPracticeLoopBacking(TestCase):
    def test_loop_verse_opens_regular_catalog_not_mission_or_jam(self) -> None:
        session = _catalog_practice_session(stale="mission")
        _open_loop(session, VERSE_1)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "regular_song")
        self.assertIn("Shape of You", str(ctx.song_title or session.get("selected_song", {}).get("title") or ""))
        self.assertEqual(session.get("backing_track_scope"), "Selected sections")
        self.assertEqual(session.get("backing_track_single_section"), VERSE_1)
        self.assertEqual(session.get("backing_track_multi_sections"), [VERSE_1])
        self.assertEqual(session.get("backing_track_loops"), 4)
        self.assertEqual(str(session.get("display_key") or ""), "C#m")
        self.assertEqual(int(session.get("backing_track_bpm") or 0), 96)
        self.assertNotEqual(ctx.source, "mission")
        self.assertNotEqual(ctx.source, "entry_jam")
        self.assertEqual(peek_backing_open_provenance(session), BACKING_PROVENANCE_PRACTICE)
        sections = {"Verse 1": VERSE_CHORDS, "Chorus": CHORUS_CHORDS}
        self.assertEqual(_selected_progression(session, sections), VERSE_CHORDS)
        self.assertNotEqual(_selected_progression(session, sections), CHORUS_CHORDS)

    def test_stale_jam_cannot_claim_catalog_loop(self) -> None:
        session = _catalog_practice_session(stale="jam")
        _open_loop(session, VERSE_1)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(session.get("backing_track_single_section"), VERSE_1)

    def test_refresh_keeps_catalog_owner_session_and_section(self) -> None:
        session = _catalog_practice_session(stale="mission")
        _open_loop(session, VERSE_1)
        session["_backing_explicit_handoff_source"] = "mission"
        session["improv_intelligence_tab"] = "Missions"
        set_backing_open_intent(session, BACKING_INTENT_RESTORE_LAST)
        hydrate_backing_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(session.get("backing_track_single_section"), VERSE_1)
        self.assertEqual(session.get("backing_track_multi_sections"), [VERSE_1])
        self.assertTrue(practice_loop_backing_is_active(session))

    def test_return_goes_to_practice(self) -> None:
        session = _catalog_practice_session()
        _open_loop(session, VERSE_1)
        ctx = get_backing_context(session)
        self.assertEqual(target_page_for_backing_context(ctx, session=session), "practice")
        self.assertEqual(prepare_return_to_backing_source(session), "practice")
        self.assertEqual(return_to_source_button_label(ctx, session=session), "Return to Practice")


class TestCustomPracticeLoopBacking(TestCase):
    def test_loop_opens_regular_custom_not_catalog(self) -> None:
        session = _custom_practice_session(stale="mission")
        _open_loop(session, VERSE_1)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "custom_progression")
        self.assertEqual(ctx.song_title, "Trial Song")
        self.assertEqual(str(ctx.key or session.get("original_key") or ""), "D")
        self.assertEqual(str(session.get("display_key") or ""), "E")
        self.assertEqual(int(session.get("backing_track_bpm") or 0), 104)
        self.assertEqual(session.get("backing_track_single_section"), VERSE_1)
        self.assertNotEqual(ctx.source, "regular_song")
        self.assertNotEqual(ctx.source, "mission")

    def test_stale_jam_cannot_claim_custom_loop(self) -> None:
        session = _custom_practice_session(stale="jam")
        _open_loop(session, CHORUS)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "custom_progression")
        self.assertEqual(session.get("backing_track_single_section"), CHORUS)

    def test_refresh_keeps_custom_owner_and_section(self) -> None:
        session = _custom_practice_session(stale="jam")
        _open_loop(session, VERSE_1)
        session["_backing_explicit_handoff_source"] = "entry_jam"
        set_backing_open_intent(session, BACKING_INTENT_RESTORE_LAST)
        hydrate_backing_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "custom_progression")
        self.assertEqual(session.get("backing_track_single_section"), VERSE_1)


class TestCompositionPracticeLoopBacking(TestCase):
    def test_loop_opens_regular_composition_not_catalog_or_custom(self) -> None:
        session = _composition_practice_session(stale="mission")
        _open_loop(session, VERSE_1)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "composition_song")
        self.assertTrue(str(session.get("active_catalog_pick_key") or "").startswith("composition::"))
        self.assertEqual(str(session.get("display_key") or ""), "G")
        self.assertEqual(int(session.get("backing_track_bpm") or 0), 108)
        self.assertEqual(session.get("backing_track_single_section"), VERSE_1)
        self.assertNotEqual(ctx.source, "regular_song")
        self.assertNotEqual(ctx.source, "custom_progression")
        self.assertNotEqual(ctx.source, "mission")

    def test_refresh_keeps_composition_owner_and_section(self) -> None:
        session = _composition_practice_session(stale="jam")
        _open_loop(session, VERSE_1)
        session["_backing_explicit_handoff_source"] = "entry_jam"
        set_backing_open_intent(session, BACKING_INTENT_RESTORE_LAST)
        hydrate_backing_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "composition_song")
        self.assertEqual(session.get("backing_track_single_section"), VERSE_1)


class TestPracticeLoopSourceSwitch(TestCase):
    def test_switch_catalog_custom_composition_repeat(self) -> None:
        catalog = _catalog_practice_session(stale="mission")
        _open_loop(catalog, VERSE_1)
        self.assertEqual(get_backing_context(catalog).source, "regular_song")  # type: ignore[union-attr]
        self.assertEqual(catalog.get("backing_track_single_section"), VERSE_1)

        custom = _custom_practice_session(stale="jam")
        _open_loop(custom, CHORUS)
        self.assertEqual(get_backing_context(custom).source, "custom_progression")  # type: ignore[union-attr]
        self.assertEqual(custom.get("backing_track_single_section"), CHORUS)
        self.assertNotEqual(get_backing_context(custom).source, "regular_song")  # type: ignore[union-attr]

        composition = _composition_practice_session(stale="mission")
        _open_loop(composition, VERSE_1)
        ctx = get_backing_context(composition)
        self.assertEqual(ctx.source, "composition_song")  # type: ignore[union-attr]
        self.assertEqual(composition.get("backing_track_single_section"), VERSE_1)

        # Returning to Catalog must not keep Custom/Composition owner.
        again = _catalog_practice_session(stale="jam")
        _open_loop(again, VERSE_1)
        self.assertEqual(get_backing_context(again).source, "regular_song")  # type: ignore[union-attr]
        self.assertEqual(again.get("backing_track_single_section"), VERSE_1)

    def test_nav_history_returns_to_practice(self) -> None:
        from studio_nav_history import go_back, navigate_studio_page

        session = _catalog_practice_session()
        session["studio_page"] = "practice"
        begin_practice_loop_backing_handoff(session, section_key=VERSE_1, loops=4)
        navigate_studio_page(session, "backing")
        self.assertEqual(session.get("studio_page"), "backing")
        self.assertTrue(go_back(session))
        self.assertEqual(session.get("studio_page"), "practice")
