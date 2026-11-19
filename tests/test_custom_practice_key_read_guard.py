"""P0d read guard: a stored Practice Key of the other tonal family than the live Custom song's Original Key is not honoured.

READ-only: nothing is written, no override flag changes, no explicit-edit marker is created. Same-family keys stay valid.
"""
from __future__ import annotations

import copy
import unittest

import custom_progression_lab as L
import source_session_state as SS
from songs.practice_key_state import get_practice_concert_key
from tests.test_sbi_custom_explicit_practice_key_edit import BLUES, BLUES_ID, TRIAL, TRIAL_ID, PHANTOM, _library, _recovered_session


def _session(trial_key="Fm", blues_key="Fm", active="trial"):
    ss = _recovered_session(extra_picks=False)
    ss["practice_key_by_source"] = {TRIAL: trial_key, BLUES: blues_key}
    ss["practice_key_user_override_picks"] = [TRIAL, BLUES]
    if active == "blues":
        ss[L.CPL_ACTIVE_KEY] = copy.deepcopy(_library()["Blues in F minor"])
        ss["active_catalog_pick_key"] = BLUES
        ss[SS.SBI_CUSTOM_IDENTITY_PICK_KEY] = BLUES
    return ss


class TestCrossFamilyStoredKeyIsIgnoredOnRead(unittest.TestCase):
    def test_trial_with_stored_fm_reads_at_its_original_key(self) -> None:
        ss = _session(trial_key="Fm")
        self.assertEqual(get_practice_concert_key(ss, TRIAL, default="D"), "D")
        self.assertEqual(SS.resolve_sbi_custom_practice_key(ss), "D")

    def test_the_fallback_is_the_original_key_even_without_a_caller_default(self) -> None:
        ss = _session(trial_key="Fm")
        self.assertEqual(get_practice_concert_key(ss, TRIAL), "D")  # not "" and never a generic "C"
        ss = _session(blues_key="F", active="blues")
        self.assertEqual(get_practice_concert_key(ss, BLUES), "Fm")

    def test_the_guard_never_writes(self) -> None:
        ss = _session(trial_key="Fm")
        before = copy.deepcopy(ss)
        get_practice_concert_key(ss, TRIAL, default="D")
        SS.resolve_sbi_custom_practice_key(ss)
        self.assertEqual(ss["practice_key_by_source"], before["practice_key_by_source"])
        self.assertEqual(ss["practice_key_user_override_picks"], before["practice_key_user_override_picks"])
        self.assertNotIn(SS.SBI_CUSTOM_EXPLICIT_PK_EDIT_KEY, ss)

    def test_stale_widget_values_of_the_wrong_family_are_ignored_too(self) -> None:
        ss = _session(trial_key="D")
        ss.pop("practice_key_by_source")
        ss["display_key_sbi_custom"] = "Fm"
        ss["_sbi_custom_visit_pk"] = "Fm"
        self.assertEqual(SS.resolve_sbi_custom_practice_key(ss), "D")


class TestDeliberateSameFamilyKeysStayValid(unittest.TestCase):
    def test_d_major_to_f_and_eb_major(self) -> None:
        for tok in ("F", "Eb", "C", "G"):
            ss = _session(trial_key=tok)
            self.assertEqual(get_practice_concert_key(ss, TRIAL, default="D"), tok)
            self.assertEqual(SS.resolve_sbi_custom_practice_key(ss), tok)

    def test_blues_in_f_minor_stays_minor(self) -> None:
        ss = _session(blues_key="Fm", active="blues")
        self.assertEqual(get_practice_concert_key(ss, BLUES, default="Fm"), "Fm")
        self.assertEqual(SS.resolve_sbi_custom_practice_key(ss), "Fm")
        ss = _session(blues_key="Gm", active="blues")
        self.assertEqual(SS.resolve_sbi_custom_practice_key(ss), "Gm")

    def test_a_major_key_stored_on_the_minor_blues_is_ignored(self) -> None:
        ss = _session(blues_key="F", active="blues")
        self.assertEqual(SS.resolve_sbi_custom_practice_key(ss), "Fm")


class TestOnlyProvenLiveSongsAreJudged(unittest.TestCase):
    def test_unknown_phantom_and_non_custom_picks_are_not_judged(self) -> None:
        ss = _session()
        for pick in (PHANTOM, "custom::Nobody", "catalog::shallow", ""):
            self.assertTrue(SS.practice_key_fits_custom_song(ss, pick, "Fm"), pick)
        self.assertTrue(SS.practice_key_fits_custom_song(ss, TRIAL, ""))
        self.assertFalse(SS.practice_key_fits_custom_song(ss, TRIAL, "Fm"))
        self.assertTrue(SS.practice_key_fits_custom_song(ss, TRIAL, "F"))

    def test_canonical_song_data_is_unchanged(self) -> None:
        ss = _session()
        golden = copy.deepcopy(ss[L.CPL_SAVED_KEY])
        for _ in range(3):
            get_practice_concert_key(ss, TRIAL, default="D")
            SS.resolve_sbi_custom_practice_key(ss)
        self.assertEqual(ss[L.CPL_SAVED_KEY], golden)


class TestBackingOwnerReadsTheGuardedKey(unittest.TestCase):
    def test_backing_canonical_key_for_a_contaminated_trial_is_d(self) -> None:
        from backing_practice_key_control import OWNER_CUSTOM, OWNER_SBI_CUSTOM, canonical_concert_key_for_owner

        ss = _session(trial_key="Fm")
        for owner in (OWNER_CUSTOM, OWNER_SBI_CUSTOM):
            self.assertEqual(canonical_concert_key_for_owner(ss, owner), "D", owner)
        ss = _session(trial_key="F")
        self.assertEqual(canonical_concert_key_for_owner(ss, OWNER_CUSTOM), "F")


class TestRenderTimeSyncDoesNotPersistTheFallback(unittest.TestCase):
    def test_syncing_the_original_key_over_a_wrong_family_key_is_skipped(self) -> None:
        from songs.practice_key_state import set_practice_concert_key

        ss = _session(trial_key="Fm")
        before = copy.deepcopy(ss["practice_key_by_source"]), list(ss["practice_key_user_override_picks"])
        set_practice_concert_key(ss, "D", pick_key=TRIAL, allow_restore_original=True)
        self.assertEqual((ss["practice_key_by_source"], ss["practice_key_user_override_picks"]), before)
        self.assertEqual(ss["practice_key_by_source"][TRIAL], "Fm")  # raw value untouched; readers still see D

    def test_a_deliberate_key_replaces_the_wrong_family_value(self) -> None:
        from songs.practice_key_state import set_practice_concert_key

        ss = _session(trial_key="Fm")
        ss["_pk_user_commit_token"] = "F"
        set_practice_concert_key(ss, "F", pick_key=TRIAL, allow_restore_original=True)
        self.assertEqual(ss["practice_key_by_source"][TRIAL], "F")
        self.assertEqual(get_practice_concert_key(ss, TRIAL, default="D"), "F")

    def test_explicit_selection_replaces_a_wrong_family_key_with_the_original_key(self) -> None:
        ss = _session(trial_key="Fm")
        L.apply_cpl_session_progression(ss, L.load_saved_progression(ss[L.CPL_SAVED_KEY], "Trial Song"), reset_display_key=True)
        self.assertEqual(ss["practice_key_by_source"][TRIAL], "D")
        self.assertEqual(ss["practice_key_by_source"][BLUES], "Fm")  # nothing else touched

    def test_explicit_selection_keeps_a_deliberate_same_family_key(self) -> None:
        ss = _session(trial_key="F")
        L.apply_cpl_session_progression(ss, L.load_saved_progression(ss[L.CPL_SAVED_KEY], "Trial Song"), reset_display_key=True)
        self.assertEqual(ss["practice_key_by_source"][TRIAL], "F")


if __name__ == "__main__":
    unittest.main()
