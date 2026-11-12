"""Issue 74: the Original Key a Backing owner reports is the song's, not the musician's.

Blue Bossa is a C minor song. Practised in A minor, the Mission Backing card
announced "Original Key: A minor" -- ``owned_backing_chart_identity`` read
``ctx.key``, and for every Creative owner that field holds the *working* key.
These tests pin the three concepts apart (Original C minor / Practice A minor /
written B minor for a B flat instrument) and pin the safety rules: an identity
that cannot be verified yields *no* Original Key rather than a plausible wrong
one, and a near-miss pick is never repaired into a different song.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backing_context import BackingContext, owned_backing_chart_identity  # noqa: E402
from backing_owner_original_key import (  # noqa: E402
    resolve_original_key_for_pick,
    resolve_owner_original_key,
)
from song_catalog.catalog import format_pick_key  # noqa: E402
from songs.music_source import (  # noqa: E402
    _catalog_picker_from_session,
    ensure_song_picker_catalog,
)

#: (title, expected original key) -- read back from the catalog in setUp, so a
#: curated re-key shows up as a catalog mismatch rather than a silent pass.
SONGS = {
    "Blue Bossa": "Jazz",          # minor jazz, the reported song
    "Autumn Leaves": "Jazz",       # another jazz standard, B minor
    "Let It Be": "Rock",           # a major-key song
    "Say": "Pop",                  # major, and the Issue 67 chart-syntax song
}


def catalog_session() -> dict:
    session: dict = {}
    ensure_song_picker_catalog(session)
    return session


def pick_for(session: dict, genre: str, title: str) -> str:
    """The exact canonical pick for a catalog song, as the app stores it."""
    catalog = _catalog_picker_from_session(session) or {}
    labels = catalog.get(genre) or {}
    for label, row in labels.items():
        if str(row.get("title") or "").strip() == title:
            return format_pick_key(genre, label)
    raise AssertionError(f"{title} not in the {genre} catalog")


def catalog_key_for(session: dict, genre: str, title: str) -> str:
    catalog = _catalog_picker_from_session(session) or {}
    for row in (catalog.get(genre) or {}).values():
        if str(row.get("title") or "").strip() == title:
            return str(row.get("key") or "").strip()
    raise AssertionError(f"{title} not in the {genre} catalog")


def mission_ctx(
    *,
    pick: str = "",
    title: str = "Blue Bossa",
    practice: str = "Am",
    source: str = "mission",
) -> BackingContext:
    """A Mission context as ``build_mission_context`` builds one.

    The point of the fixture is the key fields: that builder writes
    ``key = display_key = concert_key = practice``, which is what made reading
    ``ctx.key`` for an Original Key wrong.
    """
    return BackingContext(
        source=source,  # type: ignore[arg-type]
        source_label="Mission Backing Jam",
        active_song_id=pick,
        song_title=title,
        key=practice,
        display_key=practice,
        concert_key=practice,
        bpm=135,
        style="Jazz",
        groove="Bossa nova",
        bound_pick_key=pick,
        mission_id="mission-1",
    )


class ACatalogMissionReportsTheSongsOwnKey(unittest.TestCase):
    def setUp(self) -> None:
        self.session = catalog_session()
        self.pick = pick_for(self.session, "Jazz", "Blue Bossa")

    def test_blue_bossa_stays_c_minor_while_practising_in_a_minor(self) -> None:
        self.assertEqual(catalog_key_for(self.session, "Jazz", "Blue Bossa"), "Cm")
        resolved = resolve_owner_original_key(
            self.session, mission_ctx(pick=self.pick, practice="Am")
        )
        self.assertTrue(resolved.resolved, resolved.reason)
        self.assertEqual(resolved.key, "Cm")
        self.assertEqual(resolved.source_kind, "catalog")

    def test_the_original_key_does_not_move_with_the_practice_key(self) -> None:
        keys = {}
        for practice in ("Cm", "Am", "F", "Bbm", "Em"):
            resolved = resolve_owner_original_key(
                self.session, mission_ctx(pick=self.pick, practice=practice)
            )
            keys[practice] = resolved.key
        self.assertEqual(set(keys.values()), {"Cm"}, keys)

    def test_practising_in_the_original_key_is_still_resolved(self) -> None:
        # Original and Practice legitimately coincide; that is not a failure and
        # must not be mistaken for the defect.
        resolved = resolve_owner_original_key(
            self.session, mission_ctx(pick=self.pick, practice="Cm")
        )
        self.assertTrue(resolved.resolved)
        self.assertEqual(resolved.key, "Cm")

    def test_other_catalog_songs_report_their_own_keys(self) -> None:
        for title, genre in SONGS.items():
            with self.subTest(song=title):
                pick = pick_for(self.session, genre, title)
                want = catalog_key_for(self.session, genre, title)
                resolved = resolve_owner_original_key(
                    self.session, mission_ctx(pick=pick, title=title, practice="Em")
                )
                self.assertTrue(resolved.resolved, resolved.reason)
                self.assertEqual(resolved.key, want)


class AnUnverifiableIdentityReportsNoKeyAtAll(unittest.TestCase):
    """The rule that keeps a wrong answer from looking like a right one."""

    def setUp(self) -> None:
        self.session = catalog_session()
        self.pick = pick_for(self.session, "Jazz", "Blue Bossa")

    def assert_unresolved(self, resolved, reason: str = "") -> None:
        self.assertFalse(resolved.resolved, f"unexpectedly resolved: {resolved}")
        self.assertEqual(resolved.key, "")
        if reason:
            self.assertEqual(resolved.reason, reason)

    def test_a_near_miss_pick_is_not_repaired_into_another_song(self) -> None:
        # The catalog's own label uses one dash; this spells it with an en dash.
        # The library's fuzzy resolver answered this with *Say* in B flat.
        near = "Jazz\x1fBlue Bossa – Kenny Dorham"
        self.assertNotEqual(near, self.pick)
        self.assert_unresolved(
            resolve_owner_original_key(self.session, mission_ctx(pick=near)),
            "pick_not_in_catalog",
        )

    def test_a_bare_title_is_not_an_identity(self) -> None:
        self.assert_unresolved(
            resolve_owner_original_key(self.session, mission_ctx(pick="Blue Bossa")),
            "pick_not_canonical",
        )

    def test_an_owner_with_no_identity_reports_nothing(self) -> None:
        self.assert_unresolved(
            resolve_owner_original_key(self.session, mission_ctx(pick="")),
            "no_owner_identity",
        )

    def test_a_pick_for_a_song_that_is_not_in_the_catalog(self) -> None:
        self.assert_unresolved(
            resolve_owner_original_key(
                self.session, mission_ctx(pick=format_pick_key("Jazz", "Not A Song - Nobody"))
            ),
            "pick_not_in_catalog",
        )

    def test_a_row_that_does_not_match_the_owners_song_is_refused(self) -> None:
        self.assert_unresolved(
            resolve_owner_original_key(
                self.session, mission_ctx(pick=self.pick, title="Autumn Leaves")
            ),
            "title_mismatch",
        )

    def test_a_workflow_placeholder_title_still_trusts_the_exact_pick(self) -> None:
        # ``build_mission_context`` falls back to "Mission" when no song title is
        # in session; the exact pick membership is the identity check there.
        for title in ("Mission", "Active song", ""):
            with self.subTest(title=title):
                resolved = resolve_owner_original_key(
                    self.session, mission_ctx(pick=self.pick, title=title)
                )
                self.assertTrue(resolved.resolved, resolved.reason)
                self.assertEqual(resolved.key, "Cm")

    def test_a_legacy_genre_colon_pick_is_a_format_not_a_guess(self) -> None:
        genre, _sep, label = self.pick.partition("\x1f")
        legacy = f"{genre}::{label}"
        resolved = resolve_owner_original_key(self.session, mission_ctx(pick=legacy))
        self.assertTrue(resolved.resolved, resolved.reason)
        self.assertEqual(resolved.key, "Cm")
        # ...but the rewrite does not invent a label that is not in the catalog.
        self.assert_unresolved(
            resolve_owner_original_key(
                self.session, mission_ctx(pick=f"{genre}::Blue Bossa")
            ),
            "pick_not_in_catalog",
        )

    def test_a_jam_workflow_pick_belongs_to_no_song(self) -> None:
        self.assert_unresolved(
            resolve_owner_original_key(
                self.session, mission_ctx(pick="creative::style_jam")
            ),
            "creative_workflow_pick",
        )


class CustomAndCompositionOwnersUseTheirOwnSavedKey(unittest.TestCase):
    def test_a_custom_progression_reports_its_saved_original(self) -> None:
        from songs.music_source import custom_pick_key_for

        active = {
            "id": "trial-1",
            "name": "Trial Song",
            "original_key_center": "D",
            "sections": {"A": ["D", "G", "A"]},
        }
        pick = custom_pick_key_for(active)
        session = {"cpl_active_progression": active}
        resolved = resolve_owner_original_key(
            session,
            mission_ctx(pick=pick, title="Trial Song", practice="F"),
        )
        self.assertTrue(resolved.resolved, resolved.reason)
        self.assertEqual(resolved.key, "D")
        self.assertEqual(resolved.source_kind, "custom")

    def test_a_custom_pick_with_no_stored_progression_is_unresolved(self) -> None:
        resolved = resolve_owner_original_key(
            {}, mission_ctx(pick="custom::ghost", title="Ghost", practice="F")
        )
        self.assertFalse(resolved.resolved)
        self.assertEqual(resolved.key, "")
        self.assertEqual(resolved.reason, "custom_progression_not_found")

    def test_a_composition_reports_its_document_home_key(self) -> None:
        doc_id = "11111111-2222-3333-4444-555555555555"
        doc = {
            "id": doc_id,
            "title": "My Composition",
            "global": {"original_key_center": "Eb", "time_signature": "4/4", "bpm": 90},
            "sections": [],
        }
        from composition_session_state import COMPOSER_LIBRARY_KEY

        session = {COMPOSER_LIBRARY_KEY: {doc_id: doc}}
        resolved = resolve_owner_original_key(
            session,
            mission_ctx(pick=f"composition::{doc_id}", title="My Composition", practice="G"),
        )
        self.assertTrue(resolved.resolved, resolved.reason)
        self.assertEqual(resolved.key, "Eb")
        self.assertEqual(resolved.source_kind, "composition")

    def test_a_composition_pick_with_no_document_is_unresolved(self) -> None:
        resolved = resolve_owner_original_key(
            {}, mission_ctx(pick="composition::missing", practice="G")
        )
        self.assertFalse(resolved.resolved)
        self.assertEqual(resolved.reason, "composition_not_found")


class AGeneratedJamIsItsOwnHomeKey(unittest.TestCase):
    def test_the_working_key_of_a_generated_jam_is_its_original(self) -> None:
        ctx = BackingContext(
            source="entry_jam",  # type: ignore[arg-type]
            source_label="Creative Backing Jam",
            active_song_id="creative::style_jam",
            song_title="Entry Style Jam",
            key="Eb",
            display_key="Eb",
            concert_key="Eb",
            bpm=110,
            style="Funk",
            groove="Funk",
            entry_mode="Style Jam",
        )
        resolved = resolve_owner_original_key({}, ctx)
        self.assertTrue(resolved.resolved)
        self.assertEqual(resolved.key, "Eb")
        self.assertEqual(resolved.source_kind, "generated")


class TheBackingIdentityKeepsTheKeysApart(unittest.TestCase):
    """``owned_backing_chart_identity`` is what the Backing card reads."""

    def setUp(self) -> None:
        self.session = catalog_session()
        self.pick = pick_for(self.session, "Jazz", "Blue Bossa")

    def test_the_card_identity_reports_the_catalog_original(self) -> None:
        ident = owned_backing_chart_identity(
            self.session, mission_ctx(pick=self.pick, practice="Am")
        )
        self.assertIsNotNone(ident)
        self.assertEqual(ident["original_key"], "Cm")
        self.assertTrue(ident["original_key_resolved"])
        # The material still sounds in A minor, and the chart/coaching key says so.
        self.assertEqual(ident["working_key"], "Am")
        self.assertEqual(ident["song_data"]["key"], "Am")
        self.assertEqual(ident["song_data"]["original_key"], "Cm")

    def test_an_unresolvable_owner_reports_no_original_key(self) -> None:
        ident = owned_backing_chart_identity(
            self.session, mission_ctx(pick="Blue Bossa", practice="Am")
        )
        self.assertIsNotNone(ident)
        self.assertEqual(ident["original_key"], "")
        self.assertFalse(ident["original_key_resolved"])
        self.assertNotEqual(ident["original_key"], ident["working_key"])
        self.assertEqual(ident["song_data"]["original_key"], "")

    def test_the_coaching_sentence_still_names_the_key_that_sounds(self) -> None:
        ident = owned_backing_chart_identity(
            self.session, mission_ctx(pick=self.pick, practice="Am")
        )
        self.assertIn("Am", ident["coaching"])
        self.assertNotIn("Cm", ident["coaching"])


class TheMissionHandoffSealsEveryKeySeparately(unittest.TestCase):
    def setUp(self) -> None:
        from mission_owner_contract import clear_mission_return_eligibility

        self.session = catalog_session()
        self.pick = pick_for(self.session, "Jazz", "Blue Bossa")
        clear_mission_return_eligibility(self.session)

    def seal(self, *, instrument: str = "Piano", written_charts: bool = False, practice: str = "Am") -> dict:
        from mission_owner_contract import stamp_mission_backing_handoff

        self.session.update(
            {
                "active_catalog_pick_key": self.pick,
                "selected_song": {
                    "pick_key": self.pick,
                    "title": "Blue Bossa",
                    "artist": "Kenny Dorham",
                    "key": "Cm",
                },
                "song": "Blue Bossa",
                "instrument": instrument,
                "show_chart_in_instrument_key": bool(written_charts),
                "display_key": practice,
                "concert_key": practice,
            }
        )
        stamp_mission_backing_handoff(self.session, concert_practice_key=practice)
        return self.session

    def test_original_practice_and_written_are_three_values(self) -> None:
        from mission_owner_contract import (
            HANDOFF_ORIGINAL_KEY,
            HANDOFF_PRACTICE_KEY,
            HANDOFF_SOURCE_IDENTITY,
            HANDOFF_SOUNDING_KEY,
            HANDOFF_WRITTEN_KEY,
        )

        s = self.seal(instrument="Trumpet", written_charts=True, practice="Am")
        self.assertEqual(s[HANDOFF_ORIGINAL_KEY], "Cm")
        self.assertEqual(s[HANDOFF_PRACTICE_KEY], "Am")
        self.assertEqual(s[HANDOFF_SOUNDING_KEY], "Am")
        self.assertEqual(s[HANDOFF_WRITTEN_KEY], "Bm")
        self.assertEqual(s[HANDOFF_SOURCE_IDENTITY], self.pick)

    def test_a_concert_instrument_writes_what_it_sounds(self) -> None:
        from mission_owner_contract import HANDOFF_ORIGINAL_KEY, HANDOFF_WRITTEN_KEY

        s = self.seal(instrument="Piano", practice="Am")
        self.assertEqual(s[HANDOFF_ORIGINAL_KEY], "Cm")
        self.assertEqual(s[HANDOFF_WRITTEN_KEY], "Am")

    def test_a_stale_session_original_key_does_not_win(self) -> None:
        from mission_owner_contract import HANDOFF_ORIGINAL_KEY

        # A leftover generic value -- here the Practice Key itself, which is how
        # the defect looked -- must lose to the owner's own catalog metadata.
        self.session["original_key"] = "Am"
        s = self.seal(practice="Am")
        self.assertEqual(s[HANDOFF_ORIGINAL_KEY], "Cm")

    def test_releasing_the_mission_clears_the_whole_envelope(self) -> None:
        from mission_owner_contract import (
            HANDOFF_ORIGINAL_KEY,
            HANDOFF_PRACTICE_KEY,
            HANDOFF_SOURCE_IDENTITY,
            HANDOFF_SOUNDING_KEY,
            HANDOFF_WRITTEN_KEY,
            clear_mission_return_eligibility,
        )

        s = self.seal(practice="Am")
        clear_mission_return_eligibility(s)
        for field in (
            HANDOFF_ORIGINAL_KEY,
            HANDOFF_PRACTICE_KEY,
            HANDOFF_SOUNDING_KEY,
            HANDOFF_WRITTEN_KEY,
            HANDOFF_SOURCE_IDENTITY,
        ):
            self.assertNotIn(field, s, field)

    def test_one_songs_original_key_cannot_leak_into_the_next(self) -> None:
        from mission_owner_contract import (
            HANDOFF_ORIGINAL_KEY,
            HANDOFF_SOURCE_IDENTITY,
            clear_mission_return_eligibility,
            stamp_mission_backing_handoff,
        )

        s = self.seal(practice="Am")
        self.assertEqual(s[HANDOFF_ORIGINAL_KEY], "Cm")
        clear_mission_return_eligibility(s)

        other_pick = pick_for(self.session, "Rock", "Let It Be")
        other_key = catalog_key_for(self.session, "Rock", "Let It Be")
        s.update(
            {
                "active_catalog_pick_key": other_pick,
                "selected_song": {
                    "pick_key": other_pick,
                    "title": "Let It Be",
                    "artist": "The Beatles",
                    "key": other_key,
                },
                "song": "Let It Be",
                "display_key": "Am",
                "concert_key": "Am",
            }
        )
        stamp_mission_backing_handoff(s, concert_practice_key="Am")
        self.assertEqual(s[HANDOFF_ORIGINAL_KEY], other_key)
        self.assertEqual(s[HANDOFF_SOURCE_IDENTITY], other_pick)


class EveryCatalogSongResolvesToItsOwnMetadata(unittest.TestCase):
    """The catalog-wide check: resolved Original vs the song's canonical key.

    Deliberately not "Original differs from Practice" -- those legitimately
    match when the musician practises in the original key. Each song is checked
    against *its own* catalog row, at a Practice Key that is not that key.
    """

    def test_all_songs(self) -> None:
        session = catalog_session()
        catalog = _catalog_picker_from_session(session) or {}
        checked = 0
        mismatched: list[str] = []
        for genre, labels in catalog.items():
            for label, row in (labels or {}).items():
                want = str((row or {}).get("key") or "").strip()
                if not want:
                    continue
                pick = format_pick_key(genre, label)
                practice = "F#m" if want != "F#m" else "Gm"
                resolved = resolve_original_key_for_pick(
                    session, pick, expected_title=str(row.get("title") or "")
                )
                checked += 1
                if not resolved.resolved or resolved.key != want:
                    mismatched.append(f"{label}: want {want!r} got {resolved.key!r} ({resolved.reason})")
                # And the Backing identity the card reads agrees.
                ident = owned_backing_chart_identity(
                    session,
                    mission_ctx(pick=pick, title=str(row.get("title") or ""), practice=practice),
                )
                if ident is not None and ident["original_key"] != want:
                    mismatched.append(f"{label}: card {ident['original_key']!r} != {want!r}")
        self.assertGreater(checked, 100, f"only {checked} catalog songs checked")
        self.assertEqual(mismatched, [], f"{len(mismatched)} of {checked} mismatched")


if __name__ == "__main__":
    unittest.main()
