"""R11 JAMKEY / MODEKEY: Creative jams and SBI lanes each own a full key identity.

Human reports: the Jam Generator key looked stuck, a jam key showed up as the
song's Original Key, Style Jam Backing used the Generator's jam and key, and a
Style Jam in E (or a Generator in C minor) became the next Creative mode's key.

Live tracing found these first writers, each pinned below:

* ``build_entry_jam_context`` chose Generator vs Style from the *previous*
  Backing context instead of the launch entry mode.
* ``apply_backing_context_to_session`` and the sidebar refresh read
  ``improv_jam_key or improv_style_key`` -- either jam's key for any jam.
* ``canonical_display_key_for_current_owner`` let the last Backing context's
  entry mode outrank the live Creative mode, and returned the Generator blob's
  tonic without its mode.
* ``apply_creative_concert_key`` wrote an SBI workflow's key into a jam's key
  field whenever the entry mode still said a jam.
* ``generated_jam_practice_key_tokens`` called the song's own saved key "jam
  residue" when a jam happened to use it, so Perfect's C# fell back to G.
* The jam's pick-agnostic commit token and the sealed-catalog heal pulled the
  global song's key onto a jam.
* The sidebar's Song Original Key showed the jam key while a jam owned it.

Keys are full ``{tonic, mode}`` tokens (``C``, ``Cm``, ``Bm``); a C-minor jam
is never collapsed to C.
"""

from __future__ import annotations

import unittest

from tests.test_r11_empty_and_composition_sbi import PERFECT, _Base

SHAPE = ("Pop", "Shape of You — Ed Sheeran")


class TestJamWorkingKeyIsPerJam(unittest.TestCase):
    def test_each_jam_reads_only_its_own_key(self) -> None:
        from sbi_lane_practice_key import jam_working_key_for_entry

        session = {"improv_jam_key": "C", "improv_style_key": "F#"}
        self.assertEqual(jam_working_key_for_entry(session, "Style Jam Mode"), "F#")
        self.assertEqual(jam_working_key_for_entry(session, "Jam Session Generator"), "C")
        self.assertEqual(jam_working_key_for_entry({"improv_jam_key": "C"}, "Style Jam Mode"), "")

    def test_song_key_restore_never_writes_a_jam_key(self) -> None:
        from creative_key_sync import apply_creative_concert_key

        session = {"improv_entry_mode": "Style Jam Mode", "improv_style_key": "E", "improv_jam_key": "Cm"}
        apply_creative_concert_key(session, "C#", source="workflow_restore_song_based_improvisation",
                                   owner="song_based_improvisation")
        self.assertEqual(session["improv_style_key"], "E", "the song's C# landed in the Style Jam")
        self.assertEqual(session["improv_jam_key"], "Cm")

    def test_a_jam_restore_writes_only_that_jams_field(self) -> None:
        from creative_key_sync import apply_creative_concert_key

        session = {"improv_entry_mode": "Jam Session Generator", "improv_style_key": "E", "improv_jam_key": "Cm"}
        apply_creative_concert_key(session, "F#", source="workflow_restore_style_jam", owner="style_jam")
        self.assertEqual(session["improv_style_key"], "F#")
        self.assertEqual(session["improv_jam_key"], "Cm", "Style's key went into the Generator")


class TestGeneratorKeyKeepsItsMode(unittest.TestCase):
    def test_c_minor_generator_is_not_c_major(self) -> None:
        from songs import key_state

        class _Keys:
            practice_tonic = "C"
            practice_mode = "minor"

        class _Blob:
            keys = _Keys()

        session = {"studio_page": "creative", "improv_entry_mode": "Jam Session Generator"}
        orig_get = None
        try:
            import music_workflow_state_store as store

            orig_get = store.get_workflow_blob
            store.get_workflow_blob = lambda *_a, **_k: _Blob()
            orig_sid = key_state._jam_session_id_for_widget_owner
            key_state._jam_session_id_for_widget_owner = lambda _s: "jam-1"
            orig_owner = key_state.resolve_display_key_widget_owner_id
            key_state.resolve_display_key_widget_owner_id = lambda _s: "entry_jam::jam-1"
            self.assertEqual(key_state.canonical_display_key_for_current_owner(session), "Cm")
        finally:
            if orig_get is not None:
                store.get_workflow_blob = orig_get
                key_state._jam_session_id_for_widget_owner = orig_sid
                key_state.resolve_display_key_widget_owner_id = orig_owner


class TestSongKeyIsNotJamResidue(_Base):
    def test_song_saved_key_equal_to_a_jam_key_stays_the_songs(self) -> None:
        from generated_jam_key_context import generated_jam_practice_key_tokens
        from songs.practice_key_state import set_practice_concert_key

        session = self.new_session()
        pick = self.activate_catalog(session, *PERFECT)
        set_practice_concert_key(session, "C#", pick_key=pick, allow_restore_original=True)
        session["improv_style_key"] = "C#"     # a Style Jam that started at Perfect's key
        session["improv_jam_key"] = "Cm"
        tokens = generated_jam_practice_key_tokens(session)
        self.assertNotIn("C#", tokens, "Perfect's own C# was treated as jam residue")
        self.assertIn("Cm", tokens)


class TestJamsDoNotOwnOrdinaryPagesOrTheSbiLane(_Base):
    def test_jam_does_not_own_the_sidebar_outside_creative_or_backing(self) -> None:
        from backing_musical_state import should_skip_regular_song_defaults
        from creative_key_sync import is_creative_major_jam_active

        session = {"studio_page": "practice", "improv_entry_mode": "Style Jam Mode",
                   "improv_intelligence_tab": "Entry & Jam", "improv_style_key": "F#"}
        self.assertFalse(is_creative_major_jam_active(session))
        self.assertFalse(should_skip_regular_song_defaults(session))

    def test_jam_backing_context_is_not_the_sidebar_owner_on_practice(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from songs.key_state import resolve_display_key_widget_owner_id

        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        set_backing_context(session, BackingContext(
            source="entry_jam", source_label="Entry & Jam", active_song_id="",
            song_title="Entry Style Jam", key="F#", display_key="F#", concert_key="F#",
            bpm=110, style="Jazz Swing", groove="Medium", entry_mode="Style Jam Mode",
        ))
        session["studio_page"] = "practice"
        self.assertFalse(resolve_display_key_widget_owner_id(session).startswith(("style_jam::", "entry_jam::")))

    def test_custom_lane_does_not_claim_a_jam_mode(self) -> None:
        from source_session_state import SBI_PREVIEW_SOURCE_KEY, custom_sbi_owns_sidebar_practice_key

        session = {"studio_page": "creative", "improv_intelligence_tab": "Entry & Jam",
                   "improv_entry_mode": "Jam Session Generator",
                   "improv_song_source": "Custom progression",
                   SBI_PREVIEW_SOURCE_KEY: "Custom progression"}
        self.assertFalse(custom_sbi_owns_sidebar_practice_key(session))
        session["improv_entry_mode"] = "Song-Based Improvisation"
        self.assertTrue(custom_sbi_owns_sidebar_practice_key(session))


class TestFreshJamStartsFromTheGlobalSongKey(_Base):
    def _blob_key(self, session: dict, owner: str) -> str:
        from music_workflow_compatibility import build_workflow_blob_from_legacy
        from music_theory import key_center_token

        blob = build_workflow_blob_from_legacy(session, owner)
        return key_center_token(blob.keys.practice_tonic, blob.keys.practice_mode or "major")

    def test_unkeyed_generator_starts_at_perfects_key_not_eb(self) -> None:
        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        session["improv_jam_key"] = "Eb"          # the old hard-coded default
        self.assertEqual(self._blob_key(session, "jam_session_generator"), "G")

    def test_unkeyed_style_jam_over_a_minor_song_starts_in_its_minor_key(self) -> None:
        session = self.new_session()
        self.activate_catalog(session, *SHAPE)
        session["improv_style_key"] = "G"
        self.assertEqual(self._blob_key(session, "style_jam"), "Bm")

    def test_a_keyed_jam_keeps_its_own_key(self) -> None:
        from songs.practice_key_state import CREATIVE_JAM_SESSION_PICK, set_practice_concert_key

        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        set_practice_concert_key(session, "Cm", pick_key=CREATIVE_JAM_SESSION_PICK,
                                 allow_restore_original=True)
        session["improv_jam_key"] = "Cm"
        self.assertEqual(self._blob_key(session, "jam_session_generator"), "Cm")


if __name__ == "__main__":
    unittest.main()
