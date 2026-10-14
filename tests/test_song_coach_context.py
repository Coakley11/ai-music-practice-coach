"""Song-Aware Coaching S1 — the coached song snapshot (song_coach_context)."""

from __future__ import annotations

import copy
import unittest

from music_theory import transpose_sections_dict
from song_coach_context import (
    CHART_CONFIDENCE_LABELS,
    CHART_CONFIDENCE_NOTES,
    CHART_PRACTICE,
    CHART_USER_AUTHORED,
    CHART_USER_EDITED,
    CHART_VERIFIED,
    REASON_CHART_OUT_OF_SYNC,
    REASON_JAM_PROGRESSION,
    REASON_KEY_OUT_OF_SYNC,
    REASON_NO_CHORDS,
    REASON_NO_KEY,
    REASON_NO_SONG,
    REASON_PLACEHOLDER,
    REASON_SONG_OUT_OF_SYNC,
    SOURCE_CATALOG,
    SOURCE_COMPOSITION,
    SOURCE_CUSTOM,
    UNAVAILABLE_MESSAGES,
    build_song_coach_context,
    chart_confidence,
    composition_reference_chart,
    song_coach_context_from_session,
    source_owner,
)


def _record(title: str) -> dict:
    from song_catalog.catalog import curated_song_records

    return copy.deepcopy(next(r for r in curated_song_records() if r["title"] == title))


def _catalog_ctx(record: dict, *, key: str | None = None, sections: dict | None = None, **kw):
    original = record["key"]
    concert = key or original
    secs = sections if sections is not None else transpose_sections_dict(record["sections"], original, concert)
    return build_song_coach_context(
        identity=kw.pop("identity", f"catalog|{record['title']}"),
        source_kind=SOURCE_CATALOG,
        concert_sections=secs,
        concert_key=concert,
        section_order=record.get("section_order"),
        record=record,
        reference_sections=record["sections"],
        reference_key=original,
        **kw,
    )


PERFECT_PICK = "Perfect\x1fEd Sheeran"
IPANEMA_PICK = "The Girl from Ipanema\x1fAntônio Carlos Jobim"


def _catalog_session(record: dict, pick: str) -> dict:
    return {
        "active_catalog_pick_key": pick,
        "active_music_source": "catalog_song",
        "selected_song": dict(copy.deepcopy(record), pick_key=pick),
        "instrument": "Saxophone",
        "improv_generated_sections": {"Section A (Jazz Swing)": ["Em7", "A7", "Dmaj7", "Bm7"]},
    }


TRIAL_CPL = {
    "id": "rev42",
    "name": "Trial Song",
    "original_key_center": "E",
    "time_signature": "3/4",
    "bpm": 92,
    "original_sections": {
        "Verse": [{"chord": "E", "bars": 2}, {"chord": "C#m7", "bars": 1}, {"chord": "A", "bars": 1}],
        "Chorus": [{"chord": "A", "bars": 1}, {"chord": "B7", "bars": 1}, {"chord": "E", "bars": 2}],
    },
}
TRIAL_IN_E = {"Verse": ["E", "E", "C#m7", "A"], "Chorus": ["A", "B7", "E", "E"]}


def _custom_session(cpl: dict | None = None) -> dict:
    cpl = copy.deepcopy(TRIAL_CPL if cpl is None else cpl)
    return {
        "active_catalog_pick_key": f"custom::{cpl.get('id') or 'x'}",
        "active_music_source": "custom_progression",
        "cpl_active_progression": cpl,
        "home_sections": {"Verse 1": ["G", "G", "Em7", "Em7"]},  # the previous Catalog song's leftovers
        "improv_generated_sections": {"Section A (Jazz Swing)": ["Em7", "A7"]},
    }


def _composition(title: str = "My Song", key: str = "D", chords: list | None = None) -> dict:
    from composition_document import new_composition_document

    doc = new_composition_document(title=title)
    doc["global"]["original_key_center"] = key
    ids = doc["form"]["section_order"]
    if chords is not None:
        doc["form"]["sections"][ids[0]]["chords"] = [{"chord": c, "bars": 1} for c in chords]
    return doc


def _composition_session(doc: dict) -> dict:
    return {
        "active_catalog_pick_key": f"composition::{doc['id']}",
        "active_music_source": "composition_song",
        "composer_active_document": doc,
        "home_sections": {"Verse 1": ["G", "G", "Em7", "Em7"]},
    }


class TestChartConfidence(unittest.TestCase):
    def test_catalog_statuses(self) -> None:
        for status in ("verified", "practice_level_verified", "user_verified"):
            self.assertEqual(chart_confidence(SOURCE_CATALOG, {"chart_status": status}), CHART_VERIFIED)
        self.assertEqual(chart_confidence(SOURCE_CATALOG, {"trusted_core": True}), CHART_VERIFIED)
        for status in ("practice_simplified", "practice_needs_review", "", None):
            self.assertEqual(chart_confidence(SOURCE_CATALOG, {"chart_status": status}), CHART_PRACTICE)
        self.assertEqual(chart_confidence(SOURCE_CATALOG, None), CHART_PRACTICE)

    def test_user_charts(self) -> None:
        self.assertEqual(chart_confidence(SOURCE_CATALOG, {"chart_status": "user_corrected_reference"}), CHART_USER_EDITED)
        self.assertEqual(
            chart_confidence(SOURCE_CATALOG, {"chart_status": "practice_level_verified", "user_override": {"x": 1}}),
            CHART_USER_EDITED,
        )
        self.assertEqual(chart_confidence(SOURCE_CUSTOM, {"chart_status": "verified"}), CHART_USER_AUTHORED)
        self.assertEqual(chart_confidence(SOURCE_COMPOSITION, {}), CHART_USER_AUTHORED)

    def test_labels_distinguish_verified_from_practice_and_never_claim_a_melody(self) -> None:
        self.assertNotEqual(CHART_CONFIDENCE_LABELS[CHART_VERIFIED], CHART_CONFIDENCE_LABELS[CHART_PRACTICE])
        self.assertIn("Simplified", CHART_CONFIDENCE_LABELS[CHART_PRACTICE])
        self.assertIn("may differ from the recording", CHART_CONFIDENCE_NOTES[CHART_PRACTICE])
        for conf in (CHART_VERIFIED, CHART_PRACTICE, CHART_USER_EDITED):
            self.assertIn("does not know the song's melody", CHART_CONFIDENCE_NOTES[conf])
        for text in list(CHART_CONFIDENCE_LABELS.values()) + list(CHART_CONFIDENCE_NOTES.values()):
            self.assertNotRegex(text.lower(), r"original melody is|the solo goes|as recorded by")

    def test_title_never_decides_confidence(self) -> None:
        self.assertEqual(chart_confidence(SOURCE_CATALOG, {"title": "Perfect"}), CHART_PRACTICE)


class TestBuildContext(unittest.TestCase):
    def test_perfect_at_its_own_key(self) -> None:
        rec = _record("Perfect")
        ctx = _catalog_ctx(rec, instrument="Saxophone", chart_key="E", written_key="E")
        self.assertTrue(ctx.available, ctx.reason)
        self.assertTrue(ctx.chart_structure_verified)
        self.assertEqual(ctx.chart_confidence, CHART_VERIFIED)
        self.assertEqual([n for n, _ in ctx.sections], rec["section_order"])
        self.assertEqual(ctx.section_map()["Verse 1"], rec["sections"]["Verse 1"])
        self.assertEqual((ctx.concert_key, ctx.chart_key, ctx.written_key), ("G", "E", "E"))
        self.assertEqual(ctx.unavailable_message, "")

    def test_practice_key_move_is_accepted_only_when_the_chart_moved_with_it(self) -> None:
        rec = _record("Perfect")
        moved = _catalog_ctx(rec, key="A")
        self.assertTrue(moved.available, moved.reason)
        self.assertEqual(moved.section_map()["Chorus 1"][:4], ["F#m7", "Dadd9", "A", "E/G#"])
        stale = _catalog_ctx(rec, key="A", sections=rec["sections"])  # chart still in G
        self.assertEqual((stale.available, stale.reason), (False, REASON_KEY_OUT_OF_SYNC))
        wrong = _catalog_ctx(rec, key="A", sections=transpose_sections_dict(rec["sections"], "G", "Bb"))
        self.assertEqual(wrong.reason, REASON_KEY_OUT_OF_SYNC)

    def test_minor_key_song_moves(self) -> None:
        rec = _record("Hotel California")
        ctx = _catalog_ctx(rec, key="Dm")
        self.assertTrue(ctx.available, ctx.reason)

    def test_another_songs_chart_is_refused(self) -> None:
        perfect, ipanema = _record("Perfect"), _record("The Girl from Ipanema")
        ctx = _catalog_ctx(perfect, sections=ipanema["sections"])
        self.assertEqual((ctx.available, ctx.reason), (False, REASON_CHART_OUT_OF_SYNC))

    def test_fail_closed_reasons(self) -> None:
        rec = _record("Perfect")
        self.assertEqual(_catalog_ctx(rec, identity="").reason, REASON_NO_SONG)
        self.assertEqual(_catalog_ctx(rec, sections={}).reason, REASON_NO_CHORDS)
        self.assertEqual(
            build_song_coach_context(
                identity="custom|x", source_kind=SOURCE_CUSTOM, concert_sections={"A": ["N.C.", "N.C."]}, concert_key="C"
            ).reason,
            REASON_NO_CHORDS,
        )
        self.assertEqual(
            build_song_coach_context(
                identity="custom|x", source_kind=SOURCE_CUSTOM, concert_sections={"A": ["C", "G"]}, concert_key=""
            ).reason,
            REASON_NO_KEY,
        )
        placeholder = dict(rec, chart_status="placeholder")
        self.assertEqual(_catalog_ctx(placeholder).reason, REASON_PLACEHOLDER)
        jam = {"Section A (Jazz Swing)": ["Em7", "A7"]}
        ctx = build_song_coach_context(
            identity="catalog|x", source_kind=SOURCE_CATALOG, concert_sections=jam, concert_key="D", jam_sections=jam
        )
        self.assertEqual(ctx.reason, REASON_JAM_PROGRESSION)
        for reason in (REASON_NO_SONG, REASON_NO_CHORDS, REASON_PLACEHOLDER, REASON_JAM_PROGRESSION, REASON_KEY_OUT_OF_SYNC):
            self.assertTrue(UNAVAILABLE_MESSAGES[reason])
        self.assertFalse(_catalog_ctx(rec, identity="").sections)

    def test_fingerprint_tracks_song_key_meter_and_bars_not_projection(self) -> None:
        rec = _record("Perfect")
        base = _catalog_ctx(rec, instrument="Piano", chart_key="G")
        self.assertEqual(base.fingerprint, _catalog_ctx(rec, instrument="Piano", chart_key="G").fingerprint)
        self.assertNotEqual(base.fingerprint, _catalog_ctx(rec, identity="catalog|other").fingerprint)
        self.assertNotEqual(base.fingerprint, _catalog_ctx(rec, key="A").fingerprint)
        self.assertNotEqual(base.fingerprint, _catalog_ctx(rec, meter="3/4").fingerprint)
        edited = copy.deepcopy(rec)
        edited["sections"]["Chorus 1"][-1] = "D"
        self.assertNotEqual(base.fingerprint, _catalog_ctx(edited).fingerprint)
        sax = _catalog_ctx(rec, instrument="Saxophone", chart_key="E", written_key="E")
        self.assertEqual(base.fingerprint, sax.fingerprint)
        self.assertNotEqual(base.projection_fingerprint, sax.projection_fingerprint)

    def test_to_dict_is_json_ready(self) -> None:
        import json

        ctx = _catalog_ctx(_record("Perfect"))
        self.assertEqual(json.loads(json.dumps(ctx.to_dict()))["fingerprint"], ctx.fingerprint)


class TestCatalogSession(unittest.TestCase):
    def test_reads_the_live_catalog_song_without_writing_session(self) -> None:
        rec = _record("Perfect")
        session = _catalog_session(rec, PERFECT_PICK)
        before = copy.deepcopy(session)
        ctx = song_coach_context_from_session(
            session,
            concert_sections=transpose_sections_dict(rec["sections"], "G", "A"),
            concert_key="A",
            chart_key="F#",
            written_key="F#",
        )
        self.assertEqual(session, before)
        self.assertTrue(ctx.available, ctx.reason)
        self.assertEqual(ctx.identity, f"catalog|{PERFECT_PICK}")
        self.assertEqual((ctx.source_kind, ctx.chart_confidence, ctx.instrument), (SOURCE_CATALOG, CHART_VERIFIED, "Saxophone"))
        self.assertEqual(ctx.song_title, "Perfect")
        self.assertEqual([n for n, _ in ctx.sections], rec["section_order"])
        self.assertTrue(ctx.chart_structure_verified)

    def test_meter_and_tempo_come_from_the_song_when_not_passed(self) -> None:
        from song_catalog.catalog import curated_song_records

        waltz = next(r for r in curated_song_records() if (r.get("extensions") or {}).get("time_signature") == "3/4")
        session = _catalog_session(waltz, f"{waltz['title']}\x1f{waltz['artist']}")
        ctx = song_coach_context_from_session(session, concert_sections=waltz["sections"], concert_key=waltz["key"])
        self.assertTrue(ctx.available, ctx.reason)
        self.assertEqual(ctx.meter, "3/4")
        self.assertEqual(song_coach_context_from_session(
            session, concert_sections=waltz["sections"], concert_key=waltz["key"], meter="6/8"
        ).meter, "6/8")

    def test_jam_progression_never_stands_in_for_the_song(self) -> None:
        rec = _record("Perfect")
        session = _catalog_session(rec, PERFECT_PICK)
        ctx = song_coach_context_from_session(
            session, concert_sections=session["improv_generated_sections"], concert_key="D"
        )
        self.assertFalse(ctx.available)
        self.assertIn(ctx.reason, {REASON_JAM_PROGRESSION, REASON_CHART_OUT_OF_SYNC})

    def test_previous_songs_map_is_refused(self) -> None:
        session = _catalog_session(_record("Perfect"), PERFECT_PICK)
        ctx = song_coach_context_from_session(
            session, concert_sections=_record("The Girl from Ipanema")["sections"], concert_key="G"
        )
        self.assertEqual((ctx.available, ctx.reason), (False, REASON_CHART_OUT_OF_SYNC))

    def test_selected_song_of_another_pick_is_out_of_sync(self) -> None:
        session = _catalog_session(_record("Perfect"), PERFECT_PICK)
        session["active_catalog_pick_key"] = IPANEMA_PICK  # Songs moved on; selected_song still Perfect
        ctx = song_coach_context_from_session(session, concert_sections=_record("Perfect")["sections"], concert_key="G")
        self.assertEqual((ctx.available, ctx.reason), (False, REASON_SONG_OUT_OF_SYNC))

    def test_no_song_at_all(self) -> None:
        ctx = song_coach_context_from_session({}, concert_sections={"A": ["C", "G"]}, concert_key="C")
        self.assertEqual((ctx.available, ctx.reason), (False, REASON_NO_SONG))

    def test_sbi_custom_preview_does_not_change_the_coached_song(self) -> None:
        rec = _record("Perfect")
        session = _catalog_session(rec, PERFECT_PICK)
        session.update(
            {
                "improv_song_source": "Custom progression",
                "sbi_preview_source": "Custom progression",
                "cpl_active_progression": copy.deepcopy(TRIAL_CPL),
            }
        )
        self.assertEqual(source_owner(session), SOURCE_CATALOG)
        ctx = song_coach_context_from_session(session, concert_sections=rec["sections"], concert_key="G")
        self.assertTrue(ctx.available, ctx.reason)
        self.assertEqual(ctx.identity, f"catalog|{PERFECT_PICK}")
        refused = song_coach_context_from_session(session, concert_sections=TRIAL_IN_E, concert_key="E")
        self.assertFalse(refused.available)


class TestCustomSession(unittest.TestCase):
    def test_custom_owner_chart_at_its_practice_key(self) -> None:
        session = _custom_session()
        before = copy.deepcopy(session)
        self.assertEqual(source_owner(session), SOURCE_CUSTOM)
        at_g = transpose_sections_dict(TRIAL_IN_E, "E", "G")
        ctx = song_coach_context_from_session(session, concert_sections=at_g, concert_key="G")
        self.assertEqual(session, before)
        self.assertTrue(ctx.available, ctx.reason)
        self.assertEqual(ctx.identity, "custom|custom::rev42")
        self.assertEqual((ctx.song_title, ctx.chart_confidence, ctx.meter, ctx.bpm), ("Trial Song", CHART_USER_AUTHORED, "3/4", 92))
        self.assertEqual(ctx.section_map(), at_g)

    def test_leftover_catalog_or_stale_key_maps_are_refused(self) -> None:
        session = _custom_session()
        leftover = song_coach_context_from_session(session, concert_sections=session["home_sections"], concert_key="G")
        self.assertEqual(leftover.reason, REASON_CHART_OUT_OF_SYNC)
        stale = song_coach_context_from_session(session, concert_sections=TRIAL_IN_E, concert_key="G")
        self.assertEqual(stale.reason, REASON_KEY_OUT_OF_SYNC)

    def test_empty_custom_progression_fails_closed(self) -> None:
        from custom_progression_lab import default_active_progression

        empty = dict(default_active_progression(), id="empty1")
        session = _custom_session(empty)
        ctx = song_coach_context_from_session(session, concert_sections=session["home_sections"], concert_key="G")
        self.assertEqual((ctx.available, ctx.reason, ctx.source_kind), (False, REASON_NO_CHORDS, SOURCE_CUSTOM))


class TestCompositionSession(unittest.TestCase):
    def test_reference_mirrors_the_composition_resolver(self) -> None:
        from workflow_musical_authority import resolve_composition_concert_sections_at_practice_key

        doc = _composition(chords=["D", "G", "A7", "D"])
        ids = doc["form"]["section_order"]
        doc["form"]["sections"][ids[1]]["label"] = doc["form"]["sections"][ids[0]]["label"]  # repeated label
        doc["form"]["sections"][ids[1]]["chords"] = [{"chord": "Bm", "bars": 2}, {"chord": "G", "bars": 1}]
        session = _composition_session(doc)
        reference, key, record = composition_reference_chart(doc)
        self.assertEqual(key, "D")
        self.assertEqual(record["title"], "My Song")
        self.assertEqual(reference, resolve_composition_concert_sections_at_practice_key(session))

    def test_composition_owner_chart(self) -> None:
        doc = _composition(chords=["D", "G", "A7", "D"])
        session = _composition_session(doc)
        before = copy.deepcopy(session)
        self.assertEqual(source_owner(session), SOURCE_COMPOSITION)
        label = composition_reference_chart(doc)[0]
        ctx = song_coach_context_from_session(session, concert_sections=label, concert_key="D")
        self.assertEqual(session, before)
        self.assertTrue(ctx.available, ctx.reason)
        self.assertEqual(ctx.identity, f"composition|composition::{doc['id']}")
        self.assertEqual(ctx.chart_confidence, CHART_USER_AUTHORED)

    def test_empty_composition_never_borrows_the_previous_songs_chords(self) -> None:
        session = _composition_session(_composition(chords=None))
        ctx = song_coach_context_from_session(session, concert_sections=session["home_sections"], concert_key="G")
        self.assertEqual((ctx.available, ctx.reason, ctx.source_kind), (False, REASON_NO_CHORDS, SOURCE_COMPOSITION))


class TestWholeCatalog(unittest.TestCase):
    def test_every_curated_chart_builds_at_its_key_and_a_moved_key(self) -> None:
        from song_catalog.catalog import curated_song_records

        songs = curated_song_records()
        self.assertGreater(len(songs), 50)
        for rec in songs:
            home = _catalog_ctx(rec)
            if rec.get("chart_status") == "placeholder":
                self.assertEqual(home.reason, REASON_PLACEHOLDER, rec["title"])
                continue
            self.assertTrue(home.available, (rec["title"], home.reason))
            self.assertTrue(home.chart_structure_verified, rec["title"])
            minor = "m" in rec["key"][1:] and "maj" not in rec["key"]
            moved_key = "Ebm" if minor else "Eb"
            if rec["key"] in ("Eb", "Ebm"):
                moved_key = "Fm" if minor else "F"
            moved = _catalog_ctx(rec, key=moved_key)
            self.assertTrue(moved.available, (rec["title"], moved_key, moved.reason))
            self.assertNotEqual(home.fingerprint, moved.fingerprint, rec["title"])


if __name__ == "__main__":
    unittest.main()
