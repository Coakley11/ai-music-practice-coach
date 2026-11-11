"""Issue 64 slices 2 and 3: say what a saved project is, and find the right one.

The scenario these are written against is the user's: *All the Things You Are* saved
twice in B flat and once in A flat, *Eleanor Rigby* saved in E minor, plus an old row
from before recording identity existed. Opening the wrong one, or showing an A flat
arrangement as a B flat match, is the failure that matters - so most of these are about
what is *not* claimed.
"""

from __future__ import annotations

import unittest

from multitrack_project_discovery import (
    KEY_STATUS_LEGACY,
    KEY_STATUS_MIXED,
    KEY_STATUS_SINGLE,
    MATCH_LEGACY,
    MATCH_OTHER_KEY,
    MATCH_SONG_AND_KEY,
    describe_project,
    find_projects_for_song,
    group_projects_by_song_and_key,
    layer_key_lines,
    project_key_label,
    project_key_status,
    project_source,
)

ATTYA = ("catalog", "catalog::attya")
RIGBY = ("catalog", "catalog::rigby")


def track(instrument, key, *, source=ATTYA, slot="Sax / winds"):
    return {
        "track_id": f"t-{instrument}-{key or 'none'}", "slot": slot,
        "name": f"{instrument} take", "instrument": instrument,
        "recording_concert_key": key, "recording_written_key": "",
        "recording_source_type": source[0], "recording_source_id": source[1],
        "storage_ref": "supabase://music-media/u/w/x.wav", "deleted": False,
    }


def project(title, *, source=ATTYA, song="All The Things You Are", tracks=(),
            updated="2026-11-01T00:00:00+00:00", backing=True, identity=None,
            practice_key="Bb"):
    return {
        "multitrack_id": f"mt-{title.lower().replace(' ', '-')}",
        "title": title, "song": song, "updated_at": updated,
        "practice_concert_key": practice_key,
        "activity_source_context": (
            {"source_type": source[0], "source_id": source[1], "song": song}
            if source else {}
        ),
        "recording_identity": dict(identity or {}),
        "tracks": list(tracks),
        "backing_storage_ref": "supabase://music-media/u/w/b.wav" if backing else None,
        "deleted": False,
    }


FLUTE_BB = project("Flute Take", tracks=[track("Flute", "Bb")],
                   updated="2026-11-03T00:00:00+00:00")
ENSEMBLE_BB = project("Flute and Sax Ensemble",
                      tracks=[track("Flute", "Bb"),
                              track("Alto saxophone (Eb)", "Bb", slot="Guitar")],
                      updated="2026-11-05T00:00:00+00:00")
ALT_AB = project("Alternate Arrangement", tracks=[track("Flute", "Ab")],
                 updated="2026-11-04T00:00:00+00:00", practice_key="Ab")
RIGBY_EM = project("Guitar and Flute", source=RIGBY, song="Eleanor Rigby",
                   tracks=[track("Guitar", "Em", source=RIGBY),
                           track("Flute", "Em", source=RIGBY)],
                   updated="2026-11-06T00:00:00+00:00", practice_key="Em")
MIXED = project("Mixed Session",
                tracks=[track("Flute", "Bb"), track("Guitar", "Ab", slot="Guitar")],
                updated="2026-11-02T00:00:00+00:00")
LEGACY = {
    "multitrack_id": "mt-legacy", "title": "Old project", "song": "Autumn Leaves",
    "practice_concert_key": "G", "updated_at": "2026-10-01T00:00:00+00:00",
    "activity_source_context": {}, "recording_identity": {},
    "tracks": [{"track_id": "t1", "slot": "Guitar", "name": "Take",
                "instrument": "Guitar", "recording_concert_key": "",
                "recording_source_type": "", "recording_source_id": "",
                "storage_ref": "supabase://b/k", "deleted": False}],
    "deleted": False,
}
ALL = [FLUTE_BB, ENSEMBLE_BB, ALT_AB, RIGBY_EM, MIXED, LEGACY]


class AProjectSaysWhatKeyItIsHonestly(unittest.TestCase):
    def test_every_layer_agreeing_is_a_single_key(self):
        status, keys = project_key_status(ENSEMBLE_BB)
        self.assertEqual((status, keys), (KEY_STATUS_SINGLE, ["Bb"]))
        self.assertEqual(project_key_label(ENSEMBLE_BB), "Bb")

    def test_two_keys_are_reported_as_mixed_with_both_named(self):
        status, keys = project_key_status(MIXED)
        self.assertEqual(status, KEY_STATUS_MIXED)
        self.assertEqual(keys, ["Ab", "Bb"])
        self.assertIn("Mixed keys", project_key_label(MIXED))
        self.assertIn("Ab", project_key_label(MIXED))

    def test_a_legacy_project_says_unknown_rather_than_guessing(self):
        status, keys = project_key_status(LEGACY)
        self.assertEqual((status, keys), (KEY_STATUS_LEGACY, []))
        self.assertEqual(project_key_label(LEGACY), "Recording key unknown")

    def test_the_projects_practice_key_is_never_used_as_the_recorded_key(self):
        """LEGACY carries practice_concert_key G; that is not evidence about its take."""
        self.assertEqual(LEGACY["practice_concert_key"], "G")
        self.assertNotIn("G", project_key_label(LEGACY))

    def test_a_partly_stamped_project_is_mixed_not_single(self):
        half = project("Half", tracks=[track("Flute", "Bb"),
                                       track("Guitar", "", slot="Guitar")])
        status, _keys = project_key_status(half)
        self.assertEqual(status, KEY_STATUS_MIXED,
                         "one stamped layer does not speak for an unstamped one")

    def test_the_identity_block_is_used_when_layers_carry_no_stamp(self):
        row = project("From identity", tracks=[],
                      identity={"recording_keys": ["Bb"], "recording_concert_key": "Bb"})
        self.assertEqual(project_key_status(row), (KEY_STATUS_SINGLE, ["Bb"]))

    def test_each_layer_reports_its_own_key(self):
        lines = layer_key_lines(MIXED)
        self.assertIn("Flute - Bb", lines)
        self.assertIn("Guitar - Ab", lines)

    def test_an_unstamped_layer_says_so_in_its_line(self):
        self.assertEqual(layer_key_lines(LEGACY), ["Guitar - recording key unknown"])


class ProjectsAreFoundBySongIdentityNotTitle(unittest.TestCase):
    def test_a_matching_song_and_key_ranks_first(self):
        found = find_projects_for_song(ALL, {"source_type": ATTYA[0], "source_id": ATTYA[1]}, "Bb")
        self.assertEqual(found[0]["match"], MATCH_SONG_AND_KEY)
        self.assertEqual(
            [e["title"] for e in found if e["match"] == MATCH_SONG_AND_KEY],
            ["Flute and Sax Ensemble", "Flute Take"],
            "both B flat projects, newest first",
        )

    def test_the_same_song_in_another_key_comes_after_but_is_still_offered(self):
        found = find_projects_for_song(ALL, {"source_type": ATTYA[0], "source_id": ATTYA[1]}, "Bb")
        titles = [e["title"] for e in found]
        self.assertIn("Alternate Arrangement", titles)
        self.assertGreater(titles.index("Alternate Arrangement"), titles.index("Flute Take"))
        self.assertEqual(
            next(e for e in found if e["title"] == "Alternate Arrangement")["match"],
            MATCH_OTHER_KEY)

    def test_another_song_is_not_offered_at_all(self):
        found = find_projects_for_song(ALL, {"source_type": ATTYA[0], "source_id": ATTYA[1]}, "Bb")
        self.assertNotIn("Guitar and Flute", [e["title"] for e in found])

    def test_a_same_titled_song_from_another_source_does_not_match(self):
        composition = project("Composition version",
                              source=("composition", "composition::attya"),
                              tracks=[track("Flute", "Bb",
                                            source=("composition", "composition::attya"))])
        found = find_projects_for_song(
            [FLUTE_BB, composition],
            {"source_type": ATTYA[0], "source_id": ATTYA[1]}, "Bb")
        self.assertEqual([e["title"] for e in found], ["Flute Take"])

    def test_a_mixed_key_project_is_not_a_single_key_match(self):
        found = find_projects_for_song(
            [MIXED], {"source_type": ATTYA[0], "source_id": ATTYA[1]}, "Bb")
        self.assertEqual(found[0]["match"], MATCH_OTHER_KEY,
                         "a mixed project must not pass as an ordinary Bb match")
        self.assertEqual(found[0]["key_status"], KEY_STATUS_MIXED)

    def test_a_legacy_project_stays_findable(self):
        found = find_projects_for_song(ALL, {"source_type": ATTYA[0], "source_id": ATTYA[1]}, "Bb")
        legacy = [e for e in found if e["match"] == MATCH_LEGACY]
        self.assertEqual([e["title"] for e in legacy], ["Old project"])
        self.assertTrue(legacy[0]["legacy_identity"])

    def test_legacy_rows_rank_after_real_matches(self):
        found = find_projects_for_song(ALL, {"source_type": ATTYA[0], "source_id": ATTYA[1]}, "Bb")
        titles = [e["title"] for e in found]
        self.assertGreater(titles.index("Old project"), titles.index("Alternate Arrangement"))

    def test_asking_for_a_song_with_no_identity_returns_only_legacy_rows(self):
        found = find_projects_for_song(ALL, {}, "Bb")
        self.assertEqual([e["title"] for e in found], ["Old project"])

    def test_other_songs_can_be_requested_explicitly(self):
        found = find_projects_for_song(
            ALL, {"source_type": ATTYA[0], "source_id": ATTYA[1]}, "Bb",
            include_other_songs=True)
        self.assertIn("Guitar and Flute", [e["title"] for e in found])

    def test_a_deleted_row_is_never_offered(self):
        dead = dict(FLUTE_BB, deleted=True)
        found = find_projects_for_song(
            [dead], {"source_type": ATTYA[0], "source_id": ATTYA[1]}, "Bb")
        self.assertEqual(found, [])


class SeveralProjectsForOneSongAndKeyStaySeparate(unittest.TestCase):
    def test_project_id_is_the_identity_not_song_plus_key(self):
        found = find_projects_for_song(
            [FLUTE_BB, ENSEMBLE_BB], {"source_type": ATTYA[0], "source_id": ATTYA[1]}, "Bb")
        self.assertEqual(len(found), 2)
        self.assertEqual(len({e["multitrack_id"] for e in found}), 2)

    def test_each_reports_its_own_layer_count_and_instruments(self):
        found = {e["title"]: e for e in find_projects_for_song(
            [FLUTE_BB, ENSEMBLE_BB], {"source_type": ATTYA[0], "source_id": ATTYA[1]}, "Bb")}
        self.assertEqual(found["Flute Take"]["layer_count"], 1)
        self.assertEqual(found["Flute and Sax Ensemble"]["layer_count"], 2)
        self.assertEqual(found["Flute Take"]["instruments"], ["Flute"])
        self.assertEqual(found["Flute and Sax Ensemble"]["instruments"],
                         ["Flute", "Alto saxophone (Eb)"])


class TheAllProjectsViewGroupsWithoutMerging(unittest.TestCase):
    def test_groups_are_song_and_recorded_key(self):
        groups = group_projects_by_song_and_key(ALL)
        labels = {(g["song"], g["key_label"]) for g in groups}
        self.assertIn(("All The Things You Are", "Bb"), labels)
        self.assertIn(("All The Things You Are", "Ab"), labels)
        self.assertIn(("Eleanor Rigby", "Em"), labels)
        self.assertIn(("Autumn Leaves", "Recording key unknown"), labels)

    def test_two_projects_in_one_group_remain_two_projects(self):
        groups = {(g["song"], g["key_label"]): g for g in group_projects_by_song_and_key(ALL)}
        bb = groups[("All The Things You Are", "Bb")]
        self.assertEqual(bb["project_count"], 2)
        self.assertEqual(len({p["multitrack_id"] for p in bb["projects"]}), 2)

    def test_a_mixed_project_gets_its_own_group_not_the_bb_one(self):
        groups = {(g["song"], g["key_label"]): g for g in group_projects_by_song_and_key(ALL)}
        self.assertEqual(groups[("All The Things You Are", "Bb")]["project_count"], 2)
        mixed = [g for g in group_projects_by_song_and_key(ALL)
                 if g["key_label"].startswith("Mixed keys")]
        self.assertEqual(len(mixed), 1)
        self.assertEqual(mixed[0]["projects"][0]["title"], "Mixed Session")

    def test_each_entry_carries_what_the_view_needs(self):
        entry = describe_project(ENSEMBLE_BB)
        self.assertEqual(entry["song"], "All The Things You Are")
        self.assertEqual(entry["key_label"], "Bb")
        self.assertEqual(entry["layer_count"], 2)
        self.assertTrue(entry["has_backing"])
        self.assertTrue(entry["updated_at"])
        self.assertEqual(entry["source_id"], ATTYA[1])

    def test_a_project_without_backing_says_so(self):
        self.assertFalse(describe_project(project("No backing", backing=False))["has_backing"])

    def test_the_source_falls_back_to_the_layers_when_the_context_is_missing(self):
        row = project("Context lost", source=None, tracks=[track("Flute", "Bb")])
        self.assertEqual(project_source(row), ATTYA)


if __name__ == "__main__":
    unittest.main()


class TheLibraryShowsMatchesFirstWithoutHidingAnything(unittest.TestCase):
    """Ranking reorders the library; it must never drop a row or break load/delete."""

    def rows(self):
        return [{"item_key": p["multitrack_id"], "title": p["title"],
                 "updated_at": p["updated_at"], "payload": p} for p in ALL]

    def session(self, source=ATTYA, key="Bb"):
        return {"display_key": key, "_owner": source}

    def ranked(self, session_patch=None):
        from unittest import mock

        import multitrack_project_discovery as d

        owner = (session_patch or {}).get("owner", {"source_type": ATTYA[0],
                                                    "source_id": ATTYA[1]})
        with mock.patch.object(d, "active_song_owner", lambda ss: owner):
            return d.rank_library_rows(self.rows(), {"display_key": (session_patch or {}).get("key", "Bb")})

    def test_no_row_is_lost_by_ranking(self):
        out, _note = self.ranked()
        self.assertEqual(len(out), len(ALL))
        self.assertEqual({r["item_key"] for r in out},
                         {p["multitrack_id"] for p in ALL})

    def test_the_matching_projects_come_first(self):
        out, _note = self.ranked()
        self.assertEqual([r["title"] for r in out][:2],
                         ["Flute and Sax Ensemble", "Flute Take"])

    def test_the_note_counts_only_real_key_matches(self):
        _out, note = self.ranked()
        self.assertIn("2 saved project(s) recorded in Bb", note)

    def test_a_key_with_no_match_says_so_rather_than_claiming_one(self):
        _out, note = self.ranked({"key": "F#"})
        self.assertIn("No saved project was recorded in this key", note)

    def test_an_unknown_song_leaves_the_order_untouched(self):
        out, note = self.ranked({"owner": {}})
        self.assertEqual([r["title"] for r in out], [p["title"] for p in ALL])
        self.assertEqual(note, "")

    def test_the_original_row_objects_are_handed_back(self):
        """The list renderer's load and delete actions key off these rows."""
        originals = self.rows()
        from unittest import mock

        import multitrack_project_discovery as d

        with mock.patch.object(d, "active_song_owner",
                               lambda ss: {"source_type": ATTYA[0], "source_id": ATTYA[1]}):
            out, _ = d.rank_library_rows(originals, {"display_key": "Bb"})
        for row in out:
            self.assertTrue(any(row is o for o in originals))
