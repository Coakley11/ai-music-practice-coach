"""The Continue card tells the truth or says nothing.

A card headed "pick up where you left off" is a factual claim about the past. It
may only be made from a saved Practice Log entry, never from whatever happens to
be loaded in the workspace right now.
"""

import unittest
from datetime import date

import home_recent_session as hrs


def _entry(**over):
    base = {
        "session_id": "s-1",
        "date": "2026-11-01",
        "active_song": "Blue Bossa",
        "song_id": "Jazz::Blue Bossa",
        "instrument": "Alto Saxophone",
        "practice_concert_key": "F minor",
        "display_key": "F minor",
        "written_key": "D minor",
        "original_key": "C minor",
        "guitar_shape_key": "",
        "practice_type": "song practice",
        "focus_area": "soloing/improv",
        "duration_minutes": 25,
        "section_practiced": "whole song",
    }
    base.update(over)
    return base


class TestOnlySavedHistoryCounts(unittest.TestCase):
    def test_no_saved_entries_means_no_card(self):
        self.assertIsNone(hrs.verified_recent_session({}, entries=[]))

    def test_a_loaded_song_alone_is_not_a_previous_session(self):
        live = {
            "selected_song": {"title": "Autumn Leaves"},
            "active_catalog_pick": "Jazz::Autumn Leaves",
            "instrument": "Flute",
            "display_key": "G minor",
        }
        self.assertIsNone(hrs.verified_recent_session(live, entries=[]))

    def test_a_deleted_entry_is_not_resurrected(self):
        rows = [{"session_id": "s-1", "deleted": True, "updated_at": "2026-11-01T00:00:00Z"}]
        self.assertIsNone(hrs.verified_recent_session({}, entries=rows))

    def test_an_entry_without_an_id_is_ignored(self):
        self.assertIsNone(hrs.verified_recent_session({}, entries=[_entry(session_id="")]))

    def test_the_newest_usable_entry_wins(self):
        rows = [_entry(session_id="new", active_song="Blue Bossa"),
                _entry(session_id="old", active_song="So What")]
        got = hrs.verified_recent_session({}, entries=rows)
        self.assertEqual(got.song_title, "Blue Bossa")

    def test_an_unusable_newest_entry_falls_through_to_the_next(self):
        rows = [{"session_id": "", "active_song": "junk"},
                _entry(session_id="good", active_song="So What")]
        got = hrs.verified_recent_session({}, entries=rows)
        self.assertEqual(got.song_title, "So What")

    def test_a_built_card_declares_itself_verified(self):
        got = hrs.verified_recent_session({}, entries=[_entry()])
        self.assertTrue(got.verified)

    def test_the_empty_state_does_not_claim_a_session_exists(self):
        text = (hrs.EMPTY_STATE_TITLE + " " + hrs.EMPTY_STATE_BODY).lower()
        self.assertIn("no saved practice session", text)


class TestTheCardDoesNotPromiseARestore(unittest.TestCase):
    """This slice navigates; it does not reload the song. The words must match."""

    def test_the_heading_reports_rather_than_promising_to_resume(self):
        self.assertEqual(hrs.SECTION_EYEBROW, "Recent practice")

    def test_no_user_facing_string_implies_the_session_is_restored(self):
        blob = " ".join([hrs.SECTION_EYEBROW, hrs.EMPTY_STATE_TITLE,
                         hrs.EMPTY_STATE_BODY, hrs.ACTION_CAPTION]).lower()
        for word in ("continue practicing", "pick up where you left off", "resume"):
            self.assertNotIn(word, blob)

    def test_the_action_names_where_it_goes(self):
        got = hrs.verified_recent_session({}, entries=[_entry()])
        self.assertEqual(got.destination_label(), "Practice")
        self.assertEqual(got.action_label(), "Go to Practice")

    def test_each_destination_gets_its_own_name(self):
        cases = {
            "song practice": "Practice",
            "backing track": "Backing",
            "custom progression": "Custom Progressions",
            "multitrack/upload": "Multitrack",
            "composition practice": "Composition",
            "mission practice": "Missions",
        }
        for ptype, label in cases.items():
            with self.subTest(practice_type=ptype):
                got = hrs.session_from_entry(_entry(practice_type=ptype))
                self.assertEqual(got.destination_label(), label)

    def test_the_caption_says_the_song_is_not_reloaded(self):
        caption = hrs.ACTION_CAPTION.format(destination="Practice").lower()
        self.assertIn("does not reload the song", caption)
        self.assertIn("stay exactly as they are", caption)

    def test_the_label_never_comes_back_empty(self):
        got = hrs.session_from_entry(_entry(practice_type="interpretive dance"))
        self.assertTrue(got.destination_label().strip())
        self.assertTrue(got.action_label().startswith("Go to "))


class TestConcertAndWrittenKeysAreDistinguished(unittest.TestCase):
    def test_a_transposing_instrument_shows_both_keys_with_distinct_labels(self):
        got = hrs.verified_recent_session({}, entries=[_entry()])
        labels = dict(got.key_parts)
        self.assertIn("Practice/Concert key", labels)
        self.assertIn("Written key", labels)
        self.assertEqual(labels["Practice/Concert key"], "F minor")
        self.assertEqual(labels["Written key"], "D minor")

    def test_the_concert_key_is_never_labelled_as_the_written_key(self):
        got = hrs.verified_recent_session({}, entries=[_entry()])
        for label, value in got.key_parts:
            if label == "Written key":
                self.assertNotEqual(value, "F minor")

    def test_a_guitar_session_shows_the_shape_key(self):
        rows = [_entry(instrument="Guitar", guitar_shape_key="D minor", written_key="")]
        labels = dict(hrs.verified_recent_session({}, entries=rows).key_parts)
        self.assertEqual(labels.get("Shape key"), "D minor")
        self.assertNotIn("Written key", labels)

    def test_a_concert_instrument_does_not_invent_a_written_key(self):
        rows = [_entry(instrument="Piano", written_key="", guitar_shape_key="")]
        labels = dict(hrs.verified_recent_session({}, entries=rows).key_parts)
        self.assertIn("Practice/Concert key", labels)
        self.assertNotIn("Written key", labels)

    def test_the_original_key_is_kept_separate_from_the_practice_key(self):
        labels = dict(hrs.verified_recent_session({}, entries=[_entry()]).key_parts)
        self.assertEqual(labels.get("Original key"), "C minor")
        self.assertNotEqual(labels.get("Original key"), labels.get("Practice/Concert key"))

    def test_blank_keys_are_dropped_rather_than_shown_as_dashes(self):
        rows = [_entry(instrument="Piano", written_key="", original_key="", guitar_shape_key="")]
        got = hrs.verified_recent_session({}, entries=rows)
        self.assertTrue(all(v and v != "—" for _, v in got.key_parts))


class TestResumeTarget(unittest.TestCase):
    def test_each_practice_type_opens_its_own_workspace(self):
        cases = {
            "song practice": "practice",
            "backing track": "backing",
            "custom progression": "custom",
            "multitrack/upload": "multitrack",
            "composition practice": "composer",
            "mission practice": "creative",
        }
        for ptype, page in cases.items():
            with self.subTest(practice_type=ptype):
                got = hrs.verified_recent_session({}, entries=[_entry(practice_type=ptype)])
                self.assertEqual(got.page, page)

    def test_an_unknown_practice_type_falls_back_to_practice(self):
        got = hrs.verified_recent_session({}, entries=[_entry(practice_type="interpretive dance")])
        self.assertEqual(got.page, "practice")

    def test_a_mission_session_also_selects_the_missions_workspace(self):
        got = hrs.verified_recent_session({}, entries=[_entry(practice_type="mission practice")])
        self.assertEqual(got.creative_dest, "creative::Missions")

    def test_other_sessions_select_no_creative_workspace(self):
        got = hrs.verified_recent_session({}, entries=[_entry()])
        self.assertEqual(got.creative_dest, "")


class TestReadableDetail(unittest.TestCase):
    def test_a_session_from_today_says_today(self):
        got = hrs.session_from_entry(_entry(date="2026-11-03"), today=date(2026, 11, 3))
        self.assertEqual(got.when_label, "Today")

    def test_a_session_from_yesterday_says_yesterday(self):
        got = hrs.session_from_entry(_entry(date="2026-11-02"), today=date(2026, 11, 3))
        self.assertEqual(got.when_label, "Yesterday")

    def test_an_older_session_gets_a_date(self):
        got = hrs.session_from_entry(_entry(date="2026-09-01"), today=date(2026, 11, 3))
        self.assertIn("2026", got.when_label)

    def test_a_bad_date_does_not_raise(self):
        self.assertEqual(hrs.session_from_entry(_entry(date="not-a-date")).when_label, "")

    def test_a_named_section_is_carried_but_whole_song_is_not_noise(self):
        self.assertEqual(hrs.session_from_entry(_entry()).section_label, "")
        got = hrs.session_from_entry(_entry(section_name="Bridge"))
        self.assertEqual(got.section_label, "Bridge")

    def test_a_nonsense_duration_does_not_go_negative(self):
        self.assertEqual(hrs.session_from_entry(_entry(duration_minutes="x")).duration_minutes, 0)
        self.assertEqual(hrs.session_from_entry(_entry(duration_minutes=-5)).duration_minutes, 0)

    def test_the_key_summary_reads_as_labelled_pairs(self):
        got = hrs.session_from_entry(_entry())
        self.assertIn("Practice/Concert key: F minor", got.key_summary())
        self.assertIn("Written key: D minor", got.key_summary())


if __name__ == "__main__":
    unittest.main()
